"""Página 2 — Ocupação & Tarifas."""
import pandas as pd
import streamlit as st

from src import charts as ch
from src import components as ui
from src import formatters as fmt
from src import metrics as m
from src import theme as T
from src.components import KPI
from src.filters import get_ctx
from src.model import DATA_REF, ocupacao_diaria

ctx = get_ctx()
f, rec = ctx.filtros, ctx.rec
k = m.kpis(rec)
s12 = ctx.serie_12m()
cal = ctx.model["calendario"]
feriados = dict(zip(cal.loc[cal["Feriado"].notna(), "Data"], cal.loc[cal["Feriado"].notna(), "Feriado"]))

ui.cabecalho_pagina("Ocupação & Tarifas", "Quanto do inventário estou vendendo, em que dias e a que preço.")
if ctx.filtro_demanda_ativo:
    ui.aviso("Filtro de canal/temporada ativo — ocupação calculada sobre o inventário total.", "info")


def _sp(col):
    return s12[col].tolist() if len(s12) else []


ui.kpi_row([
    KPI("Ocupação", k["ocupacao"], "pct", ctx.cmp(m.taxa_ocupacao), icone="cama", spark=_sp("Ocupacao")),
    KPI("ADR · diária média", k["adr"], "moeda", ctx.cmp(m.adr), icone="tag", spark=_sp("ADR")),
    KPI("RevPAR", k["revpar"], "moeda", ctx.cmp(m.revpar), icone="grafico", spark=_sp("RevPAR")),
    KPI("Noites vendidas", k["noites_ocupadas"], "num", ctx.cmp(m.noites_ocupadas), icone="lua", spark=_sp("Noites")),
    KPI("Hóspedes-noite", k["hospedes_noite"], "num", ctx.cmp(m.hospedes_noite), icone="pessoas"),
], ctx.rotulo_curto)

diario = ocupacao_diaria(rec) if rec.dias > 0 else pd.DataFrame()
tem_dados = len(diario) and diario["Noites"].sum() > 0

# ---------------------------------------------------------------- calendário
with ui.card("Calendário de ocupação",
             "Cada quadrado é um dia; a cor mostra a ocupação realizada. Passe o mouse para ver ADR e feriado."):
    ui.grafico(ch.heatmap_calendario(diario, feriados) if tem_dados else None, 260)

c1, c2 = st.columns(2)
with c1:
    with ui.card("Padrão por dia da semana", "Ocupação média por mês × dia da semana — mostra a força dos fins de semana."):
        ui.grafico(ch.heatmap_mes_dow(diario) if tem_dados else None, 320)
with c2:
    un = ctx.model["unidades"]
    n_tipo = un.groupby("Tipo").size()
    pt = m.receita_por(rec, "Tipo")
    if len(pt):
        pt["Ocupacao"] = pt["Noites"] / (pt["Tipo"].map(n_tipo) * rec.dias)
        pt["Categoria"] = pt["Tipo"].map(un.drop_duplicates("Tipo").set_index("Tipo")["Categoria"])
    with ui.card("Posicionamento de preço por tipo",
                 "Cada bolha é um tipo de unidade: X = ocupação, Y = ADR, tamanho = receita. "
                 "Acima e à direita = vende bem e caro."):
        ui.grafico(ch.bolhas_adr_ocupacao(pt) if len(pt) else None, 320)

with ui.card("Ocupação diária", "Linha fina: ocupação de cada dia. Linha grossa: média móvel de 7 dias. Faixas amarelas: feriados."):
    ui.grafico(ch.linha_ocupacao_diaria(diario, feriados) if tem_dados else None, 300)

c1, c2 = st.columns(2)
with c1:
    nr = rec.noites_realizadas
    adr_tc = (nr.groupby(["Categoria", "Temporada"])
              .agg(Receita=("Receita_Noite", "sum"), Noites=("ID_Reserva", "size")).reset_index())
    adr_tc["ADR"] = adr_tc["Receita"] / adr_tc["Noites"]
    with ui.card("ADR por temporada e categoria", "Diária média realizada em cada temporada, separando quartos e camas."):
        ui.grafico(ch.barras_agrupadas(adr_tc, "Temporada", "ADR", "Categoria", T.CORES_CATEGORIA,
                                       ordem_x=["Alta", "Média", "Baixa"]) if len(adr_tc) else None, 320)
with c2:
    yoy = ctx.serie(pd.Timestamp("2025-01-01"), DATA_REF)
    with ui.card("Ocupação mensal: 2025 × 2026",
                 "Comparação mês a mês entre os dois anos (independe do período selecionado; respeita os demais filtros).",
                 f"Realizado até {fmt.data(DATA_REF)}"):
        ui.grafico(ch.linhas_ano_contra_ano(yoy) if yoy["Noites"].sum() > 0 else None, 300)

# ---------------------------------------------------------------- insights
frases = []
if tem_dados:
    dow = diario.assign(d=diario["Data"].dt.weekday).groupby("d")["Ocupacao"].mean()
    fds = dow.loc[[4, 5]].mean() if {4, 5} <= set(dow.index) else None
    semana = dow.loc[[0, 1, 2, 3]].mean() if {0, 1, 2, 3} <= set(dow.index) else None
    if fds is not None and semana is not None:
        frases.append(f"Noites de sexta e sábado ocupam <b>{fmt.pct(fds)}</b>, contra <b>{fmt.pct(semana)}</b> "
                      f"de segunda a quinta — uma diferença de {fmt.pp(fds - semana)}.")
    pico = diario.loc[diario["Ocupacao"].idxmax()]
    frases.append(f"O dia mais cheio foi <b>{fmt.data(pico['Data'])}</b> ({fmt.pct(pico['Ocupacao'])} de ocupação).")
    lotados = int((diario["Ocupacao"] >= 0.95).sum())
    if lotados:
        frases.append(f"Houve <b>{lotados} dia(s)</b> com ocupação ≥ 95% — oportunidade para tarifa dinâmica mais agressiva.")
if len(adr_tc) > 1:
    a = adr_tc.groupby("Temporada")[["Receita", "Noites"]].sum()
    a = a["Receita"] / a["Noites"]
    if {"Alta", "Baixa"} <= set(a.index):
        frases.append(f"A diária média na alta temporada é <b>{fmt.var_pct(a['Alta'] / a['Baixa'] - 1)}</b> maior que na baixa.")
ui.insights(frases)
