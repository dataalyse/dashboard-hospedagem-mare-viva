"""Página 3 — Reservas & Canais."""
from dataclasses import replace

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
f = ctx.filtros

ui.cabecalho_pagina("Reservas & Canais", "De onde vêm as reservas, quanto custam em comissão e como se comportam.")

modo = st.segmented_control(
    "Contar reservas por", ["Data de check-in", "Data da reserva"], default="Data de check-in", key="p3_modo",
    help="Check-in: reservas que chegam no período. Data da reserva: reservas vendidas no período (ritmo comercial).",
) or "Data de check-in"
por_criacao = modo == "Data da reserva"


def _r(rec):
    """Recorte com o conjunto de reservas conforme a alternância."""
    if rec is None:
        return None
    return replace(rec, reservas=rec.reservas_criadas) if por_criacao else rec


rec = _r(ctx.rec)
rec_cmp = _r(ctx.rec_cmp)
R = rec.reservas
col_mes = "Data_Reserva" if por_criacao else "Check_in"


def cmp(func):
    return func(rec_cmp) if rec_cmp is not None else None


ui.kpi_row([
    KPI("Reservas", m.total_reservas(rec), "num", cmp(m.total_reservas), icone="calendario"),
    KPI("Cancelamento", m.taxa_cancelamento(rec), "pct", cmp(m.taxa_cancelamento), melhor="baixo", icone="x"),
    KPI("No-show", m.taxa_noshow(rec), "pct", cmp(m.taxa_noshow), melhor="baixo", icone="relogio"),
    KPI("Antecedência média", m.antecedencia_media(rec), "dias", cmp(m.antecedencia_media), icone="seta"),
    KPI("Estadia média (LOS)", m.estadia_media(rec), "noites", cmp(m.estadia_media), icone="lua"),
    KPI("Reservas diretas", m.pct_diretas(rec), "pct", cmp(m.pct_diretas), icone="joinha"),
], ctx.rotulo_curto)

# ---------------------------------------------------------------- fluxo + mix
c1, c2 = st.columns([6, 6])
with c1:
    with ui.card("Fluxo das reservas", "Canal → categoria da unidade → status final. A espessura é o número de reservas."):
        ui.grafico(ch.sankey(R), 380)
with c2:
    mix = R.assign(Ano_Mes=R[col_mes].dt.strftime("%Y-%m")).groupby(["Ano_Mes", "Canal"]).size().reset_index(name="n")
    with ui.card("Mix de canais por mês", "Participação de cada canal no total de reservas do mês."):
        ui.grafico(ch.barras_100(mix, "Ano_Mes", "Canal", "n", T.CORES_CANAL), 380)

# ---------------------------------------------------------------- rentabilidade
rc = m.receita_por(ctx.rec, "Canal")
qt = R.groupby("Canal").agg(Reservas=("ID_Reserva", "size"),
                            Canceladas=("Status", lambda s: (s == "Cancelada").sum())).reset_index()
tab = qt.merge(rc, on="Canal", how="outer").fillna({"Reservas": 0, "Canceladas": 0, "Receita": 0, "Comissao": 0})
if len(tab):
    tab["Comissao_Pct"] = tab["Comissao"] / tab["Receita"].where(tab["Receita"] > 0)
    tab["Receita_Liquida"] = tab["Receita"] - tab["Comissao"]
    tab["Cancelamento"] = tab["Canceladas"] / tab["Reservas"].where(tab["Reservas"] > 0)
    tab = tab.sort_values("Receita", ascending=False)
with ui.card("Rentabilidade por canal",
             "Receita e comissão consideram as noites realizadas no período (+ no-show). Reservas e cancelamento seguem a alternância acima."):
    cols = ["Canal", "Reservas", "Receita", "Comissao", "Comissao_Pct", "Receita_Liquida", "ADR", "Cancelamento"]
    vis = tab[cols] if len(tab) else tab
    ui.tabela_barras(
        vis,
        formatos={"Reservas": "num", "Receita": "moeda", "Comissao": "moeda", "Comissao_Pct": "pct",
                  "Receita_Liquida": "moeda", "ADR": "moeda", "Cancelamento": "pct"},
        rotulos={"Comissao": "Comissão R$", "Comissao_Pct": "Comissão %", "Receita_Liquida": "Receita líquida"},
        barras=["Reservas", "Receita", "Comissao_Pct", "Cancelamento"],
        cores_linha=T.CORES_CANAL,
    )
    if len(tab):
        ui.download_csv(tab[cols].round(4), "rentabilidade_por_canal")

# ---------------------------------------------------------------- distribuição
realizadas = R[R["Status"].isin(STATUS_REALIZADO)]
c1, c2 = st.columns(2)
with c1:
    with ui.card("Antecedência por canal", "Dias entre a reserva e o check-in (reservas realizadas). Linha tracejada = média."):
        ui.grafico(ch.box_por_grupo(realizadas, "Canal", "Antecedencia_Dias", T.CORES_CANAL), 340)
with c2:
    with ui.card("Distribuição da estadia", "Número de noites por reserva realizada, por categoria."):
        ui.grafico(ch.histograma(realizadas, "Noites", "Categoria", T.CORES_CATEGORIA, rotulo="Noites",
                                 xbins=dict(start=0.5, size=1)), 340)

c1, c2 = st.columns([5, 7])
with c1:
    avaliadas = R["ID_Reserva"].isin(ctx.model["avaliacoes"]["ID_Reserva"]).sum()
    etapas = [
        ("Reservas criadas", len(R)),
        ("Não canceladas", int((R["Status"] != "Cancelada").sum())),
        ("Realizadas", int(R["Status"].isin(STATUS_REALIZADO).sum())),
        ("Avaliadas", int(avaliadas)),
    ]
    with ui.card("Funil da reserva", "Da reserva criada à avaliação publicada pelo hóspede."):
        ui.grafico(ch.funil(etapas), 320)
with c2:
    rc_sem = ctx.rec.reservas_criadas
    sem = (rc_sem.assign(Semana=rc_sem["Data_Reserva"].dt.to_period("W-SUN").dt.start_time)
           .groupby("Semana").size().reset_index(name="Reservas"))
    with ui.card("Ritmo de vendas", "Reservas criadas por semana (pela data da reserva) e média de 4 semanas."):
        ui.grafico(ch.linha_semanal(sem, "Semana", "Reservas"), 320)

# ---------------------------------------------------------------- insights
frases = []
if len(tab) and tab["Receita"].sum() > 0:
    caro = tab[tab["Receita"] > 0].sort_values("Comissao_Pct", ascending=False).iloc[0]
    frases.append(f"<b>{caro['Canal']}</b> é o canal mais caro: {fmt.pct(caro['Comissao_Pct'])} da receita vai para comissão "
                  f"({fmt.moeda(caro['Comissao'])} no período).")
    dir_ = m.pct_diretas(rec)
    if dir_ is not None:
        frases.append(f"Reservas diretas (WhatsApp/telefone + site) são <b>{fmt.pct(dir_)}</b> das estadias realizadas — "
                      "cada ponto migrado das OTAs reduz o custo de distribuição.")
if len(tab) and tab["Reservas"].sum() > 0:
    cx = tab[tab["Reservas"] >= 10].sort_values("Cancelamento", ascending=False)
    if len(cx):
        c = cx.iloc[0]
        frases.append(f"Maior taxa de cancelamento: <b class='neg'>{c['Canal']} ({fmt.pct(c['Cancelamento'])})</b>.")
if len(realizadas):
    lt = realizadas.groupby("Canal")["Antecedencia_Dias"].mean().sort_values()
    frases.append(f"<b>{lt.index[0]}</b> traz as reservas mais em cima da hora ({fmt.num(lt.iloc[0], 0)} dias de antecedência média); "
                  f"<b>{lt.index[-1]}</b>, as mais antecipadas ({fmt.num(lt.iloc[-1], 0)} dias).")
ui.insights(frases)
