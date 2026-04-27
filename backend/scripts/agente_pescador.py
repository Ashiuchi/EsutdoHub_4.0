import os
import time
import json
import random
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, time as dtime

# Configurações
BASE_URL = "https://www.pciconcursos.com.br"
REGIONS = ["nacional", "sudeste", "sul", "nordeste", "centro-oeste", "norte"]
# Armazenamento no HD Externo (K: mapeado como /storage_k no Docker)
SAVE_DIR = "/storage_k"
# Logs permanecem na pasta storage persistente
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

    def mark_visited(self, url):
        if url not in self.data["visited_urls"]:
            self.data["visited_urls"].append(url)
            self._save()

    def mark_downloaded(self, filename, url):
        self.data["downloaded_files"].append({
            "filename": filename, 
            "url": url, 
            "timestamp": datetime.now().isoformat()
        })
        self._save()

class AgentePescador:
    def __init__(self):
        self.logger = PescaLogger(LOG_FILE)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # Verifica se o HD externo está montado internamente
        if not os.path.exists("/storage_k"):
            print("AVISO: Unidade /storage_k não encontrada. O script pode falhar ao salvar.")
        
        if not os.path.exists(SAVE_DIR):
            try:
                os.makedirs(SAVE_DIR, exist_ok=True)
                print(f"Diretório de armazenamento criado em: {SAVE_DIR}")
            except Exception as e:
                print(f"ERRO ao criar diretório no HD externo: {e}")

    def is_night_mode(self):
        now = datetime.now().time()
        # Novo Horário: 00:00 às 02:00
        return dtime(0, 0) <= now <= dtime(2, 0)

    def wait_for_night(self):
        if not self.is_night_mode():
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Fora do horário (00:00 - 02:00). Aguardando...")
            while not self.is_night_mode():
                time.sleep(60)

    def slow_down(self):
        wait = random.uniform(5, 15)
        print(f"Slow & Stealth: Dormindo por {wait:.2f}s...")
        time.sleep(wait)

    def fetch_page(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Erro ao buscar {url}: {e}")
            return None

    def download_pdf(self, pdf_url, filename):
        self.wait_for_night()
        
        if not pdf_url.startswith("http"):
            pdf_url = BASE_URL + (pdf_url if pdf_url.startswith("/") else "/" + pdf_url)
            
        try:
            print(f"Baixando edital: {pdf_url}")
            response = requests.get(pdf_url, headers=self.headers, stream=True, timeout=30)
            response.raise_for_status()
            
            filepath = os.path.join(SAVE_DIR, filename)
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.logger.mark_downloaded(filename, pdf_url)
            print(f"Sucesso: {filename} salvo em {SAVE_DIR}")
            return True
        except Exception as e:
            print(f"Falha ao baixar PDF {pdf_url}: {e}")
            return False

    def extract_metadata(self, soup, organ_listing):
        corpo = soup.find('div', id='noticia_corpo') or soup.find('div', class_='noticia') or soup
        text_corpo = corpo.get_text()
        
        meses = "janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
        re_num = r'(\d{2}/\d{2}/(202[0-6]))'
        re_ext = rf'(\d{{1,2}}\s+de\s+({meses})\s+de\s+(202[0-6]))'
        
        year = None
        combined_match = re.search(f"{re_num}|{re_ext}", text_corpo, re.I)
        if combined_match:
            year = int(combined_match.group(2) or combined_match.group(5))

        banca = "DESCONHECIDA"
        patterns = [r'Organizadora:\s*([^<\n\.]+)', r'Banca:\s*([^<\n\.]+)', r'Organização:\s*([^<\n\.]+)']
        for p in patterns:
            match = re.search(p, text_corpo, re.I)
            if match:
                banca = match.group(1).strip()
                break
        
        if banca == "DESCONHECIDA":
            links = soup.find_all('a', href=True)
            banca_keywords = {
                "cebraspe": "CEBRASPE", "cespe": "CEBRASPE",
                "fgv": "FGV", "vunesp": "VUNESP", "fcc": "FCC",
                "cesgranrio": "CESGRANRIO", "idecan": "IDECAN",
                "ibfc": "IBFC", "quadrix": "QUADRIX", "nossorumo": "NOSSO_RUMO"
            }
            for link in links:
                href = link['href'].lower()
                for key, val in banca_keywords.items():
                    if key in href:
                        banca = val
                        break
                if banca != "DESCONHECIDA": break

        return year, banca

    def scrape_contest_detail(self, url, organ_listing):
        if self.logger.is_visited(url):
            return

        self.slow_down()
        html = self.fetch_page(url)
        if not html:
            return

        soup = BeautifulSoup(html, 'html.parser')
        
        edital_link = None
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            text = a.get_text().lower()
            if (".pdf" in href or "pdf" in href) and ("edital" in text or "abertura" in text or "retificado" in text):
                edital_link = a['href']
                break
        
        if not edital_link:
            for a in soup.find_all('a', href=True):
                if a['href'].lower().endswith('.pdf') and "edital" in a['href'].lower():
                    edital_link = a['href']
                    break

        if not edital_link:
            self.logger.mark_visited(url)
            return

        year, banca = self.extract_metadata(soup, organ_listing)
        
        if year and YEAR_MIN <= year <= YEAR_MAX:
            def clean(s):
                s = s.replace("/", "_")
                return re.sub(r'[^\w\s-]', '', s).strip().replace(' ', '_').upper()
            
            fname = f"{year}_{clean(banca)}_{clean(organ_listing)}.pdf"
            if self.download_pdf(edital_link, fname):
                self.logger.mark_visited(url)
        else:
            self.logger.mark_visited(url)

    def run(self):
        print(f"Pescador Iniciado (Storage: {SAVE_DIR} | Janela: 00h-02h)")
        
        for region in REGIONS:
            region_url = f"{BASE_URL}/concursos/{region}/"
            html = self.fetch_page(region_url)
            if not html: continue
                
            soup = BeautifulSoup(html, 'html.parser')
            contest_divs = soup.find_all('div', class_=re.compile(r'^[dna]a$'))
            
            for div in contest_divs:
                link_tag = div.find('a', href=True)
                if not link_tag: continue
                contest_url = BASE_URL + link_tag['href'] if not link_tag['href'].startswith("http") else link_tag['href']
                self.scrape_contest_detail(contest_url, link_tag.get_text().strip())

if __name__ == "__main__":
    agente = AgentePescador()
    while True:
        agente.run()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Ciclo completo. Dormindo 1h antes de re-verificar...")
        time.sleep(3600)
