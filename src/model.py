"""Tabelas derivadas do modelo e recorte por período.

Regra de ouro da hotelaria: ocupação, ADR e receita são medidas POR NOITE.
Uma reserva de 28/01 a 03/02 contribui com noites em dois meses diferentes,
por isso tudo parte de `fNoites` (uma linha por reserva × noite).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DATA_REF = pd.Timestamp("2026-10-18")

STATUS_OCUPA = ["Concluída", "Hospedado", "Confirmada"]
STATUS_REALIZADO = ["Concluída", "Hospedado"]
CANAIS_DIRETOS = ["Direto (WhatsApp/Telefone)", "Site Próprio"]
CRITERIOS = {
    "Limpeza": "Limpeza",
    "Atendimento": "Atendimento",
    "Localizacao": "Localização",
    "Conforto": "Conforto",
    "Cafe_da_Manha": "Café da manhã",
    "Custo_Beneficio": "Custo-benefício",
    "Wifi": "Wi-Fi",
}


# ---------------------------------------------------------------- construção do modelo
def _explodir_noites(reservas: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por noite, de Check_in até Check_out − 1 dia (vetorizado)."""
    r = reservas[reservas["Status"].isin(STATUS_OCUPA)].copy()
    r["Noites"] = (r["Check_out"] - r["Check_in"]).dt.days.clip(lower=0).astype(int)
    r = r[r["Noites"] > 0]
    rep = r.loc[r.index.repeat(r["Noites"])].copy()
    deslocamento = rep.groupby(level=0).cumcount()
    rep["Data"] = rep["Check_in"] + pd.to_timedelta(deslocamento, unit="D")
    rep = rep.reset_index(drop=True)
    noites = pd.DataFrame({
        "Data": rep["Data"],
        "ID_Reserva": rep["ID_Reserva"],
        "ID_Unidade": rep["ID_Unidade"],
        "ID_Hospede": rep["ID_Hospede"],
        "Canal": rep["Canal"],
        "Status": rep["Status"],
        "Qtd_Hospedes": rep["Qtd_Hospedes"],
        "Receita_Noite": rep["Tarifa_Media_Diaria"],
        "Comissao_Noite": rep["Tarifa_Media_Diaria"] * rep["Taxa_Comissao"],
        "Realizada": rep["Status"] != "Confirmada",
        "Data_Reserva": rep["Data_Reserva"],
        "Check_in": rep["Check_in"],
    })
    return noites


def build_model(dfs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    un = dfs["dUnidades"].copy()
    hosp = dfs["dHospedes"].copy()
    cal = dfs["dCalendario"].copy()
    res = dfs["fReservas"].copy()
    cons = dfs["fConsumos"].copy()
    aval = dfs["fAvaliacoes"].copy()
    desp = dfs["fDespesas"].copy()
    metas = dfs["fMetas"].copy()

    cal["Feriado"] = cal["Feriado"].where(cal["Feriado"].notna(), None)
    cal_attrs = cal[["Data", "Ano_Mes", "Dia_Semana", "Temporada", "Feriado", "Fim_de_Semana"]]
    un_attrs = un[["ID_Unidade", "Unidade", "Tipo", "Categoria"]]

    # reservas enriquecidas (temporada do check-in define a temporada da reserva)
    res = res.merge(un_attrs, on="ID_Unidade", how="left")
    res = res.merge(
        hosp[["ID_Hospede", "Faixa_Etaria", "Cidade", "UF", "Pais", "Genero"]],
        on="ID_Hospede", how="left",
    )
    res = res.merge(
        cal[["Data", "Temporada"]].rename(columns={"Data": "Check_in"}), on="Check_in", how="left"
    )
    res["Ano_Mes_CI"] = res["Check_in"].dt.strftime("%Y-%m")

    # fNoites
    noites = _explodir_noites(res)
    noites = noites.merge(un_attrs, on="ID_Unidade", how="left")
    noites = noites.merge(cal_attrs, on="Data", how="left")
    noites = noites.merge(hosp[["ID_Hospede", "Faixa_Etaria", "Cidade", "UF", "Pais"]], on="ID_Hospede", how="left")

    # fatos ligados à reserva herdam canal / unidade / hóspede
    chave_res = res[["ID_Reserva", "ID_Unidade", "ID_Hospede", "Canal", "Tipo", "Categoria", "Status"]]
    cons = cons.rename(columns={"Categoria": "Categoria_Consumo"}).merge(chave_res, on="ID_Reserva", how="left")
    cons = cons.merge(cal[["Data", "Temporada", "Ano_Mes"]], on="Data", how="left")
    aval = aval.merge(chave_res, on="ID_Reserva", how="left")
    aval = aval.merge(
        cal[["Data", "Temporada", "Ano_Mes"]].rename(columns={"Data": "Data_Avaliacao"}),
        on="Data_Avaliacao", how="left",
    )

    # histórico de reservas realizadas por hóspede (recorrência)
    realizadas = res[res["Status"].isin(STATUS_REALIZADO)]
    n_res_hosp = realizadas.groupby("ID_Hospede").size().rename("Reservas_Realizadas").reset_index()
    hosp = hosp.merge(n_res_hosp, on="ID_Hospede", how="left")
    hosp["Reservas_Realizadas"] = hosp["Reservas_Realizadas"].fillna(0).astype(int)

    return {
        "unidades": un, "hospedes": hosp, "calendario": cal, "reservas": res,
        "noites": noites, "consumos": cons, "avaliacoes": aval,
        "despesas": desp, "metas": metas,
    }


def ultimo_dia_com_despesa(model: dict) -> pd.Timestamp:
    ult = model["despesas"]["Ano_Mes"].max()
    return pd.Period(ult, freq="M").end_time.normalize()


# ---------------------------------------------------------------- recorte
@dataclass
class Recorte:
    """Fatos já filtrados (dimensões + período) e o inventário correspondente."""
    inicio: pd.Timestamp
    fim: pd.Timestamp
    n_unidades: int
    noites: pd.DataFrame          # todas (realizadas + carteira) no período
    reservas: pd.DataFrame        # reservas com Check_in no período (todos os status)
    reservas_criadas: pd.DataFrame  # reservas com Data_Reserva no período
    consumos: pd.DataFrame
    avaliacoes: pd.DataFrame
    despesas: pd.DataFrame        # já com coluna Valor_Periodo (proporcional aos dias)
    metas: pd.DataFrame           # com coluna Peso_Dias
    hospedes_hist: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def dias(self) -> int:
        if self.fim < self.inicio:
            return 0
        return int((self.fim - self.inicio).days) + 1

    @property
    def noites_disponiveis(self) -> int:
        return self.n_unidades * self.dias

    @property
    def noites_realizadas(self) -> pd.DataFrame:
        return self.noites[self.noites["Realizada"]]

    @property
    def noshows(self) -> pd.DataFrame:
        return self.reservas[self.reservas["Status"] == "No-show"]


def filtrar_dimensoes(model: dict, unidades: list[str] | None, canais: list[str] | None,
                      temporadas: list[str] | None) -> dict:
    """Aplica filtros de unidade / canal / temporada a todas as datas (resultado reutilizável)."""
    def _f(df, col_temp="Temporada", usa_unidade=True):
        m = pd.Series(True, index=df.index)
        if unidades is not None and usa_unidade:
            m &= df["ID_Unidade"].isin(unidades)
        if canais is not None:
            m &= df["Canal"].isin(canais)
        if temporadas is not None:
            m &= df[col_temp].isin(temporadas)
        return df[m]

    un = model["unidades"]
    n_un = len(un) if unidades is None else len(unidades)
    # despesas não são lançadas por unidade: rateio pela capacidade (leitos) do inventário filtrado
    cap_total = float(un["Capacidade"].sum())
    cap_filtro = cap_total if unidades is None else float(un.loc[un["ID_Unidade"].isin(unidades), "Capacidade"].sum())
    return {
        "n_unidades": n_un,
        "fator_despesa": cap_filtro / cap_total if cap_total else 0.0,
        "noites": _f(model["noites"]),
        "reservas": _f(model["reservas"]),
        "consumos": _f(model["consumos"]),
        "avaliacoes": _f(model["avaliacoes"]),
        "despesas": model["despesas"],
        "metas": model["metas"],
        "hospedes": model["hospedes"],
        "calendario": model["calendario"],
        # para "por data da reserva" a temporada é a do check-in também
    }


def _peso_mes(ano_mes: pd.Series, inicio: pd.Timestamp, fim: pd.Timestamp) -> tuple[pd.Series, pd.Series]:
    """(fração do mês, nº de dias) de cada mês AAAA-MM coberto pelo intervalo [inicio, fim]."""
    per = pd.PeriodIndex(ano_mes, freq="M")
    ini_m = per.start_time.normalize()
    fim_m = per.end_time.normalize()
    a = np.maximum(ini_m.values, np.datetime64(inicio))
    b = np.minimum(fim_m.values, np.datetime64(fim))
    dias = (b - a).astype("timedelta64[D]").astype(int) + 1
    dias = np.clip(dias, 0, None)
    return pd.Series(dias / per.days_in_month.values, index=ano_mes.index), pd.Series(dias, index=ano_mes.index)


def recortar(base: dict, inicio, fim) -> Recorte:
    inicio, fim = pd.Timestamp(inicio).normalize(), pd.Timestamp(fim).normalize()
    n = base["noites"]
    r = base["reservas"]
    c = base["consumos"]
    a = base["avaliacoes"]

    desp = base["despesas"].copy()
    frac, _ = _peso_mes(desp["Ano_Mes"], inicio, fim)
    desp["Fracao"] = frac
    desp = desp[desp["Fracao"] > 0].copy()
    desp["Valor_Periodo"] = desp["Valor"] * desp["Fracao"] * base.get("fator_despesa", 1.0)

    metas = base["metas"].copy()
    frac_m, dias_m = _peso_mes(metas["Ano_Mes"], inicio, fim)
    metas["Fracao"] = frac_m
    metas["Peso_Dias"] = dias_m
    metas = metas[metas["Peso_Dias"] > 0]

    return Recorte(
        inicio=inicio, fim=fim, n_unidades=base["n_unidades"],
        noites=n[(n["Data"] >= inicio) & (n["Data"] <= fim)],
        reservas=r[(r["Check_in"] >= inicio) & (r["Check_in"] <= fim)],
        reservas_criadas=r[(r["Data_Reserva"] >= inicio) & (r["Data_Reserva"] <= fim)],
        consumos=c[(c["Data"] >= inicio) & (c["Data"] <= fim)],
        avaliacoes=a[(a["Data_Avaliacao"] >= inicio) & (a["Data_Avaliacao"] <= fim)],
        despesas=desp,
        metas=metas,
        hospedes_hist=base["hospedes"],
    )


def periodo_comparativo(inicio, fim, modo: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    inicio, fim = pd.Timestamp(inicio), pd.Timestamp(fim)
    if modo == "anterior":
        dur = fim - inicio
        f = inicio - pd.Timedelta(days=1)
        return f - dur, f
    return inicio - pd.DateOffset(years=1), fim - pd.DateOffset(years=1)


def ocupacao_diaria(rec: Recorte, somente_realizada: bool = True) -> pd.DataFrame:
    """Uma linha por dia do período: noites ocupadas, ocupação e ADR."""
    dias = pd.DataFrame({"Data": pd.date_range(rec.inicio, rec.fim, freq="D")})
    n = rec.noites_realizadas if somente_realizada else rec.noites
    g = n.groupby("Data").agg(Noites=("ID_Reserva", "size"), Receita=("Receita_Noite", "sum"))
    dias = dias.merge(g, on="Data", how="left").fillna({"Noites": 0, "Receita": 0.0})
    dias["Ocupacao"] = dias["Noites"] / rec.n_unidades if rec.n_unidades else np.nan
    dias["ADR"] = np.where(dias["Noites"] > 0, dias["Receita"] / dias["Noites"].replace(0, np.nan), np.nan)
    return dias
