---
title: Self-Healing Containers — Fábrica Automática EstudoHub 4.0
date: 2026-04-27
status: approved
---

## Problema

Os scripts `mass_ingestion_industrial.py` (Moenda) e `agente_pescador.py` (Pescador) são executados via `docker exec` e morrem sem recuperação quando o container do backend reinicia ou o PC cai. O sistema não é resiliente a falhas.

## Objetivo

Transformar o EstudoHub em uma "fábrica automática": após qualquer queda, os processos de ingestão e coleta retomam sozinhos, sem intervenção humana, e nunca reprocessam o que já está no banco.

---

## Decisões de Design

- **Idempotência via content_hash**: o campo `content_hash` já existe como `unique=True` e indexado em `Edital`. A consulta por hash é O(1) e suficiente como guarda de duplicata.
- **Check direto no banco (não via HTTP)**: a moenda importa `app.*` diretamente; passar pelo endpoint `/upload` adicionaria latência e dependência de rede desnecessária.
- **Imagem separada para o pescador**: o pescador não usa `app.*` — apenas `requests` e `beautifulsoup4`. Uma imagem dedicada e leve evita carregar todo o stack do backend.
- **Daemon mode via loop infinito**: ambos os scripts ganham um `while True` com sleep entre ciclos, em vez de depender do backoff do Docker para criar o efeito de polling.
- **`restart: unless-stopped`**: reinicia automaticamente após falhas, mas respeita um `docker compose stop` explícito durante manutenção.

---

## Componentes e Mudanças

### 1. `backend/app/api/endpoints.py` — Idempotência no Upload

**Onde:** função `upload_edital`, após calcular `content_hash` e antes de gravar o arquivo temporário.

**Lógica:**
```python
db = SessionLocal()
try:
    existing = db.query(models.Edital).filter_by(content_hash=content_hash).first()
    if existing:
        return IngestionResponse(
            id=existing.id,
            content_hash=existing.content_hash,
            status=existing.status,
            total_tables=0,
            total_links=0,
            total_chars=0,
        )
finally:
    db.close()
```

**Resultado:** retorna `200` com o edital existente. Nenhum arquivo temporário é criado. Nenhuma background task é enfileirada.

---

### 2. `backend/mass_ingestion_industrial.py` — Daemon com Pre-Check

**Mudança 1 — Pre-check no banco antes de processar:**

No início do loop por arquivo, após calcular o hash a partir dos bytes:
```python
db = SessionLocal()
try:
    exists = db.query(models.Edital).filter_by(content_hash=content_hash).first()
finally:
    db.close()
if exists:
    logger.info(f"⏭️  Já no banco, pulando: {pdf_path.name}")
    continue
```

**Mudança 2 — Loop daemon:**

A função `moenda_industrial()` vira um loop `while True`. Após cada varredura completa:
```python
logger.info("💤 Ciclo completo. Aguardando 5 minutos para re-escanear...")
await asyncio.sleep(300)
```

Isso garante que novos PDFs depositados pelo pescador em `/storage_k` sejam captados automaticamente no próximo ciclo.

---

### 3. `backend/scripts/agente_pescador.py` — Daemon com Loop Diário

O método `run()` é envolvido em um `while True` no `__main__`:
```python
while True:
    agente.run()
    print("Ciclo completo. Dormindo 1 hora antes de re-verificar...")
    time.sleep(3600)
```

O `wait_for_night()` já existente dentro de `download_pdf` garante que os downloads só ocorram entre 00h00 e 02h00. O loop externo garante que o script nunca saia voluntariamente.

---

### 4. `backend/scripts/Dockerfile.pescador` — Imagem Leve (nova)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir requests beautifulsoup4
COPY agente_pescador.py .
CMD ["python", "-u", "agente_pescador.py"]
```

Sem `COPY . .` — apenas o script necessário. Imagem resultante ~80% menor que a do backend.

---

### 5. `docker-compose.yml` — Dois Novos Serviços

```yaml
moenda:
  build: ./backend
  command: python mass_ingestion_industrial.py
  volumes:
    - ./backend:/app
    - K:\estudohub_storage:/storage_k
    - ./storage:/app/storage
  environment:
    - DATABASE_URL=postgresql://estudohub_admin:estudohub_pass@db:5432/estudohub
  depends_on:
    - db
  restart: unless-stopped

pescador:
  build:
    context: ./backend/scripts
    dockerfile: Dockerfile.pescador
  volumes:
    - K:\estudohub_storage:/storage_k
    - ./storage:/app/storage
  restart: unless-stopped
```

A moenda depende do `db` para garantir que o Postgres esteja disponível antes de tentar conectar. O pescador não depende do banco — ele só baixa PDFs para o volume.

---

## Fluxo de Auto-Recuperação (Self-Healing)

```
PC reinicia
  └─> Docker Engine sobe
        ├─> db sobe
        ├─> backend sobe
        ├─> moenda sobe → checa banco → pula já processados → processa novos → dorme 5min → repete
        └─> pescador sobe → aguarda 00h00 → baixa PDFs novos → dorme 1h → repete
```

Se qualquer container cair com erro:
```
container morre (exit != 0)
  └─> Docker detecta
        └─> restart: unless-stopped → container volta em segundos
```

---

## Arquivos Afetados

| Arquivo | Tipo de mudança |
|---|---|
| `backend/app/api/endpoints.py` | Modificação (add DB check) |
| `backend/mass_ingestion_industrial.py` | Modificação (add DB check + daemon loop) |
| `backend/scripts/agente_pescador.py` | Modificação (add daemon loop) |
| `backend/scripts/Dockerfile.pescador` | Criação (nova imagem leve) |
| `docker-compose.yml` | Modificação (add moenda + pescador services) |

---

## Notas de Implementação

- `mass_ingestion_industrial.py` contém `sys.path.append(str(current_dir / "backend"))` projetado para execução fora do Docker. Dentro do container com `WORKDIR /app`, a linha é inofensiva (o `app.*` resolve pelo WORKDIR), mas pode ser removida para clareza.
- Os caminhos relativos de log (`storage/industrial_ingestion.log`, `storage/pescaria_log.json`) funcionam corretamente dentro dos containers porque o volume `./storage:/app/storage` mapeia o diretório correto.
- O `Dockerfile.pescador` usa `python -u` (unbuffered) para que os logs apareçam em tempo real no `docker compose logs`.

---

## O que NÃO muda

- Schema do banco (nenhuma migração necessária — `content_hash` já é `unique=True`)
- Lógica de processamento da moenda (pipeline AI, Trindade, Fingerprint)
- Lógica de scraping do pescador
- Dockerfile do backend
- Jenkins pipeline (continua sendo usado para deploy e testes)
