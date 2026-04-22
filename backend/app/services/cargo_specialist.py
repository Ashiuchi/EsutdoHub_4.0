import os
import re
import json
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
import io
from pydantic import BaseModel

from app.providers.ollama_provider import OllamaProvider
from app.providers.gemini_provider import GeminiProvider
from app.core.config import settings
from app.schemas.edital_schema import CargoIdentificado
from app.core.logging_streamer import log_streamer

logger = logging.getLogger(__name__)

class CargoTitleAgent:
    def __init__(self):
        self.ollama_provider = OllamaProvider()
        self.gemini_provider = GeminiProvider()
        # Semáforo para limitar concorrência no LLM local
        self.semaphore = asyncio.Semaphore(3)
        # Anchors for regex
        self.anchors = [
            r"Cód\.", r"Cargo", r"Função", r"Vagas", r"AC/PCD", 
            r"Nível Superior", r"Nível Médio", r"Especialidade", r"Jornada"
        ]
        self.anchor_re = re.compile("|".join(self.anchors), re.IGNORECASE)

    def _identify_relevant_chunks(self, md_content: str) -> List[str]:
        """Divide o 'main.md' em janelas e pontua pela densidade de âncoras."""
        window_size = 3000
        overlap = 500
        chunks = []
        
        # Sliding window
        if len(md_content) <= window_size:
            chunks = [md_content]
        else:
            for i in range(0, len(md_content), window_size - overlap):
                chunk = md_content[i:i + window_size]
                chunks.append(chunk)
                if i + window_size >= len(md_content):
                    break
            
        scored_chunks = []
        for chunk in chunks:
            # Score based on anchors
            score = len(self.anchor_re.findall(chunk))
            # Bonus score for other keywords
            score += chunk.lower().count("vagas") * 0.5
            score += chunk.lower().count("jornada") * 0.5
            score += chunk.lower().count("remuneração") * 0.5
            scored_chunks.append((score, chunk))
            
        # Sort by score and take top 3
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        # Only return chunks with some relevance
        return [chunk for score, chunk in scored_chunks[:3] if score > 0]

    async def hunt_titles(self, content_hash: str) -> List[CargoIdentificado]:
        """Identifica todos os títulos e códigos de cargos como instâncias únicas."""
        storage_path = Path("storage/processed") / content_hash
        tables_dir = storage_path / "tables"
        main_md_path = storage_path / "main.md"
        
        all_cargos: Dict[str, CargoIdentificado] = {}

        def _add_cargo(cargo: CargoIdentificado):
            key = f"{cargo.codigo_edital}_{cargo.titulo}" if cargo.codigo_edital else cargo.titulo
            if key not in all_cargos:
                all_cargos[key] = cargo
                # Streaming do Cargo identificado (parcial) para o Cockpit
                log_streamer.broadcast({
                    "type": "data",
                    "payload": {
                        "titulo": cargo.titulo,
                        "codigo_edital": cargo.codigo_edital,
                        "status": "identificado",
                        "vagas_ac": 0, "vagas_cr": 0, "vagas_total": 0, "salario": 0, "materias": []
                    }
                })

        # Radar de Relevância no main.md
        if main_md_path.exists():
            main_content = main_md_path.read_text(encoding="utf-8")
            log_streamer.broadcast({"type": "log", "message": "📡 CargoTitleAgent: Ativando Radar de Relevância no texto principal...", "level": "INFO"})
            relevant_chunks = self._identify_relevant_chunks(main_content)
            
            async def _process_chunk(chunk: str, idx: int):
                log_streamer.broadcast({"type": "log", "message": f"🔍 Analisando Bloco Relevante {idx+1}/{len(relevant_chunks)}...", "level": "INFO"})
                found_cargos = await self._deep_scan(chunk)
                for cargo in found_cargos:
                    _add_cargo(cargo)

            # Processamento em paralelo dos blocos do main.md
            if relevant_chunks:
                await asyncio.gather(*[_process_chunk(c, i) for i, c in enumerate(relevant_chunks)])

        # Análise de tabelas
        if tables_dir.exists():
            table_files = sorted(list(tables_dir.glob("*.md")))
            log_streamer.broadcast({"type": "log", "message": f"🔍 CargoTitleAgent: Analisando {len(table_files)} tabelas...", "level": "INFO"})

            async def _process_table_file(table_file: Path):
                table_content = table_file.read_text(encoding="utf-8")
                
                # Sprint Scan: Busca âncoras
                found_cargos = []
                if self.anchor_re.search(table_content):
                    logger.info(f"Sprint Scan: Âncoras encontradas em {table_file.name}. Tentando extração heurística.")
                    found_cargos = self._sprint_scan(table_content)
                    
                    if not found_cargos:
                        logger.info(f"Sprint Scan inconclusivo em {table_file.name}. Acionando Deep Scan (IA).")
                        found_cargos = await self._deep_scan(table_content)
                else:
                    if any(kw in table_content.lower() for kw in ["vagas", "remuneração", "vencimento", "salário"]):
                        logger.info(f"Tabela {table_file.name} sem âncoras claras mas relevante. Acionando Deep Scan (IA).")
                        found_cargos = await self._deep_scan(table_content)
                
                for cargo in found_cargos:
                    _add_cargo(cargo)

            # Processamento em paralelo de todas as tabelas (respeitando o semáforo dentro do _deep_scan)
            if table_files:
                await asyncio.gather(*[_process_table_file(f) for f in table_files])
        else:
            logger.warning(f"Diretório de tabelas não encontrado: {tables_dir}")
        
        result_list = list(all_cargos.values())
        log_streamer.broadcast({"type": "log", "message": f"✅ CargoTitleAgent: {len(result_list)} cargos identificados.", "level": "INFO"})
        return result_list

    def _sprint_scan(self, table_content: str) -> List[CargoIdentificado]:
        """Extração baseada em heurísticas e Regex para tabelas bem formatadas."""
        try:
            # Converter markdown table para DataFrame simplificado
            lines = [l.strip() for l in table_content.strip().splitlines() if l.strip()]
            if len(lines) < 3:
                return []

            # Limpar separadores do markdown
            content_lines = [l for l in lines if not all(c in '|- : \t' for c in l)]
            
            df = pd.read_csv(
                io.StringIO('\n'.join(content_lines)),
                sep='|',
                skipinitialspace=True
            ).loc[:, ~pd.Series([True]*0)] # Placeholder para limpeza de colunas Unnamed
            
            # Limpar colunas Unnamed
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            df.columns = [c.strip() for c in df.columns]
            
            # Identificar colunas de interesse
            col_cargo = None
            col_codigo = None
            
            for col in df.columns:
                col_lower = col.lower()
                if any(x in col_lower for x in ["cargo", "função", "denominação"]):
                    col_cargo = col
                if any(x in col_lower for x in ["cód", "codigo", "item"]):
                    col_codigo = col
            
            if not col_cargo:
                return []
                
            cargos = []
            for _, row in df.iterrows():
                titulo = str(row[col_cargo]).strip()
                if not titulo or titulo.lower() in ["nan", "None", ""]:
                    continue
                
                codigo = str(row[col_codigo]).strip() if col_codigo else None
                if codigo and codigo.lower() in ["nan", "None", ""]:
                    codigo = None
                    
                cargos.append(CargoIdentificado(titulo=titulo, codigo_edital=codigo))
            
            return cargos
        except Exception as e:
            logger.warning(f"Sprint Scan falhou: {e}")
            return []

    async def _deep_scan(self, fragment: str) -> List[CargoIdentificado]:
        """Usa IA para extrair cargos de fragmentos complexos ou mal formatados."""
        async with self.semaphore:
            prompt = f"""
            Analise o fragmento abaixo extraído de um edital de concurso.
            Identifique e extraia TODOS os cargos e seus respectivos códigos (se houver).
            
            REGRAS CRÍTICAS:
            1. Combine cargo e especialidade no título (ex: "Cargo - Área").
            2. Extraia o código se disponível.
            3. Retorne APENAS um JSON: {{"cargos": [{{"titulo": "NOME DO CARGO", "codigo_edital": "CÓDIGO"}}, ...]}}

            FRAGMENTO:
            {fragment}
            """
            
            providers = [self.ollama_provider, self.gemini_provider]
            if settings.llm_strategy == "cloud_only":
                providers = [self.gemini_provider]
            elif settings.llm_strategy == "local_only":
                providers = [self.ollama_provider]

            for provider in providers:
                try:
                    class CargoList(BaseModel):
                        cargos: List[CargoIdentificado]

                    result: CargoList = await provider.generate_json(prompt=prompt, schema=CargoList)
                    return result.cargos
                except Exception as e:
                    logger.error(f"Deep Scan falhou com {provider.__class__.__name__}: {e}")
                    continue
            
            return []
