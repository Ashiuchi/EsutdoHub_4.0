import os
import re
import logging
import pandas as pd
import io
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.providers.base_provider import BaseLLMProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.gemini_provider import GeminiProvider
from app.core.config import settings
from app.schemas.edital_schema import Cargo, EditalGeral, CargoIdentificado
from app.core.logging_streamer import log_streamer

logger = logging.getLogger(__name__)

class MappingDiscovery(BaseModel):
    acronyms: Dict[str, str]  # Ex: {"AC": "vagas_ac", "PcD": "vagas_pcd"}
    regions: Dict[str, str]   # Ex: {"158": "Agente de Tecnologia"}
    headers: List[str]        # Colunas candidatas a conter nomes de cargos

class GlobalMetadata(BaseModel):
    edital_info: EditalGeral
    salary_patterns: List[str]

class VitaminData(BaseModel):
    edital_info: EditalGeral
    cargos_vitaminados: List[Cargo]

class CargoVitaminizerAgent:
    def __init__(self):
        # Semáforo para limitar concorrência no LLM local e não travar a GPU
        self.semaphore = asyncio.Semaphore(3)

    async def _discover_structure(self, main_md: str, tables: List[str], chain: List[BaseLLMProvider]) -> MappingDiscovery:
        """Usa IA para descobrir o significado de legendas, siglas e códigos regionais."""
        async with self.semaphore:
            log_streamer.broadcast({"type": "log", "message": "🔍 Analisando legendas e estruturas dinâmicas...", "level": "INFO"})
            
            headers_sample = [t.splitlines()[0] for t in tables[:15] if "|" in t]
            
            prompt = f"""
            Analise o texto e os cabeçalhos das tabelas de um edital.
            Identifique o significado de siglas de vagas e mapeamentos de códigos/regiões para cargos.

            TEXTO (FRAGMENTO):
            {main_md[:5000]}

            CABEÇALHOS DE TABELAS:
            {headers_sample}

            Retorne um JSON:
            {{
                "acronyms": {{ "SIGLA": "campo_pydantic" }},
                "regions": {{ "CÓDIGO": "NOME DO CARGO" }},
                "headers": ["Nomes de colunas de cargo"]
            }}

            CAMPOS VÁLIDOS: vagas_ac, vagas_pcd, vagas_negros, vagas_indigenas, vagas_trans, vagas_cr, vagas_total.
            """
            
            for provider in chain:
                try:
                    mapping = await provider.generate_json(prompt=prompt, schema=MappingDiscovery)
                    for sigla, campo in mapping.acronyms.items():
                        log_streamer.broadcast({"type": "log", "message": f"📌 Legenda descoberta: {sigla} -> {campo}", "level": "INFO"})
                    for cod, cargo in mapping.regions.items():
                        log_streamer.broadcast({"type": "log", "message": f"📌 Mapeamento descoberto: {cod} -> {cargo}", "level": "INFO"})
                    return mapping
                except Exception as e:
                    logger.warning(f"⚠️ {provider.__class__.__name__} falhou em _discover_structure: {e}")
                    continue

            logger.error("Todos os providers falharam em _discover_structure.")
            return MappingDiscovery(acronyms={}, regions={}, headers=[])

    def _process_single_table(self, table_md: str, discovery: MappingDiscovery, identified_cargos: List[CargoIdentificado], cargo_totals: Dict[str, Dict[str, int]]):
        """Processa uma única tabela e acumula no dicionário global de totais."""
        try:
            lines = [l.strip() for l in table_md.splitlines() if "|" in l]
            if len(lines) < 3: return
            clean_lines = [lines[0]] + [l for l in lines[1:] if not all(c in "|- : \t" for c in l)]
            df = pd.read_csv(io.StringIO("\n".join(clean_lines)), sep="|").loc[:, ~pd.Series([True]*0)]
            df.columns = [c.strip() for c in df.columns]
            
            for _, row in df.iterrows():
                row_str = " ".join(str(v) for v in row.values)
                target_cargo = None
                for code, name in discovery.regions.items():
                    if code in row_str:
                        target_cargo = next((c.titulo for c in identified_cargos if name.lower() in c.titulo.lower()), None)
                        break
                if not target_cargo:
                    for c in identified_cargos:
                        if c.titulo.lower() in row_str.lower():
                            target_cargo = c.titulo
                            break
                
                if target_cargo and target_cargo in cargo_totals:
                    for sigla, field in discovery.acronyms.items():
                        for col in df.columns:
                            if sigla.lower() == col.lower():
                                val = str(row[col]).strip()
                                nums = re.findall(r"\d+", val)
                                if nums: cargo_totals[target_cargo][field] += int(nums[0])
        except Exception as e:
            logger.warning(f"Erro ao processar tabela: {e}")

    def _aggregate_vacancies(self, tables: List[str], discovery: MappingDiscovery, identified_cargos: List[CargoIdentificado]) -> Dict[str, Dict[str, int]]:
        """Soma as vagas usando o mapeamento descoberto (Soma Determinística)."""
        cargo_totals = {c.titulo: {f: 0 for f in ["vagas_ac", "vagas_pcd", "vagas_negros", "vagas_indigenas", "vagas_trans", "vagas_cr", "vagas_total"]} for c in identified_cargos}
        
        # Como o processamento das tabelas é síncrono (Pandas/Regex), não usamos gather aqui para evitar GIL contention
        # Mas mantemos a estrutura para possível paralelização em threads se necessário.
        for table_md in tables:
            self._process_single_table(table_md, discovery, identified_cargos, cargo_totals)
            
        return cargo_totals

    async def _extract_global_metadata(self, main_md: str, chain: List[BaseLLMProvider]) -> GlobalMetadata:
        async with self.semaphore:
            prompt = f"Extraia metadados globais do edital em JSON (EditalGeral + salary_patterns como lista de strings).\nTEXTO: {main_md[:5000]}"
            
            for provider in chain:
                try:
                    return await provider.generate_json(prompt=prompt, schema=GlobalMetadata)
                except Exception as e:
                    logger.warning(f"⚠️ {provider.__class__.__name__} falhou em _extract_global_metadata: {e}")
                    continue

            logger.error("Todos os providers falharam em _extract_global_metadata.")
            # Graceful degradation: retorna objeto vazio mas válido
            return GlobalMetadata(
                edital_info=EditalGeral(orgao="Pendente", banca="Pendente"), 
                salary_patterns=[]
            )

    async def vitaminize(self, content_hash: str, identified_cargos: List[CargoIdentificado], chain: List[BaseLLMProvider]) -> VitaminData:
        storage_path = None
        for candidate in [
            Path("backend/storage/processed") / content_hash,
            Path("storage/processed") / content_hash,
            Path("/app/storage/processed") / content_hash,
        ]:
            if candidate.exists():
                storage_path = candidate
                break
        
        if not storage_path:
            logger.error(f"CargoVitaminizerAgent: Storage não encontrado para {content_hash}")
            return VitaminData(
                edital_info=EditalGeral(orgao="Pendente", banca="Pendente"),
                cargos_vitaminados=[Cargo(titulo=c.titulo, status="error") for c in identified_cargos]
            )
            
        main_md = (storage_path / "main.md").read_text(encoding="utf-8") if (storage_path / "main.md").exists() else ""
        table_files = sorted((storage_path / "tables").glob("*.md")) if (storage_path / "tables").exists() else []
        tables = [f.read_text(encoding="utf-8") for f in table_files]

        log_streamer.broadcast({"type": "log", "message": "📡 Iniciando Vitaminização V3.1 (Agnóstica)...", "level": "INFO"})

        # Filtro de Ruído: Ignorar termos comuns que não são cargos
        ruido = ["jurado", "redator", "espectro", "deficiência", "negros", "total", "nenhum", "cargo", "área"]
        identified_cargos = [c for c in identified_cargos if not any(r in c.titulo.lower() for r in ruido)]

        discovery = await self._discover_structure(main_md, tables, chain)
        vagas_agregadas = self._aggregate_vacancies(tables, discovery, identified_cargos)
        metadata = await self._extract_global_metadata(main_md, chain)

        cargos_finais = []
        for cargo_id in identified_cargos:
            v_data = vagas_agregadas.get(cargo_id.titulo, {})
            sal_str = metadata.salary_patterns[0] if metadata.salary_patterns else "0"
            salario = float(re.sub(r"[^\d.]", "", sal_str.replace(".", "").replace(",", "."))) if sal_str else 0.0

            cargo_vitaminado = Cargo(
                titulo=cargo_id.titulo,
                vagas_ac=str(v_data.get("vagas_ac", 0)),
                vagas_pcd=str(v_data.get("vagas_pcd", 0)),
                vagas_cr=str(v_data.get("vagas_cr", 0)),
                vagas_negros=str(v_data.get("vagas_negros", 0)),
                vagas_total=str(v_data.get("vagas_total", 0) or sum(v for k, v in v_data.items() if "total" not in k)),
                salario=salario,
                status="vitaminado"
            )
            cargos_finais.append(cargo_vitaminado)
            
            # Streaming do Cargo individual para o Cockpit
            log_streamer.broadcast({
                "type": "data",
                "payload": cargo_vitaminado.model_dump()
            })
            log_streamer.broadcast({
                "type": "log", 
                "message": f"✅ Cargo vitaminado: {cargo_vitaminado.titulo} ({cargo_vitaminado.vagas_total} vagas)", 
                "level": "INFO"
            })

        return VitaminData(edital_info=metadata.edital_info, cargos_vitaminados=cargos_finais)
