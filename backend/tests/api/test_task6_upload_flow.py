import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import shutil
import os
from main import app

client = TestClient(app)

def test_upload_flow_integration(tmp_path):
    # Mockando o storage base para não poluir o projeto real durante testes
    from app.services import subtractive_service
    original_storage = subtractive_service.STORAGE_BASE
    subtractive_service.STORAGE_BASE = tmp_path
    
    # Criar um PDF fake (ou usar um real pequeno se disponível)
    # Aqui vamos mockar o PDFService.to_markdown para focar no fluxo do endpoint
    from unittest.mock import patch
    
    mock_md = """
# Edital Teste
| Tabela 1 | Info |
|---|---|
| Dado 1 | Dado 2 |

Link: http://teste.com
Contato: contato@teste.com
"""
    
    with patch("app.api.endpoints.PDFService.to_markdown", return_value=mock_md):
        # Simular upload
        pdf_content = b"%PDF-1.4 test content"
        response = client.post(
            "/upload",
            files={"file": ("test.pdf", pdf_content, "application/pdf")}
        )
        
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "ingestado"
    assert data["total_tables"] == 1
    assert data["total_links"] == 1
    
    # Verificar se arquivos foram criados no tmp_path
    content_hash = data["content_hash"]
    storage_path = tmp_path / content_hash
    
    assert storage_path.exists()
    assert (storage_path / "main.md").exists()
    assert (storage_path / "tables" / "tabela_0.md").exists()
    assert (storage_path / "metadata.json").exists()
    
    # Limpar/Restaurar
    subtractive_service.STORAGE_BASE = original_storage
