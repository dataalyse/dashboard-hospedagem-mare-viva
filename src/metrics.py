"""Dicionário de KPIs (seção 6 do escopo).

Funções puras: recebem DataFrames/recortes já filtrados e devolvem números.
Toda divisão é protegida — retorna None quando o denominador é zero, e o
card exibe "—".
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.model import CANAIS_DIRETOS, STATUS_REALIZADO, Recorte


def div(a, b):
    try:
        if b is None or a is None or pd.isna(b) or b == 0:
            return None
        return float(a) / float(b)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- ocupação e tarifas
def noites_ocupadas(rec: Recorte) -> int:
    return int(len(rec.noites_realizadas))


def noites_disponiveis(rec: Recorte) -> int:
    return int(rec.noites_disponiveis)


def taxa_ocupacao(rec: Recorte):
    return div(noites_ocupadas(rec), noites_disponiveis(rec))


def receita_diarias(rec: Recorte) -> float:
    """Σ Receita_Noite das noites realizadas (sem no-show)."""
    return float(rec.noites_realizadas["Receita_Noite"].sum())


def receita_hospedagem(rec: Recorte) -> float:
    """Noites realizadas + 1ª diária dos no-shows com check-in no período (5.2)."""
    return receita_diarias(rec) + float(rec.noshows["Receita_Hospedagem"].sum())


def comissoes(rec: Recorte) -> float:
    return float(rec.noites_realizadas["Comissao_Noite"].sum()) + float(rec.noshows["Valor_Comissao"].sum())


def adr(rec: Recorte):
    return div(receita_diarias(rec), noites_ocupadas(rec))


def revpar(rec: Recorte):
    return div(receita_hospedagem(rec), noites_disponiveis(rec))


def receita_consumos(rec: Recorte) -> float:
    return float(rec.consumos["Valor_Total"].sum())


def trevpar(rec: Recorte):
    return div(receita_hospedagem(rec) + receita_consumos(rec), noites_disponiveis(rec))


def receita_total(rec: Recorte) -> float:
    return receita_hospedagem(rec) + receita_consumos(rec)


def receita_liquida_canais(rec: Recorte) -> float:
    return receita_hospedagem(rec) - comissoes(rec)


def custo_distribuicao(rec: Recorte):
    return div(comissoes(rec), receita_hospedagem(rec))


def hospedes_noite(rec: Recorte) -> int:
    return int(rec.noites_realizadas["Qtd_Hospedes"].sum())


# ---------------------------------------------------------------- financeiro
def despesas(rec: Recorte) -> float:
    return float(rec.despesas["Valor_Periodo"].sum()) if len(rec.despesas) else 0.0


def gop(rec: Recorte) -> float:
    return receita_total(rec) - comissoes(rec) - despesas(rec)


def margem_gop(rec: Recorte):
    return div(gop(rec), receita_total(rec))


def goppar(rec: Recorte):
    return div(gop(rec), noites_disponiveis(rec))


def cpor(rec: Recorte):
    return div(despesas(rec), noites_ocupadas(rec))


# ---------------------------------------------------------------- reservas
def reservas_realizadas(rec: Recorte) -> pd.DataFrame:
    return rec.reservas[rec.reservas["Status"].isin(STATUS_REALIZADO)]


def total_reservas(rec: Recorte) -> int:
    return int(len(rec.reservas))


def taxa_cancelamento(rec: Recorte):
    return div((rec.reservas["Status"] == "Cancelada").sum(), len(rec.reservas))


def taxa_noshow(rec: Recorte):
    return div((rec.reservas["Status"] == "No-show").sum(), len(rec.reservas))


def estadia_media(rec: Recorte):
    r = reservas_realizadas(rec)
    return float(r["Noites"].mean()) if len(r) else None


def antecedencia_media(rec: Recorte):
    r = reservas_realizadas(rec)
    return float(r["Antecedencia_Dias"].mean()) if len(r) else None


def pct_diretas(rec: Recorte):
    r = reservas_realizadas(rec)
    return div(r["Canal"].isin(CANAIS_DIRETOS).sum(), len(r))


# ---------------------------------------------------------------- hóspedes
def hospedes_unicos(rec: Recorte) -> int:
    return int(rec.noites_realizadas["ID_Hospede"].nunique())


def gasto_extra_por_hospede(rec: Recorte):
    return div(receita_consumos(rec), hospedes_unicos(rec))


def taxa_recorrencia(rec: Recorte):
    ids = rec.noites_realizadas["ID_Hospede"].unique()
    if len(ids) == 0:
        return None
    h = rec.hospedes_hist
    rec_ids = h.loc[h["Reservas_Realizadas"] >= 2, "ID_Hospede"]
    return div(np.isin(ids, rec_ids).sum(), len(ids))


def pct_estrangeiros(rec: Recorte):
    r = reservas_realizadas(rec)
    if not len(r):
        return None
    hosp = r.drop_duplicates("ID_Hospede")
    return div((hosp["Pais"] != "Brasil").sum(), len(hosp))


# ---------------------------------------------------------------- experiência
def nota_media(rec: Recorte):
    a = rec.avaliacoes
    return float(a["Nota_Geral"].mean()) if len(a) else None


def n_avaliacoes(rec: Recorte) -> int:
    return int(len(rec.avaliacoes))


def pct_recomendaria(rec: Recorte):
    a = rec.avaliacoes
    return div((a["Recomendaria"] == "Sim").sum(), len(a))


def taxa_avaliacao(rec: Recorte):
    concl = (rec.reservas["Status"] == "Concluída").sum()
    return div(len(rec.avaliacoes), concl)


# ---------------------------------------------------------------- metas
def meta_ocupacao(rec: Recorte):
    m = rec.metas
    return div((m["Meta_Ocupacao"] * m["Peso_Dias"]).sum(), m["Peso_Dias"].sum()) if len(m) else None


def meta_adr(rec: Recorte):
    m = rec.metas
    return div((m["Meta_ADR"] * m["Peso_Dias"]).sum(), m["Peso_Dias"].sum()) if len(m) else None


def meta_receita(rec: Recorte):
    m = rec.metas
    return float((m["Meta_Receita_Hospedagem"] * m["Fracao"]).sum()) if len(m) else None


def meta_nota(rec: Recorte):
    m = rec.metas
    return div((m["Meta_Nota_Media"] * m["Peso_Dias"]).sum(), m["Peso_Dias"].sum()) if len(m) else None


def atingimento(realizado, meta):
    return div(realizado, meta)


# ---------------------------------------------------------------- pacote de KPIs
def kpis(rec: Recorte) -> dict:
    return {
        "ocupacao": taxa_ocupacao(rec),
        "adr": adr(rec),
        "revpar": revpar(rec),
        "trevpar": trevpar(rec),
        "noites_ocupadas": noites_ocupadas(rec),
        "noites_disponiveis": noites_disponiveis(rec),
        "hospedes_noite": hospedes_noite(rec),
        "receita_hospedagem": receita_hospedagem(rec),
        "receita_consumos": receita_consumos(rec),
        "receita_total": receita_total(rec),
        "comissoes": comissoes(rec),
        "receita_liquida": receita_liquida_canais(rec),
        "custo_distribuicao": custo_distribuicao(rec),
        "reservas": total_reservas(rec),
        "cancelamento": taxa_cancelamento(rec),
        "noshow": taxa_noshow(rec),
        "estadia_media": estadia_media(rec),
        "antecedencia": antecedencia_media(rec),
        "pct_diretas": pct_diretas(rec),
        "hospedes_unicos": hospedes_unicos(rec),
        "gasto_extra": gasto_extra_por_hospede(rec),
        "recorrencia": taxa_recorrencia(rec),
        "estrangeiros": pct_estrangeiros(rec),
        "nota": nota_media(rec),
        "n_avaliacoes": n_avaliacoes(rec),
        "recomendaria": pct_recomendaria(rec),
        "taxa_avaliacao": taxa_avaliacao(rec),
        "meta_ocupacao": meta_ocupacao(rec),
        "meta_adr": meta_adr(rec),
        "meta_receita": meta_receita(rec),
        "meta_nota": meta_nota(rec),
    }


def kpis_lucro(rec: Recorte) -> dict:
    """KPIs que dependem de despesa — chamar com recorte limitado aos meses com despesa lançada."""
    return {
        "receita_total": receita_total(rec),
        "receita_hospedagem": receita_hospedagem(rec),
        "receita_consumos": receita_consumos(rec),
        "comissoes": comissoes(rec),
        "despesas": despesas(rec),
        "gop": gop(rec),
        "margem": margem_gop(rec),
        "goppar": goppar(rec),
        "cpor": cpor(rec),
    }


# ---------------------------------------------------------------- quebras por dimensão
def receita_por(rec: Recorte, col: str) -> pd.DataFrame:
    """Receita de hospedagem (5.2), comissões e noites por uma coluna (Canal, Tipo, Categoria…)."""
    n = rec.noites_realizadas.groupby(col).agg(
        Receita_Diarias=("Receita_Noite", "sum"), Comissao=("Comissao_Noite", "sum"), Noites=("ID_Reserva", "size"),
    )
    ns = rec.noshows.groupby(col).agg(Receita_NS=("Receita_Hospedagem", "sum"), Comissao_NS=("Valor_Comissao", "sum"))
    df = n.join(ns, how="outer").fillna(0)
    df["Receita"] = df["Receita_Diarias"] + df["Receita_NS"]
    df["Comissao"] = df["Comissao"] + df["Comissao_NS"]
    df["ADR"] = df["Receita_Diarias"] / df["Noites"].replace(0, np.nan)
    return df[["Receita", "Comissao", "Noites", "ADR", "Receita_Diarias"]].reset_index()


def media_criterios(aval: pd.DataFrame) -> dict:
    from src.model import CRITERIOS
    if not len(aval):
        return {nome: None for nome in CRITERIOS.values()}
    return {nome: float(aval[col].mean()) for col, nome in CRITERIOS.items()}


# ---------------------------------------------------------------- séries mensais
def serie_mensal(base: dict, inicio, fim) -> pd.DataFrame:
    """KPIs por mês (AAAA-MM) para o intervalo, calculados por agregação vetorizada."""
    inicio, fim = pd.Timestamp(inicio), pd.Timestamp(fim)
    meses = pd.period_range(inicio, fim, freq="M")
    if len(meses) == 0:
        return pd.DataFrame()
    df = pd.DataFrame({"Ano_Mes": meses.strftime("%Y-%m")})
    ini_m = np.maximum(meses.start_time.normalize().values, np.datetime64(inicio))
    fim_m = np.minimum(meses.end_time.normalize().values, np.datetime64(fim))
    df["Dias"] = (fim_m - ini_m).astype("timedelta64[D]").astype(int) + 1
    df["Noites_Disp"] = df["Dias"] * base["n_unidades"]

    n = base["noites"]
    n = n[(n["Data"] >= inicio) & (n["Data"] <= fim) & n["Realizada"]]
    gn = n.groupby("Ano_Mes").agg(
        Noites=("ID_Reserva", "size"), Receita_Diarias=("Receita_Noite", "sum"),
        Comissao_Noites=("Comissao_Noite", "sum"),
    )
    r = base["reservas"]
    ns = r[(r["Status"] == "No-show") & (r["Check_in"] >= inicio) & (r["Check_in"] <= fim)]
    gns = ns.groupby("Ano_Mes_CI").agg(Receita_NS=("Receita_Hospedagem", "sum"), Comissao_NS=("Valor_Comissao", "sum"))
    gns.index.name = "Ano_Mes"
    c = base["consumos"]
    c = c[(c["Data"] >= inicio) & (c["Data"] <= fim)]
    gc = c.groupby("Ano_Mes").agg(Consumos=("Valor_Total", "sum"))
    a = base["avaliacoes"]
    a = a[(a["Data_Avaliacao"] >= inicio) & (a["Data_Avaliacao"] <= fim)]
    ga = a.groupby("Ano_Mes").agg(Nota=("Nota_Geral", "mean"), N_Aval=("Nota_Geral", "size"))
    d = base["despesas"]
    gd = d.groupby("Ano_Mes").agg(Despesas=("Valor", "sum")) * base.get("fator_despesa", 1.0)
    gm = base["metas"].set_index("Ano_Mes")[["Meta_Ocupacao", "Meta_Receita_Hospedagem", "Meta_ADR", "Meta_Nota_Media"]]

    df = df.set_index("Ano_Mes").join([gn, gns, gc, ga, gd, gm]).reset_index()
    for col in ["Noites", "Receita_Diarias", "Comissao_Noites", "Receita_NS", "Comissao_NS", "Consumos"]:
        df[col] = df[col].fillna(0)
    frac = df["Dias"] / pd.PeriodIndex(df["Ano_Mes"], freq="M").days_in_month
    df["Despesas"] = df["Despesas"] * frac  # NaN quando o mês não tem despesa lançada
    df["Receita_Hospedagem"] = df["Receita_Diarias"] + df["Receita_NS"]
    df["Comissoes"] = df["Comissao_Noites"] + df["Comissao_NS"]
    df["Receita_Total"] = df["Receita_Hospedagem"] + df["Consumos"]
    df["Ocupacao"] = df["Noites"] / df["Noites_Disp"].replace(0, np.nan)
    df["ADR"] = df["Receita_Diarias"] / df["Noites"].replace(0, np.nan)
    df["RevPAR"] = df["Receita_Hospedagem"] / df["Noites_Disp"].replace(0, np.nan)
    df["GOP"] = df["Receita_Total"] - df["Comissoes"] - df["Despesas"]
    df["Margem"] = df["GOP"] / df["Receita_Total"].replace(0, np.nan)
    df["Meta_Receita_Hospedagem"] = df["Meta_Receita_Hospedagem"] * frac
    df["Data_Mes"] = pd.PeriodIndex(df["Ano_Mes"], freq="M").start_time
    return df
