import pytest
from app.services.subtractive_service import SubtractiveAgent

def test_format_table_md_fixes_messy_table():
    agent = SubtractiveAgent()
    messy_table = """
| Cargo | Vagas |   Salário   |
|:---|---|:---:|
|  Analista de TI  | 05 |  R$ 10.000,00  |
| Técnico Judiciário | 20 | R$ 6.000,00 |
"""
    formatted = agent._format_table_md(messy_table)
    
    # Verificar se colunas estão presentes
    assert "Cargo" in formatted
    assert "Vagas" in formatted
    assert "Salário" in formatted
    
    # Verificar limpeza de espaços
    assert "  Analista de TI  " not in formatted
    assert "Analista de TI" in formatted
    
    # Pandas to_markdown gera separadores consistentes
    assert "|" in formatted
    lines = formatted.strip().splitlines()
    assert len(lines) >= 3 # Header, separator, data

def test_format_table_md_fallback_on_invalid():
    agent = SubtractiveAgent()
    invalid_table = "Não sou uma tabela"
    # Deve retornar o original graciosamente
    formatted = agent._format_table_md(invalid_table)
    assert formatted == invalid_table

def test_format_table_md_handles_outer_pipes():
    agent = SubtractiveAgent()
    table_with_pipes = """
| Header 1 | Header 2 |
|----------|----------|
| Value 1  | Value 2  |
"""
    formatted = agent._format_table_md(table_with_pipes)
    # Pandas não deve criar colunas "Unnamed" se os pipes forem bem tratados
    assert "Unnamed" not in formatted
    assert "Header 1" in formatted
    assert "Value 1" in formatted
