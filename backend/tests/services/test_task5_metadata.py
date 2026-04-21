import pytest
from app.services.subtractive_service import SubtractiveAgent

def test_extract_metadata_links_and_emails():
    agent = SubtractiveAgent()
    text = """
    Acesse o site http://estudohub.com.br ou https://portal.concursos.gov.br para mais info.
    Dúvidas para suporte@estudohub.com.br ou contato@banca.org.
    Não esqueça de checar http://estudohub.com.br novamente.
    Email repetido: suporte@estudohub.com.br
    """
    
    metadata = agent._extract_metadata(text)
    
    # Verificar Links
    assert len(metadata["links"]) == 2
    assert "http://estudohub.com.br" in metadata["links"]
    assert "https://portal.concursos.gov.br" in metadata["links"]
    
    # Verificar Emails
    assert len(metadata["contact_emails"]) == 2
    assert "suporte@estudohub.com.br" in metadata["contact_emails"]
    assert "contato@banca.org" in metadata["contact_emails"]

def test_extract_metadata_empty():
    agent = SubtractiveAgent()
    metadata = agent._extract_metadata("Texto sem nada especial.")
    assert metadata["links"] == []
    assert metadata["contact_emails"] == []
