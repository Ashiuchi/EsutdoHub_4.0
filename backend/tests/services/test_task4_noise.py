import pytest
from app.services.subtractive_service import SubtractiveAgent

def test_suppress_noise_removes_repetitive_footer():
    agent = SubtractiveAgent()
    
    # Simular 10 páginas com um rodapé repetitivo
    pages = []
    for i in range(10):
        content = f"Conteúdo da página {i}\nLinha importante {i}\nRodapé Padrão v1.0"
        pages.append(content)
    
    md_with_noise = "\n---\n".join(pages)
    
    clean_md = agent._suppress_noise(md_with_noise)
    
    # Verificar se o rodapé sumiu
    assert "Rodapé Padrão v1.0" not in clean_md
    # Verificar se conteúdo importante ficou
    assert "Conteúdo da página 0" in clean_md
    assert "Conteúdo da página 9" in clean_md

def test_suppress_noise_keeps_rare_lines():
    agent = SubtractiveAgent()
    
    # Linha que aparece em apenas 2 de 10 páginas (20% < 30%)
    pages = [f"Página {i}\nTexto comum" for i in range(10)]
    pages[0] += "\nObservação Única"
    pages[1] += "\nObservação Única"
    
    md = "\n---\n".join(pages)
    clean_md = agent._suppress_noise(md)
    
    # Deve manter a observação pois não atingiu o threshold de 30% (3 páginas)
    assert "Observação Única" in clean_md

def test_suppress_noise_ignores_short_lines():
    agent = SubtractiveAgent()
    
    # Linha curta (ex: "Page") repetida 10 vezes
    pages = [f"Conteúdo {i}\nPage" for i in range(10)]
    md = "\n---\n".join(pages)
    
    clean_md = agent._suppress_noise(md)
    
    # Deve manter "Page" porque tem menos de 5 caracteres (critério de segurança)
    assert "Page" in clean_md
