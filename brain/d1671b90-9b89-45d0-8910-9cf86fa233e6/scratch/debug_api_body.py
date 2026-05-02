import requests

url = "https://concursos.cesgranrio.org.br/gpoweb-prd-hibrido3/eventos"
headers = {"User-Agent": "Mozilla/5.0"}
resp = requests.get(url, headers=headers)
print(f"Status: {resp.status_code}")
print(f"Body Length: {len(resp.text)}")
print(f"Body Start: {resp.text[:500]}")
