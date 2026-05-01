import os
import time
import json
import random
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, time as dtime
from urllib.parse import urljoin

# Configurações
PCI_BASE_URL = "https://www.pciconcursos.com.br"
CNB_BASE_URL = "https://concursosnobrasil.com.br"

# Novas Rotas de Bancas (Elite)
BANCAS_CONFIG = {
    "CESGRANRIO": "https://www.cesgranrio.org.br/concursos/",
    "CESGRANRIO_CNU": "https://cpnu.cesgranrio.org.br/página-inicial", # Exemplo de rota CNU
    "CEBRASPE_ANDAMENTO": "https://www.cebraspe.org.br/concursos/em-andamento/",
    "FGV": "https://conhecimento.fgv.br/concursos",
    "VUNESP": "https://www.vunesp.com.br/busca/concurso/encerrados"
}

# User-Agents para rotação e combate a bloqueios
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"
]

SAVE_DIR = "/storage_k"
LOG_FILE = "storage/pescaria_log.json"
YEAR_MIN = 2020
YEAR_MAX = 2026

class PescaLogger:
    def __init__(self, log_path):
        self.log_path = log_path
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"visited_urls": [], "downloaded_files": []}

    def _save(self):
        with open(self.log_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def is_visited(self, url):
        return url in self.data["visited_urls"]

    def is_downloaded_by_contest_url(self, contest_url):
        for entry in self.data["downloaded_files"]:
            if entry.get("contest_url") == contest_url:
                return True
        return False

    def mark_visited(self, url):
        if url not in self.data["visited_urls"]:
            self.data["visited_urls"].append(url)
            self._save()

    def mark_downloaded(self, filename, pdf_url, contest_url=None):
        self.data["downloaded_files"].append({
            "filename": filename, 
            "pdf_url": pdf_url, 
            "contest_url": contest_url,
            "timestamp": datetime.now().isoformat()
        })
        self._save()

class AgentePescador:
    def __init__(self):
        self.logger = PescaLogger(LOG_FILE)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENTS[0]})
        
        if not os.path.exists(SAVE_DIR):
            try:
                os.makedirs(SAVE_DIR, exist_ok=True)
            except Exception as e:
                print(f"ERRO ao criar diretório: {e}")

    def is_night_mode(self):
        now = datetime.now().time()
        return dtime(0, 0) <= now <= dtime(2, 0)

    def wait_for_night(self):
        if not self.is_night_mode():
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Fora da janela 00h-02h. Aguardando...")
            while not self.is_night_mode():
                time.sleep(60)

    def slow_down(self, fast=False):
        wait = random.uniform(1, 3) if fast else random.uniform(3, 8)
        time.sleep(wait)

    def fetch_page(self, url, mobile=False):
        headers = {"User-Agent": USER_AGENTS[1] if mobile else USER_AGENTS[0]}
        try:
            response = self.session.get(url, headers=headers, timeout=20)
            if response.status_code == 403 and not mobile:
                print(f"!!! 403 detectado em {url}. Retentando com Mobile UA...")
                return self.fetch_page(url, mobile=True)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Erro ao buscar {url}: {e}")
            return None

    def is_edital_link(self, href, text):
        href = href.lower()
        text = text.lower()
        # Lógica flexível de detecção
        is_pdf_like = href.endswith(".pdf") or "download" in href or "get_file" in href or "portal" in href or "arquivo" in href
        is_edital_text = any(kw in text for kw in ["edital", "abertura", "retificação", "regulamento", "anexo", "normativo"])
        return is_pdf_like and is_edital_text

    def download_pdf(self, pdf_url, filename, contest_url=None, ignore_night_mode=False, mobile=False):
        if not ignore_night_mode:
            self.wait_for_night()
        
        headers = {"User-Agent": USER_AGENTS[1] if mobile else USER_AGENTS[0]}
        try:
            print(f">>> [FISGADO] Tentando baixar de: {pdf_url}")
            response = self.session.get(pdf_url, headers=headers, stream=True, timeout=60)
            if response.status_code == 403 and not mobile:
                return self.download_pdf(pdf_url, filename, contest_url, ignore_night_mode, mobile=True)
            response.raise_for_status()
            
            filepath = os.path.join(SAVE_DIR, filename)
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.logger.mark_downloaded(filename, pdf_url, contest_url)
            print(f"SUCESSO: {filename}")
            return True
        except Exception as e:
            print(f"FALHA: {e}")
            return False

    def clean_filename(self, year, banca, organ):
        fname = f"{year}_{banca}_{organ}.pdf".replace(' ', '_')
        fname = re.sub(r'[^\w\s\.-]', '', fname).upper()
        return fname[:150] # Limite de tamanho

    def scrape_cesgranrio(self, bypass=False):
        print("Scraping CESGRANRIO (Geral + CNU)...")
        # Geral
        html = self.fetch_page(BANCAS_CONFIG["CESGRANRIO"])
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            for a in soup.find_all('a', href=True):
                if "detalhe" in a['href'].lower() or "/concursos/" in a['href'].lower():
                    url = urljoin(BANCAS_CONFIG["CESGRANRIO"], a['href'])
                    if not bypass and self.logger.is_visited(url): continue
                    self.slow_down(fast=bypass)
                    detail_html = self.fetch_page(url)
                    if not detail_html: continue
                    detail_soup = BeautifulSoup(detail_html, 'html.parser')
                    for pdf_a in detail_soup.find_all('a', href=True):
                        if self.is_edital_link(pdf_a['href'], pdf_a.get_text()):
                            pdf_url = urljoin(url, pdf_a['href'])
                            organ = detail_soup.find(['h1', 'h2'])
                            organ_name = organ.get_text().strip() if organ else "CESGRANRIO_CONCURSO"
                            fname = self.clean_filename(datetime.now().year, "CESGRANRIO", organ_name)
                            if self.download_pdf(pdf_url, fname, url, ignore_night_mode=bypass):
                                self.logger.mark_visited(url)
                                break
        
        # CNU Foco
        print("Scraping CNU (Cesgranrio)...")
        cnu_html = self.fetch_page("https://www.gov.br/gestao/pt-br/concursonacional/editais") # URL oficial de editais gov.br
        if cnu_html:
            cnu_soup = BeautifulSoup(cnu_html, 'html.parser')
            for a in cnu_soup.find_all('a', href=True):
                if self.is_edital_link(a['href'], a.get_text()) or "bloco" in a.get_text().lower():
                    pdf_url = urljoin("https://www.gov.br", a['href'])
                    fname = self.clean_filename(2024, "CNU", a.get_text().strip())
                    self.download_pdf(pdf_url, fname, "CNU_GOV_BR", ignore_night_mode=bypass)

        # BB e CAIXA (Sempre Cesgranrio)
        for target in ["Banco do Brasil", "Caixa"]:
            print(f"Buscando especificamente por {target} na Cesgranrio...")
            # Aqui poderíamos adicionar uma busca via Google ou rotas específicas se soubermos,
            # mas por enquanto vamos forçar o re-scan da página de concursos da Cesgranrio
            # com foco em palavras-chave no texto.
            self.scrape_cesgranrio(bypass=True) # Re-scans detail pages

    def scrape_cebraspe(self, url, bypass=False):
        print(f"Scraping CEBRASPE ({url})...")
        html = self.fetch_page(url)
        if not html: return
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "/concursos/" in a['href'] and len(a['href'].split('/')) > 4:
                contest_url = urljoin(url, a['href'])
                if not bypass and self.logger.is_visited(contest_url): continue
                self.slow_down(fast=bypass)
                detail_html = self.fetch_page(contest_url)
                if not detail_html: continue
                detail_soup = BeautifulSoup(detail_html, 'html.parser')
                found = False
                for row in detail_soup.find_all(['tr', 'li']):
                    pdf_link = row.find('a', href=True)
                    if pdf_link and self.is_edital_link(pdf_link['href'], row.get_text()):
                        pdf_url = urljoin(contest_url, pdf_link['href'])
                        h2 = detail_soup.find('h2')
                        organ_name = h2.get_text().strip() if h2 else "CEBRASPE_CONCURSO"
                        fname = self.clean_filename(datetime.now().year, "CEBRASPE", organ_name)
                        if self.download_pdf(pdf_url, fname, contest_url, ignore_night_mode=bypass):
                            self.logger.mark_visited(contest_url)
                            found = True
                            break
                if not found: self.logger.mark_visited(contest_url)

    def scrape_fgv(self, bypass=False):
        print("Scraping FGV...")
        html = self.fetch_page(BANCAS_CONFIG["FGV"])
        if not html: return
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "/concursos/" in a['href'] and len(a['href'].split('/')) > 4:
                url = urljoin(BANCAS_CONFIG["FGV"], a['href'])
                if not bypass and self.logger.is_visited(url): continue
                self.slow_down(fast=bypass)
                detail_html = self.fetch_page(url)
                if not detail_html: continue
                detail_soup = BeautifulSoup(detail_html, 'html.parser')
                for pdf_a in detail_soup.find_all('a', href=True):
                    if self.is_edital_link(pdf_a['href'], pdf_a.get_text()):
                        pdf_url = urljoin(url, pdf_a['href'])
                        organ = detail_soup.find('h1')
                        organ_name = organ.get_text().strip() if organ else "FGV_CONCURSO"
                        fname = self.clean_filename(datetime.now().year, "FGV", organ_name)
                        if self.download_pdf(pdf_url, fname, url, ignore_night_mode=bypass):
                            self.logger.mark_visited(url)
                            break

    def scrape_vunesp(self, bypass=False):
        print("Scraping VUNESP...")
        html = self.fetch_page(BANCAS_CONFIG["VUNESP"])
        if not html: return
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "/concurso/" in a['href'].lower() and "detalhe" not in a['href'].lower():
                url = urljoin("https://www.vunesp.com.br", a['href'])
                if not bypass and self.logger.is_visited(url): continue
                self.slow_down(fast=bypass)
                detail_html = self.fetch_page(url)
                if not detail_html: continue
                detail_soup = BeautifulSoup(detail_html, 'html.parser')
                for pdf_a in detail_soup.find_all('a', href=True):
                    if self.is_edital_link(pdf_a['href'], pdf_a.get_text()):
                        pdf_url = urljoin(url, pdf_a['href'])
                        organ = detail_soup.find('h1')
                        organ_name = organ.get_text().strip() if organ else "VUNESP_CONCURSO"
                        fname = self.clean_filename(datetime.now().year, "VUNESP", organ_name)
                        if self.download_pdf(pdf_url, fname, url, ignore_night_mode=bypass):
                            self.logger.mark_visited(url)
                            break

    def run(self):
        print(f">>> JORNADA DE PESCARIA: {datetime.now()} <<<")
        self.scrape_cesgranrio(bypass=True)
        self.scrape_cebraspe(BANCAS_CONFIG["CEBRASPE_ANDAMENTO"], bypass=True)
        self.scrape_fgv(bypass=True)
        self.scrape_vunesp(bypass=True)

if __name__ == "__main__":
    agente = AgentePescador()
    while True:
        try:
            agente.run()
        except Exception as e:
            print(f"Erro no ciclo: {e}")
        
        # Lógica de Overtime: se houver um arquivo .overtime, espera apenas 1 minuto
        if os.path.exists("storage/overtime.signal"):
            print(">>> MODO OVERTIME ATIVO: Próximo ciclo em 1 minuto...")
            time.sleep(60)
        else:
            print(f"Ciclo concluído. Aguardando 1h...")
            time.sleep(3600)
