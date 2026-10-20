"""Página 5 — Experiência (Avaliações)."""
import numpy as np
import pandas as pd
import streamlit as st

from src import charts as ch
from src import components as ui
from src import formatters as fmt
from src import metrics as m
from src import theme as T
from src.components import KPI
from src.filters import get_ctx
from src.model import CRITERIOS

META_NOTA = 9.0

ctx = get_ctx()
f, rec = ctx.filtros, ctx.rec
k = m.kpis(rec)
s12 = ctx.serie_12m()
av = rec.avaliacoes

ui.cabecalho_pagina("Experiência", "O que os hóspedes dizem: notas por critério, plataforma e tipo de unidade.")

ui.kpi_row([
    KPI("Nota média", k["nota"], "nota", ctx.cmp(m.nota_media), icone="estrela",
        spark=s12["Nota"].tolist() if len(s12) else []),
    KPI("Recomendariam", k["recomendaria"], "pct", ctx.cmp(m.pct_recomendaria), icone="joinha"),
    KPI("Avaliações", k["n_avaliacoes"], "num", ctx.cmp(m.n_avaliacoes), icone="recibo",
        spark=s12["N_Aval"].tolist() if len(s12) else []),
    KPI("Taxa de avaliação", k["taxa_avaliacao"], "pct", ctx.cmp(m.taxa_avaliacao), icone="porcento",
        ref="avaliações ÷ estadias concluídas"),
], ctx.rotulo_curto)

crit_atual = m.media_criterios(av)
crit_cmp = m.media_criterios(ctx.rec_cmp.avaliacoes) if ctx.rec_cmp is not None else None

c1, c2 = st.columns(2)
with c1:
    with ui.card("Critérios de avaliação", f"Nota média de cada critério no período atual vs {ctx.rotulo_cmp}."):
        ui.grafico(ch.radar(crit_atual, crit_cmp, "Período atual", ctx.rotulo_cmp.capitalize()), 380)
with c2:
    meses = pd.period_range(f.inicio, f.fim, freq="M")
    serie = ctx.serie(f.inicio, f.fim) if len(meses) >= 3 else s12
    with ui.card("Nota média por mês", f"Média da nota geral das avaliações publicadas em cada mês. Meta: {fmt.num(META_NOTA, 1)}."):
        ui.grafico(ch.linha_com_meta(serie, "Nota", None, "nota", meta_fixa=META_NOTA), 380)

c1, c2 = st.columns(2)
with c1:
    pl = av.groupby("Plataforma").agg(Nota=("Nota_Geral", "mean"), N=("Nota_Geral", "size")).reset_index()
    with ui.card("Nota por plataforma", "Nota média em cada site de avaliação; o rótulo mostra o nº de avaliações."):
        txt = [f"{fmt.num(n, 2)} · {fmt.num(q)} aval." for n, q in pl.sort_values("Nota")[["Nota", "N"]].values] if len(pl) else None
        fig = ch.barras_h(pl, "Plataforma", "Nota", fmt_x="nota", texto=txt) if len(pl) else None
        if fig is not None:
            fig.update_xaxes(range=[max(0, pl["Nota"].min() - 1.2), 10.4])
        ui.grafico(fig, 340)
with c2:
    if len(av) >= 10:
        corr = [{"Criterio": nome, "Nota": av[col].mean(), "Correlacao": av[col].corr(av["Nota_Geral"])}
                for col, nome in CRITERIOS.items()]
        mp = pd.DataFrame(corr)
    else:
        mp = pd.DataFrame()
    with ui.card("Matriz de prioridade",
                 "X = nota do critério; Y = correlação com a nota geral (quanto o critério pesa na satisfação). "
                 "Nota baixa + impacto alto = corrigir primeiro."):
        ui.grafico(ch.matriz_prioridade(mp) if len(mp) else None, 340, "Poucas avaliações para calcular correlações.")

c1, c2 = st.columns(2)
with c1:
    with ui.card("Distribuição das notas", "Quantidade de avaliações por nota geral. Abaixo de 7,5 o hóspede não recomendaria."):
        fig = ch.histograma(av.assign(Faixa=np.where(av["Nota_Geral"] >= 7.5, "Recomendaria", "Não recomendaria")),
                            "Nota_Geral", "Faixa", {"Recomendaria": T.ACCENT, "Não recomendaria": T.NEGATIVE},
                            rotulo="Nota", xbins=dict(start=0, end=10.01, size=0.5), linha_corte=7.5) if len(av) else None
        ui.grafico(fig, 320)
with c2:
    if len(av):
        pv = av.groupby("Tipo")[list(CRITERIOS)].mean().rename(columns=CRITERIOS)
        pv["Geral"] = av.groupby("Tipo")["Nota_Geral"].mean()
    else:
        pv = None
    with ui.card("Tipo de unidade × critério", "Nota média de cada critério por tipo de unidade — onde cada produto perde pontos."):
        ui.grafico(ch.heatmap_simples(pv, escala=[[0, "#991B1B"], [0.35, "#16294A"], [0.7, "#155E75"], [1, "#0891B2"]],
                                      zmin=7, zmax=10), 320)

# ---------------------------------------------------------------- insights
frases = []
crit = {c: v for c, v in crit_atual.items() if v is not None}
if crit:
    pior = min(crit, key=crit.get)
    frases.append(f"O critério mais fraco é <b class='neg'>{pior} ({fmt.nota(crit[pior])})</b>.")
    if len(mp):
        prio = mp[(mp["Nota"] < mp["Nota"].mean()) & (mp["Correlacao"] > mp["Correlacao"].mean())]
        if len(prio):
            frases.append("Prioridade de correção (nota baixa e alto impacto): <b>" + ", ".join(prio["Criterio"]) + "</b>.")
    if crit_cmp:
        dif = {c: crit[c] - crit_cmp[c] for c in crit if crit_cmp.get(c) is not None}
        if dif:
            mm = max(dif, key=lambda c: abs(dif[c]))
            frases.append(f"Maior variação vs {ctx.rotulo_cmp}: <b>{mm}</b> ({'+' if dif[mm] > 0 else ''}{fmt.num(dif[mm], 2)} ponto).")
if len(pl) > 1:
    b = pl.sort_values("Nota").iloc[0]
    frases.append(f"Plataforma com nota mais baixa: <b>{b['Plataforma']}</b> ({fmt.nota(b['Nota'])}, {fmt.num(b['N'])} avaliações).")
if k["nota"] is not None:
    gap = k["nota"] - META_NOTA
    frases.append(f"A nota média está <b class='{'pos' if gap >= 0 else 'neg'}'>{fmt.num(abs(gap), 2)} ponto "
                  f"{'acima' if gap >= 0 else 'abaixo'}</b> da meta de {fmt.num(META_NOTA, 1)}.")
ui.insights(frases)
