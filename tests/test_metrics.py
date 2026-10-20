"""Valores de referência da seção 12 do escopo (ano de 2025, sem filtros)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import metrics as m  # noqa: E402
from src.data_loader import load_data_sem_cache  # noqa: E402
from src.model import build_model, filtrar_dimensoes, ocupacao_diaria, recortar  # noqa: E402

TOL = 0.005


@pytest.fixture(scope="module")
def model():
    return build_model(load_data_sem_cache())


@pytest.fixture(scope="module")
def rec(model):
    base = filtrar_dimensoes(model, None, None, None)
    return recortar(base, "2025-01-01", "2025-12-31")


def aprox(v, esperado):
    return v == pytest.approx(esperado, rel=TOL)


def test_noites(rec):
    assert aprox(m.noites_ocupadas(rec), 5498)
    assert m.noites_disponiveis(rec) == 9125


def test_ocupacao(rec):
    assert aprox(m.taxa_ocupacao(rec), 0.6025)


def test_ocupacao_por_categoria(model):
    un = model["unidades"]
    for cat, esperado in [("Quarto Privativo", 0.5955), ("Cama em Dormitório", 0.6080)]:
        ids = un.loc[un["Categoria"] == cat, "ID_Unidade"].tolist()
        r = recortar(filtrar_dimensoes(model, ids, None, None), "2025-01-01", "2025-12-31")
        assert aprox(m.taxa_ocupacao(r), esperado), cat


def test_tarifas_e_receitas(rec):
    assert aprox(m.adr(rec), 271.64)
    assert aprox(m.receita_hospedagem(rec), 1_506_043.23)
    assert aprox(m.revpar(rec), 165.05)
    assert aprox(m.receita_consumos(rec), 375_235.06)
    assert aprox(m.trevpar(rec), 206.17)
    assert aprox(m.comissoes(rec), 168_574.94)


def test_financeiro(rec):
    assert aprox(m.despesas(rec), 1_235_687.37)
    assert aprox(m.gop(rec), 477_015.98)


def test_reservas(rec):
    st = rec.reservas["Status"].value_counts()
    assert len(rec.reservas) == 2279
    assert st.get("Concluída", 0) == 2000
    assert st.get("Cancelada", 0) == 235
    assert st.get("No-show", 0) == 44
    assert aprox(m.taxa_cancelamento(rec), 0.1031)
    assert aprox(m.taxa_noshow(rec), 0.0193)
    assert aprox(m.estadia_media(rec), 2.76)
    assert aprox(m.antecedencia_media(rec), 22.5)


def test_avaliacoes(rec):
    assert m.n_avaliacoes(rec) == 1041
    assert aprox(m.nota_media(rec), 8.78)


def test_ocupacao_nunca_passa_de_100(model):
    n = model["noites"]
    assert not n.duplicated(["Data", "ID_Unidade"]).any(), "unidade com duas reservas na mesma noite"
    base = filtrar_dimensoes(model, None, None, None)
    d = ocupacao_diaria(recortar(base, "2025-01-01", "2026-12-31"), somente_realizada=False)
    assert d["Ocupacao"].max() <= 1.0


def test_divisao_por_zero(model):
    base = filtrar_dimensoes(model, [], [], [])
    r = recortar(base, "2025-01-01", "2025-12-31")
    k = m.kpis(r)
    assert k["ocupacao"] is None and k["adr"] is None and k["nota"] is None


def test_rateio_despesa_por_categoria_soma_o_total(model, rec):
    un = model["unidades"]
    gops = []
    for cat in ["Quarto Privativo", "Cama em Dormitório"]:
        ids = un.loc[un["Categoria"] == cat, "ID_Unidade"].tolist()
        gops.append(m.gop(recortar(filtrar_dimensoes(model, ids, None, None), "2025-01-01", "2025-12-31")))
    assert aprox(sum(gops), m.gop(rec))


def test_serie_mensal_bate_com_total(model, rec):
    base = filtrar_dimensoes(model, None, None, None)
    s = m.serie_mensal(base, pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31"))
    assert aprox(s["Receita_Hospedagem"].sum(), m.receita_hospedagem(rec))
    assert aprox(s["GOP"].sum(), m.gop(rec))
