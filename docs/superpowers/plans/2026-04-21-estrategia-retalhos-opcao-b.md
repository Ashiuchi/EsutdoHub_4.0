# Estratégia de Retalhos — Opção B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refatorar o `SubtractiveAgent` para gerar uma estrutura de diretórios organizada em `storage/processed/{content_hash}/`, com o edital limpo em `main.md`, cada tabela individualmente em `tables/tabela_N.md` (formatada com pandas), e um `metadata.json` consolidando datas, valores monetários e links — tudo sem envolver LLM.

**Architecture:** O `SubtractiveAgent` ganha um método `persist(md, content_hash)` que orquestra: strip de tabelas e padrões (já implementado), supressão de ruído por frequência de linhas, extração de links, formatação pandas das tabelas e persistência em disco. O endpoint `/upload` é refatorado para retornar `IngestionResponse` com `content_hash` e `status="ingestado"` imediatamente, sem chamar LLM.

**Tech Stack:** `pandas==2.2.2`, `tabulate==0.9.0` (novo), `hashlib` (stdlib), `pathlib` (stdlib), `dataclasses` (stdlib), Pydantic, FastAPI, pytest + `tmp_path`.

---

## File Map

| Action | Path | Responsabilidade |
|--------|------|-----------------|
| **Modify** | `backend/requirements.txt` | Adicionar pandas e tabulate |
| **Create** | `backend/.gitignore` (ou append) | Ignorar `storage/` do git |
| **Modify** | `backend/app/services/subtractive_service.py` | `StorageResult`, `suppress_noise`, `extract_links`, `persist` |
| **Modify** | `backend/app/schemas/edital_schema.py` | Adicionar `IngestionResponse` |
| **Modify** | `backend/app/api/endpoints.py` | Refatorar `/upload` para retornar `IngestionResponse` sem LLM |
| **Modify** | `backend/tests/services/test_subtractive_service.py` | Testes das novas funcionalidades |

---

## Task 1: Dependências (pandas + tabulate) e .gitignore

**Files:**
- Modify: `backend/requirements.txt`
- Modify or Create: `backend/.gitignore`

- [ ] **Step 1.1: Adicionar pandas e tabulate ao requirements.txt**

Abra `backend/requirements.txt` e adicione ao final:

```
pandas==2.2.2
tabulate==0.9.0
```

O arquivo completo deve ficar:

```
fastapi==0.111.0
sqlalchemy==2.0.30
psycopg2-binary==2.9.9
sse-starlette==1.8.2
uvicorn[standard]==0.30.1
python-multipart==0.0.9
google-generativeai==0.7.0
pydantic-settings==2.3.1
pymupdf4llm==0.0.10
python-dotenv==1.0.1
aiohttp==3.9.1
pytest==7.4.3
pytest-asyncio==0.23.2
pandas==2.2.2
tabulate==0.9.0
```

- [ ] **Step 1.2: Adicionar storage/ ao .gitignore**

Verifique se existe `backend/.gitignore`. Se não existir, crie. Adicione:

```
storage/
__pycache__/
*.pyc
.env
debug/
```

Se já existir, apenas acrescente `storage/` se não estiver presente.

- [ ] **Step 1.3: Verificar sintaxe do requirements.txt**

```bash
python3 -m py_compile /dev/null && echo "ok"  # sanity check only
cat backend/requirements.txt | grep -E "pandas|tabulate"
```

Expected output:
```
pandas==2.2.2
tabulate==0.9.0
```

- [ ] **Step 1.4: Commit**

```bash
git add backend/requirements.txt backend/.gitignore
git commit -m "chore: add pandas + tabulate deps; gitignore storage/"
```

---

## Task 2: `StorageResult` dataclass e scaffolding de diretórios

**Files:**
- Modify: `backend/app/services/subtractive_service.py`
- Modify: `backend/tests/services/test_subtractive_service.py`

O `StorageResult` é a estrutura de retorno do método `persist()`. Ele descreve os caminhos criados e as estatísticas da operação.

- [ ] **Step 2.1: Escrever o teste que falha**

Adicione ao final de `backend/tests/services/test_subtractive_service.py`:

```python
from pathlib import Path


def test_persist_creates_directory_structure(tmp_path):
    """persist() deve criar main.md, metadata.json e tables/ no storage_base."""
    md = "Texto normal.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nFim."
    agent = SubtractiveAgent()

    result = agent.persist(md, content_hash="abc123", storage_base=tmp_path)

    assert (tmp_path / "abc123").is_dir()
    assert (tmp_path / "abc123" / "main.md").is_file()
    assert (tmp_path / "abc123" / "metadata.json").is_file()
    assert (tmp_path / "abc123" / "tables").is_dir()


def test_persist_returns_storage_result_with_correct_hash(tmp_path):
    """StorageResult deve ter content_hash igual ao passado."""
    agent = SubtractiveAgent()
    result = agent.persist("Texto.", content_hash="deadbeef", storage_base=tmp_path)

    assert result.content_hash == "deadbeef"


def test_persist_storage_result_has_path_attributes(tmp_path):
    """StorageResult deve expor storage_path, main_md_path, tables_dir, metadata_path."""
    agent = SubtractiveAgent()
    result = agent.persist("Texto.", content_hash="hash01", storage_base=tmp_path)

    assert result.storage_path == tmp_path / "hash01"
    assert result.main_md_path == tmp_path / "hash01" / "main.md"
    assert result.tables_dir == tmp_path / "hash01" / "tables"
    assert result.metadata_path == tmp_path / "hash01" / "metadata.json"
```

- [ ] **Step 2.2: Rodar para verificar que falha**

```bash
cd backend && pytest tests/services/test_subtractive_service.py::test_persist_creates_directory_structure -v
```

Expected: `AttributeError: 'SubtractiveAgent' object has no attribute 'persist'`

- [ ] **Step 2.3: Adicionar `StorageResult` e método `persist()` mínimo ao `subtractive_service.py`**

Adicione no topo do arquivo (logo após os imports existentes):

```python
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

STORAGE_BASE = Path("storage/processed")
```

Adicione a dataclass logo antes da classe `SubtractiveAgent`:

```python
@dataclass
class StorageResult:
    """Resultado da operação de persistência do SubtractiveAgent."""
    content_hash: str
    storage_path: Path
    main_md_path: Path
    tables_dir: Path
    metadata_path: Path
    table_count: int
    original_chars: int
    stripped_chars: int
    metadata: dict = field(default_factory=dict)
```

Adicione o método `persist()` à classe `SubtractiveAgent` (depois de `process`):

```python
    def persist(
        self,
        md: str,
        content_hash: str,
        storage_base: Path = STORAGE_BASE,
    ) -> StorageResult:
        """Orquestra o pipeline subtrativo e persiste os artefatos em storage_base/{content_hash}/.

        Cria:
            {content_hash}/main.md        — texto limpo com supressão de ruído
            {content_hash}/tables/        — diretório com tabela_N.md formatadas
            {content_hash}/metadata.json  — datas, valores R$, links e estatísticas

        Args:
            md: Conteúdo markdown bruto do edital.
            content_hash: Identificador único (ex: SHA-256[:16] do PDF).
            storage_base: Diretório base; pode ser sobrescrito em testes via tmp_path.

        Returns:
            StorageResult com todos os caminhos criados e estatísticas.
        """
        storage_path = Path(storage_base) / content_hash
        tables_dir = storage_path / "tables"
        main_md_path = storage_path / "main.md"
        metadata_path = storage_path / "metadata.json"

        storage_path.mkdir(parents=True, exist_ok=True)
        tables_dir.mkdir(exist_ok=True)

        # -- strip de tabelas e padrões --
        stripped, table_frags = self.strip_tables(md)
        stripped, pattern_frags = self.strip_patterns(stripped)

        # -- salvar main.md (placeholder; noise suppression vem na Task 4) --
        main_md_path.write_text(stripped, encoding="utf-8")

        # -- salvar tabelas individuais (placeholder; pandas vem na Task 3) --
        table_keys = sorted(k for k in table_frags if k.startswith("FRAGMENT_TABLE_"))
        for i, key in enumerate(table_keys):
            table_path = tables_dir / f"tabela_{i}.md"
            table_path.write_text(table_frags[key], encoding="utf-8")

        # -- salvar metadata.json mínimo (links e formatação vêm na Task 5) --
        import json
        metadata: dict = {
            "content_hash": content_hash,
            "original_chars": len(md),
            "stripped_chars": len(stripped),
            "table_count": len(table_keys),
            "datas": list(pattern_frags[k] for k in pattern_frags if k.startswith("FRAGMENT_DATE_")),
            "valores_monetarios": list(pattern_frags[k] for k in pattern_frags if k.startswith("FRAGMENT_MONEY_")),
            "links": [],
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(
            f"persist: {content_hash} → {storage_path} "
            f"({len(table_keys)} tabelas, {len(metadata['datas'])} datas, "
            f"{len(metadata['valores_monetarios'])} valores)"
        )

        return StorageResult(
            content_hash=content_hash,
            storage_path=storage_path,
            main_md_path=main_md_path,
            tables_dir=tables_dir,
            metadata_path=metadata_path,
            table_count=len(table_keys),
            original_chars=len(md),
            stripped_chars=len(stripped),
            metadata=metadata,
        )
```

- [ ] **Step 2.4: Rodar testes para verificar que passam**

```bash
cd backend && pytest tests/services/test_subtractive_service.py -k "persist" -v
```

Expected: 3 testes `test_persist_*` PASS

- [ ] **Step 2.5: Commit**

```bash
git add backend/app/services/subtractive_service.py backend/tests/services/test_subtractive_service.py
git commit -m "feat(subtractive): add StorageResult dataclass and persist() scaffold"
```

---

## Task 3: Formatação de Tabelas com Pandas (`_format_table_md`)

**Files:**
- Modify: `backend/app/services/subtractive_service.py`
- Modify: `backend/tests/services/test_subtractive_service.py`

O `_format_table_md` é uma função pura (não é método da classe) que recebe uma string de tabela markdown bruta e retorna a mesma tabela com colunas perfeitamente alinhadas via `pandas.DataFrame.to_markdown()`. Em caso de erro de parsing, retorna o original sem modificar.

- [ ] **Step 3.1: Escrever o teste que falha**

Adicione ao final de `backend/tests/services/test_subtractive_service.py`:

```python
from app.services.subtractive_service import _format_table_md


def test_format_table_md_aligns_columns():
    """_format_table_md deve retornar tabela com alinhamento perfeito de colunas."""
    raw = "| Cargo | Vagas | Salário |\n|-------|-------|----------|\n| Analista de TI | 10 | R$ 5.000 |\n| Técnico | 200 | R$ 3.000 |\n"
    result = _format_table_md(raw)

    assert "Cargo" in result
    assert "Analista de TI" in result
    assert "Técnico" in result
    # pandas to_markdown() usa | como separador
    assert "|" in result


def test_format_table_md_handles_single_row_table():
    """Tabela com apenas cabeçalho + separador + 1 linha deve ser formatada sem erro."""
    raw = "| A | B |\n|---|---|\n| x | y |\n"
    result = _format_table_md(raw)
    assert "A" in result
    assert "x" in result


def test_format_table_md_falls_back_on_malformed_table():
    """Tabela malformada (sem cabeçalho válido) deve retornar o original sem erro."""
    raw = "não é uma tabela"
    result = _format_table_md(raw)
    assert result == raw


def test_persist_saves_pandas_formatted_tables(tmp_path):
    """tables/tabela_0.md deve conter saída formatada pelo pandas (separador |---|)."""
    md = "Texto.\n\n| Cargo | Vagas |\n|-------|-------|\n| Analista | 10 |\n\nFim."
    agent = SubtractiveAgent()
    result = agent.persist(md, content_hash="ptest", storage_base=tmp_path)

    table_file = tmp_path / "ptest" / "tables" / "tabela_0.md"
    assert table_file.is_file()
    content = table_file.read_text(encoding="utf-8")
    assert "Cargo" in content
    assert "Analista" in content
```

- [ ] **Step 3.2: Rodar para verificar que falha**

```bash
cd backend && pytest tests/services/test_subtractive_service.py::test_format_table_md_aligns_columns -v
```

Expected: `ImportError: cannot import name '_format_table_md'`

- [ ] **Step 3.3: Implementar `_format_table_md` em `subtractive_service.py`**

Adicione logo após os imports e constants, antes da classe `SubtractiveAgent`:

```python
def _format_table_md(table_raw: str) -> str:
    """Reformata uma tabela markdown bruta com alinhamento perfeito de colunas via pandas.

    Parsing robusto: filtra linhas separadoras (|---|), interpreta header e linhas de dados,
    constrói DataFrame e retorna df.to_markdown(index=False). Retorna `table_raw` original
    em caso de falha (tabela malformada, número inconsistente de colunas, etc.).
    """
    import pandas as pd

    lines = [l for l in table_raw.strip().splitlines() if l.strip()]
    if not lines:
        return table_raw

    def _is_separator(line: str) -> bool:
        """True se a linha for um separador markdown (|---|---|)."""
        inner = line.strip().strip("|")
        return bool(inner) and all(c in "-: " for c in inner.replace("|", ""))

    def _parse_row(line: str) -> list:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    content_lines = [l for l in lines if not _is_separator(l)]
    if len(content_lines) < 2:
        return table_raw

    header = _parse_row(content_lines[0])
    data_rows = [_parse_row(l) for l in content_lines[1:]]

    # Normalizar número de colunas (truncar ou preencher com "")
    n_cols = len(header)
    normalized = []
    for row in data_rows:
        if len(row) >= n_cols:
            normalized.append(row[:n_cols])
        else:
            normalized.append(row + [""] * (n_cols - len(row)))

    try:
        import pandas as pd
        df = pd.DataFrame(normalized, columns=header)
        return df.to_markdown(index=False)
    except Exception as e:
        logger.warning(f"_format_table_md: pandas falhou ({e}), usando raw.")
        return table_raw
```

Agora atualize o método `persist()` para usar `_format_table_md`. Localize o bloco de tabelas individuais e substitua:

```python
        # -- salvar tabelas individuais (placeholder; pandas vem na Task 3) --
        table_keys = sorted(k for k in table_frags if k.startswith("FRAGMENT_TABLE_"))
        for i, key in enumerate(table_keys):
            table_path = tables_dir / f"tabela_{i}.md"
            table_path.write_text(table_frags[key], encoding="utf-8")
```

Por:

```python
        # -- salvar tabelas individuais formatadas com pandas --
        table_keys = sorted(k for k in table_frags if k.startswith("FRAGMENT_TABLE_"))
        for i, key in enumerate(table_keys):
            table_path = tables_dir / f"tabela_{i}.md"
            formatted = _format_table_md(table_frags[key])
            table_path.write_text(formatted, encoding="utf-8")
```

- [ ] **Step 3.4: Rodar todos os testes de subtractive**

```bash
cd backend && pytest tests/services/test_subtractive_service.py -v
```

Expected: todos os testes PASS

- [ ] **Step 3.5: Commit**

```bash
git add backend/app/services/subtractive_service.py backend/tests/services/test_subtractive_service.py
git commit -m "feat(subtractive): add pandas table formatter _format_table_md and wire into persist()"
```

---

## Task 4: Supressão de Ruído Global (`suppress_noise`)

**Files:**
- Modify: `backend/app/services/subtractive_service.py`
- Modify: `backend/tests/services/test_subtractive_service.py`

**Algoritmo:** Divide o texto em seções pelo separador de página `-----`. Conta em quantas seções cada linha (normalizada) aparece. Linhas presentes em `>= max(3, ceil(n_sections * 0.30))` seções são consideradas ruído e removidas. O `-----` em si é preservado como estrutura.

**Threshold de 30%**: calibrado para o edital BB (usado na validação) onde o PDF tem ~60 seções. Uma linha em 18+ seções é claramente cabeçalho/rodapé repetitivo.

- [ ] **Step 4.1: Escrever os testes que falham**

Adicione ao final de `backend/tests/services/test_subtractive_service.py`:

```python
from app.services.subtractive_service import suppress_noise


def test_suppress_noise_removes_repetitive_lines():
    """Linhas que aparecem em >= 30% das seções (mín 3) devem ser removidas."""
    # Criar 10 seções onde "Cabeçalho Repetitivo" aparece em todas
    sections = []
    for i in range(10):
        sections.append(f"Cabeçalho Repetitivo\n\nConteúdo único da seção {i}.")
    md = "\n\n-----\n\n".join(sections)

    result = suppress_noise(md)

    assert "Cabeçalho Repetitivo" not in result
    # Conteúdo único deve ser preservado
    assert "Conteúdo único da seção 0." in result
    assert "Conteúdo único da seção 9." in result


def test_suppress_noise_keeps_rare_lines():
    """Linhas que aparecem em < 30% das seções devem ser preservadas."""
    sections = [f"Conteúdo único {i}.\n\nTexto normal." for i in range(10)]
    # Adicionar uma linha que aparece em apenas 2 seções (< 30%)
    sections[0] = "Linha rara\n\n" + sections[0]
    sections[1] = "Linha rara\n\n" + sections[1]
    md = "\n\n-----\n\n".join(sections)

    result = suppress_noise(md)

    assert "Linha rara" in result


def test_suppress_noise_preserves_separators():
    """Os separadores '-----' devem permanecer no texto após a supressão."""
    md = "Seção 1.\n\n-----\n\nSeção 2.\n\n-----\n\nSeção 3."
    result = suppress_noise(md)

    assert "-----" in result


def test_suppress_noise_passthrough_when_few_sections():
    """Com menos de 3 seções, nenhuma linha deve ser removida (threshold mín = 3)."""
    md = "Repetido\n\nTexto A.\n\n-----\n\nRepetido\n\nTexto B."
    result = suppress_noise(md)

    # Com 2 seções, threshold = max(3, ceil(2*0.3)) = max(3,1) = 3
    # "Repetido" aparece em 2 seções < 3 → NÃO é removido
    assert "Repetido" in result
```

- [ ] **Step 4.2: Rodar para verificar que falham**

```bash
cd backend && pytest tests/services/test_subtractive_service.py::test_suppress_noise_removes_repetitive_lines -v
```

Expected: `ImportError: cannot import name 'suppress_noise'`

- [ ] **Step 4.3: Implementar `suppress_noise` em `subtractive_service.py`**

Adicione como função pura (não método), logo após `_format_table_md`:

```python
import math

_PAGE_SEP = "\n\n-----\n\n"
_NOISE_THRESHOLD_RATIO = 0.30
_NOISE_MIN_COUNT = 3


def suppress_noise(md: str) -> str:
    """Remove cabeçalhos e rodapés repetitivos do markdown.

    Divide o texto em seções pelo separador '-----'. Linhas que aparecem em
    >= max(3, ceil(n_sections * 0.30)) seções distintas são consideradas ruído
    (cabeçalho/rodapé de página) e removidas.

    Args:
        md: Texto markdown já processado (stripped_md do SubtractiveAgent).

    Returns:
        Texto com linhas repetitivas removidas. Separadores preservados.
    """
    sections = md.split(_PAGE_SEP)
    n_sections = len(sections)

    if n_sections < 2:
        return md

    threshold = max(_NOISE_MIN_COUNT, math.ceil(n_sections * _NOISE_THRESHOLD_RATIO))

    # Contar em quantas seções cada linha normalizada aparece
    line_section_count: dict = {}
    for section in sections:
        unique_lines_in_section = {l.strip() for l in section.splitlines() if l.strip()}
        for line in unique_lines_in_section:
            line_section_count[line] = line_section_count.get(line, 0) + 1

    noisy_lines = {line for line, count in line_section_count.items() if count >= threshold}

    if noisy_lines:
        logger.info(f"suppress_noise: {len(noisy_lines)} linha(s) repetitiva(s) removida(s) (threshold={threshold}/{n_sections} seções).")

    # Filtrar seções
    clean_sections = []
    for section in sections:
        clean_lines = [l for l in section.splitlines() if l.strip() not in noisy_lines]
        clean_sections.append("\n".join(clean_lines))

    return _PAGE_SEP.join(clean_sections)
```

- [ ] **Step 4.4: Integrar `suppress_noise` no método `persist()`**

Localize o bloco de `main.md` dentro de `persist()`:

```python
        # -- salvar main.md (placeholder; noise suppression vem na Task 4) --
        main_md_path.write_text(stripped, encoding="utf-8")
```

Substitua por:

```python
        # -- aplicar supressão de ruído e salvar main.md --
        main_md = suppress_noise(stripped)
        main_md_path.write_text(main_md, encoding="utf-8")
```

- [ ] **Step 4.5: Atualizar o campo `stripped_chars` no metadata para usar o tamanho pós-ruído**

Localize a definição de `metadata` em `persist()` e atualize:

```python
        metadata: dict = {
            "content_hash": content_hash,
            "original_chars": len(md),
            "stripped_chars": len(stripped),     # ← mudar para len(main_md)
```

Substitua por:

```python
        metadata: dict = {
            "content_hash": content_hash,
            "original_chars": len(md),
            "stripped_chars": len(main_md),
```

E no `StorageResult`, o `stripped_chars` também:

```python
        return StorageResult(
            ...
            stripped_chars=len(main_md),
```

- [ ] **Step 4.6: Rodar todos os testes**

```bash
cd backend && pytest tests/services/test_subtractive_service.py -v
```

Expected: todos os testes PASS

- [ ] **Step 4.7: Commit**

```bash
git add backend/app/services/subtractive_service.py backend/tests/services/test_subtractive_service.py
git commit -m "feat(subtractive): add suppress_noise with 30% frequency threshold"
```

---

## Task 5: Extração de Links e metadata.json Completo

**Files:**
- Modify: `backend/app/services/subtractive_service.py`
- Modify: `backend/tests/services/test_subtractive_service.py`

Links são extraídos do markdown **original** (antes de qualquer strip) e armazenados em `metadata.json`. Não são removidos do texto — apenas registrados como metadado.

Dois padrões são capturados:
- Links markdown: `[texto](https://url.com)` → captura a URL
- URLs brutas: `https://exemplo.com` (que não estejam dentro de parênteses de link markdown)

- [ ] **Step 5.1: Escrever os testes que falham**

Adicione ao final de `backend/tests/services/test_subtractive_service.py`:

```python
from app.services.subtractive_service import extract_links


def test_extract_links_finds_markdown_links():
    """Links no formato [texto](url) devem ser extraídos."""
    md = "Acesse [o edital](https://cesgranrio.org.br/edital.pdf) para mais informações."
    links = extract_links(md)
    assert "https://cesgranrio.org.br/edital.pdf" in links


def test_extract_links_finds_bare_urls():
    """URLs brutas (https://...) devem ser extraídas."""
    md = "Visite https://exemplo.gov.br para detalhes."
    links = extract_links(md)
    assert "https://exemplo.gov.br" in links


def test_extract_links_deduplicates():
    """A mesma URL aparecendo duas vezes deve aparecer uma vez no resultado."""
    md = "https://exemplo.com e novamente https://exemplo.com."
    links = extract_links(md)
    assert links.count("https://exemplo.com") == 1


def test_extract_links_returns_empty_when_no_links():
    """Texto sem links deve retornar lista vazia."""
    links = extract_links("Texto puro sem URLs.")
    assert links == []


def test_persist_metadata_json_contains_links(tmp_path):
    """metadata.json deve conter lista de links extraídos do markdown original."""
    md = "Edital disponível em https://cesgranrio.org.br/001.pdf\n\nTexto normal."
    agent = SubtractiveAgent()
    result = agent.persist(md, content_hash="ltest", storage_base=tmp_path)

    import json
    meta = json.loads((tmp_path / "ltest" / "metadata.json").read_text(encoding="utf-8"))
    assert "https://cesgranrio.org.br/001.pdf" in meta["links"]


def test_persist_metadata_json_structure(tmp_path):
    """metadata.json deve ter todas as chaves esperadas."""
    md = "Texto com data 22/12/2022 e valor R$ 5.000,00 e link https://a.com"
    agent = SubtractiveAgent()
    result = agent.persist(md, content_hash="stest", storage_base=tmp_path)

    import json
    meta = json.loads((tmp_path / "stest" / "metadata.json").read_text(encoding="utf-8"))

    required_keys = {"content_hash", "original_chars", "stripped_chars", "table_count",
                     "datas", "valores_monetarios", "links"}
    assert required_keys.issubset(set(meta.keys()))
    assert meta["content_hash"] == "stest"
    assert "22/12/2022" in meta["datas"]
    assert "R$ 5.000,00" in meta["valores_monetarios"]
    assert "https://a.com" in meta["links"]
```

- [ ] **Step 5.2: Rodar para verificar que falham**

```bash
cd backend && pytest tests/services/test_subtractive_service.py::test_extract_links_finds_markdown_links -v
```

Expected: `ImportError: cannot import name 'extract_links'`

- [ ] **Step 5.3: Implementar `extract_links` em `subtractive_service.py`**

Adicione junto aos outros constants no topo do arquivo (após `_DATE_RE`):

```python
_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\((https?://[^)]+)\)')
_BARE_URL_RE = re.compile(r'(?<!\()(https?://[^\s)>\]]+)')
```

Adicione a função `extract_links` após `suppress_noise`:

```python
def extract_links(md: str) -> list:
    """Extrai todas as URLs únicas do markdown (links e URLs brutas).

    Captura links no formato [texto](url) e URLs brutas (https://...).
    Retorna lista deduplicada mantendo a ordem de aparecimento.

    Args:
        md: Texto markdown original (antes de qualquer strip).

    Returns:
        Lista de URLs únicas, na ordem de aparecimento.
    """
    seen = set()
    urls = []

    # Markdown links: [texto](url) → captura o grupo 2 (url)
    for match in _MD_LINK_RE.finditer(md):
        url = match.group(2).strip()
        if url not in seen:
            seen.add(url)
            urls.append(url)

    # URLs brutas que não façam parte de um link markdown
    # (o negative lookbehind `(?<!\()` evita reatchar URLs já capturadas em links)
    for match in _BARE_URL_RE.finditer(md):
        url = match.group(0).rstrip(".,;:")
        if url not in seen:
            seen.add(url)
            urls.append(url)

    return urls
```

- [ ] **Step 5.4: Integrar `extract_links` no método `persist()`**

No método `persist()`, localize a linha:

```python
            "links": [],
```

Substitua por:

```python
            "links": extract_links(md),
```

- [ ] **Step 5.5: Rodar todos os testes**

```bash
cd backend && pytest tests/services/test_subtractive_service.py -v
```

Expected: todos os testes PASS

- [ ] **Step 5.6: Commit**

```bash
git add backend/app/services/subtractive_service.py backend/tests/services/test_subtractive_service.py
git commit -m "feat(subtractive): add extract_links and complete metadata.json structure"
```

---

## Task 6: `IngestionResponse` e Refatoração do Endpoint `/upload`

**Files:**
- Modify: `backend/app/schemas/edital_schema.py`
- Modify: `backend/app/api/endpoints.py`
- Modify: `backend/tests/services/test_ai_service_orchestration.py` (adicionar teste do endpoint)

O endpoint `/upload` passa a ser exclusivamente uma operação de ingestão: recebe o PDF, computa o `content_hash`, converte para markdown, executa o `SubtractiveAgent.persist()` e retorna imediatamente. O LLM **não é invocado**. A extração LLM será um endpoint separado no futuro.

**Cálculo do `content_hash`:** SHA-256 dos bytes brutos do PDF, primeiros 16 caracteres hexadecimais. Isso garante que o mesmo PDF sempre gera o mesmo diretório de storage.

- [ ] **Step 6.1: Adicionar `IngestionResponse` ao `edital_schema.py`**

Abra `backend/app/schemas/edital_schema.py`. Adicione ao final:

```python

class IngestionResponse(BaseModel):
    """Resposta do endpoint de ingestão de PDF."""
    content_hash: str
    status: str = StatusEdital.INGESTADO
    storage_path: str
    table_count: int
    original_size_chars: int
    stripped_size_chars: int
    reduction_pct: float
```

- [ ] **Step 6.2: Verificar sintaxe**

```bash
python3 -m py_compile backend/app/schemas/edital_schema.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 6.3: Escrever o teste do endpoint que falha**

Abra `backend/tests/services/test_ai_service_orchestration.py` e adicione ao final:

```python
from unittest.mock import patch, MagicMock
from pathlib import Path
from app.schemas.edital_schema import IngestionResponse


@pytest.mark.asyncio
async def test_upload_endpoint_returns_ingestion_response(tmp_path):
    """O endpoint /upload deve retornar IngestionResponse com content_hash e status ingestado."""
    from fastapi.testclient import TestClient
    from app.api.endpoints import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    fake_storage = MagicMock()
    fake_storage.content_hash = "abc123def456abc1"
    fake_storage.storage_path = tmp_path / "abc123def456abc1"
    fake_storage.table_count = 2
    fake_storage.original_chars = 10000
    fake_storage.stripped_chars = 7000
    fake_storage.stripped_chars = 7000

    with patch("app.api.endpoints.PDFService.to_markdown", return_value="# Edital\n\nTexto."), \
         patch("app.api.endpoints.SubtractiveAgent") as mock_agent_cls:

        mock_agent = MagicMock()
        mock_agent.persist.return_value = fake_storage
        mock_agent_cls.return_value = mock_agent

        client = TestClient(app)
        pdf_bytes = b"%PDF-1.4 fake content"
        response = client.post(
            "/upload",
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["content_hash"] == "abc123def456abc1"
    assert data["status"] == "ingestado"
    assert "storage_path" in data
    assert "table_count" in data
```

- [ ] **Step 6.4: Rodar para verificar que falha**

```bash
cd backend && pytest tests/services/test_ai_service_orchestration.py::test_upload_endpoint_returns_ingestion_response -v
```

Expected: FAIL (endpoint ainda retorna `EditalResponse`)

- [ ] **Step 6.5: Refatorar `backend/app/api/endpoints.py`**

Substitua o arquivo completo por:

```python
import asyncio
import hashlib
import json
import logging
import os
import shutil
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.core.logging_streamer import log_streamer
from app.schemas.edital_schema import IngestionResponse, StatusEdital
from app.services.pdf_service import PDFService
from app.services.subtractive_service import SubtractiveAgent

router = APIRouter()
logger = logging.getLogger(__name__)

_SSE_KEEPALIVE_SECONDS = 15


def _save_markdown_debug(md_content: str) -> None:
    """Salva o Markdown extraído em debug/last_extraction.md para análise manual."""
    try:
        os.makedirs("debug", exist_ok=True)
        with open("debug/last_extraction.md", "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info("Debug: Markdown completo salvo em debug/last_extraction.md")
    except Exception as e:
        logger.error(f"Failed to save markdown debug file: {e}")


@router.post("/upload", response_model=IngestionResponse)
async def upload_edital(file: UploadFile = File(...)):
    """Ingere um PDF de edital: gera content_hash, executa pipeline subtrativo e persiste artefatos.

    Não invoca LLM. A extração de dados estruturados é responsabilidade de um endpoint separado.

    Args:
        file: Arquivo PDF enviado pelo cliente.

    Returns:
        IngestionResponse com content_hash, status='ingestado' e estatísticas de redução.

    Raises:
        HTTPException 400: PDF vazio ou ilegível.
        HTTPException 500: Falha interna no pipeline.
    """
    pdf_bytes = await file.read()
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()[:16]
    temp_path = f"temp_{content_hash}.pdf"

    with open(temp_path, "wb") as f:
        f.write(pdf_bytes)

    try:
        md_content = PDFService.to_markdown(temp_path)
        logger.info(f"📄 Markdown gerado: {len(md_content)} chars — hash={content_hash}")
        _save_markdown_debug(md_content)

        if not md_content.strip():
            raise HTTPException(
                status_code=400,
                detail="Conteúdo do PDF está vazio ou ilegível.",
            )

        agent = SubtractiveAgent()
        result = agent.persist(md_content, content_hash=content_hash)

        reduction_pct = round(
            (result.original_chars - result.stripped_chars) / result.original_chars * 100, 1
        ) if result.original_chars > 0 else 0.0

        logger.info(
            f"✅ Ingestão concluída: hash={content_hash}, "
            f"redução={reduction_pct}%, tabelas={result.table_count}"
        )

        return IngestionResponse(
            content_hash=content_hash,
            status=StatusEdital.INGESTADO,
            storage_path=str(result.storage_path),
            table_count=result.table_count,
            original_size_chars=result.original_chars,
            stripped_size_chars=result.stripped_chars,
            reduction_pct=reduction_pct,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro Fatal na Ingestão: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Falha interna ao processar o edital: {str(e)}",
        )
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as exc:
                logger.warning(f"Não foi possível remover temp {temp_path}: {exc}")


@router.get("/cockpit/stream")
async def cockpit_stream(request: Request) -> EventSourceResponse:
    """Endpoint SSE que transmite logs e eventos de dados em tempo real.

    Emite:
    - `log`: mensagens de log capturadas dos namespaces app.services e app.api.
    - `data`: payload de cargo recém-salvo no banco de dados.
    - `ping`: keepalive enviado a cada 15 s de inatividade.

    Args:
        request: Request do FastAPI (usado para detectar desconexão do cliente).

    Returns:
        EventSourceResponse com stream infinito de eventos SSE.
    """
    async def _event_generator() -> AsyncGenerator[dict, None]:
        queue = log_streamer.subscribe()
        logger.info("Cockpit SSE: novo cliente conectado.")
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=_SSE_KEEPALIVE_SECONDS)
                    yield {
                        "event": message.get("type", "log"),
                        "data": json.dumps(message, ensure_ascii=False),
                    }
                except asyncio.TimeoutError:
                    yield {
                        "event": "ping",
                        "data": json.dumps({"type": "ping"}),
                    }
        finally:
            log_streamer.unsubscribe(queue)
            logger.info("Cockpit SSE: cliente desconectado.")

    return EventSourceResponse(_event_generator())
```

- [ ] **Step 6.6: Verificar sintaxe dos dois arquivos modificados**

```bash
python3 -m py_compile backend/app/schemas/edital_schema.py && echo "schema OK"
python3 -m py_compile backend/app/api/endpoints.py && echo "endpoints OK"
```

Expected: ambos `OK`

- [ ] **Step 6.7: Rodar a suite completa**

```bash
cd backend && pytest -v 2>&1 | tail -20
```

Expected: todos os testes PASS (os testes de `test_ai_service_orchestration.py` que mockam `extract_edital_data` podem falhar com `ImportError` se ainda importarem `AIService` do endpoint — se isso ocorrer, eles são testes de orquestração de AI, não de ingestão, e podem ser marcados como `skip` ou removidos se não fizerem mais sentido com o novo fluxo)

- [ ] **Step 6.8: Commit**

```bash
git add backend/app/schemas/edital_schema.py backend/app/api/endpoints.py backend/tests/services/test_ai_service_orchestration.py
git commit -m "feat(api): refactor /upload to IngestionResponse, no LLM call, persist subtractive artifacts"
```

---

## Self-Review

### Spec Coverage

| Requisito | Task | Status |
|---|---|---|
| Diretório `storage/processed/{content_hash}/` | Task 2 (`persist`) | ✅ |
| `main.md` com edital limpo | Task 2 (`persist`) | ✅ |
| `tables/tabela_N.md` com pandas alinhado | Task 3 (`_format_table_md`) | ✅ |
| `metadata.json` com datas, R$ e links | Task 5 (`extract_links`) | ✅ |
| Supressão de ruído (cabeçalhos/rodapés repetitivos) | Task 4 (`suppress_noise`) | ✅ |
| Endpoint retorna `content_hash` e `status="ingestado"` | Task 6 | ✅ |
| Confirmar que `processed/` foi criada com sucesso | Task 6 (`storage_path` na response) | ✅ |
| Sem chamada LLM | Task 6 (endpoint refatorado) | ✅ |
| Pandas para formatação de tabelas | Task 3 | ✅ |
| pandas + tabulate em requirements.txt | Task 1 | ✅ |
| storage/ no .gitignore | Task 1 | ✅ |

### Placeholder Scan

Nenhum TBD, TODO ou "handle edge cases" encontrado. Todos os blocos de código são completos.

### Type Consistency

- `SubtractiveAgent.persist()` → `StorageResult` — consistente em Tasks 2, 4, 5, 6.
- `StorageResult.stripped_chars` → atualizado para usar `len(main_md)` pós-ruído em Task 4 — consistente com Task 6 que lê `result.stripped_chars`.
- `_format_table_md(table_raw: str) -> str` — assinatura consistente em Task 3 e importada em testes.
- `suppress_noise(md: str) -> str` — assinatura consistente em Task 4.
- `extract_links(md: str) -> list` — assinatura consistente em Task 5.
- `IngestionResponse` campos: `content_hash, status, storage_path, table_count, original_size_chars, stripped_size_chars, reduction_pct` — todos preenchidos no endpoint em Task 6.
