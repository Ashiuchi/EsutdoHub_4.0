"""
AI Provider Check-up — EstudoHub 4.0
Testa cada provider com extração simples de um cargo a partir do edital do BB.
Run inside backend container: python /app/scripts/checkup_ia.py
"""
import asyncio
import time
import sys
import os

sys.path.insert(0, "/app")
os.chdir("/app")

from pydantic import BaseModel
from typing import Optional, List


class CargoSimples(BaseModel):
    nome: str
    vagas: Optional[str] = None
    salario: Optional[str] = None


class ResultadoSimples(BaseModel):
    cargos: List[CargoSimples]


BB_HASH = "1931b0c36c121d802b7ad146978b130b62dde53aab89a9d18963ee5dad0648d0"
STORAGE_PATH = f"/app/storage/processed/{BB_HASH}/main.md"

PROMPT_TEMPLATE = """Você é um extrator de dados de editais de concurso público.

Abaixo está o início do edital do Banco do Brasil. Extraia APENAS 1 (um) cargo com suas informações básicas.

Responda EXCLUSIVAMENTE em JSON válido, no formato:
{{
  "cargos": [
    {{
      "nome": "nome do cargo",
      "vagas": "número ou descrição de vagas",
      "salario": "valor do salário como texto"
    }}
  ]
}}

EDITAL (primeiros 3000 chars):
{conteudo}
"""


async def testar_provider(nome, provider, prompt, timeout_override=None):
    print(f"\n{'='*55}")
    print(f"  PROVIDER: {nome}")
    print(f"{'='*55}")
    inicio = time.time()
    try:
        if timeout_override:
            provider.timeout = timeout_override
        resultado = await provider.generate_json(prompt, ResultadoSimples)
        elapsed = time.time() - inicio
        print(f"  Status : SUCESSO ✓")
        print(f"  Tempo  : {elapsed:.2f}s")
        print(f"  JSON   : {resultado.model_dump_json(indent=2)}")
    except Exception as e:
        elapsed = time.time() - inicio
        print(f"  Status : ERRO ✗")
        print(f"  Tempo  : {elapsed:.2f}s")
        print(f"  Erro   : {type(e).__name__}: {str(e)[:200]}")


async def main():
    print("\n" + "="*55)
    print("  EstudoHub AI Provider Check-up")
    print("  Edital: Banco do Brasil (BB)")
    print("="*55)

    if not os.path.exists(STORAGE_PATH):
        print(f"ERRO: main.md não encontrado em {STORAGE_PATH}")
        sys.exit(1)

    with open(STORAGE_PATH, "r") as f:
        conteudo = f.read()[:3000]

    prompt = PROMPT_TEMPLATE.format(conteudo=conteudo)
    print(f"\nPrompt: {len(prompt)} chars | Conteúdo: {len(conteudo)} chars")

    from app.providers.ollama_provider import OllamaProvider
    from app.providers.groq_provider import GroqProvider
    from app.providers.gemini_provider import GeminiProvider
    from app.providers.openrouter_provider import OpenRouterProvider

    # Ollama primeiro — primário local
    print("\n>>> Testando Ollama (primário local, timeout=180s)...")
    await testar_provider("Ollama", OllamaProvider(timeout=180), prompt)

    # Cloud providers
    for nome, provider in [
        ("Groq",            GroqProvider()),
        ("OpenRouter",      OpenRouterProvider()),
        ("Gemini 2.5-pro",  GeminiProvider()),
    ]:
        await testar_provider(nome, provider, prompt)

    print("\n" + "="*55)
    print("  Check-up concluído.")
    print("="*55 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
