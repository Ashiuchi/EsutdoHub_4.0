import pytest
from app.services.cargo_auditor import CargoAuditorAgent, AuditResult
from app.schemas.edital_schema import Cargo


def _cargo(**kwargs) -> Cargo:
    defaults = dict(
        titulo="Analista Judiciário",
        salario=8000.0,
        escolaridade="Ensino Superior em Direito",
        vagas_total="10",
        atribuicoes="Analisar, Instruir",
        requisitos="Graduação em Direito",
        jornada="40h semanais",
    )
    defaults.update(kwargs)
    return Cargo(**defaults)


# ── _is_noise ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("titulo", [
    "Anexo II",
    "Anexo 3",
    "Tabela 1",
    "Quadro I",
    "Taxas de Inscrição",
    "1. Cargo Auxiliar",
    "total",
    "SUBTOTAL",
    "Observação",
    "Obs.",
    "Nota 1",
])
def test_is_noise_true(titulo):
    agent = CargoAuditorAgent()
    assert agent._is_noise(titulo) is True


@pytest.mark.parametrize("titulo", [
    "Analista Judiciário",
    "Técnico de TI",
    "Engenheiro Civil",
    "Agente Administrativo",
    "Médico - Clínica Geral",
])
def test_is_noise_false(titulo):
    agent = CargoAuditorAgent()
    assert agent._is_noise(titulo) is False


# ── _score_dimensions ────────────────────────────────────────────────────────

def test_score_salario_present():
    agent = CargoAuditorAgent()
    dims = agent._score_dimensions(_cargo(salario=5000.0))
    assert dims.salario == 3


def test_score_salario_zero():
    agent = CargoAuditorAgent()
    dims = agent._score_dimensions(_cargo(salario=0.0))
    assert dims.salario == 0


def test_score_escolaridade_filled():
    agent = CargoAuditorAgent()
    dims = agent._score_dimensions(_cargo(escolaridade="Ensino Superior"))
    assert dims.escolaridade == 3


def test_score_escolaridade_pendente():
    agent = CargoAuditorAgent()
    dims = agent._score_dimensions(_cargo(escolaridade="Pendente"))
    assert dims.escolaridade == 0


def test_score_escolaridade_nao_informada():
    agent = CargoAuditorAgent()
    dims = agent._score_dimensions(_cargo(escolaridade="Não informada"))
    assert dims.escolaridade == 0


def test_score_vagas_total_present():
    agent = CargoAuditorAgent()
    dims = agent._score_dimensions(_cargo(vagas_total="5"))
    assert dims.vagas == 2


def test_score_vagas_partial_only():
    agent = CargoAuditorAgent()
    dims = agent._score_dimensions(_cargo(vagas_total="0", vagas_pcd="2"))
    assert dims.vagas == 1


def test_score_vagas_all_zero():
    agent = CargoAuditorAgent()
    dims = agent._score_dimensions(_cargo(vagas_total="0", vagas_pcd="0"))
    assert dims.vagas == 0


def test_score_detalhes_two_filled():
    agent = CargoAuditorAgent()
    dims = agent._score_dimensions(_cargo(
        atribuicoes="Analisar", requisitos="Graduação", jornada="Não informada"
    ))
    assert dims.detalhes == 2


def test_score_detalhes_one_filled():
    agent = CargoAuditorAgent()
    dims = agent._score_dimensions(_cargo(
        atribuicoes="Analisar", requisitos="Não informada", jornada="Não informada"
    ))
    assert dims.detalhes == 1


def test_score_detalhes_none_filled():
    agent = CargoAuditorAgent()
    dims = agent._score_dimensions(_cargo(
        atribuicoes="Não informada", requisitos="Não informada", jornada="Não informada"
    ))
    assert dims.detalhes == 0


# ── audit ────────────────────────────────────────────────────────────────────

def test_audit_aprovado():
    agent = CargoAuditorAgent()
    results = agent.audit([_cargo()])
    assert len(results) == 1
    r = results[0]
    assert r.verdict == "aprovado"
    assert r.score >= 6
    assert r.is_noise is False


def test_audit_quarentena_zero_salario_zero_escolaridade():
    agent = CargoAuditorAgent()
    c = _cargo(salario=0.0, escolaridade="Pendente", vagas_total="0", atribuicoes="Não informada")
    results = agent.audit([c])
    r = results[0]
    assert r.verdict == "quarentena"
    assert r.score < 6


def test_audit_noise_is_discarded_flag():
    agent = CargoAuditorAgent()
    results = agent.audit([_cargo(titulo="Anexo II")])
    r = results[0]
    assert r.is_noise is True


def test_audit_mixed_batch():
    agent = CargoAuditorAgent()
    cargos = [
        _cargo(titulo="Analista Judiciário"),                          # aprovado
        _cargo(titulo="Técnico", salario=0.0, escolaridade="Pendente",
               vagas_total="0", atribuicoes="Não informada",
               requisitos="Não informada", jornada="Não informada"),  # quarentena
        _cargo(titulo="Anexo II"),                                     # ruído
    ]
    results = agent.audit(cargos)
    assert len(results) == 3

    by_title = {r.cargo.titulo: r for r in results}
    assert by_title["Analista Judiciário"].verdict == "aprovado"
    assert by_title["Técnico"].verdict == "quarentena"
    assert by_title["Anexo II"].is_noise is True


def test_audit_score_max():
    agent = CargoAuditorAgent()
    results = agent.audit([_cargo()])
    assert results[0].score == 10


def test_audit_dimensions_sum_equals_score():
    agent = CargoAuditorAgent()
    results = agent.audit([_cargo()])
    r = results[0]
    total = r.dimensions.salario + r.dimensions.escolaridade + r.dimensions.vagas + r.dimensions.detalhes
    assert total == r.score
