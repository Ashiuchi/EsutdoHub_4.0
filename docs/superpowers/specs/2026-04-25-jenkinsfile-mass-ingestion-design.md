# Design: Jenkinsfile — Estágio Mass Ingestion & Extraction

**Date:** 2026-04-25  
**Status:** Approved

## Problem

A ingestão de editais em massa era feita manualmente ou por scripts ad-hoc, violando o ENGINEERING_PROTOCOL. O pipeline Jenkins é o único mecanismo oficial de validação e extração em massa.

## Solution

Adicionar o estágio `Mass Ingestion & Extraction` ao Jenkinsfile, imediatamente após o estágio `Security Check`. O estágio percorre recursivamente `sample_editais/`, envia cada PDF ao endpoint `/upload` do backend via `curl`, e imprime um resumo de sucesso/falha no log Jenkins.

## Architecture

```
Jenkinsfile
  └── stage('Mass Ingestion & Extraction')
        └── sh block
              ├── find sample_editais -name "*.pdf" → /tmp/pdf_list.txt
              ├── while loop over pdf_list.txt
              │     ├── curl -F "file=@$path" http://backend:8000/upload
              │     ├── check HTTP code (2xx = success, else = fail)
              │     └── log [OK] or [ERRO] per file
              └── echo resumo: X/Y enviados | Falhas: Z
```

**Rede:** Jenkins está na `estudohub_40_default` junto com o backend — hostname `backend` é resolvível diretamente.

**Endpoint:** `POST http://backend:8000/upload` com multipart form `file=@<path>`. Retorna imediatamente com `PROCESSANDO` (processamento em background).

## Behavior

| Cenário | Resultado |
|---------|-----------|
| curl retorna 2xx | `[OK]`, incrementa sucesso |
| curl retorna 4xx/5xx | `[ERRO]`, incrementa falhas, continua |
| curl falha (timeout/refused) | `[ERRO] HTTP connection_failed`, continua |
| Stage completo | Sempre exit 0 (resiliente), imprime resumo |

## Key Shell Decisions

- `set +e` — shell não para em erro individual
- `find ... > /tmp/pdf_list.txt` + `done < /tmp/pdf_list.txt` — preserva contadores fora de subshell
- `IFS= read -r path` — preserva espaços em nomes de arquivo
- `"file=@$path"` com aspas duplas — curl recebe path completo mesmo com espaços
- `--max-time 30` — evita hang se backend não responder

## Files Changed

| File | Action |
|------|--------|
| `Jenkinsfile` | Add `Mass Ingestion & Extraction` stage after `Security Check` |

## Out of Scope

- Aguardar conclusão do processamento em background (rastreável pelo Cockpit)
- Deduplicação de editais já processados (responsabilidade do backend)
- Paralelismo no envio dos arquivos
