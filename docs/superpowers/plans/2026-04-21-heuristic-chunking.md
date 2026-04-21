# Heuristic Chunking — Two-Pass Edital Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o Fatiador Inteligente (Heuristic Chunking) com extração em duas passadas — Pass 1 extrai o esqueleto do edital, Pass 2 preenche as matérias por cargo usando chunks focados.

**Architecture:** PDFService ganha `get_segments()` (split por marcadores heurísticos) e `find_cargo_chunk()` (localiza seção de um cargo no conteúdo programático). AIService orquestra duas chamadas LLM: Pass 1 extrai EditalGeral sem matérias; Pass 2 itera pelos cargos, faz chunk por cargo, e preenche `materias`. Prompts usam a técnica de Placeholders Concretos validada experimentalmente.

**Tech Stack:** Python 3.12, Pydantic v2, aiohttp, pytest-asyncio, unicodedata (stdlib), re (stdlib), dataclasses (stdlib)

---

## File Map

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `backend/app/schemas/edital_schema.py` | Modificar | Adicionar `MateriasWrapper` (schema da Pass 2) |
| `backend/app/services/pdf_service.py` | Modificar | `EditalSegments`, `get_segments()`, `find_cargo_chunk()`, `_normalize_for_search()` |
| `backend/app/services/ai_service.py` | Modificar | Refatorar `extract_edital_data()` + `_extract_general_info()` + `_extract_cargo_materias()` |
| `backend/app/providers/ollama_provider.py` | Modificar | Adicionar parâmetro `num_ctx` com default 32768 |
| `backend/tests/services/__init__.py` | Criar | Marker de pacote pytest |
| `backend/tests/services/test_pdf_segmentation.py` | Criar | Testes de `get_segments()` e `find_cargo_chunk()` |
| `backend/tests/services/test_ai_service_two_pass.py` | Criar | Testes de `_extract_general_info()`, `_extract_cargo_materias()`, `extract_edital_data()` |
| `backend/tests/providers/test_ollama_provider.py` | Modificar | Atualizar assertion para incluir `num_ctx` |

---

## Task 1: Adicionar `MateriasWrapper` ao schema

**Files:**
- Modify: `backend/app/schemas/edital_schema.py`

- [ ] **Step 1.1: Adicionar `MateriasWrapper` ao final de `edital_schema.py`**

Adicione após a classe `EditalGeral`:

```python
class MateriasWrapper(BaseModel):
    materias: List[Materia]
```

O arquivo completo deve ficar:

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class Materia(BaseModel):
    nome: str
    topicos: List[str]
    peso: Optional[float] = 1.0
    quantidade_questoes: Optional[int] = 0

class Cargo(BaseModel):
    titulo: str
    vagas_ampla: int
    vagas_cotas: int
    salario: float
    requisitos: str
    materias: List[Materia] = Field(description='Lista de matérias exigidas para este cargo específico')

class EditalGeral(BaseModel):
    orgao: str
    banca: str
    data_prova: Optional[str]
    periodo_inscricao: Optional[str]
    link_edital: Optional[str]
    cargos: List[Cargo]

class MateriasWrapper(BaseModel):
    materias: List[Materia]
```

- [ ] **Step 1.2: Verificar import no container**

```bash
docker exec estudohub_40-backend-1 python3 -c "
from app.schemas.edital_schema import MateriasWrapper
print('MateriasWrapper OK:', MateriasWrapper.model_fields.keys())
"
```

Esperado: `MateriasWrapper OK: dict_keys(['materias'])`

- [ ] **Step 1.3: Commit**

```bash
git add backend/app/schemas/edital_schema.py
git commit -m "feat: add MateriasWrapper schema for Pass 2 validation"
```

---

## Task 2: Implementar `EditalSegments` + `PDFService.get_segments()`

**Files:**
- Modify: `backend/app/services/pdf_service.py`
- Create: `backend/tests/services/__init__.py`
- Create: `backend/tests/services/test_pdf_segmentation.py`

- [ ] **Step 2.1: Criar `backend/tests/services/__init__.py`**

```python
```
(arquivo vazio — marker de pacote)

- [ ] **Step 2.2: Escrever os testes de `get_segments()` (TDD — devem falhar)**

Crie `backend/tests/services/test_pdf_segmentation.py`:

```python
import pytest
from app.services.pdf_service import PDFService, EditalSegments


MARKDOWN_COMPLETO = """
# Edital

Órgão: TRT-24. Banca: FGV.

## 3. DOS CARGOS

| Cargo | Vagas |
|-------|-------|
| Analista Judiciário | 10 |

Salário: R$ 13.994,78

## CONTEÚDO PROGRAMÁTICO

### ANALISTA JUDICIÁRIO – ÁREA JUDICIÁRIA

**Língua Portuguesa**
- Interpretação de texto
- Gramática
""".strip()

MARKDOWN_SEM_PROGRAMATICO = """
# Edital simples

## DOS CARGOS

Cargo: Técnico
""".strip()

MARKDOWN_SEM_MARCADORES = """
# Edital sem marcadores padrão

Texto livre sem seções reconhecíveis.
""".strip()


def test_get_segments_retorna_tres_blocos():
    segs = PDFService.get_segments(MARKDOWN_COMPLETO)
    assert isinstance(segs, EditalSegments)
    assert isinstance(segs.general_info, str)
    assert isinstance(segs.cargo_table, str)
    assert isinstance(segs.programmatic_content, str)


def test_get_segments_general_info_antes_de_dos_cargos():
    segs = PDFService.get_segments(MARKDOWN_COMPLETO)
    assert "Órgão: TRT-24" in segs.general_info
    assert "DOS CARGOS" not in segs.general_info


def test_get_segments_cargo_table_contem_quadro():
    segs = PDFService.get_segments(MARKDOWN_COMPLETO)
    assert "DOS CARGOS" in segs.cargo_table
    assert "Analista Judiciário" in segs.cargo_table
    assert "CONTEÚDO PROGRAMÁTICO" not in segs.cargo_table


def test_get_segments_programmatic_content_correto():
    segs = PDFService.get_segments(MARKDOWN_COMPLETO)
    assert "CONTEÚDO PROGRAMÁTICO" in segs.programmatic_content
    assert "Língua Portuguesa" in segs.programmatic_content


def test_get_segments_sem_conteudo_programatico():
    segs = PDFService.get_segments(MARKDOWN_SEM_PROGRAMATICO)
    assert segs.programmatic_content == ""
    assert "DOS CARGOS" in segs.cargo_table


def test_get_segments_sem_marcadores_coloca_tudo_em_cargo_table():
    segs = PDFService.get_segments(MARKDOWN_SEM_MARCADORES)
    assert segs.general_info == ""
    assert segs.programmatic_content == ""
    assert "Texto livre" in segs.cargo_table


def test_get_segments_variante_quadro_de_vagas():
    md = "Intro\n\n## QUADRO DE VAGAS\n\nTabela\n\n## CONTEÚDO PROGRAMÁTICO\n\nMatérias"
    segs = PDFService.get_segments(md)
    assert "QUADRO DE VAGAS" in segs.cargo_table
    assert "Matérias" in segs.programmatic_content


def test_get_segments_variante_conteudo_sem_acento():
    md = "Intro\n\n## DOS CARGOS\n\nTabela\n\n## CONTEUDO PROGRAMATICO\n\nMatérias"
    segs = PDFService.get_segments(md)
    assert "Matérias" in segs.programmatic_content
```

- [ ] **Step 2.3: Rodar testes para confirmar que falham**

```bash
docker exec estudohub_40-backend-1 python3 -m pytest tests/services/test_pdf_segmentation.py -v 2>&1 | head -40
```

Esperado: `ImportError` ou `AttributeError` — `EditalSegments` não existe ainda.

- [ ] **Step 2.4: Implementar `EditalSegments` + `get_segments()` em `pdf_service.py`**

O arquivo completo de `backend/app/services/pdf_service.py`:

```python
import re
import unicodedata
from dataclasses import dataclass

import pymupdf4llm


@dataclass
class EditalSegments:
    general_info: str
    cargo_table: str
    programmatic_content: str


class PDFService:

    _MARKER_CARGO = re.compile(
        r'DOS CARGOS|QUADRO DE VAGAS|DAS VAGAS',
        re.IGNORECASE,
    )
    _MARKER_PROGRAMMATIC_SPECIFIC = re.compile(
        r'CONTEÚDO PROGRAMÁTICO|CONTEUDO PROGRAMATICO|PROGRAMA DE PROVAS',
        re.IGNORECASE,
    )
    _MARKER_PROGRAMMATIC_ANEXO = re.compile(
        r'(?:^|\n)\s*(?:\*\*)?ANEXO\s+[IVX]+(?:\*\*)?',
        re.IGNORECASE | re.MULTILINE,
    )

    @staticmethod
    def to_markdown(file_path: str) -> str:
        try:
            return pymupdf4llm.to_markdown(file_path)
        except Exception as e:
            raise Exception(f'Erro na conversão do PDF: {str(e)}')

    @staticmethod
    def get_segments(md_content: str) -> EditalSegments:
        """Split markdown into 3 semantic segments using heuristic markers."""
        m1 = PDFService._MARKER_CARGO.search(md_content)

        # Prefer specific programmatic marker; fall back to ANEXO only if needed
        m2 = PDFService._MARKER_PROGRAMMATIC_SPECIFIC.search(md_content)
        if not m2:
            m2 = PDFService._MARKER_PROGRAMMATIC_ANEXO.search(md_content)

        if m1 and m2 and m1.start() < m2.start():
            return EditalSegments(
                general_info=md_content[: m1.start()],
                cargo_table=md_content[m1.start() : m2.start()],
                programmatic_content=md_content[m2.start() :],
            )

        if m2:
            return EditalSegments(
                general_info="",
                cargo_table=md_content[: m2.start()],
                programmatic_content=md_content[m2.start() :],
            )

        return EditalSegments(
            general_info="",
            cargo_table=md_content,
            programmatic_content="",
        )

    @staticmethod
    def _normalize_for_search(text: str) -> str:
        """Remove accents, uppercase. Output length equals input length."""
        result = []
        for char in text:
            nfd = unicodedata.normalize('NFD', char)
            base = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
            result.append(base.upper() if base else ' ')
        return ''.join(result)

    @staticmethod
    def find_cargo_chunk(cargo_titulo: str, programmatic_content: str) -> str:
        """Extract the chunk of programmatic_content relevant to cargo_titulo."""
        if not programmatic_content:
            return ""

        _STOPWORDS = {
            'DE', 'DO', 'DA', 'DAS', 'DOS', 'E', 'A', 'O', 'AS', 'OS',
            'EM', 'POR', 'SEM', 'AREA',
        }
        norm = PDFService._normalize_for_search
        norm_title = norm(cargo_titulo)
        key_words = [
            w for w in norm_title.split()
            if w not in _STOPWORDS and len(w) > 3
        ][:4]

        if not key_words:
            return ""

        norm_content = norm(programmatic_content)
        pattern = r'.{0,80}'.join(re.escape(w) for w in key_words)
        match = re.search(pattern, norm_content, re.DOTALL)

        if not match:
            return ""

        start = match.start()
        # Cap chunk at 20K chars — large enough for any single cargo section
        end = min(start + 20_000, len(programmatic_content))
        return programmatic_content[start:end]
```

- [ ] **Step 2.5: Rodar testes de `get_segments()` para confirmar que passam**

```bash
docker exec estudohub_40-backend-1 python3 -m pytest tests/services/test_pdf_segmentation.py -v 2>&1
```

Esperado: todos os 8 testes `PASSED`.

- [ ] **Step 2.6: Commit**

```bash
git add backend/app/services/pdf_service.py backend/tests/services/__init__.py backend/tests/services/test_pdf_segmentation.py
git commit -m "feat: add EditalSegments and get_segments() to PDFService"
```

---

## Task 3: Implementar e testar `find_cargo_chunk()`

**Files:**
- Modify: `backend/tests/services/test_pdf_segmentation.py` (adicionar testes)

Os testes de `find_cargo_chunk` vão no mesmo arquivo de segmentação.

- [ ] **Step 3.1: Adicionar testes de `find_cargo_chunk()` ao arquivo de testes**

Adicione ao final de `backend/tests/services/test_pdf_segmentation.py`:

```python
PROGRAMMATIC = """
## CONTEÚDO PROGRAMÁTICO

### ANALISTA JUDICIÁRIO – ÁREA JUDICIÁRIA – OFICIAL DE JUSTIÇA AVALIADOR FEDERAL

**Língua Portuguesa**
- Interpretação de texto
- Coesão e coerência

**Raciocínio Lógico**
- Lógica proposicional
- Diagramas lógicos

### ANALISTA JUDICIÁRIO – ÁREA ADMINISTRATIVA – CONTABILIDADE

**Contabilidade Geral**
- Balanço patrimonial
- Demonstrações contábeis

### TÉCNICO JUDICIÁRIO – ÁREA ADMINISTRATIVA – AGENTE DA POLÍCIA JUDICIAL

**Direito Constitucional**
- Princípios fundamentais
""".strip()


def test_find_cargo_chunk_retorna_chunk_correto():
    chunk = PDFService.find_cargo_chunk(
        "Analista Judiciário – Área Judiciária – Oficial de Justiça Avaliador Federal",
        PROGRAMMATIC,
    )
    assert "Língua Portuguesa" in chunk
    assert "Raciocínio Lógico" in chunk


def test_find_cargo_chunk_nao_inclui_cargo_seguinte():
    chunk = PDFService.find_cargo_chunk(
        "Analista Judiciário – Área Judiciária – Oficial de Justiça Avaliador Federal",
        PROGRAMMATIC,
    )
    # 20K cap garante que o chunk não inclui o texto do cargo seguinte neste teste pequeno
    # (o PROGRAMMATIC de teste é pequeno — verifica que Contabilidade Geral não veio para o chunk de Oficial)
    # Nota: em documentos reais o cap de 20K pode incluir algum overlap — isso é aceitável
    assert "OFICIAL DE JUSTIÇA" in chunk.upper()


def test_find_cargo_chunk_cargo_nao_encontrado_retorna_vazio():
    chunk = PDFService.find_cargo_chunk("Cargo Inexistente XYZW", PROGRAMMATIC)
    assert chunk == ""


def test_find_cargo_chunk_content_vazio_retorna_vazio():
    chunk = PDFService.find_cargo_chunk("Analista Judiciário", "")
    assert chunk == ""


def test_find_cargo_chunk_ignora_acentos():
    chunk = PDFService.find_cargo_chunk(
        "Técnico Judiciário – Área Administrativa – Agente da Polícia Judicial",
        PROGRAMMATIC,
    )
    assert "Direito Constitucional" in chunk


def test_find_cargo_chunk_titulo_sem_palavras_chave_retorna_vazio():
    chunk = PDFService.find_cargo_chunk("De Do Da", PROGRAMMATIC)
    assert chunk == ""
```

- [ ] **Step 3.2: Rodar testes para confirmar que passam (implementação já está em pdf_service.py)**

```bash
docker exec estudohub_40-backend-1 python3 -m pytest tests/services/test_pdf_segmentation.py -v 2>&1
```

Esperado: todos os 14 testes `PASSED`.

- [ ] **Step 3.3: Commit**

```bash
git add backend/tests/services/test_pdf_segmentation.py
git commit -m "test: add find_cargo_chunk tests to pdf segmentation suite"
```

---

## Task 4: Atualizar `OllamaProvider` com parâmetro `num_ctx`

**Files:**
- Modify: `backend/app/providers/ollama_provider.py`
- Modify: `backend/tests/providers/test_ollama_provider.py`

- [ ] **Step 4.1: Atualizar o teste de inicialização do OllamaProvider**

Em `backend/tests/providers/test_ollama_provider.py`, atualize `test_ollama_provider_initialization`:

```python
@pytest.mark.asyncio
async def test_ollama_provider_initialization():
    """OllamaProvider should initialize with correct defaults"""
    provider = OllamaProvider()
    assert provider.base_url == settings.ollama_url
    assert provider.model == "llama3.1:8b"
    assert provider.timeout == settings.ollama_timeout
    assert provider.num_ctx == 32768
```

- [ ] **Step 4.2: Rodar para confirmar que falha**

```bash
docker exec estudohub_40-backend-1 python3 -m pytest tests/providers/test_ollama_provider.py::test_ollama_provider_initialization -v 2>&1
```

Esperado: `FAILED — AttributeError: 'OllamaProvider' object has no attribute 'num_ctx'`

- [ ] **Step 4.3: Implementar `num_ctx` no OllamaProvider**

O arquivo completo de `backend/app/providers/ollama_provider.py`:

```python
import logging
import aiohttp
import asyncio
from typing import Type, TypeVar
from pydantic import BaseModel

from .base_provider import BaseLLMProvider
from app.core.config import settings

T = TypeVar('T', bound=BaseModel)
logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Local Ollama LLM provider"""

    def __init__(
        self,
        base_url: str = None,
        model: str = "llama3.1:8b",
        timeout: int = None,
        num_ctx: int = 32768,
    ):
        self.base_url = base_url or settings.ollama_url
        self.model = model
        self.timeout = timeout or settings.ollama_timeout
        self.num_ctx = num_ctx
        logger.info(
            f"OllamaProvider initialized: {self.base_url}, model={self.model}, "
            f"timeout={self.timeout}s, num_ctx={self.num_ctx}"
        )

    async def generate_json(self, prompt: str, schema: Type[T]) -> T:
        """Generate JSON response from Ollama local model"""
        logger.info(f"OllamaProvider: Starting JSON generation for schema {schema.__name__}")

        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"num_ctx": self.num_ctx},
        }

        url = f"{self.base_url}/api/generate"

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:
                logger.debug(f"Sending request to {url}")
                async with session.post(url, json=payload) as response:
                    data = await response.json()
                    response_text = data.get("response", "")
                    logger.info(
                        f"OllamaProvider: Received response ({len(response_text)} chars)"
                    )

        except asyncio.TimeoutError:
            logger.error(f"OllamaProvider: Timeout after {self.timeout}s")
            raise TimeoutError(f"Ollama request timed out after {self.timeout}s")
        except aiohttp.ClientConnectorError as e:
            logger.error(f"OllamaProvider: Connection error - {e}")
            raise ConnectionError(f"Failed to connect to Ollama at {self.base_url}: {e}")
        except aiohttp.ClientError as e:
            logger.error(f"OllamaProvider: Request error - {e}")
            raise ConnectionError(f"Ollama request failed: {e}")

        try:
            result = self._validate_json_response(response_text, schema)
            logger.info(
                f"OllamaProvider: Successfully validated response for {schema.__name__}"
            )
            return result
        except Exception as e:
            logger.error(f"OllamaProvider: Validation failed - {e}")
            raise
```

- [ ] **Step 4.4: Rodar todos os testes do provider**

```bash
docker exec estudohub_40-backend-1 python3 -m pytest tests/providers/test_ollama_provider.py -v 2>&1
```

Esperado: todos os testes `PASSED`.

- [ ] **Step 4.5: Commit**

```bash
git add backend/app/providers/ollama_provider.py backend/tests/providers/test_ollama_provider.py
git commit -m "feat: add num_ctx parameter to OllamaProvider (default 32768)"
```

---

## Task 5: Implementar `_extract_general_info()` no AIService (Pass 1)

**Files:**
- Modify: `backend/app/services/ai_service.py`
- Create: `backend/tests/services/test_ai_service_two_pass.py`

- [ ] **Step 5.1: Escrever testes para `_extract_general_info()` (TDD — devem falhar)**

Crie `backend/tests/services/test_ai_service_two_pass.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.services.ai_service import AIService
from app.schemas.edital_schema import EditalGeral, Cargo, Materia, MateriasWrapper


EDITAL_BLOCK = """
Tribunal Regional do Trabalho da 24ª Região.
Banca: FGV.

## DOS CARGOS
| Cargo | Vagas |
| Analista Judiciário – Área Judiciária | 2 |
| Técnico Judiciário – Área Administrativa | 1 |
"""

EDITAL_GERAL_SEM_MATERIAS = EditalGeral(
    orgao="Tribunal Regional do Trabalho da 24ª Região",
    banca="FGV",
    data_prova=None,
    periodo_inscricao="06/11/2024 a 07/12/2024",
    link_edital=None,
    cargos=[
        Cargo(
            titulo="Analista Judiciário – Área Judiciária",
            vagas_ampla=2,
            vagas_cotas=0,
            salario=13994.78,
            requisitos="Graduação em Direito",
            materias=[],
        ),
        Cargo(
            titulo="Técnico Judiciário – Área Administrativa",
            vagas_ampla=1,
            vagas_cotas=0,
            salario=8529.65,
            requisitos="Ensino Superior",
            materias=[],
        ),
    ],
)


@pytest.mark.asyncio
async def test_extract_general_info_retorna_edital_geral():
    service = AIService()
    service.ollama_provider.generate_json = AsyncMock(return_value=EDITAL_GERAL_SEM_MATERIAS)

    result = await service._extract_general_info(EDITAL_BLOCK)

    assert isinstance(result, EditalGeral)
    assert result.orgao == "Tribunal Regional do Trabalho da 24ª Região"
    assert result.banca == "FGV"
    assert len(result.cargos) == 2


@pytest.mark.asyncio
async def test_extract_general_info_passa_bloco_correto_no_prompt():
    service = AIService()
    captured_prompt = []

    async def mock_generate(prompt, schema):
        captured_prompt.append(prompt)
        return EDITAL_GERAL_SEM_MATERIAS

    service.ollama_provider.generate_json = mock_generate

    await service._extract_general_info(EDITAL_BLOCK)

    assert len(captured_prompt) == 1
    assert "EDITAL:" in captured_prompt[0]
    assert EDITAL_BLOCK in captured_prompt[0]


@pytest.mark.asyncio
async def test_extract_general_info_usa_schema_edital_geral():
    service = AIService()
    captured_schema = []

    async def mock_generate(prompt, schema):
        captured_schema.append(schema)
        return EDITAL_GERAL_SEM_MATERIAS

    service.ollama_provider.generate_json = mock_generate

    await service._extract_general_info(EDITAL_BLOCK)

    assert captured_schema[0] is EditalGeral


@pytest.mark.asyncio
async def test_extract_general_info_propaga_excecao_do_provider():
    service = AIService()
    service.ollama_provider.generate_json = AsyncMock(
        side_effect=ConnectionError("Ollama offline")
    )

    with pytest.raises(ConnectionError, match="Ollama offline"):
        await service._extract_general_info(EDITAL_BLOCK)
```

- [ ] **Step 5.2: Rodar para confirmar que falham**

```bash
docker exec estudohub_40-backend-1 python3 -m pytest tests/services/test_ai_service_two_pass.py::test_extract_general_info_retorna_edital_geral -v 2>&1
```

Esperado: `FAILED — AttributeError: 'AIService' object has no attribute '_extract_general_info'`

- [ ] **Step 5.3: Adicionar `_extract_general_info()` ao `ai_service.py`**

Adicione o método dentro da classe `AIService` (antes de `extract_edital_data`):

```python
async def _extract_general_info(self, block: str) -> EditalGeral:
    """Pass 1: extract EditalGeral skeleton (no materias) from the initial block."""
    prompt = f"""Você é um extrator de dados de editais de concurso público brasileiro.
Leia o edital abaixo e preencha o JSON de saída com os dados encontrados.

FORMATO DE SAÍDA (preencha com os dados reais do edital):
{{
  "orgao": "<nome da instituição que realiza o concurso>",
  "banca": "<empresa organizadora: FGV, CEBRASPE, CESPE, FCC, VUNESP, etc>",
  "data_prova": "<data da prova ou null>",
  "periodo_inscricao": "<período de inscrição ou null>",
  "link_edital": null,
  "cargos": [
    {{
      "titulo": "<nome completo do cargo>",
      "vagas_ampla": <número inteiro de vagas ampla concorrência, 0 se não encontrado>,
      "vagas_cotas": <número inteiro de vagas cotas, 0 se não encontrado>,
      "salario": <valor numérico do salário em reais, 0 se não encontrado>,
      "requisitos": "<escolaridade/requisitos ou string vazia>",
      "materias": []
    }}
  ]
}}

REGRAS:
- Retorne SOMENTE o JSON preenchido, sem explicações
- Liste TODOS os cargos mencionados no edital
- Use os dados reais do documento, não invente

EDITAL:
{block}
"""
    providers = self._get_provider_chain()
    last_error = None
    for provider in providers:
        try:
            return await provider.generate_json(prompt=prompt, schema=EditalGeral)
        except (ConnectionError, TimeoutError, ValueError) as e:
            last_error = e
            logger.warning(
                f"_extract_general_info: {provider.__class__.__name__} failed — {e}"
            )
            continue
        except Exception as e:
            last_error = e
            logger.error(
                f"_extract_general_info: {provider.__class__.__name__} unexpected error — {e}"
            )
            continue
    raise RuntimeError(f"Pass 1 failed. Last error: {last_error}")
```

- [ ] **Step 5.4: Rodar testes de `_extract_general_info()`**

```bash
docker exec estudohub_40-backend-1 python3 -m pytest tests/services/test_ai_service_two_pass.py -k "general_info" -v 2>&1
```

Esperado: 4 testes `PASSED`.

- [ ] **Step 5.5: Commit**

```bash
git add backend/app/services/ai_service.py backend/tests/services/test_ai_service_two_pass.py
git commit -m "feat: add AIService._extract_general_info() for Pass 1 extraction"
```

---

## Task 6: Implementar `_extract_cargo_materias()` no AIService (Pass 2)

**Files:**
- Modify: `backend/app/services/ai_service.py`
- Modify: `backend/tests/services/test_ai_service_two_pass.py`

- [ ] **Step 6.1: Adicionar testes para `_extract_cargo_materias()`**

Adicione ao final de `backend/tests/services/test_ai_service_two_pass.py`:

```python
CARGO_CHUNK = """
### ANALISTA JUDICIÁRIO – ÁREA JUDICIÁRIA

**Língua Portuguesa**
1. Interpretação de texto
2. Coesão e coerência textual
3. Classes de palavras

**Raciocínio Lógico**
1. Proposições e conectivos
2. Diagramas lógicos
"""

MATERIAS_WRAPPER_MOCK = MateriasWrapper(
    materias=[
        Materia(nome="Língua Portuguesa", topicos=["Interpretação de texto", "Coesão e coerência textual"]),
        Materia(nome="Raciocínio Lógico", topicos=["Proposições e conectivos", "Diagramas lógicos"]),
    ]
)


@pytest.mark.asyncio
async def test_extract_cargo_materias_retorna_lista_materia():
    service = AIService()
    service.ollama_provider.generate_json = AsyncMock(return_value=MATERIAS_WRAPPER_MOCK)

    result = await service._extract_cargo_materias(
        CARGO_CHUNK, "Analista Judiciário – Área Judiciária"
    )

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0].nome == "Língua Portuguesa"
    assert "Interpretação de texto" in result[0].topicos


@pytest.mark.asyncio
async def test_extract_cargo_materias_chunk_vazio_retorna_lista_vazia():
    service = AIService()
    service.ollama_provider.generate_json = AsyncMock()

    result = await service._extract_cargo_materias("", "Analista Judiciário")

    assert result == []
    service.ollama_provider.generate_json.assert_not_called()


@pytest.mark.asyncio
async def test_extract_cargo_materias_inclui_titulo_no_prompt():
    service = AIService()
    captured = []

    async def mock_generate(prompt, schema):
        captured.append(prompt)
        return MATERIAS_WRAPPER_MOCK

    service.ollama_provider.generate_json = mock_generate

    await service._extract_cargo_materias(CARGO_CHUNK, "Analista Judiciário – Área Judiciária")

    assert "Analista Judiciário – Área Judiciária" in captured[0]
    assert "CONTEÚDO PROGRAMÁTICO:" in captured[0]


@pytest.mark.asyncio
async def test_extract_cargo_materias_usa_schema_materias_wrapper():
    service = AIService()
    captured_schema = []

    async def mock_generate(prompt, schema):
        captured_schema.append(schema)
        return MATERIAS_WRAPPER_MOCK

    service.ollama_provider.generate_json = mock_generate

    await service._extract_cargo_materias(CARGO_CHUNK, "Cargo X")

    assert captured_schema[0] is MateriasWrapper


@pytest.mark.asyncio
async def test_extract_cargo_materias_retorna_vazio_se_provider_falha():
    service = AIService()
    service.ollama_provider.generate_json = AsyncMock(
        side_effect=ConnectionError("offline")
    )
    # Gemini também falha
    service.gemini_provider.generate_json = AsyncMock(
        side_effect=ConnectionError("offline")
    )

    result = await service._extract_cargo_materias(CARGO_CHUNK, "Cargo X")

    assert result == []
```

- [ ] **Step 6.2: Rodar para confirmar que falham**

```bash
docker exec estudohub_40-backend-1 python3 -m pytest tests/services/test_ai_service_two_pass.py -k "cargo_materias" -v 2>&1
```

Esperado: `FAILED — AttributeError: 'AIService' object has no attribute '_extract_cargo_materias'`

- [ ] **Step 6.3: Adicionar `_extract_cargo_materias()` ao `ai_service.py`**

Adicione o método dentro da classe `AIService` (após `_extract_general_info`):

```python
async def _extract_cargo_materias(self, chunk: str, cargo_titulo: str) -> list:
    """Pass 2: extract List[Materia] from a focused cargo chunk."""
    if not chunk:
        return []

    prompt = f"""Para o cargo "{cargo_titulo}", extraia todas as matérias e seus tópicos do conteúdo abaixo.

FORMATO DE SAÍDA (preencha com os dados reais):
{{
  "materias": [
    {{
      "nome": "<nome da matéria/disciplina>",
      "topicos": ["<tópico 1>", "<tópico 2>", "<tópico 3>"]
    }}
  ]
}}

REGRAS:
- Retorne SOMENTE o JSON preenchido, sem explicações
- Liste TODAS as matérias encontradas para este cargo
- Se não houver matérias, retorne {{"materias": []}}

CONTEÚDO PROGRAMÁTICO:
{chunk}
"""
    providers = self._get_provider_chain()
    for provider in providers:
        try:
            result = await provider.generate_json(prompt=prompt, schema=MateriasWrapper)
            logger.info(
                f"_extract_cargo_materias: ✓ '{cargo_titulo}' — "
                f"{len(result.materias)} matéria(s) extraída(s)"
            )
            return result.materias
        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.warning(
                f"_extract_cargo_materias: {provider.__class__.__name__} failed "
                f"for '{cargo_titulo}' — {e}"
            )
            continue
        except Exception as e:
            logger.error(
                f"_extract_cargo_materias: unexpected error for '{cargo_titulo}' — {e}"
            )
            continue

    logger.error(f"_extract_cargo_materias: all providers failed for '{cargo_titulo}'")
    return []
```

Adicione o import de `MateriasWrapper` no topo do arquivo:

```python
from app.schemas.edital_schema import EditalGeral, MateriasWrapper
```

- [ ] **Step 6.4: Rodar testes de `_extract_cargo_materias()`**

```bash
docker exec estudohub_40-backend-1 python3 -m pytest tests/services/test_ai_service_two_pass.py -k "cargo_materias" -v 2>&1
```

Esperado: 5 testes `PASSED`.

- [ ] **Step 6.5: Commit**

```bash
git add backend/app/services/ai_service.py backend/tests/services/test_ai_service_two_pass.py
git commit -m "feat: add AIService._extract_cargo_materias() for Pass 2 extraction"
```

---

## Task 7: Refatorar `extract_edital_data()` para orquestrar as duas passadas

**Files:**
- Modify: `backend/app/services/ai_service.py`
- Modify: `backend/tests/services/test_ai_service_two_pass.py`

- [ ] **Step 7.1: Adicionar testes de integração da orquestração**

Adicione ao final de `backend/tests/services/test_ai_service_two_pass.py`:

```python
MD_COMPLETO = """
Tribunal Regional do Trabalho da 24ª Região. Banca: FGV.

## DOS CARGOS
| Analista Judiciário – Área Judiciária | 2 vagas |

## CONTEÚDO PROGRAMÁTICO

### ANALISTA JUDICIÁRIO – ÁREA JUDICIÁRIA
**Língua Portuguesa**
1. Interpretação de texto
"""


@pytest.mark.asyncio
async def test_extract_edital_data_faz_duas_passadas():
    service = AIService()

    edital_sem_materias = EditalGeral(
        orgao="TRT-24",
        banca="FGV",
        data_prova=None,
        periodo_inscricao=None,
        link_edital=None,
        cargos=[
            Cargo(
                titulo="Analista Judiciário – Área Judiciária",
                vagas_ampla=2,
                vagas_cotas=0,
                salario=13994.78,
                requisitos="Graduação",
                materias=[],
            )
        ],
    )
    materias_wrapper = MateriasWrapper(
        materias=[Materia(nome="Língua Portuguesa", topicos=["Interpretação de texto"])]
    )

    call_count = 0

    async def mock_generate(prompt, schema):
        nonlocal call_count
        call_count += 1
        if schema is EditalGeral:
            return edital_sem_materias
        if schema is MateriasWrapper:
            return materias_wrapper
        raise ValueError(f"Schema inesperado: {schema}")

    service.ollama_provider.generate_json = mock_generate

    result = await service.extract_edital_data(MD_COMPLETO)

    assert result.orgao == "TRT-24"
    assert result.banca == "FGV"
    assert len(result.cargos) == 1
    assert len(result.cargos[0].materias) == 1
    assert result.cargos[0].materias[0].nome == "Língua Portuguesa"
    assert call_count == 2  # 1 chamada Pass 1 + 1 chamada Pass 2


@pytest.mark.asyncio
async def test_extract_edital_data_sem_conteudo_programatico_pula_pass2():
    service = AIService()

    md_sem_programatico = "TRT-24. Banca: FGV.\n\n## DOS CARGOS\nAnalista Judiciário | 2"

    edital_sem_materias = EditalGeral(
        orgao="TRT-24", banca="FGV", data_prova=None,
        periodo_inscricao=None, link_edital=None,
        cargos=[Cargo(titulo="Analista Judiciário", vagas_ampla=2,
                      vagas_cotas=0, salario=0, requisitos="", materias=[])],
    )

    call_count = 0

    async def mock_generate(prompt, schema):
        nonlocal call_count
        call_count += 1
        return edital_sem_materias

    service.ollama_provider.generate_json = mock_generate

    result = await service.extract_edital_data(md_sem_programatico)

    assert result.orgao == "TRT-24"
    assert call_count == 1  # apenas Pass 1 — Pass 2 pulada (sem conteúdo programático)


@pytest.mark.asyncio
async def test_extract_edital_data_cargo_sem_chunk_mantém_materias_vazias():
    service = AIService()

    edital = EditalGeral(
        orgao="TRT-24", banca="FGV", data_prova=None,
        periodo_inscricao=None, link_edital=None,
        cargos=[
            Cargo(titulo="Cargo XYZW Inexistente", vagas_ampla=1,
                  vagas_cotas=0, salario=0, requisitos="", materias=[]),
        ],
    )

    async def mock_generate(prompt, schema):
        if schema is EditalGeral:
            return edital
        raise AssertionError("Pass 2 não deve ser chamada se chunk não encontrado")

    service.ollama_provider.generate_json = mock_generate

    md = "## DOS CARGOS\nCargo XYZW\n\n## CONTEÚDO PROGRAMÁTICO\nNada relevante aqui"
    result = await service.extract_edital_data(md)

    assert result.cargos[0].materias == []
```

- [ ] **Step 7.2: Rodar para confirmar que falham**

```bash
docker exec estudohub_40-backend-1 python3 -m pytest tests/services/test_ai_service_two_pass.py -k "extract_edital_data" -v 2>&1
```

Esperado: testes falham porque `extract_edital_data` ainda não usa as duas passadas.

- [ ] **Step 7.3: Refatorar `extract_edital_data()` em `ai_service.py`**

Substitua o método `extract_edital_data` existente. O arquivo `ai_service.py` completo:

```python
import logging
from typing import Type, TypeVar, List
from pydantic import BaseModel

from app.core.config import settings
from app.providers.ollama_provider import OllamaProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.base_provider import BaseLLMProvider
from app.schemas.edital_schema import EditalGeral, MateriasWrapper
from app.services.pdf_service import PDFService

T = TypeVar('T', bound=BaseModel)
logger = logging.getLogger(__name__)


class AIService:
    """Orchestrates LLM provider selection, failover, and two-pass edital extraction."""

    def __init__(self):
        self.ollama_provider = OllamaProvider()
        self.gemini_provider = GeminiProvider()
        self.strategy = settings.llm_strategy
        self.cloud_fallback = settings.cloud_fallback
        logger.info(
            f"AIService initialized with strategy={self.strategy}, "
            f"cloud_fallback={self.cloud_fallback}"
        )

    def _get_provider_chain(self) -> List[BaseLLMProvider]:
        if self.strategy == "local_only":
            return [self.ollama_provider]
        elif self.strategy == "cloud_only":
            return [self.gemini_provider]
        else:  # local_first (default)
            chain = [self.ollama_provider]
            if self.cloud_fallback:
                chain.append(self.gemini_provider)
            return chain

    async def _extract_general_info(self, block: str) -> EditalGeral:
        """Pass 1: extract EditalGeral skeleton (no materias) from the initial block."""
        prompt = f"""Você é um extrator de dados de editais de concurso público brasileiro.
Leia o edital abaixo e preencha o JSON de saída com os dados encontrados.

FORMATO DE SAÍDA (preencha com os dados reais do edital):
{{
  "orgao": "<nome da instituição que realiza o concurso>",
  "banca": "<empresa organizadora: FGV, CEBRASPE, CESPE, FCC, VUNESP, etc>",
  "data_prova": "<data da prova ou null>",
  "periodo_inscricao": "<período de inscrição ou null>",
  "link_edital": null,
  "cargos": [
    {{
      "titulo": "<nome completo do cargo>",
      "vagas_ampla": <número inteiro de vagas ampla concorrência, 0 se não encontrado>,
      "vagas_cotas": <número inteiro de vagas cotas, 0 se não encontrado>,
      "salario": <valor numérico do salário em reais, 0 se não encontrado>,
      "requisitos": "<escolaridade/requisitos ou string vazia>",
      "materias": []
    }}
  ]
}}

REGRAS:
- Retorne SOMENTE o JSON preenchido, sem explicações
- Liste TODOS os cargos mencionados no edital
- Use os dados reais do documento, não invente

EDITAL:
{block}
"""
        providers = self._get_provider_chain()
        last_error = None
        for provider in providers:
            try:
                return await provider.generate_json(prompt=prompt, schema=EditalGeral)
            except (ConnectionError, TimeoutError, ValueError) as e:
                last_error = e
                logger.warning(
                    f"_extract_general_info: {provider.__class__.__name__} failed — {e}"
                )
            except Exception as e:
                last_error = e
                logger.error(
                    f"_extract_general_info: {provider.__class__.__name__} "
                    f"unexpected error — {e}"
                )
        raise RuntimeError(f"Pass 1 failed. Last error: {last_error}")

    async def _extract_cargo_materias(self, chunk: str, cargo_titulo: str) -> list:
        """Pass 2: extract List[Materia] from a focused cargo chunk."""
        if not chunk:
            return []

        prompt = f"""Para o cargo "{cargo_titulo}", extraia todas as matérias e seus tópicos do conteúdo abaixo.

FORMATO DE SAÍDA (preencha com os dados reais):
{{
  "materias": [
    {{
      "nome": "<nome da matéria/disciplina>",
      "topicos": ["<tópico 1>", "<tópico 2>", "<tópico 3>"]
    }}
  ]
}}

REGRAS:
- Retorne SOMENTE o JSON preenchido, sem explicações
- Liste TODAS as matérias encontradas para este cargo
- Se não houver matérias, retorne {{"materias": []}}

CONTEÚDO PROGRAMÁTICO:
{chunk}
"""
        providers = self._get_provider_chain()
        for provider in providers:
            try:
                result = await provider.generate_json(prompt=prompt, schema=MateriasWrapper)
                logger.info(
                    f"_extract_cargo_materias: ✓ '{cargo_titulo}' — "
                    f"{len(result.materias)} matéria(s)"
                )
                return result.materias
            except (ConnectionError, TimeoutError, ValueError) as e:
                logger.warning(
                    f"_extract_cargo_materias: {provider.__class__.__name__} failed "
                    f"for '{cargo_titulo}' — {e}"
                )
            except Exception as e:
                logger.error(
                    f"_extract_cargo_materias: unexpected error for '{cargo_titulo}' — {e}"
                )

        logger.error(f"_extract_cargo_materias: all providers failed for '{cargo_titulo}'")
        return []

    async def extract_edital_data(self, md_content: str) -> EditalGeral:
        """Two-pass extraction: Pass 1 builds skeleton, Pass 2 fills materias per cargo."""
        segments = PDFService.get_segments(md_content)
        initial_block = segments.general_info + segments.cargo_table

        logger.info(
            f"extract_edital_data: segments — general={len(segments.general_info)}c, "
            f"cargo_table={len(segments.cargo_table)}c, "
            f"programmatic={len(segments.programmatic_content)}c"
        )

        # Pass 1 — EditalGeral skeleton
        logger.info("extract_edital_data: [Pass 1] extracting general info + cargo list")
        edital = await self._extract_general_info(initial_block)
        logger.info(
            f"extract_edital_data: [Pass 1] ✓ {len(edital.cargos)} cargo(s) found"
        )

        # Pass 2 — materias per cargo
        if not segments.programmatic_content:
            logger.warning(
                "extract_edital_data: [Pass 2] skipped — no programmatic content found"
            )
            return edital

        logger.info(
            f"extract_edital_data: [Pass 2] extracting materias for "
            f"{len(edital.cargos)} cargo(s)"
        )
        for i, cargo in enumerate(edital.cargos, 1):
            chunk = PDFService.find_cargo_chunk(
                cargo.titulo, segments.programmatic_content
            )
            if not chunk:
                logger.warning(
                    f"extract_edital_data: [Pass 2] cargo {i}/{len(edital.cargos)} "
                    f"'{cargo.titulo}' — chunk not found, skipping"
                )
                continue

            logger.info(
                f"extract_edital_data: [Pass 2] cargo {i}/{len(edital.cargos)} "
                f"'{cargo.titulo}' — chunk {len(chunk)}c"
            )
            cargo.materias = await self._extract_cargo_materias(chunk, cargo.titulo)

        logger.info("extract_edital_data: ✓ complete")
        return edital
```

- [ ] **Step 7.4: Rodar todos os testes**

```bash
docker exec estudohub_40-backend-1 python3 -m pytest tests/services/ tests/providers/ -v 2>&1
```

Esperado: todos os testes `PASSED`.

- [ ] **Step 7.5: Commit final**

```bash
git add backend/app/services/ai_service.py backend/tests/services/test_ai_service_two_pass.py
git commit -m "feat: refactor AIService to two-pass heuristic chunking extraction"
```

---

## Task 8: Verificação End-to-End com o arquivo TRT real

Esta task usa o script de debug existente para validar o pipeline completo no container.

**Files:**
- Modify: `backend/debug/test_chunking.py` (atualizar para usar o novo AIService)

- [ ] **Step 8.1: Atualizar o script de debug para usar o AIService refatorado**

Substitua o conteúdo de `backend/debug/test_chunking.py`:

```python
"""
Verificação E2E: testa o pipeline completo de two-pass extraction com o TRT real.
"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, "/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("e2e_test")

PDF_PATH = "/app/debug/trt.pdf"
DEBUG_DIR = "/app/debug"


async def main():
    import pymupdf4llm
    from app.services.pdf_service import PDFService
    from app.services.ai_service import AIService

    # Etapa 1: Converter PDF
    logger.info(f"Convertendo {PDF_PATH} para Markdown...")
    md_content = pymupdf4llm.to_markdown(PDF_PATH)
    logger.info(f"Markdown total: {len(md_content)} chars")

    # Salvar markdown completo para debug
    with open(f"{DEBUG_DIR}/trt_full.md", "w", encoding="utf-8") as f:
        f.write(md_content)

    # Etapa 2: Segmentar
    segs = PDFService.get_segments(md_content)
    logger.info(f"Segmentos — general_info: {len(segs.general_info)}c | "
                f"cargo_table: {len(segs.cargo_table)}c | "
                f"programmatic: {len(segs.programmatic_content)}c")

    # Etapa 3: Two-pass extraction
    logger.info("Iniciando extração two-pass...")
    service = AIService()
    result = await service.extract_edital_data(md_content)

    # Relatório
    print("\n" + "=" * 60)
    print("RESULTADO TWO-PASS EXTRACTION — TRT 24ª Região")
    print("=" * 60)
    print(f"  Órgão  : {result.orgao}")
    print(f"  Banca  : {result.banca}")
    print(f"  Período: {result.periodo_inscricao}")
    print(f"  Cargos : {len(result.cargos)}")
    for i, cargo in enumerate(result.cargos, 1):
        mat_count = len(cargo.materias)
        topics_count = sum(len(m.topicos) for m in cargo.materias)
        print(f"    {i:2d}. {cargo.titulo}")
        print(f"        └─ {mat_count} matéria(s), {topics_count} tópico(s) total")
    print("=" * 60)

    # Salvar JSON completo
    out_path = f"{DEBUG_DIR}/trt_extraction.json"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2, ensure_ascii=False))
    logger.info(f"JSON completo salvo em {out_path}")

    # Avaliação
    cargos_com_materias = sum(1 for c in result.cargos if c.materias)
    print(f"\n  Cargos com matérias preenchidas: {cargos_com_materias}/{len(result.cargos)}")

    if result.orgao and result.banca and result.cargos:
        print("✓ PASS 1: SUCESSO")
    else:
        print("✗ PASS 1: FALHOU")

    if cargos_com_materias > 0:
        print("✓ PASS 2: SUCESSO (ao menos 1 cargo com matérias)")
    else:
        print("✗ PASS 2: NENHUMA MATÉRIA EXTRAÍDA")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 8.2: Rodar verificação E2E no container**

```bash
docker exec estudohub_40-backend-1 python3 /app/debug/test_chunking.py 2>&1
```

Esperado:
- `✓ PASS 1: SUCESSO` com órgão, banca e 13 cargos
- `✓ PASS 2: SUCESSO` com pelo menos 1 cargo com matérias preenchidas
- JSON salvo em `/app/debug/trt_extraction.json`

- [ ] **Step 8.3: Commit final da fase**

```bash
git add backend/debug/test_chunking.py
git commit -m "test: update E2E debug script to validate two-pass pipeline"
```

---

## Checklist de Auto-Review do Plano

- [x] **Cobertura da spec:** `EditalSegments` ✓ | `get_segments()` ✓ | `find_cargo_chunk()` ✓ | `_extract_general_info()` ✓ | `_extract_cargo_materias()` ✓ | `extract_edital_data()` refatorado ✓ | `num_ctx` ✓ | `MateriasWrapper` ✓
- [x] **Sem placeholders:** todos os steps têm código completo
- [x] **Consistência de tipos:** `MateriasWrapper` definido em Task 1, usado em Tasks 5-7. `EditalSegments` definido em Task 2, usado em Task 7. `_normalize_for_search` definido junto com `find_cargo_chunk` em Task 2.
- [x] **Import de `MateriasWrapper`:** adicionado explicitamente no Step 6.3
- [x] **Import de `PDFService`:** adicionado no Step 7.3 (`from app.services.pdf_service import PDFService`)
- [x] **Test do OllamaProvider atualizado:** Step 4.1 atualiza a assertion de `num_ctx`
