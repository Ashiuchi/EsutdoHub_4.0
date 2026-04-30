import re
import logging
import pandas as pd
import io
import asyncio
from pathlib import Path
from typing import List, Dict, Optional

from pydantic import BaseModel

from app.providers.base_provider import BaseLLMProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.gemini_provider import GeminiProvider
from app.core.config import settings
from app.schemas.edital_schema import Cargo, EditalGeral, CargoIdentificado
from app.core.logging_streamer import log_streamer

logger = logging.getLogger(__name__)


class MappingDiscovery(BaseModel):
    acronyms: Dict[str, str]
    regions: Dict[str, str]
    headers: List[str]


class GlobalDNA(BaseModel):
    """Metadados globais (Parte 1 do DNA 26)"""
    orgao: str
    banca: str
    data_prova: Optional[str] = "Não informada"
    published_at: Optional[str] = "Não informada"
    inscription_start: Optional[str] = "Não informada"
    inscription_end: Optional[str] = "Não informada"
    payment_deadline: Optional[str] = "Não informada"
    fee: Optional[float] = 0.0
    exam_cities: Optional[str] = "Não informada"
    link_edital: Optional[str] = None
    salary_patterns: List[str] = []


class CargoDNA(BaseModel):
    """Metadados por Cargo (Parte 2 do DNA 26)"""
    salario: Optional[float] = 0.0
    escolaridade: Optional[str] = "Não informada"
    area: Optional[str] = "Não informada"
    atribuicoes: Optional[str] = "Não informada"
    requisitos: Optional[str] = "Não informada"
    lotation_cities: Optional[str] = "Não informada"
    jornada: Optional[str] = "Não informada"


class VitaminData(BaseModel):
    edital_info: EditalGeral
    cargos_vitaminados: List[Cargo]


class CargoVitaminizerAgent:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(5)
        self.gemini_provider = GeminiProvider()
        self.ollama_provider = OllamaProvider(model="llama3.2:3b")

    def _build_chain(self) -> List[BaseLLMProvider]:
        """Gemini primeiro para poupar CPU local."""
        chain: List[BaseLLMProvider] = []
        if settings.gemini_api_key:
            chain.append(self.gemini_provider)
        chain.append(self.ollama_provider)
        return chain

    async def _discover_structure(self, main_md: str, tables: List[str]) -> MappingDiscovery:
        """Descobre siglas, códigos regionais e legendas dinâmicas do edital."""
        chain = self._build_chain()
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
                        log_streamer.broadcast({"type": "log", "message": f"📌 Mapeamento: {cod} -> {cargo}", "level": "INFO"})
                    return mapping
                except Exception as e:
                    logger.warning("⚠️ %s falhou em _discover_structure: %s", provider.__class__.__name__, e)

        logger.error("Todos os providers falharam em _discover_structure.")
        return MappingDiscovery(acronyms={}, regions={}, headers=[])

    def _process_single_table(
        self,
        table_md: str,
        discovery: MappingDiscovery,
        identified_cargos: List[CargoIdentificado],
        cargo_totals: Dict[str, Dict[str, int]],
    ) -> None:
        """Processa uma única tabela e acumula totais de vagas."""
        try:
            lines = [l.strip() for l in table_md.splitlines() if "|" in l]
            if len(lines) < 3:
                return
            clean_lines = [lines[0]] + [l for l in lines[1:] if not all(c in "|- : \t" for c in l)]
            df = pd.read_csv(io.StringIO("\n".join(clean_lines)), sep="|").loc[:, ~pd.Series([True] * 0)]
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
                                if nums:
                                    cargo_totals[target_cargo][field] += int(nums[0])
        except Exception as e:
            logger.warning("Erro ao processar tabela: %s", e)

    def _aggregate_vacancies(
        self,
        tables: List[str],
        discovery: MappingDiscovery,
        identified_cargos: List[CargoIdentificado],
    ) -> Dict[str, Dict[str, int]]:
        """Soma vagas deterministicamente via Pandas/Regex."""
        vacancy_fields = ["vagas_ac", "vagas_pcd", "vagas_negros", "vagas_indigenas", "vagas_trans", "vagas_cr", "vagas_total"]
        cargo_totals = {c.titulo: {f: 0 for f in vacancy_fields} for c in identified_cargos}
        for table_md in tables:
            self._process_single_table(table_md, discovery, identified_cargos, cargo_totals)
        return cargo_totals

    async def _extract_global_dna(self, main_md: str) -> GlobalDNA:
        """Extrai cronograma completo e taxas do edital (DNA Global)."""
        chain = self._build_chain()
        async with self.semaphore:
            prompt = f"""
            Analise o fragmento do edital abaixo e extraia os metadados globais.
            IMPORTANTE: Use nomes REAIS encontrados no texto.

            Retorne APENAS o JSON:
            {{
                "orgao": "NOME REAL DA INSTITUIÇÃO",
                "banca": "NOME REAL DA BANCA",
                "data_prova": "DD/MM/AAAA ou Não informada",
                "published_at": "DD/MM/AAAA ou Não informada",
                "inscription_start": "DD/MM/AAAA ou Não informada",
                "inscription_end": "DD/MM/AAAA ou Não informada",
                "payment_deadline": "DD/MM/AAAA ou Não informada",
                "fee": 0.0,
                "exam_cities": "Cidades ou Não informada",
                "link_edital": null,
                "salary_patterns": ["R$ 0.000,00"]
            }}

            TEXTO DO EDITAL:
            {main_md[:8000]}
            """

            for provider in chain:
                try:
                    return await provider.generate_json(prompt=prompt, schema=GlobalDNA)
                except Exception as e:
                    logger.warning("⚠️ %s falhou em _extract_global_dna: %s", provider.__class__.__name__, e)

        logger.error("Todos os providers falharam em _extract_global_dna.")
        return GlobalDNA(orgao="Pendente", banca="Pendente")

    async def _extract_cargo_dna(self, titulo: str, context: Optional[str]) -> CargoDNA:
        """DNA Sniper: extrai qualificações do cargo usando contexto ancorado."""
        if not context:
            return CargoDNA()

        chain = self._build_chain()
        async with self.semaphore:
            prompt = f"""
            Analise o contexto do cargo "{titulo}" extraído de um edital de concurso.
            Extraia os 7 campos em JSON. REGRAS CRÍTICAS:
            - salario: valor numérico float (ex: 8500.50). Retorne 0.0 se não encontrado.
            - escolaridade: nível mínimo exigido (ex: "Ensino Superior em Direito").
            - area: área de atuação (ex: "Tecnologia da Informação").
            - atribuicoes: máximo 3 verbos-chave separados por vírgula (ex: "Analisar, Elaborar, Fiscalizar"). Foque em ações que indiquem as matérias do concurso.
            - requisitos: formação + especializações em formato conciso (ex: "Graduação em Ciência da Computação, CRE ativo").
            - lotation_cities: cidades de lotação ou "Não informada".
            - jornada: carga horária (ex: "40h semanais").
            - Para campos não encontrados, retorne "Não informada".

            Retorne APENAS o JSON:
            {{
                "salario": 0.0,
                "escolaridade": "Não informada",
                "area": "Não informada",
                "atribuicoes": "Não informada",
                "requisitos": "Não informada",
                "lotation_cities": "Não informada",
                "jornada": "Não informada"
            }}

            CONTEXTO DO CARGO:
            {context[:8000]}
            """

            for provider in chain:
                try:
                    return await provider.generate_json(prompt=prompt, schema=CargoDNA)
                except Exception as e:
                    logger.warning("⚠️ %s falhou em _extract_cargo_dna (%s): %s", provider.__class__.__name__, titulo, e)

        logger.warning("Todos os providers falharam em _extract_cargo_dna para '%s'.", titulo)
        return CargoDNA()

    async def vitaminize(
        self,
        content_hash: str,
        identified_cargos: List[CargoIdentificado],
        cargo_contexts: Optional[Dict[str, str]] = None,
    ) -> VitaminData:
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
            logger.error("CargoVitaminizerAgent: Storage não encontrado para %s", content_hash)
            return VitaminData(
                edital_info=EditalGeral(orgao="Pendente", banca="Pendente"),
                cargos_vitaminados=[Cargo(titulo=c.titulo, status="error") for c in identified_cargos],
            )

        main_md = (storage_path / "main.md").read_text(encoding="utf-8") if (storage_path / "main.md").exists() else ""
        table_files = sorted((storage_path / "tables").glob("*.md")) if (storage_path / "tables").exists() else []
        tables = [f.read_text(encoding="utf-8") for f in table_files]

        log_streamer.broadcast({"type": "log", "message": "🧬 Iniciando Extração DNA 26...", "level": "INFO"})

        # Fase 1: GlobalDNA + MappingDiscovery em paralelo
        global_dna, discovery = await asyncio.gather(
            self._extract_global_dna(main_md),
            self._discover_structure(main_md, tables),
        )

        # Fase 2: Vagas determinísticas (Pandas, síncrono)
        vagas_agregadas = self._aggregate_vacancies(tables, discovery, identified_cargos)

        # Fase 3: DNA Sniper — todos os cargos em paralelo, Semaphore controla a porteira
        contexts = cargo_contexts or {}
        cargo_dnas: List[CargoDNA] = await asyncio.gather(
            *[self._extract_cargo_dna(c.titulo, contexts.get(c.titulo)) for c in identified_cargos]
        )

        # Salário global como fallback
        global_salary = 0.0
        if global_dna.salary_patterns:
            try:
                sal_str = global_dna.salary_patterns[0]
                global_salary = float(re.sub(r"[^\d.]", "", sal_str.replace(".", "").replace(",", ".")))
            except (ValueError, IndexError):
                pass

        cargos_finais = []
        for cargo_id, dna in zip(identified_cargos, cargo_dnas):
            v_data = vagas_agregadas.get(cargo_id.titulo, {})
            salario = dna.salario if dna.salario and dna.salario > 0.0 else global_salary

            cargo_vitaminado = Cargo(
                titulo=cargo_id.titulo,
                codigo_edital=cargo_id.codigo_edital,
                vagas_ac=str(v_data.get("vagas_ac", 0)),
                vagas_pcd=str(v_data.get("vagas_pcd", 0)),
                vagas_cr=str(v_data.get("vagas_cr", 0)),
                vagas_negros=str(v_data.get("vagas_negros", 0)),
                vagas_indigenas=str(v_data.get("vagas_indigenas", 0)),
                vagas_trans=str(v_data.get("vagas_trans", 0)),
                vagas_total=str(
                    v_data.get("vagas_total", 0)
                    or sum(v for k, v in v_data.items() if "total" not in k)
                ),
                salario=salario,
                escolaridade=dna.escolaridade,
                area=dna.area,
                atribuicoes=dna.atribuicoes,
                requisitos=dna.requisitos,
                lotation_cities=dna.lotation_cities,
                jornada=dna.jornada,
                status="vitaminado",
            )
            cargos_finais.append(cargo_vitaminado)

            log_streamer.broadcast({"type": "data", "payload": cargo_vitaminado.model_dump()})
            log_streamer.broadcast({
                "type": "log",
                "message": f"✅ DNA extraído: {cargo_vitaminado.titulo} | R$ {salario:.0f} | {cargo_vitaminado.vagas_total} vagas",
                "level": "INFO",
            })

        edital_info = EditalGeral(
            orgao=global_dna.orgao,
            banca=global_dna.banca,
            data_prova=global_dna.data_prova,
            published_at=global_dna.published_at,
            inscription_start=global_dna.inscription_start,
            inscription_end=global_dna.inscription_end,
            payment_deadline=global_dna.payment_deadline,
            fee=global_dna.fee,
            exam_cities=global_dna.exam_cities,
            link_edital=global_dna.link_edital,
        )

        return VitaminData(edital_info=edital_info, cargos_vitaminados=cargos_finais)
