# Ollama Integration with Provider Failover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate local Ollama (Llama 3) with automatic failover to Gemini, enabling flexible LLM provider switching via configuration strategies.

**Architecture:** Abstract provider pattern with BaseLLMProvider interface. OllamaProvider handles local inference with 120s timeout, GeminiProvider wraps existing Gemini API with 15s timeout. AIService acts as orchestrator selecting provider chain based on LLM_STRATEGY (local_first/local_only/cloud_only). Standard Python logging to stdout for Docker observability.

**Tech Stack:** 
- Python async/await (existing)
- Pydantic for schema validation (existing)
- requests library for Ollama HTTP API
- Python logging module
- Docker networking (host.docker.internal)

---

## Task 1: Update Configuration with LLM Settings

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Read current config.py to understand structure**

Current structure uses Pydantic BaseSettings with env_file=".env"

- [ ] **Step 2: Add new configuration variables**

Update `backend/app/core/config.py`:

```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Existing
    gemini_api_key: Optional[str] = None
    debug: bool = False
    
    # New LLM Provider Configuration
    use_local_llm: bool = True
    ollama_url: str = "http://host.docker.internal:11434"
    ollama_timeout: int = 120  # seconds
    gemini_timeout: int = 15   # seconds
    llm_strategy: str = "local_first"  # local_first, local_only, cloud_only
    cloud_fallback: bool = True  # Allow fallback to Gemini in local_first mode

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()
```

- [ ] **Step 3: Verify imports and syntax**

Run: `cd /mnt/c/Dev/EstudoHub_4.0/backend && python -c "from app.core.config import settings; print(f'Config loaded: {settings.llm_strategy}')"`

Expected: Output shows `Config loaded: local_first`

- [ ] **Step 4: Commit configuration changes**

```bash
cd /mnt/c/Dev/EstudoHub_4.0
git add backend/app/core/config.py
git commit -m "feat: add LLM provider configuration variables"
```

---

## Task 2: Create BaseLLMProvider Abstract Base Class

**Files:**
- Create: `backend/app/providers/__init__.py`
- Create: `backend/app/providers/base_provider.py`
- Create: `backend/tests/providers/__init__.py`
- Create: `backend/tests/providers/test_base_provider.py`

- [ ] **Step 1: Create providers package**

```bash
mkdir -p /mnt/c/Dev/EstudoHub_4.0/backend/app/providers
touch /mnt/c/Dev/EstudoHub_4.0/backend/app/providers/__init__.py
```

- [ ] **Step 2: Create test directory**

```bash
mkdir -p /mnt/c/Dev/EstudoHub_4.0/backend/tests/providers
touch /mnt/c/Dev/EstudoHub_4.0/backend/tests/providers/__init__.py
```

- [ ] **Step 3: Write test for BaseLLMProvider**

Create `backend/tests/providers/test_base_provider.py`:

```python
import pytest
from abc import ABC
from pydantic import BaseModel
from app.providers.base_provider import BaseLLMProvider


class SampleSchema(BaseModel):
    title: str
    description: str


def test_base_llm_provider_is_abstract():
    """BaseLLMProvider should be abstract and not instantiable"""
    assert issubclass(BaseLLMProvider, ABC)
    
    with pytest.raises(TypeError):
        BaseLLMProvider()


@pytest.mark.asyncio
async def test_base_llm_provider_has_generate_json_method():
    """BaseLLMProvider must define generate_json async method"""
    assert hasattr(BaseLLMProvider, 'generate_json')
    assert callable(getattr(BaseLLMProvider, 'generate_json'))
```

- [ ] **Step 4: Run test to verify it fails**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/providers/test_base_provider.py -v
```

Expected: FAIL - `ModuleNotFoundError: No module named 'app.providers.base_provider'`

- [ ] **Step 5: Implement BaseLLMProvider**

Create `backend/app/providers/base_provider.py`:

```python
import logging
from abc import ABC, abstractmethod
from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError

T = TypeVar('T', bound=BaseModel)
logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers (Ollama, Gemini, etc)"""
    
    @abstractmethod
    async def generate_json(self, prompt: str, schema: Type[T]) -> T:
        """
        Generate a response from the LLM and validate against schema.
        
        Args:
            prompt: The input prompt for the LLM
            schema: A Pydantic model class to validate response against
            
        Returns:
            Instance of schema class with validated data
            
        Raises:
            ConnectionError: If provider is unavailable
            ValidationError: If response doesn't match schema
            TimeoutError: If request exceeds timeout
        """
        pass
    
    def _validate_json_response(self, response_text: str, schema: Type[T]) -> T:
        """
        Parse and validate JSON response against Pydantic schema.
        
        Args:
            response_text: Raw text response from LLM
            schema: Pydantic model class to validate against
            
        Returns:
            Validated instance of schema
            
        Raises:
            ValidationError: If JSON doesn't match schema
        """
        import json
        
        # Clean up markdown code blocks if present
        cleaned = response_text.strip().replace('```json', '').replace('```', '').strip()
        
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}\nResponse was: {cleaned[:200]}")
            raise ValueError(f"Invalid JSON response: {e}")
        
        try:
            return schema(**data)
        except ValidationError as e:
            logger.error(f"Schema validation error: {e}")
            raise
```

- [ ] **Step 6: Update providers/__init__.py**

Create `backend/app/providers/__init__.py`:

```python
from .base_provider import BaseLLMProvider

__all__ = ['BaseLLMProvider']
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/providers/test_base_provider.py -v
```

Expected: PASS

- [ ] **Step 8: Commit provider base class**

```bash
cd /mnt/c/Dev/EstudoHub_4.0
git add backend/app/providers/ backend/tests/providers/
git commit -m "feat: create BaseLLMProvider abstract base class"
```

---

## Task 3: Implement OllamaProvider

**Files:**
- Create: `backend/app/providers/ollama_provider.py`
- Create: `backend/tests/providers/test_ollama_provider.py`

- [ ] **Step 1: Write tests for OllamaProvider**

Create `backend/tests/providers/test_ollama_provider.py`:

```python
import pytest
import asyncio
import json
from unittest.mock import patch, AsyncMock
from pydantic import BaseModel, ValidationError

from app.providers.ollama_provider import OllamaProvider
from app.core.config import settings


class TestSchema(BaseModel):
    name: str
    age: int


@pytest.mark.asyncio
async def test_ollama_provider_initialization():
    """OllamaProvider should initialize with correct defaults"""
    provider = OllamaProvider()
    assert provider.base_url == settings.ollama_url
    assert provider.model == "llama3:8b"
    assert provider.timeout == settings.ollama_timeout


@pytest.mark.asyncio
async def test_ollama_provider_successful_json_generation():
    """OllamaProvider should successfully generate and validate JSON"""
    provider = OllamaProvider()
    
    mock_response = '{"name": "John", "age": 30}'
    
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response_obj = AsyncMock()
        mock_response_obj.json.return_value = {"response": mock_response}
        mock_post.return_value.__aenter__.return_value = mock_response_obj
        
        result = await provider.generate_json(
            prompt="Generate a person",
            schema=TestSchema
        )
        
        assert result.name == "John"
        assert result.age == 30


@pytest.mark.asyncio
async def test_ollama_provider_connection_error():
    """OllamaProvider should raise ConnectionError when unavailable"""
    provider = OllamaProvider()
    
    with patch('aiohttp.ClientSession.post', side_effect=ConnectionError("Connection refused")):
        with pytest.raises(ConnectionError):
            await provider.generate_json(
                prompt="Test",
                schema=TestSchema
            )


@pytest.mark.asyncio
async def test_ollama_provider_invalid_json():
    """OllamaProvider should raise ValueError for invalid JSON"""
    provider = OllamaProvider()
    
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response_obj = AsyncMock()
        mock_response_obj.json.return_value = {"response": "not valid json {"]
        mock_post.return_value.__aenter__.return_value = mock_response_obj
        
        with pytest.raises(ValueError):
            await provider.generate_json(
                prompt="Test",
                schema=TestSchema
            )


@pytest.mark.asyncio
async def test_ollama_provider_schema_validation_error():
    """OllamaProvider should raise ValidationError for non-matching schema"""
    provider = OllamaProvider()
    
    # Response missing required 'age' field
    mock_response = '{"name": "John"}'
    
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response_obj = AsyncMock()
        mock_response_obj.json.return_value = {"response": mock_response}
        mock_post.return_value.__aenter__.return_value = mock_response_obj
        
        with pytest.raises(ValidationError):
            await provider.generate_json(
                prompt="Test",
                schema=TestSchema
            )


@pytest.mark.asyncio
async def test_ollama_provider_timeout():
    """OllamaProvider should raise TimeoutError on timeout"""
    provider = OllamaProvider(timeout=1)
    
    with patch('aiohttp.ClientSession.post', side_effect=asyncio.TimeoutError()):
        with pytest.raises(TimeoutError):
            await provider.generate_json(
                prompt="Test",
                schema=TestSchema
            )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/providers/test_ollama_provider.py -v
```

Expected: FAIL - `ModuleNotFoundError: No module named 'app.providers.ollama_provider'`

- [ ] **Step 3: Implement OllamaProvider**

Create `backend/app/providers/ollama_provider.py`:

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
    
    def __init__(self, base_url: str = None, model: str = "llama3:8b", timeout: int = None):
        self.base_url = base_url or settings.ollama_url
        self.model = model
        self.timeout = timeout or settings.ollama_timeout
        logger.info(f"OllamaProvider initialized: {self.base_url}, model={self.model}, timeout={self.timeout}s")
    
    async def generate_json(self, prompt: str, schema: Type[T]) -> T:
        """Generate JSON response from Ollama local model"""
        logger.info(f"OllamaProvider: Starting JSON generation for schema {schema.__name__}")
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False
        }
        
        url = f"{self.base_url}/api/generate"
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                logger.debug(f"Sending request to {url}")
                async with session.post(url, json=payload) as response:
                    data = await response.json()
                    response_text = data.get("response", "")
                    logger.info(f"OllamaProvider: Received response ({len(response_text)} chars)")
        
        except asyncio.TimeoutError:
            logger.error(f"OllamaProvider: Timeout after {self.timeout}s")
            raise TimeoutError(f"Ollama request timed out after {self.timeout}s")
        except aiohttp.ClientConnectorError as e:
            logger.error(f"OllamaProvider: Connection error - {e}")
            raise ConnectionError(f"Failed to connect to Ollama at {self.base_url}: {e}")
        except aiohttp.ClientError as e:
            logger.error(f"OllamaProvider: Request error - {e}")
            raise ConnectionError(f"Ollama request failed: {e}")
        
        # Validate response against schema
        try:
            result = self._validate_json_response(response_text, schema)
            logger.info(f"OllamaProvider: Successfully validated response for {schema.__name__}")
            return result
        except Exception as e:
            logger.error(f"OllamaProvider: Validation failed - {e}")
            raise
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/providers/test_ollama_provider.py -v
```

Expected: PASS (all tests pass)

- [ ] **Step 5: Commit OllamaProvider**

```bash
cd /mnt/c/Dev/EstudoHub_4.0
git add backend/app/providers/ollama_provider.py backend/tests/providers/test_ollama_provider.py
git commit -m "feat: implement OllamaProvider with JSON validation and error handling"
```

---

## Task 4: Implement GeminiProvider

**Files:**
- Create: `backend/app/providers/gemini_provider.py`
- Create: `backend/tests/providers/test_gemini_provider.py`

- [ ] **Step 1: Write tests for GeminiProvider**

Create `backend/tests/providers/test_gemini_provider.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from pydantic import BaseModel, ValidationError

from app.providers.gemini_provider import GeminiProvider
from app.core.config import settings


class TestSchema(BaseModel):
    title: str
    content: str


@pytest.mark.asyncio
async def test_gemini_provider_initialization():
    """GeminiProvider should initialize with correct defaults"""
    provider = GeminiProvider()
    assert provider.timeout == settings.gemini_timeout
    assert provider.model_name == "gemini-2.0-flash"


@pytest.mark.asyncio
async def test_gemini_provider_successful_json_generation():
    """GeminiProvider should successfully generate and validate JSON"""
    provider = GeminiProvider()
    
    mock_response_text = '{"title": "Test", "content": "Description"}'
    
    with patch('google.generativeai.GenerativeModel') as mock_model_class:
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = mock_response_text
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        provider.model = mock_model
        
        result = await provider.generate_json(
            prompt="Generate content",
            schema=TestSchema
        )
        
        assert result.title == "Test"
        assert result.content == "Description"


@pytest.mark.asyncio
async def test_gemini_provider_invalid_json():
    """GeminiProvider should raise ValueError for invalid JSON"""
    provider = GeminiProvider()
    
    with patch('google.generativeai.GenerativeModel') as mock_model_class:
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "not valid json {"
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        provider.model = mock_model
        
        with pytest.raises(ValueError):
            await provider.generate_json(
                prompt="Test",
                schema=TestSchema
            )


@pytest.mark.asyncio
async def test_gemini_provider_schema_validation_error():
    """GeminiProvider should raise ValidationError for non-matching schema"""
    provider = GeminiProvider()
    
    # Missing 'content' required field
    mock_response_text = '{"title": "Test"}'
    
    with patch('google.generativeai.GenerativeModel') as mock_model_class:
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = mock_response_text
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        provider.model = mock_model
        
        with pytest.raises(ValidationError):
            await provider.generate_json(
                prompt="Test",
                schema=TestSchema
            )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/providers/test_gemini_provider.py -v
```

Expected: FAIL - `ModuleNotFoundError: No module named 'app.providers.gemini_provider'`

- [ ] **Step 3: Implement GeminiProvider**

Create `backend/app/providers/gemini_provider.py`:

```python
import logging
import asyncio
from typing import Type, TypeVar
from pydantic import BaseModel
import google.generativeai as genai

from .base_provider import BaseLLMProvider
from app.core.config import settings

T = TypeVar('T', bound=BaseModel)
logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Cloud-based Google Gemini LLM provider"""
    
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.0-flash", timeout: int = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name
        self.timeout = timeout or settings.gemini_timeout
        
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(model_name)
        else:
            self.model = None
            logger.warning("GeminiProvider: No API key configured")
        
        logger.info(f"GeminiProvider initialized: model={self.model_name}, timeout={self.timeout}s")
    
    async def generate_json(self, prompt: str, schema: Type[T]) -> T:
        """Generate JSON response from Gemini"""
        logger.info(f"GeminiProvider: Starting JSON generation for schema {schema.__name__}")
        
        if not self.model:
            raise ConnectionError("GeminiProvider not configured - missing API key")
        
        try:
            # Gemini API is synchronous, run it in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.model.generate_content(prompt)
                ),
                timeout=self.timeout
            )
            
            response_text = response.text
            logger.info(f"GeminiProvider: Received response ({len(response_text)} chars)")
        
        except asyncio.TimeoutError:
            logger.error(f"GeminiProvider: Timeout after {self.timeout}s")
            raise TimeoutError(f"Gemini request timed out after {self.timeout}s")
        except Exception as e:
            logger.error(f"GeminiProvider: Request error - {e}")
            raise ConnectionError(f"Gemini request failed: {e}")
        
        # Validate response against schema
        try:
            result = self._validate_json_response(response_text, schema)
            logger.info(f"GeminiProvider: Successfully validated response for {schema.__name__}")
            return result
        except Exception as e:
            logger.error(f"GeminiProvider: Validation failed - {e}")
            raise
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/providers/test_gemini_provider.py -v
```

Expected: PASS (all tests pass)

- [ ] **Step 5: Commit GeminiProvider**

```bash
cd /mnt/c/Dev/EstudoHub_4.0
git add backend/app/providers/gemini_provider.py backend/tests/providers/test_gemini_provider.py
git commit -m "feat: implement GeminiProvider with async support and timeout handling"
```

---

## Task 5: Refactor AIService with Provider Orchestration

**Files:**
- Modify: `backend/app/services/ai_service.py`
- Create: `backend/tests/services/test_ai_service_orchestration.py`

- [ ] **Step 1: Write tests for AIService orchestration**

Create `backend/tests/services/test_ai_service_orchestration.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from pydantic import BaseModel

from app.services.ai_service import AIService
from app.core.config import settings
from app.schemas.edital_schema import EditalGeral, Cargo, Materia


@pytest.mark.asyncio
async def test_ai_service_local_first_success():
    """AIService should use Ollama first with local_first strategy"""
    service = AIService()
    
    mock_edital = EditalGeral(
        orgao="Test Org",
        banca="Test Bank",
        cargos=[
            Cargo(
                titulo="Test Position",
                vagas_ampla=5,
                vagas_cotas=2,
                salario=3000.0,
                requisitos="Test requirements",
                materias=[Materia(nome="Math", topicos=["Algebra"])]
            )
        ]
    )
    
    with patch.object(service.ollama_provider, 'generate_json', new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = mock_edital
        
        result = await service.extract_edital_data(md_content="Test content")
        
        assert result.orgao == "Test Org"
        mock_ollama.assert_called_once()


@pytest.mark.asyncio
async def test_ai_service_local_first_fallback_to_gemini():
    """AIService should fallback to Gemini when Ollama fails"""
    service = AIService()
    
    mock_edital = EditalGeral(
        orgao="Test Org",
        banca="Test Bank",
        cargos=[]
    )
    
    with patch.object(service.ollama_provider, 'generate_json', new_callable=AsyncMock) as mock_ollama, \
         patch.object(service.gemini_provider, 'generate_json', new_callable=AsyncMock) as mock_gemini:
        
        mock_ollama.side_effect = ConnectionError("Ollama unavailable")
        mock_gemini.return_value = mock_edital
        
        result = await service.extract_edital_data(md_content="Test content")
        
        assert result.orgao == "Test Org"
        mock_gemini.assert_called_once()


@pytest.mark.asyncio
async def test_ai_service_local_only_fails_without_fallback():
    """AIService should fail immediately with local_only strategy if Ollama unavailable"""
    with patch('app.services.ai_service.settings') as mock_settings:
        mock_settings.llm_strategy = "local_only"
        mock_settings.gemini_api_key = "test-key"
        mock_settings.ollama_url = "http://localhost:11434"
        mock_settings.cloud_fallback = True
        
        service = AIService()
        
        with patch.object(service.ollama_provider, 'generate_json', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.side_effect = ConnectionError("Ollama unavailable")
            
            with pytest.raises(ConnectionError):
                await service.extract_edital_data(md_content="Test content")
            
            mock_ollama.assert_called_once()


@pytest.mark.asyncio
async def test_ai_service_cloud_only_uses_gemini():
    """AIService should use only Gemini with cloud_only strategy"""
    with patch('app.services.ai_service.settings') as mock_settings:
        mock_settings.llm_strategy = "cloud_only"
        mock_settings.gemini_api_key = "test-key"
        mock_settings.ollama_url = "http://localhost:11434"
        
        service = AIService()
        
        mock_edital = EditalGeral(
            orgao="Cloud Org",
            banca="Cloud Bank",
            cargos=[]
        )
        
        with patch.object(service.gemini_provider, 'generate_json', new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = mock_edital
            
            result = await service.extract_edital_data(md_content="Test content")
            
            assert result.orgao == "Cloud Org"
            mock_gemini.assert_called_once()


@pytest.mark.asyncio
async def test_ai_service_all_providers_exhausted():
    """AIService should raise error when all providers fail"""
    service = AIService()
    
    with patch.object(service.ollama_provider, 'generate_json', new_callable=AsyncMock) as mock_ollama, \
         patch.object(service.gemini_provider, 'generate_json', new_callable=AsyncMock) as mock_gemini:
        
        mock_ollama.side_effect = ConnectionError("Ollama down")
        mock_gemini.side_effect = ConnectionError("Gemini down")
        
        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            await service.extract_edital_data(md_content="Test content")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/services/test_ai_service_orchestration.py -v
```

Expected: FAIL - `AttributeError: 'AIService' object has no attribute 'ollama_provider'`

- [ ] **Step 3: Refactor AIService with orchestration**

Replace `backend/app/services/ai_service.py`:

```python
import logging
from typing import Type, TypeVar, List
from pydantic import BaseModel

from app.core.config import settings
from app.providers.ollama_provider import OllamaProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.base_provider import BaseLLMProvider
from app.schemas.edital_schema import EditalGeral

T = TypeVar('T', bound=BaseModel)
logger = logging.getLogger(__name__)


class AIService:
    """Orchestrates LLM provider selection and failover strategy"""
    
    def __init__(self):
        self.ollama_provider = OllamaProvider()
        self.gemini_provider = GeminiProvider()
        self.strategy = settings.llm_strategy
        self.cloud_fallback = settings.cloud_fallback
        
        logger.info(f"AIService initialized with strategy={self.strategy}, cloud_fallback={self.cloud_fallback}")
    
    def _get_provider_chain(self) -> List[BaseLLMProvider]:
        """Build ordered list of providers based on strategy"""
        if self.strategy == "local_only":
            return [self.ollama_provider]
        elif self.strategy == "cloud_only":
            return [self.gemini_provider]
        elif self.strategy == "local_first":
            chain = [self.ollama_provider]
            if self.cloud_fallback:
                chain.append(self.gemini_provider)
            return chain
        else:
            logger.warning(f"Unknown strategy '{self.strategy}', defaulting to local_first")
            chain = [self.ollama_provider]
            if self.cloud_fallback:
                chain.append(self.gemini_provider)
            return chain
    
    async def extract_edital_data(self, md_content: str) -> EditalGeral:
        """Extract structured edital data from markdown content"""
        prompt = f'''
        Analise o edital abaixo e extraia os dados estruturados.
        Foque especialmente na separação por CARGOS. Cada cargo deve ter suas matérias e requisitos.
        Retorne APENAS o JSON puro seguindo este schema:
        {EditalGeral.model_json_schema()}

        EDITAL EM MARKDOWN:
        {md_content}
        '''
        
        providers = self._get_provider_chain()
        logger.info(f"extract_edital_data: Attempting with {len(providers)} provider(s): {[p.__class__.__name__ for p in providers]}")
        
        last_error = None
        for provider in providers:
            try:
                logger.info(f"extract_edital_data: Trying {provider.__class__.__name__}")
                result = await provider.generate_json(prompt=prompt, schema=EditalGeral)
                logger.info(f"extract_edital_data: ✓ Success with {provider.__class__.__name__}")
                return result
            
            except (ConnectionError, TimeoutError, ValueError) as e:
                last_error = e
                logger.warning(f"extract_edital_data: {provider.__class__.__name__} failed - {type(e).__name__}: {e}")
                continue
            except Exception as e:
                last_error = e
                logger.error(f"extract_edital_data: {provider.__class__.__name__} unexpected error - {e}")
                continue
        
        # All providers exhausted
        error_msg = f"All LLM providers failed. Last error: {last_error}"
        logger.error(f"extract_edital_data: ✗ {error_msg}")
        raise RuntimeError(error_msg)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/services/test_ai_service_orchestration.py -v
```

Expected: PASS (all tests pass)

- [ ] **Step 5: Run all provider tests to ensure nothing broke**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/providers/ tests/services/ -v
```

Expected: All tests pass

- [ ] **Step 6: Commit AIService refactor**

```bash
cd /mnt/c/Dev/EstudoHub_4.0
git add backend/app/services/ai_service.py backend/tests/services/test_ai_service_orchestration.py
git commit -m "feat: refactor AIService as provider orchestrator with failover strategy"
```

---

## Task 6: Update Environment Configuration

**Files:**
- Modify: `.env`
- Create/Modify: `.env.example`

- [ ] **Step 1: Check current .env file**

```bash
cat /mnt/c/Dev/EstudoHub_4.0/.env
```

- [ ] **Step 2: Add LLM configuration to .env**

Update or create `.env`:

```
# Existing
GEMINI_API_KEY=your-gemini-api-key-here
DEBUG=False

# New LLM Provider Configuration
USE_LOCAL_LLM=true
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_TIMEOUT=120
GEMINI_TIMEOUT=15
LLM_STRATEGY=local_first
CLOUD_FALLBACK=true
```

- [ ] **Step 3: Update .env.example**

Update or create `.env.example`:

```
# Existing
GEMINI_API_KEY=your-gemini-api-key-here
DEBUG=False

# New LLM Provider Configuration
# Options: local_first, local_only, cloud_only
LLM_STRATEGY=local_first
# Allow fallback to Gemini when local provider fails (only applies to local_first)
CLOUD_FALLBACK=true
# Ollama configuration
USE_LOCAL_LLM=true
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_TIMEOUT=120
# Gemini configuration
GEMINI_TIMEOUT=15
```

- [ ] **Step 4: Commit environment configuration**

```bash
cd /mnt/c/Dev/EstudoHub_4.0
git add .env .env.example
git commit -m "feat: add LLM provider environment configuration"
```

---

## Task 7: Update Docker Compose for Ollama Networking

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Read current docker-compose.yml**

```bash
cat /mnt/c/Dev/EstudoHub_4.0/docker-compose.yml
```

- [ ] **Step 2: Add extra_hosts to backend service**

Locate the `backend:` service and add `extra_hosts` section:

```yaml
backend:
  build:
    context: ./backend
    dockerfile: Dockerfile
  # ... existing config ...
  extra_hosts:
    - "host.docker.internal:host-gateway"
  # ... rest of service config ...
```

Full example (adapt to your structure):

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - USE_LOCAL_LLM=true
      - OLLAMA_URL=http://host.docker.internal:11434
      - LLM_STRATEGY=local_first
      - CLOUD_FALLBACK=true
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      - db
    volumes:
      - ./backend:/app

  # ... other services ...
```

- [ ] **Step 3: Verify docker-compose syntax**

```bash
docker-compose -f /mnt/c/Dev/EstudoHub_4.0/docker-compose.yml config
```

Expected: Valid YAML output, no errors

- [ ] **Step 4: Commit docker-compose updates**

```bash
cd /mnt/c/Dev/EstudoHub_4.0
git add docker-compose.yml
git commit -m "feat: add extra_hosts configuration for Ollama connectivity"
```

---

## Task 8: Configure Python Logging

**Files:**
- Create: `backend/app/logging_config.py`
- Modify: `backend/app/main.py` (or FastAPI app initialization)

- [ ] **Step 1: Create logging configuration**

Create `backend/app/logging_config.py`:

```python
import logging
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "default",
            "stream": "ext://sys.stdout"
        }
    },
    "loggers": {
        "app.providers": {
            "level": "INFO",
            "handlers": ["console"]
        },
        "app.services": {
            "level": "INFO",
            "handlers": ["console"]
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"]
    }
}


def setup_logging():
    """Initialize application logging"""
    logging.config.dictConfig(LOGGING_CONFIG)
```

- [ ] **Step 2: Find and update main.py/app initialization**

Locate your FastAPI app initialization file (usually `backend/app/main.py` or `backend/main.py`):

```bash
find /mnt/c/Dev/EstudoHub_4.0/backend -name "main.py" -o -name "app.py" | head -5
```

- [ ] **Step 3: Initialize logging in app startup**

Update app initialization (typically near the top of main.py):

```python
from app.logging_config import setup_logging

# Initialize logging before anything else
setup_logging()

# ... rest of imports and app setup ...
```

- [ ] **Step 4: Commit logging configuration**

```bash
cd /mnt/c/Dev/EstudoHub_4.0
git add backend/app/logging_config.py
git commit -m "feat: configure Python logging for provider operations"
```

---

## Task 9: Validate with Test PDF (trt.pdf)

**Files:**
- Create: `backend/tests/integration/test_edital_extraction_e2e.py`

- [ ] **Step 1: Check if trt.pdf exists**

```bash
find /mnt/c/Dev/EstudoHub_4.0 -name "trt.pdf" -type f
```

If not found, you'll need to place a test PDF file in the project.

- [ ] **Step 2: Write E2E test for edital extraction**

Create `backend/tests/integration/test_edital_extraction_e2e.py`:

```python
import pytest
import logging
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_extract_edital_from_pdf():
    """E2E test: Extract edital from trt.pdf using local Llama 3"""
    # Note: This test requires:
    # 1. Ollama running locally at http://localhost:11434
    # 2. llama3:8b model downloaded
    # 3. trt.pdf existing in test fixtures
    
    service = AIService()
    
    # Read sample markdown content (simulating PDF extraction)
    with open("tests/fixtures/trt_sample.md", "r", encoding="utf-8") as f:
        md_content = f.read()
    
    logger.info("Starting E2E edital extraction with local Llama 3")
    
    result = await service.extract_edital_data(md_content=md_content)
    
    # Assertions
    assert result.orgao is not None, "Orgao (organization) should be extracted"
    assert result.banca is not None, "Banca (exam board) should be extracted"
    assert len(result.cargos) > 0, "At least one cargo (position) should be extracted"
    
    for cargo in result.cargos:
        assert cargo.titulo, f"Cargo titulo should not be empty"
        assert cargo.vagas_ampla >= 0, f"Vagas ampla should be non-negative"
        assert len(cargo.materias) > 0, f"Cargo should have at least one materia"
    
    logger.info(f"✓ Successfully extracted edital with {len(result.cargos)} cargos")
    logger.info(f"Extracted organization: {result.orgao}")
    logger.info(f"Exam board: {result.banca}")
```

- [ ] **Step 3: Create test fixture directory and sample**

```bash
mkdir -p /mnt/c/Dev/EstudoHub_4.0/backend/tests/fixtures
mkdir -p /mnt/c/Dev/EstudoHub_4.0/backend/tests/integration
touch /mnt/c/Dev/EstudoHub_4.0/backend/tests/integration/__init__.py
```

- [ ] **Step 4: Create sample markdown fixture**

Create `backend/tests/fixtures/trt_sample.md`:

```markdown
# EDITAL DE CONCURSO PÚBLICO

## Órgão Responsável
Tribunal Regional do Trabalho

## Banca Examinadora
CESPE/CEBRASPE

## Período de Inscrição
01 de janeiro a 31 de janeiro de 2024

## Data da Prova
15 de março de 2024

## CARGOS

### Analista Judiciário - Especialidade: Direito

**Vagas para Ampla Concorrência:** 10  
**Vagas para Cotas (PcD):** 2  
**Salário:** R$ 8.000,00

**Requisitos:**
- Bacharelado em Direito
- Registro na OAB

**Matérias:**

1. **Direito Constitucional**
   - Tópicos: Princípios constitucionais, Direitos fundamentais, Poder judiciário

2. **Direito Trabalhista**
   - Tópicos: CLT, Contratos de trabalho, Rescisão contratual

### Técnico Judiciário - Especialidade: Administrativa

**Vagas para Ampla Concorrência:** 5  
**Vagas para Cotas (PcD):** 1  
**Salário:** R$ 3.500,00

**Requisitos:**
- Ensino Médio Completo

**Matérias:**

1. **Administração Pública**
   - Tópicos: Princípios administrativos, Processo administrativo

2. **Português**
   - Tópicos: Interpretação de texto, Gramática, Redação
```

- [ ] **Step 5: Run unit/integration tests**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
# Run all unit tests first
python -m pytest tests/providers/ tests/services/ -v

# Run integration test (requires Ollama running)
# python -m pytest tests/integration/test_edital_extraction_e2e.py -v -s
```

- [ ] **Step 6: Manual validation with Ollama**

Before running the E2E test, ensure Ollama is running:

```bash
# In WSL, start Ollama if not already running
ollama serve

# In another terminal, verify model is available
ollama list
# Should show: llama3:8b
```

Then run the E2E test:

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/integration/test_edital_extraction_e2e.py -v -s
```

Expected output:
```
[INFO] OllamaProvider initialized: http://localhost:11434, model=llama3:8b, timeout=120s
[INFO] AIService initialized with strategy=local_first, cloud_fallback=True
[INFO] extract_edital_data: Attempting with 1 provider(s): ['OllamaProvider']
[INFO] OllamaProvider: Starting JSON generation for schema EditalGeral
[INFO] OllamaProvider: Received response (...) 
[INFO] OllamaProvider: Successfully validated response for EditalGeral
[INFO] extract_edital_data: ✓ Success with OllamaProvider
PASSED
```

- [ ] **Step 7: Commit integration test**

```bash
cd /mnt/c/Dev/EstudoHub_4.0
git add backend/tests/integration/ backend/tests/fixtures/
git commit -m "test: add E2E integration test for edital extraction with Ollama"
```

---

## Task 10: Verify All Tests Pass and Create Summary

**Files:**
- No new files

- [ ] **Step 1: Run complete test suite**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -m pytest tests/ -v --tb=short
```

Expected: All tests pass (except integration test if Ollama not running)

- [ ] **Step 2: Verify no import errors**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -c "from app.services.ai_service import AIService; from app.providers.ollama_provider import OllamaProvider; from app.providers.gemini_provider import GeminiProvider; print('✓ All imports successful')"
```

Expected: `✓ All imports successful`

- [ ] **Step 3: Check logging works**

```bash
cd /mnt/c/Dev/EstudoHub_4.0/backend
python -c "
import logging
from app.logging_config import setup_logging
setup_logging()
logger = logging.getLogger('app.providers')
logger.info('✓ Logging initialized successfully')
"
```

Expected: Log message appears on stdout

- [ ] **Step 4: Final verification summary**

Create a checklist of what was implemented:

```
✓ BaseLLMProvider abstract base class
✓ OllamaProvider with local llama3:8b support
✓ GeminiProvider wrapping Gemini API
✓ AIService as orchestrator with strategy routing
✓ Config support for LLM_STRATEGY (local_first, local_only, cloud_only)
✓ Per-provider timeout configuration
✓ Failover logic with CLOUD_FALLBACK
✓ Standard Python logging to stdout
✓ Docker networking configuration (host.docker.internal)
✓ Environment configuration
✓ Comprehensive unit tests
✓ E2E integration test with sample edital
```

- [ ] **Step 5: Final commit**

```bash
cd /mnt/c/Dev/EstudoHub_4.0
git log --oneline -10  # View recent commits
git status  # Should be clean
```

---

## Summary

This plan implements a production-ready LLM provider architecture with:

1. **Provider Abstraction:** BaseLLMProvider interface allows multiple LLM backends
2. **Flexible Strategies:** Three routing strategies (local_first, local_only, cloud_only)
3. **Intelligent Failover:** Automatic fallback from Ollama to Gemini with clear logging
4. **Per-Provider Tuning:** Separate timeouts and configuration for each provider
5. **Observability:** Standard Python logging showing which provider executed each task
6. **Extensibility:** Adding new tasks or providers requires minimal changes
7. **Docker Ready:** Networking configured for both local and cloud providers
8. **Well-Tested:** Unit and integration tests covering all scenarios

**Next Steps After Implementation:**
1. Run full test suite
2. Test with actual trt.pdf (ensure it's converted to markdown first)
3. Monitor logs in Docker to verify provider selection
4. Adjust timeouts based on observed performance
5. Consider adding metrics/tracing for provider performance analysis
