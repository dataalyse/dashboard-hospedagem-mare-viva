"""Página 4 — Hóspedes & Mercados."""
import pandas as pd
import streamlit as st

from src import charts as ch
from src import components as ui
from src import formatters as fmt
from src import metrics as m
from src import theme as T
from src.components import KPI
from src.filters import get_ctx
from src.model import STATUS_REALIZADO

ctx = get_ctx()
rec = ctx.rec
k = m.kpis(rec)

ui.cabecalho_pagina("Hóspedes & Mercados", "Quem são os hóspedes, de onde vêm, por que viajam e quanto voltam.")

ui.kpi_row([
    KPI("Hóspedes únicos", k["hospedes_unicos"], "num", ctx.cmp(m.hospedes_unicos), icone="pessoas"),
    KPI("Taxa de recorrência", k["recorrencia"], "pct", ctx.cmp(m.taxa_recorrencia), icone="repetir"),
    KPI("Estrangeiros", k["estrangeiros"], "pct", ctx.cmp(m.pct_estrangeiros), icone="globo"),
    KPI("Gasto extra por hóspede", k["gasto_extra"], "moeda", ctx.cmp(m.gasto_extra_por_hospede), icone="cifrao"),
], ctx.rotulo_curto)

nr = rec.noites_realizadas


def _por(df, col):
    return (df.groupby(col).agg(Hospedes=("ID_Hospede", "nunique"), Noites=("ID_Reserva", "size"),
                                Receita=("Receita_Noite", "sum"))
            .reset_index())


# ---------------------------------------------------------------- mapas
c1, c2 = st.columns(2)
with c1:
    br = _por(nr[nr["Pais"] == "Brasil"], "UF")
    geo = ch.carregar_geojson_br()
    with ui.card("Hóspedes brasileiros por UF", "Hóspedes únicos atendidos no período, por estado de origem."):
        if geo is not None:
            ui.grafico(ch.mapa_brasil(br, geo), 380)
        else:
            ui.grafico(ch.barras_h(br, "UF", "Hospedes", fmt_x="num"), 380)
with c2:
    ex = _por(nr[nr["Pais"] != "Brasil"], "Pais")
    with ui.card("Hóspedes estrangeiros por país", "Hóspedes únicos atendidos no período, por país de origem."):
        ui.grafico(ch.mapa_mundi(ex), 380, "Nenhum hóspede estrangeiro no período.")

# ---------------------------------------------------------------- composição
c1, c2 = st.columns(2)
with c1:
    tm = nr.groupby(["Pais", "Cidade"]).size().reset_index(name="Noites")
    cores_pais = T.mapa_cores(tm.groupby("Pais")["Noites"].sum().sort_values(ascending=False).index)
    with ui.card("Origem das noites: país → cidade", "Tamanho = noites vendidas. Clique num país para abrir as cidades."):
        ui.grafico(ch.treemap(tm, ["Pais", "Cidade"], "Noites", cores_pais), 380)
with c2:
    pir = nr.drop_duplicates(["ID_Hospede", "Categoria"]).groupby(["Faixa_Etaria", "Categoria"]).size().reset_index(name="n")
    with ui.card("Faixa etária por categoria",
                 "Distribuição dos hóspedes únicos de cada categoria por faixa etária (% dentro da categoria)."):
        ui.grafico(ch.piramide(pir, "Faixa_Etaria", "Categoria", "n", "Cama em Dormitório", "Quarto Privativo"), 380)

c1, c2 = st.columns([4, 8])
with c1:
    rr = rec.reservas[rec.reservas["Status"].isin(STATUS_REALIZADO)]
    mot = rr.groupby("Motivo_Viagem").size().reset_index(name="Reservas")
    with ui.card("Motivo da viagem", "Motivo declarado nas reservas realizadas."):
        ui.grafico(ch.donut(mot, "Motivo_Viagem", "Reservas", hover_moeda=False,
                            centro=f"<b>{fmt.num(len(rr))}</b><br><span style='font-size:11px;color:{T.MUTED}'>reservas</span>"), 360)
with c2:
    cid = nr.groupby(["Cidade", "Pais"]).agg(Hospedes=("ID_Hospede", "nunique"), Noites=("ID_Reserva", "size"),
                                             Receita=("Receita_Noite", "sum")).reset_index()
    cid["ADR"] = cid["Receita"] / cid["Noites"]
    top = cid.sort_values("Receita", ascending=False).head(10)
    with ui.card("Top 10 cidades emissoras", "Cidades que mais geraram receita de diárias no período."):
        ui.tabela_barras(top[["Cidade", "Pais", "Hospedes", "Noites", "Receita", "ADR"]],
                         formatos={"Hospedes": "num", "Noites": "num", "Receita": "moeda", "ADR": "moeda"},
                         rotulos={"Pais": "País", "Hospedes": "Hóspedes"}, barras=["Receita", "Noites"])
        ui.download_csv(cid.sort_values("Receita", ascending=False).round(2), "receita_por_cidade", "Baixar todas as cidades (CSV)")

# ---------------------------------------------------------------- insights
frases = []
if len(nr):
    tot = nr["ID_Hospede"].nunique()
    pais = _por(nr, "Pais").sort_values("Hospedes", ascending=False)
    est = pais[pais["Pais"] != "Brasil"]
    if len(est):
        p = est.iloc[0]
        frases.append(f"<b>{p['Pais']}</b> é o principal mercado internacional: {fmt.pct(p['Hospedes'] / tot)} dos hóspedes "
                      f"e ADR de {fmt.moeda(p['Receita'] / p['Noites'])}.")
    if len(br):
        u = br.sort_values("Hospedes", ascending=False).iloc[0]
        frases.append(f"<b>{u['UF']}</b> lidera entre os estados brasileiros, com {fmt.num(u['Hospedes'])} hóspedes.")
    fx = nr.drop_duplicates("ID_Hospede").groupby(["Categoria", "Faixa_Etaria"]).size()
    for cat in ["Cama em Dormitório", "Quarto Privativo"]:
        if cat in fx.index.get_level_values(0):
            s = fx.loc[cat]
            frases.append(f"Em <b>{cat.lower()}</b>, a faixa predominante é <b>{s.idxmax()}</b> ({fmt.pct(s.max() / s.sum())}).")
if k["recorrencia"] is not None:
    frases.append(f"<b>{fmt.pct(k['recorrencia'])}</b> dos hóspedes do período já se hospedaram mais de uma vez — "
                  "base para campanhas de fidelização via canal direto.")
ui.insights(frases)
