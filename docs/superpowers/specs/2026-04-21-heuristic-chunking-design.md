# Fase 7 — Heuristic Chunking: Two-Pass Edital Extraction

**Data:** 2026-04-21  
**Status:** Aprovado pelo Arquiteto  
**Contexto:** EstudoHub Pro 4.0 — Engine de Editais

---

## Problema

O `AIService` enviava o Markdown completo do edital em uma única chamada ao LLM. Com o llama3:8b (contexto 8K tokens), documentos de 72 páginas geravam overflow silencioso (`{}` em 2 segundos). Mesmo com llama3.1:8b (128K tokens), enviar 264K chars (~66K tokens) em uma chamada é ineficiente e gera extração imprecisa.

**Evidência empírica (testes manuais — 2026-04-20):**

| Modelo | Páginas | Chars | Tokens est. | Resultado |
|--------|---------|-------|-------------|-----------|
| llama3:8b | 10 | 33.587 | ~9.200 | `{}` overflow |
| llama3:8b | 3 | 9.990 | ~2.500 | JSON sem schema |
| llama3.1:8b | 10 | 33.587 | ~9.200 | ✓ 13 cargos extraídos |

**Lição adicional:** o prompt baseado em `model_json_schema()` confundia o modelo (ele reproduzia o schema). A técnica de **Prompt com Placeholders Concretos** resolveu o problema de schema adherence.

---

## Solução: Fatiador Inteligente (Heuristic Chunking)

Dividir o Markdown em segmentos semânticos usando marcadores heurísticos, e processar cada segmento com um prompt focado.

---

## Arquitetura

### Novo componente: `EditalSegments` (dataclass)

```
EditalSegments:
  ├── general_info: str          # Início → "DOS CARGOS" (intro, banca, órgão)
  ├── cargo_table: str           # "DOS CARGOS" → "CONTEÚDO PROGRAMÁTICO" (vagas, salários)
  └── programmatic_content: str  # "CONTEÚDO PROGRAMÁTICO" → EOF (matérias por cargo)
```

Localização: `backend/app/services/pdf_service.py` (dataclass inline).

---

### `PDFService.get_segments(md_content: str) -> EditalSegments`

Método estático. Busca marcadores via `re.search()` case-insensitive:

| Segmento | Padrões buscados |
|----------|-----------------|
| Marcador 1 (Quadro de Vagas) | `DOS CARGOS`, `QUADRO DE VAGAS`, `DAS VAGAS` |
| Marcador 2 (Conteúdo Prog.) | `CONTEÚDO PROGRAMÁTICO`, `CONTEUDO PROGRAMATICO`, `PROGRAMA DE PROVAS`, `ANEXO [IVX]+` |

**Degradação graciosa:**
- Marcador 1 não encontrado → `general_info = ""`, `cargo_table = md_content` inteiro
- Marcador 2 não encontrado → `programmatic_content = ""` (Pass 2 é pulada)

**Posições reais no TRT 24ª Região (72 págs):**
- "DOS CARGOS" @ char 3.683 (1%)
- "QUADRO DE VAGAS" @ char 3.851 (1%)
- "CONTEÚDO PROGRAMÁTICO" @ char 64.534 (24%)

---

### `PDFService.find_cargo_chunk(cargo_titulo: str, programmatic_content: str) -> str`

Método estático auxiliar para a Passada 2.

**Algoritmo:**
1. Normaliza `cargo_titulo`: remove acentos (unicodedata), uppercase, colapsa espaços
2. Busca o início da seção do cargo no bloco programático (regex permissivo)
3. Extrai do match até o próximo marcador de cargo (mesmo padrão) ou EOF
4. Retorna a string do chunk (vazia se não encontrado → `materias=[]`)

---

### `AIService.extract_edital_data(md_content: str) -> EditalGeral`

Orquestra as duas passadas. Contrato público inalterado — o chamador (endpoint) não muda.

#### Passada 1 — Esqueleto do Edital

**Input:** `segments.general_info + segments.cargo_table` (concatenados)  
**Output:** `EditalGeral` com todos os cargos nomeados e `materias=[]`

**Prompt (Placeholders Concretos):**
```
Você é um extrator de dados de editais de concurso público brasileiro.
Leia o edital abaixo e preencha o JSON de saída com os dados encontrados.

FORMATO DE SAÍDA:
{
  "orgao": "<nome da instituição que realiza o concurso>",
  "banca": "<empresa organizadora: FGV, CEBRASPE, FCC, VUNESP, etc>",
  "data_prova": "<data da prova ou null>",
  "periodo_inscricao": "<período de inscrição ou null>",
  "link_edital": null,
  "cargos": [
    {
      "titulo": "<nome completo do cargo>",
      "vagas_ampla": <inteiro, 0 se não encontrado>,
      "vagas_cotas": <inteiro, 0 se não encontrado>,
      "salario": <float em reais, 0 se não encontrado>,
      "requisitos": "<escolaridade/requisitos ou string vazia>",
      "materias": []
    }
  ]
}

REGRAS:
- Retorne SOMENTE o JSON preenchido, sem explicações
- Liste TODOS os cargos mencionados
- Use os dados reais do documento

EDITAL:
{general_info + cargo_table}
```

#### Passada 2 — Matérias por Cargo

Para cada `cargo` em `edital.cargos` (sequencial, com logs individuais):

1. `chunk = PDFService.find_cargo_chunk(cargo.titulo, segments.programmatic_content)`
2. Se `chunk` vazio → `log.warning` + `continue` (mantém `materias=[]`)
3. `cargo.materias = await self._extract_cargo_materias(chunk, cargo.titulo)`

**Prompt da Passada 2 (Placeholders Concretos):**
```
Para o cargo "{cargo_titulo}", extraia todas as matérias e seus tópicos do conteúdo abaixo.

FORMATO DE SAÍDA:
{
  "materias": [
    {
      "nome": "<nome da matéria/disciplina>",
      "topicos": ["<tópico 1>", "<tópico 2>", ...]
    }
  ]
}

REGRAS:
- Retorne SOMENTE o JSON preenchido
- Liste TODAS as matérias encontradas para este cargo
- Se não houver matérias, retorne {"materias": []}

CONTEÚDO PROGRAMÁTICO:
{chunk}
```

**Schema de validação da Passada 2:** novo `MateriasWrapper(BaseModel)`:
```python
class MateriasWrapper(BaseModel):
    materias: List[Materia]
```

---

## Fluxo Completo

```
POST /upload
  → PDFService.to_markdown(pdf_path)          # sem mudança
  → AIService.extract_edital_data(md_content)
       │
       ├─ PDFService.get_segments(md_content)
       │    → EditalSegments(general_info, cargo_table, programmatic_content)
       │
       ├─ [PASS 1] _extract_general_info(general_info + cargo_table)
       │    → EditalGeral com cargos nomeados, materias=[]
       │
       └─ [PASS 2] para cada cargo em edital.cargos:
            ├─ PDFService.find_cargo_chunk(cargo.titulo, prog_content)
            └─ _extract_cargo_materias(chunk, cargo.titulo)
                 → List[Materia] mergeada em cargo.materias
       │
  ← EditalGeral JSON completo
```

---

## Tratamento de Erros

| Cenário | Comportamento |
|---------|---------------|
| Pass 1 falha (todos providers) | `RuntimeError` — comportamento atual, sem mudança |
| Marcador não encontrado | Segmento vazio, Pass 2 pulada com `log.warning` |
| Cargo não encontrado no conteúdo prog. | `materias=[]` para aquele cargo, `log.warning`, outros continuam |
| Pass 2 LLM falha para um cargo | `materias=[]`, `log.error`, continua para próximos cargos |

---

## Arquivos Afetados

| Arquivo | Mudança |
|---------|---------|
| `backend/app/services/pdf_service.py` | + `EditalSegments` dataclass + `get_segments()` + `find_cargo_chunk()` |
| `backend/app/services/ai_service.py` | Refatorar `extract_edital_data()` + `_extract_general_info()` + `_extract_cargo_materias()` |
| `backend/app/schemas/edital_schema.py` | + `MateriasWrapper` schema para validação da Pass 2 |
| `backend/app/api/endpoints.py` | Sem mudança |
| `backend/app/providers/ollama_provider.py` | Adicionar `num_ctx` nas options da chamada |

---

## Decisões de Design

- **Sequencial na Passada 2:** facilita debug via logs individuais por cargo. Paralelismo com `asyncio.gather` é extensão futura trivial.
- **`num_ctx=32768`** nas chamadas Ollama: suficiente para qualquer chunk de cargo individual.
- **Prompt com Placeholders** (não `model_json_schema()`): validado experimentalmente — evita que o modelo reproduza o schema como output.
- **`MateriasWrapper`** como schema separado: permite validação limpa do JSON da Pass 2 sem requerer o `EditalGeral` completo.
- **Fallback gracioso por cargo:** um cargo sem matérias não deve derrubar toda a extração.

---

## O que NÃO está no escopo desta fase

- Paralelização da Passada 2 com `asyncio.gather`
- Cache de segmentos por hash do PDF
- Suporte a mais de 2 passadas (ex.: passada 3 para correção de dados)
- Testes unitários automatizados (próxima fase)
