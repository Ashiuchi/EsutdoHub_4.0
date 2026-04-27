import re
import logging
import asyncio
from pathlib import Path
from typing import List, Dict

import pandas as pd
import io
from pydantic import BaseModel

from app.providers.base_provider import BaseLLMProvider
from app.schemas.edital_schema import CargoIdentificado
from app.core.logging_streamer import log_streamer

logger = logging.getLogger(__name__)


class CargoTitleAgent:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(3)
        self.anchors = [
            r"Cód\.", r"Cargo", r"Função", r"Vagas", r"AC/PCD",
            r"Nível Superior", r"Nível Médio", r"Especialidade", r"Jornada"
        ]
        self.anchor_re = re.compile("|".join(self.anchors), re.IGNORECASE)

    def _identify_relevant_chunks(self, md_content: str) -> List[str]:
        window_size = 3000
        overlap = 500
        chunks = []

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
            score = len(self.anchor_re.findall(chunk))
            score += chunk.lower().count("vagas") * 0.5
            score += chunk.lower().count("jornada") * 0.5
            score += chunk.lower().count("remuneração") * 0.5
            scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for score, chunk in scored_chunks[:3] if score > 0]

    async def hunt_titles(self, content_hash: str, chain: List[BaseLLMProvider]) -> List[CargoIdentificado]:
        """Identifica todos os títulos e códigos de cargos como instâncias únicas."""
        storage_path = Path("backend/storage/processed") / content_hash
        if not storage_path.exists():
            storage_path = Path("storage/processed") / content_hash
        
        tables_dir = storage_path / "tables"
        main_md_path = storage_path / "main.md"

        all_cargos: Dict[str, CargoIdentificado] = {}

        def _add_cargo(cargo: CargoIdentificado):
            key = f"{cargo.codigo_edital}_{cargo.titulo}" if cargo.codigo_edital else cargo.titulo
            if key not in all_cargos:
                all_cargos[key] = cargo
                log_streamer.broadcast({
                    "type": "data",
                    "payload": {
                        "titulo": cargo.titulo,
                        "codigo_edital": cargo.codigo_edital,
                        "status": "identificado",
                        "vagas_ac": 0, "vagas_cr": 0, "vagas_total": 0, "salario": 0, "materias": []
                    }
                })

        if main_md_path.exists():
            main_content = main_md_path.read_text(encoding="utf-8")
            log_streamer.broadcast({"type": "log", "message": "📡 CargoTitleAgent: Ativando Radar de Relevância no texto principal...", "level": "INFO"})
            relevant_chunks = self._identify_relevant_chunks(main_content)

            async def _process_chunk(chunk: str, idx: int):
                log_streamer.broadcast({"type": "log", "message": f"🔍 Analisando Bloco Relevante {idx+1}/{len(relevant_chunks)}...", "level": "INFO"})
                found_cargos = await self._deep_scan(chunk, chain)
                for cargo in found_cargos:
                    _add_cargo(cargo)

            if relevant_chunks:
                await asyncio.gather(*[_process_chunk(c, i) for i, c in enumerate(relevant_chunks)])

        if tables_dir.exists():
            table_files = sorted(list(tables_dir.glob("*.md")))
            log_streamer.broadcast({"type": "log", "message": f"🔍 CargoTitleAgent: Analisando {len(table_files)} tabelas...", "level": "INFO"})

            async def _process_table_file(table_file: Path):
                table_content = table_file.read_text(encoding="utf-8")
                found_cargos = []
                if self.anchor_re.search(table_content):
                    logger.info("Sprint Scan: Âncoras encontradas em %s.", table_file.name)
                    found_cargos = self._sprint_scan(table_content)
                    if not found_cargos:
                        logger.info("Sprint Scan inconclusivo em %s. Acionando Deep Scan.", table_file.name)
                        found_cargos = await self._deep_scan(table_content, chain)
                else:
                    if any(kw in table_content.lower() for kw in ["vagas", "remuneração", "vencimento", "salário"]):
                        logger.info("Tabela %s sem âncoras claras mas relevante. Deep Scan.", table_file.name)
                        found_cargos = await self._deep_scan(table_content, chain)
                for cargo in found_cargos:
                    _add_cargo(cargo)

            if table_files:
                await asyncio.gather(*[_process_table_file(f) for f in table_files])
        else:
            logger.warning("Diretório de tabelas não encontrado: %s", tables_dir)

        result_list = list(all_cargos.values())
        log_streamer.broadcast({"type": "log", "message": f"✅ CargoTitleAgent: {len(result_list)} cargos identificados.", "level": "INFO"})
        return result_list

    def _sprint_scan(self, table_content: str) -> List[CargoIdentificado]:
        try:
            lines = [l.strip() for l in table_content.strip().splitlines() if l.strip()]
            if len(lines) < 3:
                return []
            content_lines = [l for l in lines if not all(c in '|- : \t' for c in l)]
            df = pd.read_csv(
                io.StringIO('\n'.join(content_lines)),
                sep='|',
                skipinitialspace=True
            ).loc[:, ~pd.Series([True]*0)]
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            df.columns = [c.strip() for c in df.columns]

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
                if not titulo or titulo.lower() in ["nan", "none", ""]:
                    continue
                codigo = str(row[col_codigo]).strip() if col_codigo else None
                if codigo and codigo.lower() in ["nan", "none", ""]:
                    codigo = None
                cargos.append(CargoIdentificado(titulo=titulo, codigo_edital=codigo))
            return cargos
        except Exception as e:
            logger.warning("Sprint Scan falhou: %s", e)
            return []

    async def _deep_scan(self, fragment: str, chain: List[BaseLLMProvider]) -> List[CargoIdentificado]:
        """Usa a chain de providers para extrair cargos de fragmentos complexos."""
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

            class CargoList(BaseModel):
                cargos: List[CargoIdentificado]

            for provider in chain:
                try:
                    result: CargoList = await provider.generate_json(prompt=prompt, schema=CargoList)
                    return result.cargos
                except Exception as e:
                    logger.warning("⚠️ %s falhou, tentando próximo: %s", provider.__class__.__name__, e)
                    continue

            logger.error("Todos os providers falharam em _deep_scan.")
            return []
