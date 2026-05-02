import json
import os
import random
import re
import string
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

JC_BASE_URL = "https://jcconcursos.com.br"
CNB_BASE_URL = "https://www.concursosnobrasil.com.br"
CEBRASPE_EVENTOS_ENCERRADOS_API = (
    "https://apis.cebraspe.org.br/cebraspe/eventos/tipo/concursos/fase/encerrado"
)

BANCAS_CONFIG = {
    "CESGRANRIO": "https://www.cesgranrio.org.br/concursos/",
    "CESGRANRIO_CNU": "https://cpnu.cesgranrio.org.br/página-inicial",
    "CEBRASPE_ANDAMENTO": "https://www.cebraspe.org.br/concursos/em-andamento/",
    "CEBRASPE_ENCERRADO": "https://www.cebraspe.org.br/concursos/encerrado",
    "FGV": "https://conhecimento.fgv.br/concursos",
    "VUNESP": "https://www.vunesp.com.br/concurso/inscricoesAbertas",
    "CAIXA_2024": "https://www.cesgranrio.org.br/concursos/evento.aspx?id=caixa0124",
    "BB_SEARCH": "https://www.cesgranrio.org.br/concursos/evento.aspx?id=bb0122",
    "CAIXA_2025_M": "https://concursos.cesgranrio.org.br/portal/avaliacoes/19",
    "VUNESP_MIRROR": "https://www.direcaoconcursos.com.br/noticias/vunesp-concursos",
    "FGV_MIRROR": "https://www.direcaoconcursos.com.br/noticias/fgv-concursos",
    "TRIBUNAIS_MIRROR": "https://www.direcaoconcursos.com.br/noticias/concurso-tribunal",
    "BANCARIOS_MIRROR": "https://www.direcaoconcursos.com.br/concursos?career=9",
    "POLICIAL_MIRROR": "https://www.direcaoconcursos.com.br/noticias/concurso-policial",
    "FISCAL_MIRROR": "https://www.direcaoconcursos.com.br/noticias/concurso-fiscal",
}

MIRROR_TARGETS = [
    (BANCAS_CONFIG["VUNESP_MIRROR"], "VUNESP_MIRROR"),
    (BANCAS_CONFIG["FGV_MIRROR"], "FGV_MIRROR"),
    (BANCAS_CONFIG["TRIBUNAIS_MIRROR"], "TRIBUNAIS_MIRROR"),
    (BANCAS_CONFIG["BANCARIOS_MIRROR"], "BANCARIOS_MIRROR"),
    (BANCAS_CONFIG["POLICIAL_MIRROR"], "POLICIAL_MIRROR"),
    (BANCAS_CONFIG["FISCAL_MIRROR"], "FISCAL_MIRROR"),
]

OFFICIAL_TARGETS = {
    "CESGRANRIO": {"url": BANCAS_CONFIG["CESGRANRIO"], "official": True},
    "CEBRASPE": {"url": BANCAS_CONFIG["CEBRASPE_ANDAMENTO"], "official": True},
    "FGV": {"url": BANCAS_CONFIG["FGV"], "official": True},
    "VUNESP": {"url": BANCAS_CONFIG["VUNESP"], "official": True},
    "CAIXA": {"url": BANCAS_CONFIG["CAIXA_2025_M"], "official": True},
    "BB": {"url": BANCAS_CONFIG["BB_SEARCH"], "official": True},
}

TRIGGER_KEYWORDS = {
    "CESGRANRIO": ["cesgranrio"],
    "CAIXA": ["caixa", "caixa econômica", "caixa economica"],
    "BB": ["banco do brasil", "bb "],
    "FGV": ["fgv"],
    "VUNESP": ["vunesp"],
    "CEBRASPE": ["cebraspe", "cespe"],
}

POPULAR_TAGS = [
    "banco do brasil",
    "caixa",
    "tse",
    "tj",
    "trt",
    "tre",
    "trf",
    "dpe",
    "tcu",
    "mpu",
    "mp-",
    "mcu",
    "bndes",
    "cnu",
    "pf",
    "prf",
    "procurador",
    "policia civil",
    "policia militar",
    "oficial",
    "agente",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

LOG_FILE = "storage/pescaria_log.json"
INDUSTRIAL_LOG_FILE = "storage/industrial_ingestion.log"
YEAR_MIN = 2020
YEAR_MAX = 2026
QUARANTINE_HOURS = 12
MIRROR_COOLDOWN_SECONDS = 3600
NORMAL_REST_SECONDS = 3600
FISHING_WINDOW_START_HOUR = 0
FISHING_WINDOW_END_HOUR = 2
URL_BLACKLIST = [
    "/noticias",
    "/login",
    "/categoria",
    "/contato",
    "/imprensa",
    "/sobre-nos",
]
DOCUMENT_PORTAL_MARKERS = [
    "concursos.cesgranrio.org.br/portal/avaliacoes/",
    "apis.cebraspe.org.br",
    "cdn.cebraspe.org.br",
]
DOCUMENT_PAGE_KEYWORDS = [
    "edital",
    "retificacao",
    "retificacoes",
    "retificado",
    "normativo",
    "abertura",
    "documento",
    "publicacao",
]
ELITE_DOCUMENT_WHITELIST = [
    "edital",
    "abertura",
    "normativo",
    "retificacao",
    "retificado",
    "regulamento",
]
ELITE_DOCUMENT_BLACKLIST = [
    "isencao",
    "resultado",
    "gabarito",
    "prova",
    "homologacao",
    "inscritos",
    "demanda",
    "pne",
    "pcd",
    "negro",
    "indigena",
    "trans",
    "deferido",
    "indeferido",
    "convocacao",
]


def resolve_storage_path():
    raw_path = os.getenv("STORAGE_K_PATH")
    if not raw_path:
        return Path("storage_k").resolve()

    raw_path = raw_path.strip().strip('"').strip("'")
    if os.name != "nt":
        match = re.match(r"^([a-zA-Z]):[\\/](.*)$", raw_path)
        if match:
            drive = match.group(1).lower()
            tail = match.group(2).replace("\\", "/")
            return Path(f"/mnt/{drive}/{tail}").resolve()

    return Path(raw_path).expanduser().resolve()


SAVE_DIR = resolve_storage_path()


def is_fishing_window(now=None):
    current = now or datetime.now()
    return FISHING_WINDOW_START_HOUR <= current.hour < FISHING_WINDOW_END_HOUR


def seconds_until_next_fishing_window(now=None):
    current = now or datetime.now()
    next_window = current.replace(
        hour=FISHING_WINDOW_START_HOUR, minute=0, second=0, microsecond=0
    )
    if current >= next_window:
        next_window += timedelta(days=1)
    return max(1, int((next_window - current).total_seconds()))


class PescaLogger:
    def __init__(self, log_path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()
        self._ensure_schema()
        self._save()

    def _load(self):
        if self.log_path.exists():
            try:
                with self.log_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data.get("visited_urls"), list):
                        data["visited_urls"] = {
                            url: "2000-01-01T00:00:00" for url in data["visited_urls"]
                        }
                    return data
            except Exception:
                pass
        return {}

    def _ensure_schema(self):
        self.data.setdefault("visited_urls", {})
        self.data.setdefault("downloaded_files", [])
        self.data.setdefault("targets", {})
        self.data.setdefault("url_status", {})
        for target_name in OFFICIAL_TARGETS:
            self.get_target_status(target_name)

    def _save(self):
        with self.log_path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def get_target_status(self, target_name):
        targets = self.data.setdefault("targets", {})
        status = targets.setdefault(
            target_name,
            {
                "last_visit": None,
                "last_success": None,
                "last_failure": None,
                "deep_scraped": False,
                "failure_streak": 0,
                "quarantine_until": None,
            },
        )
        status.setdefault("deep_scraped", False)
        status.setdefault("failure_streak", status.pop("failures", 0))
        status.setdefault("quarantine_until", None)
        status.setdefault("last_visit", None)
        status.setdefault("last_success", None)
        status.setdefault("last_failure", None)
        return status

    def is_target_quarantined(self, target_name):
        status = self.get_target_status(target_name)
        if status.get("failure_streak", 0) < 3:
            return False
        until = status.get("quarantine_until")
        if not until:
            return False
        try:
            return datetime.now() < datetime.fromisoformat(until)
        except ValueError:
            return False

    def mark_target_attempt(self, target_name, success, deep_scraped=None):
        status = self.get_target_status(target_name)
        now = datetime.now()
        status["last_visit"] = now.isoformat()
        if success:
            status["last_success"] = now.isoformat()
            status["failure_streak"] = 0
            status["quarantine_until"] = None
        else:
            status["last_failure"] = now.isoformat()
            status["failure_streak"] = status.get("failure_streak", 0) + 1
            if status["failure_streak"] >= 3:
                status["quarantine_until"] = (
                    now + timedelta(hours=QUARANTINE_HOURS)
                ).isoformat()
        if deep_scraped is not None:
            status["deep_scraped"] = deep_scraped
        self.data["targets"][target_name] = status
        self._save()

    def is_visited(self, url, cooldown_seconds=43200):
        last_visit = self.data["visited_urls"].get(url)
        if not last_visit:
            return False
        try:
            return (datetime.now() - datetime.fromisoformat(last_visit)).total_seconds() < cooldown_seconds
        except ValueError:
            return True

    def mark_visited(self, url):
        self.data["visited_urls"][url] = datetime.now().isoformat()
        self._save()

    def get_url_status(self, url):
        status = self.data.setdefault("url_status", {}).setdefault(
            url,
            {
                "last_success": None,
                "last_failure": None,
                "failure_streak": 0,
                "quarantine_until": None,
            },
        )
        status.setdefault("failure_streak", 0)
        status.setdefault("quarantine_until", None)
        return status

    def is_url_quarantined(self, url):
        status = self.get_url_status(url)
        if status.get("failure_streak", 0) < 3:
            return False
        until = status.get("quarantine_until")
        if not until:
            return False
        try:
            return datetime.now() < datetime.fromisoformat(until)
        except ValueError:
            return False

    def mark_url_success(self, url):
        status = self.get_url_status(url)
        status["last_success"] = datetime.now().isoformat()
        status["failure_streak"] = 0
        status["quarantine_until"] = None
        self.data["url_status"][url] = status
        self._save()

    def mark_url_failure(self, url):
        status = self.get_url_status(url)
        now = datetime.now()
        status["last_failure"] = now.isoformat()
        status["failure_streak"] = status.get("failure_streak", 0) + 1
        if status["failure_streak"] >= 3:
            status["quarantine_until"] = (
                now + timedelta(hours=QUARANTINE_HOURS)
            ).isoformat()
        self.data["url_status"][url] = status
        self._save()

    def is_pdf_downloaded(self, pdf_url):
        return any(entry.get("pdf_url") == pdf_url for entry in self.data["downloaded_files"])

    def mark_downloaded(self, filename, pdf_url, contest_url=None):
        self.data["downloaded_files"].append(
            {
                "filename": filename,
                "pdf_url": pdf_url,
                "contest_url": contest_url,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self._save()


class AgentePescador:
    def __init__(self):
        self.logger = PescaLogger(LOG_FILE)
        self.session = requests.Session()
        self.log_file_path = Path(INDUSTRIAL_LOG_FILE)
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        self._log(f"Storage ativo para downloads: {SAVE_DIR}")

    def _log(self, msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"[{timestamp}] [PESCADOR] {msg}"
        print(full_msg)
        try:
            with self.log_file_path.open("a", encoding="utf-8") as f:
                f.write(full_msg + "\n")
        except PermissionError:
            fallback_path = self.log_file_path.with_name("industrial_ingestion.pescador.log")
            with fallback_path.open("a", encoding="utf-8") as f:
                f.write(
                    f"{full_msg} | fallback_log={fallback_path} reason=industrial_ingestion.log_sem_permissao\n"
                )

    def _headers(self, referer="https://www.google.com/"):
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "Referer": referer,
        }

    def slow_down(self, fast=False):
        time.sleep(random.uniform(0.8, 2.2) if fast else random.uniform(3.0, 7.5))

    def fetch_page(self, url, *, fast=False, ignore_quarantine=False):
        if not ignore_quarantine and self.logger.is_url_quarantined(url):
            status = self.logger.get_url_status(url)
            self._log(
                f"PULANDO URL em quarentena: {url} | failure_streak={status['failure_streak']} until={status['quarantine_until']}"
            )
            return None

        self.slow_down(fast=fast)
        try:
            resp = self.session.get(
                url,
                headers=self._headers(),
                timeout=30,
                allow_redirects=True,
            )
            if resp.status_code == 200:
                self.logger.mark_url_success(url)
                return resp.text
            self.logger.mark_url_failure(url)
            self._log(f"FETCH falhou: {url} | status={resp.status_code}")
            return None
        except Exception as e:
            self.logger.mark_url_failure(url)
            self._log(f"FETCH erro: {url} | {e}")
            return None

    def fetch_json(self, url, *, fast=False, ignore_quarantine=False):
        if not ignore_quarantine and self.logger.is_url_quarantined(url):
            status = self.logger.get_url_status(url)
            self._log(
                f"PULANDO JSON em quarentena: {url} | failure_streak={status['failure_streak']} until={status['quarantine_until']}"
            )
            return None

        self.slow_down(fast=fast)
        try:
            resp = self.session.get(
                url,
                headers=self._headers(referer="https://www.cebraspe.org.br/concursos/encerrado"),
                timeout=30,
                allow_redirects=True,
            )
            if resp.status_code == 200:
                self.logger.mark_url_success(url)
                return resp.json()
            self.logger.mark_url_failure(url)
            self._log(f"FETCH JSON falhou: {url} | status={resp.status_code}")
            return None
        except Exception as e:
            self.logger.mark_url_failure(url)
            self._log(f"FETCH JSON erro: {url} | {e}")
            return None

    def is_blacklisted_url(self, url):
        url_l = url.lower()
        return "#" in url_l or any(blocked in url_l for blocked in URL_BLACKLIST)

    def is_direct_document_url(self, url):
        clean_url = url.lower().split("?", 1)[0]
        return clean_url.endswith(".pdf") or clean_url.endswith(".zip")

    def normalize_filter_text(self, *parts):
        text = " ".join(str(part or "") for part in parts)
        text = unquote(text).lower()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        return text

    def is_elite_document_candidate(self, url, text="", filename=""):
        context = self.normalize_filter_text(url, text, filename)
        blocked = next((term for term in ELITE_DOCUMENT_BLACKLIST if term in context), None)
        if blocked:
            self._log(f"PULANDO documento ruído: termo_blacklist={blocked} | {url}")
            return False

        allowed = any(term in context for term in ELITE_DOCUMENT_WHITELIST)
        if not allowed:
            self._log(f"PULANDO documento sem termo elite: {url}")
        return allowed

    def is_official_document_portal(self, url):
        url_l = url.lower()
        return any(marker in url_l for marker in DOCUMENT_PORTAL_MARKERS)

    def contest_slug_from_url(self, url):
        match = re.search(r"/concurso/([^/?#]+)/?", url.lower())
        if match:
            return match.group(1)
        match = re.search(r"/concursos/([^/?#]+)/?", url.lower())
        if match:
            return match.group(1)
        return ""

    def is_allowed_document_page(self, candidate_url, text, parent_url):
        if self.is_blacklisted_url(candidate_url):
            return False
        if self.is_direct_document_url(candidate_url):
            return self.is_elite_document_candidate(candidate_url, text)

        candidate_l = candidate_url.lower()
        text_l = text.lower()
        context = f"{candidate_l} {text_l}"
        if not self.is_elite_document_candidate(candidate_url, text):
            return False
        parent_slug = self.contest_slug_from_url(parent_url)
        has_document_keyword = any(keyword in context for keyword in DOCUMENT_PAGE_KEYWORDS)
        has_same_contest_slug = bool(parent_slug and parent_slug in candidate_l)
        return has_document_keyword or has_same_contest_slug

    def is_edital_link(self, href, text):
        href_l = href.lower()
        text_l = text.lower()
        clean_href = href_l.split("?")[0]
        if not any(clean_href.endswith(ext) for ext in [".pdf", ".zip"]):
            return False
        return self.is_elite_document_candidate(href_l, text_l)

    def clean_filename(self, year, banca, organ):
        name = f"{year}_{banca}_{organ}".upper()
        name = name.replace(" ", "_").replace("/", "-").replace(":", "-")
        name = re.sub(r"[^\w\-.]", "", name)
        suffix = ".zip" if name.endswith(".ZIP") else ".pdf"
        if name.endswith((".PDF", ".ZIP")):
            name = name.rsplit(".", 1)[0]
        return f"{name[:175]}{suffix}"

    def download_pdf(self, pdf_url, filename, contest_url=None):
        if not self.is_elite_document_candidate(pdf_url, filename):
            return False
        if self.logger.is_pdf_downloaded(pdf_url):
            self._log(f"PULANDO download já registrado: {pdf_url}")
            return False
        if self.logger.is_url_quarantined(pdf_url):
            self._log(f"PULANDO download em quarentena: {pdf_url}")
            return False

        for attempt in range(2):
            headers = self._headers(referer=contest_url or "https://www.google.com/")
            try:
                self._log(f">>> [FISGADO] Download tentativa {attempt + 1}: {pdf_url}")
                self.slow_down(fast=attempt > 0)
                response = self.session.get(
                    pdf_url, headers=headers, stream=True, timeout=60, allow_redirects=True
                )
                if response.status_code == 403 and attempt == 0:
                    self._log("403 recebido; alternando User-Agent e repetindo uma vez.")
                    continue
                response.raise_for_status()

                filepath = SAVE_DIR / filename
                with filepath.open("wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                self.logger.mark_url_success(pdf_url)
                self.logger.mark_downloaded(filename, pdf_url, contest_url)
                self._log(f"--- [SUCESSO] Edital salvo em {filepath}")
                return True
            except Exception as e:
                self.logger.mark_url_failure(pdf_url)
                self._log(f"!!! [ERRO] Falha no download {pdf_url}: {e}")
        return False

    def extract_pdf_links(self, html, base_url):
        raw_links = set()
        patterns = [
            r"https?://[^\s\"'<>)]*?\.pdf(?:\?[^\s\"'<>)]*sig=[^\s\"'<>)]*)?",
            r"https?://[^\s\"'<>)]*?\.zip(?:\?[^\s\"'<>)]*)?",
            r"https?://cdn\.direcaoconcursos\.com\.br/[^\s\"'<>)]*",
        ]
        for pattern in patterns:
            for match in re.findall(pattern, html, re.IGNORECASE):
                raw_links.add(match.replace("&amp;", "&"))

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, a["href"])
            text = a.get_text(" ", strip=True)
            if self.is_blacklisted_url(href):
                continue
            if self.is_edital_link(href, text):
                raw_links.add(href.replace("&amp;", "&"))

        return sorted(raw_links)

    def scrape_contest_detail(self, url, banca_name, depth=0, *, event_trigger=False):
        if self.is_blacklisted_url(url):
            self._log(f"PULANDO URL bloqueada por blacklist/âncora: {url}")
            return False

        max_depth = 2 if self.is_official_document_portal(url) else 1
        if depth > max_depth:
            self._log(f"PULANDO profundidade excessiva: {url} depth={depth} max_depth={max_depth}")
            return False

        if self.is_direct_document_url(url):
            if not self.is_elite_document_candidate(url):
                return False
            fname = self.clean_filename(
                datetime.now().year,
                banca_name,
                f"EDITAL_{Path(url.split('?')[0]).name[:60]}",
            )
            return self.download_pdf(url, fname, url)

        if not event_trigger and self.logger.is_visited(url, cooldown_seconds=43200):
            self._log(f"PULANDO detalhe já visitado em cooldown: {url}")
            return False

        self._log(
            f"Scraping detalhe: {url} ({banca_name}) depth={depth} event_trigger={event_trigger}"
        )
        html = self.fetch_page(url, fast=event_trigger, ignore_quarantine=event_trigger)
        if not html:
            return False

        found_any = False
        for pdf_url in self.extract_pdf_links(html, url):
            if not self.is_edital_link(pdf_url, ""):
                continue
            fname = self.clean_filename(
                datetime.now().year,
                banca_name,
                f"EDITAL_{Path(pdf_url.split('?')[0]).name[:60]}",
            )
            if self.download_pdf(pdf_url, fname, url):
                found_any = True

        if found_any:
            self.logger.mark_visited(url)
            return True

        if depth >= 2:
            self.logger.mark_visited(url)
            return False

        soup = BeautifulSoup(html, "html.parser")
        subpages = []
        for a in soup.find_all("a", href=True):
            full_url = urljoin(url, a["href"])
            text = a.get_text(" ", strip=True)
            if self.is_direct_document_url(full_url):
                if not self.is_elite_document_candidate(full_url, text):
                    continue
                fname = self.clean_filename(
                    datetime.now().year,
                    banca_name,
                    f"EDITAL_{Path(full_url.split('?')[0]).name[:60]}",
                )
                if self.download_pdf(full_url, fname, url):
                    found_any = True
                continue

            if self.is_allowed_document_page(full_url, text, url) and full_url not in subpages:
                subpages.append(full_url)

        for sub_url in subpages[:5]:
            found_any = self.scrape_contest_detail(
                sub_url, banca_name, depth + 1, event_trigger=event_trigger
            ) or found_any

        self.logger.mark_visited(url)
        return found_any

    def scrape_cesgranrio(self, *, event_trigger=False):
        status = self.logger.get_target_status("CESGRANRIO")
        if not event_trigger and status["deep_scraped"]:
            self._log("PULANDO CESGRANRIO oficial: deep_scraped=True e sem gatilho de notícia.")
            return False
        if not event_trigger and self.logger.is_target_quarantined("CESGRANRIO"):
            self._log(
                f"PULANDO CESGRANRIO oficial: quarentena ativa until={status['quarantine_until']}"
            )
            return False

        self._log(f"CESGRANRIO deep scrape iniciado | event_trigger={event_trigger}")
        found_any = False
        success_pages = 0
        for page in range(1, 6):
            page_url = BANCAS_CONFIG["CESGRANRIO"] if page == 1 else f"{BANCAS_CONFIG['CESGRANRIO']}page/{page}"
            html = self.fetch_page(page_url, fast=event_trigger, ignore_quarantine=event_trigger)
            if not html:
                self._log(f"CESGRANRIO página {page} sem HTML; seguindo para próxima.")
                continue
            success_pages += 1
            detail_links = self.extract_cesgranrio_detail_links(html)
            self._log(f"CESGRANRIO página {page}: {len(detail_links)} candidatos.")
            for detail_url in detail_links:
                found_any = self.scrape_contest_detail(
                    detail_url, "CESGRANRIO", event_trigger=event_trigger
                ) or found_any

        completed = success_pages > 0
        self.logger.mark_target_attempt(
            "CESGRANRIO", success=completed, deep_scraped=completed or status["deep_scraped"]
        )
        self._log(
            f"CESGRANRIO deep scrape finalizado | paginas_ok={success_pages}/5 found_any={found_any} deep_scraped={completed or status['deep_scraped']}"
        )
        return found_any

    def extract_cesgranrio_detail_links(self, html):
        soup = BeautifulSoup(html, "html.parser")
        detail_links = []
        for a in soup.find_all("a", href=True):
            detail_url = urljoin(BANCAS_CONFIG["CESGRANRIO"], a["href"])
            if self.is_blacklisted_url(detail_url):
                continue
            href = detail_url.lower()
            if "evento.aspx" in href or "detalhe" in href or "/concurso/" in href:
                if detail_url not in detail_links:
                    detail_links.append(detail_url)
        return detail_links

    def dry_run_cesgranrio_page(self, page=1):
        page_url = BANCAS_CONFIG["CESGRANRIO"] if page == 1 else f"{BANCAS_CONFIG['CESGRANRIO']}page/{page}"
        html = self.fetch_page(page_url, fast=True, ignore_quarantine=True)
        if not html:
            self._log(f"DRY-RUN CESGRANRIO página {page}: sem HTML.")
            return []
        detail_links = self.extract_cesgranrio_detail_links(html)
        self._log(f"DRY-RUN CESGRANRIO página {page}: {len(detail_links)} candidatos.")
        for detail_url in detail_links[:10]:
            self._log(f"DRY-RUN CESGRANRIO página {page}: {detail_url}")
        return detail_links

    def scrape_cebraspe(self, *, event_trigger=False):
        found_open = self.scrape_generic_official(
            "CEBRASPE", BANCAS_CONFIG["CEBRASPE_ANDAMENTO"], event_trigger
        )
        found_historical = self.scrape_cebraspe_historico(event_trigger=event_trigger)
        return found_open or found_historical

    def extract_fgv_slugs(self, html):
        soup = BeautifulSoup(html, "html.parser")
        slugs = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            match = re.search(r"/concursos/([^/?#]+)", href)
            if not match:
                continue
            slug = match.group(1).strip("/")
            if slug and slug not in slugs:
                slugs.append(slug)
        return slugs

    def extract_fgv_pdf_links(self, html, detail_url):
        pdf_links = set()
        pattern = r"(?:https?://conhecimento\.fgv\.br)?/sites/default/files/concursos/[^\s\"'<>]+?\.pdf(?:\?[^\s\"'<>]*)?"
        for match in re.findall(pattern, html, re.IGNORECASE):
            pdf_url = urljoin(detail_url, match.replace("&amp;", "&"))
            if self.is_elite_document_candidate(pdf_url):
                pdf_links.add(pdf_url)
        return sorted(pdf_links)

    def scrape_fgv(self, *, event_trigger=False, dry_run=False, slug_limit=None):
        target_name = "FGV"
        status = self.logger.get_target_status(target_name)
        if not event_trigger and not dry_run and status["deep_scraped"]:
            self._log("PULANDO FGV oficial: deep_scraped=True e sem gatilho.")
            return False
        if not event_trigger and not dry_run and self.logger.is_target_quarantined(target_name):
            self._log(f"PULANDO FGV oficial: quarentena ativa until={status['quarantine_until']}")
            return False

        html = self.fetch_page(
            BANCAS_CONFIG["FGV"], fast=event_trigger or dry_run, ignore_quarantine=event_trigger
        )
        if not html:
            if not dry_run:
                self.logger.mark_target_attempt(target_name, success=False)
            return False

        slugs = self.extract_fgv_slugs(html)
        if slug_limit:
            slugs = slugs[:slug_limit]
        self._log(f"FGV especialista: {len(slugs)} slugs capturados.")

        found_any = False
        for slug in slugs:
            detail_url = f"https://conhecimento.fgv.br/concursos/{slug}"
            detail_html = self.fetch_page(
                detail_url, fast=event_trigger or dry_run, ignore_quarantine=event_trigger
            )
            if not detail_html:
                continue
            pdf_links = self.extract_fgv_pdf_links(detail_html, detail_url)
            self._log(f"FGV slug={slug}: {len(pdf_links)} PDFs em /sites/default/files/concursos/.")
            if dry_run:
                continue
            for pdf_url in pdf_links:
                if self.logger.is_pdf_downloaded(pdf_url):
                    continue
                fname = self.clean_filename(
                    datetime.now().year,
                    "FGV",
                    f"{slug}_{Path(pdf_url.split('?')[0]).name[:60]}",
                )
                if self.download_pdf(pdf_url, fname, detail_url):
                    found_any = True

        if not dry_run:
            self.logger.mark_target_attempt(target_name, success=True, deep_scraped=True)
        return found_any

    def has_safra_year(self, text):
        return bool(re.search(r"\b20(?:20|21|22|23|24|25|26)\b|\b(?:20|21|22|23|24|25|26)\b", text))

    def extract_cebraspe_historical_candidates_from_html(self, html, base_url, letter):
        soup = BeautifulSoup(html, "html.parser")
        candidates = []
        for a in soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True)
            full_url = urljoin(base_url, a["href"])
            context = f"{text} {full_url}"
            if "/concursos/" not in full_url.lower():
                continue
            if not self.has_safra_year(context):
                continue
            contest_key = re.sub(r"[^a-z0-9]", "", text.lower()) or Path(full_url).name.lower()
            if letter and not contest_key.startswith(letter.lower()):
                continue
            if full_url not in [url for url, _ in candidates]:
                candidates.append((full_url, text))
        return candidates

    def extract_cebraspe_historical_candidates_from_api(self, payload, letter):
        candidates = []
        groups = payload if isinstance(payload, list) else []
        for group in groups:
            for event in group.get("eventos", []):
                name = event.get("eventoNomeAbreviado") or ""
                event_url = event.get("eventoURL") or ""
                year = str(event.get("eventoAno") or "")
                context = f"{name} {event_url} {year}"
                if letter and not name.upper().startswith(letter.upper()):
                    continue
                if not self.has_safra_year(context):
                    continue
                contest_url = urljoin("https://www.cebraspe.org.br/concursos/", event_url)
                if contest_url not in [url for url, _ in candidates]:
                    candidates.append((contest_url, name))
        return candidates

    def scrape_cebraspe_historico(self, *, event_trigger=False, dry_run=False, letters=None):
        target_name = "CEBRASPE_HISTORICO"
        if not dry_run and self.logger.is_target_quarantined(target_name):
            status = self.logger.get_target_status(target_name)
            self._log(
                f"PULANDO CEBRASPE histórico: quarentena ativa until={status['quarantine_until']}"
            )
            return False

        api_payload = self.fetch_json(
            CEBRASPE_EVENTOS_ENCERRADOS_API,
            fast=event_trigger or dry_run,
            ignore_quarantine=event_trigger or dry_run,
        )
        base_html = None
        if not api_payload:
            base_url = BANCAS_CONFIG["CEBRASPE_ENCERRADO"]
            base_html = self.fetch_page(
                base_url, fast=event_trigger or dry_run, ignore_quarantine=event_trigger
            )
            if not base_html:
                if not dry_run:
                    self.logger.mark_target_attempt(target_name, success=False)
                return False

        found_any = False
        letters_to_scan = list(letters) if letters else list(string.ascii_uppercase)
        for letter in letters_to_scan:
            if api_payload:
                letter_candidates = self.extract_cebraspe_historical_candidates_from_api(
                    api_payload, letter
                )
            else:
                letter_candidates = self.extract_cebraspe_historical_candidates_from_html(
                    base_html, BANCAS_CONFIG["CEBRASPE_ENCERRADO"], letter
                )

            deduped = []
            seen = set()
            for contest_url, text in letter_candidates:
                if contest_url not in seen:
                    seen.add(contest_url)
                    deduped.append((contest_url, text))

            self._log(
                f"CEBRASPE histórico aba {letter}: {len(deduped)} concursos filtrados por safra 2020-2026."
            )
            if dry_run:
                for contest_url, text in deduped[:10]:
                    self._log(f"DRY-RUN CEBRASPE {letter}: {text[:80]} -> {contest_url}")
                continue

            for contest_url, _text in deduped:
                found_any = self.scrape_contest_detail(
                    contest_url, "CEBRASPE", event_trigger=event_trigger
                ) or found_any

        if not dry_run:
            self.logger.mark_target_attempt(target_name, success=True, deep_scraped=True)
        return found_any

    def scrape_vunesp(self, *, event_trigger=False):
        return self.scrape_generic_official("VUNESP", BANCAS_CONFIG["VUNESP"], event_trigger)

    def scrape_generic_official(self, target_name, url, event_trigger=False):
        status = self.logger.get_target_status(target_name)
        if not event_trigger and status["deep_scraped"]:
            self._log(f"PULANDO {target_name} oficial: deep_scraped=True e sem gatilho.")
            return False
        if not event_trigger and self.logger.is_target_quarantined(target_name):
            self._log(
                f"PULANDO {target_name} oficial: quarentena ativa until={status['quarantine_until']}"
            )
            return False

        html = self.fetch_page(url, fast=event_trigger, ignore_quarantine=event_trigger)
        if not html:
            self.logger.mark_target_attempt(target_name, success=False)
            return False

        found_any = False
        soup = BeautifulSoup(html, "html.parser")
        candidates = []
        for a in soup.find_all("a", href=True):
            full_url = urljoin(url, a["href"])
            text = a.get_text(" ", strip=True).lower()
            href_l = full_url.lower()
            if self.is_blacklisted_url(full_url):
                continue
            if self.is_direct_document_url(full_url):
                if self.is_elite_document_candidate(full_url, text):
                    candidates.append(full_url)
                continue
            if self.is_allowed_document_page(full_url, text, url) and any(
                x in href_l or x in text
                for x in ["concurso", "edital", "retificacao", "normativo", "avaliacoes"]
            ):
                if full_url not in candidates:
                    candidates.append(full_url)

        self._log(f"{target_name} oficial: {len(candidates[:10])} candidatos analisáveis.")
        for candidate in candidates[:10]:
            found_any = self.scrape_contest_detail(
                candidate, target_name, event_trigger=event_trigger
            ) or found_any

        self.logger.mark_target_attempt(target_name, success=True, deep_scraped=True)
        return found_any

    def detect_triggers(self, text):
        text_l = f" {text.lower()} "
        triggered = set()
        for target_name, keywords in TRIGGER_KEYWORDS.items():
            if any(keyword in text_l for keyword in keywords):
                triggered.add(target_name)
        return triggered

    def activate_target(self, target_name, source_url):
        self._log(f"GATILHO ATIVADO por mirror: {target_name} | source={source_url}")
        if target_name == "CESGRANRIO":
            return self.scrape_cesgranrio(event_trigger=True)
        if target_name == "CEBRASPE":
            return self.scrape_cebraspe(event_trigger=True)
        if target_name == "FGV":
            return self.scrape_fgv(event_trigger=True)
        if target_name == "VUNESP":
            return self.scrape_vunesp(event_trigger=True)
        if target_name in ["CAIXA", "BB"]:
            return self.scrape_contest_detail(
                OFFICIAL_TARGETS[target_name]["url"], target_name, event_trigger=True
            )
        return False

    def scrape_mirror(self, url, banca_tag):
        if self.logger.is_visited(url, cooldown_seconds=MIRROR_COOLDOWN_SECONDS):
            self._log(f"PULANDO mirror em cooldown de 1h: {url}")
            return set()

        self._log(f"Modo vigilante: scraping mirror {banca_tag} | {url}")
        html = self.fetch_page(url, fast=True)
        if not html:
            return set()

        soup = BeautifulSoup(html, "html.parser")
        triggered_targets = set()
        links_found = 0
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            text = a.get_text(" ", strip=True)
            context = f"{text} {href}"
            href_l = href.lower()
            if self.is_blacklisted_url(href):
                continue
            if any(
                blocked in href_l
                for blocked in [
                    "whatsapp.com",
                    "facebook.com",
                    "linkedin.com",
                    "twitter.com",
                    "x.com",
                    "telegram.me",
                    "instagram.com",
                    "youtube.com",
                    "assinaturas",
                    "professores",
                    "afiliados",
                    "google.com",
                    "bing.com",
                ]
            ):
                continue

            is_news = any(x in href_l for x in ["concurso", "edital", ".html", "organizadora"])
            is_popular = any(tag in context.lower() for tag in POPULAR_TAGS)
            triggers = self.detect_triggers(context)
            if not (is_news or is_popular or triggers):
                continue

            links_found += 1
            if not self.logger.is_visited(href, cooldown_seconds=43200):
                self._log(f"Mirror notícia candidata: {href} | {text[:80]}")
                if self.is_allowed_document_page(href, text, url):
                    self.scrape_contest_detail(href, banca_tag, event_trigger=False)
                else:
                    self._log(f"Mirror não aprofundado: sem palavra-chave documental/slug | {href}")
                self.logger.mark_visited(href)
            else:
                self._log(f"Mirror link já visto; usando apenas como contexto de gatilho: {href}")

            for target_name in triggers:
                triggered_targets.add(target_name)

        self.logger.mark_visited(url)
        self._log(
            f"Mirror finalizado: {banca_tag} | links_analisados={links_found} triggers={sorted(triggered_targets)}"
        )
        return triggered_targets

    def run(self):
        self._log(f">>> CICLO REATIVO PESCADOR V4.0: {datetime.now().isoformat()} <<<")

        # Deep scrape histórico só acontece quando ainda não há marca de conclusão.
        self.scrape_cesgranrio(event_trigger=False)

        triggered_targets = set()
        for url, tag in MIRROR_TARGETS:
            triggered_targets.update(self.scrape_mirror(url, tag))

        if not triggered_targets:
            self._log("Sem gatilhos novos nos mirrors; oficiais deep_scraped continuam em repouso.")
            return

        for target_name in sorted(triggered_targets):
            self.activate_target(target_name, "mirror")


if __name__ == "__main__":
    agente = AgentePescador()
    run_now = "--now" in sys.argv
    if "--dry-run-smoke" in sys.argv:
        agente._log("DRY-RUN SMOKE: Cesgranrio página 1 + Cebraspe aba A.")
        agente.dry_run_cesgranrio_page(page=1)
        agente.scrape_cebraspe_historico(dry_run=True, letters=["A"])
        sys.exit(0)

    if run_now:
        agente._log("Bypass --now ativo: executando um ciclo completo imediatamente.")
        try:
            agente.run()
        except Exception as e:
            agente._log(f"Erro crítico no ciclo --now: {e}")
        sys.exit(0)

    while True:
        if not is_fishing_window():
            agente._log("Fora da janela de pescaria (00h-02h). Aguardando...")
            time.sleep(seconds_until_next_fishing_window())
            continue

        try:
            agente.run()
        except Exception as e:
            agente._log(f"Erro crítico no ciclo: {e}")

        if is_fishing_window():
            agente._log(f"Ciclo concluído. Descanso mínimo de {NORMAL_REST_SECONDS // 3600}h.")
            time.sleep(NORMAL_REST_SECONDS)
        else:
            agente._log("Ciclo concluído fora da janela. Próximo ciclo aguardará 00h.")
