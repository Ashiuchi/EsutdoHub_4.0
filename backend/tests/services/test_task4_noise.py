import pytest
from app.services.subtractive_service import SubtractiveAgent

def test_suppress_noise_removes_repetitive_footer():
    agent = SubtractiveAgent()

    # _normalize() substitui dígitos no FIM da linha por '#'.
    # Conteúdo com número no MEIO ("Seção 0 - texto") permanece único por página
    # e não colapsa para a mesma forma normalizada — portanto não é ruído.
    # O rodapé fixo "Rodapé Padrão v1.0" → "Rodapé Padrão v1.#" é idêntico
    # em todas as páginas e ultrapassa o threshold → é removido.
    pages = []
    for i in range(10):
        content = (
            f"Seção {i} - Disposições gerais desta parte\n"
            f"Artigo {i} descreve os requisitos específicos\n"
            "Rodapé Padrão v1.0"
        )
        pages.append(content)

    md_with_noise = "\n---\n".join(pages)
    clean_md = agent._suppress_noise(md_with_noise)

    assert "Rodapé Padrão v1.0" not in clean_md
    assert "Seção 0 - Disposições gerais desta parte" in clean_md
    assert "Seção 9 - Disposições gerais desta parte" in clean_md

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
