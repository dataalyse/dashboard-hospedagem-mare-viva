"""Página 7 — Carteira Futura (On the Books)."""
import pandas as pd
import streamlit as st

from src import charts as ch
from src import components as ui
from src import formatters as fmt
from src import metrics as m
from src import theme as T
from src.components import KPI
from src.filters import get_ctx
from src.model import DATA_REF

ctx = get_ctx()
base = ctx.base
n_un = base["n_unidades"]
noites = base["noites"]
res = base["reservas"]
un = ctx.model["unidades"]
un_f = un if ctx.chave[0] is None else un[un["ID_Unidade"].isin(ctx.chave[0])]  # unidades no filtro

ui.cabecalho_pagina(
    "Carteira Futura",
    f"O que já está vendido a partir de {fmt.data(DATA_REF + pd.Timedelta(days=1))} (reservas confirmadas). "
    "Esta página ignora o filtro de período; os demais filtros valem.",
)

ini = DATA_REF + pd.Timedelta(days=1)
fim = pd.Timestamp(f"{DATA_REF.year}-12-31")
dias = (fim - ini).days + 1
otb = noites[(noites["Data"] >= ini) & (noites["Data"] <= fim)]
ly_ini, ly_fim = ini - pd.DateOffset(years=1), fim - pd.DateOffset(years=1)
ly = noites[(noites["Data"] >= ly_ini) & (noites["Data"] <= ly_fim) & noites["Realizada"]]

ocup_otb = m.div(len(otb), n_un * dias)
ocup_ly = m.div(len(ly), n_un * dias)
receita_otb = float(otb["Receita_Noite"].sum())
receita_ly = float(ly["Receita_Noite"].sum())
reservas_otb = res[(res["Status"] == "Confirmada")]

periodo_txt = f"{fmt.data_curta(ini)}–{fmt.data_curta(fim)}"
ui.kpi_row([
    KPI("Noites reservadas", len(otb), "num", len(ly), "neutro", icone="lua", ref=f"{periodo_txt} · vs final 2025"),
    KPI("Ocupação garantida", ocup_otb, "pct", ocup_ly, "neutro", icone="cama", ref="vs ocupação final 2025"),
    KPI("Receita contratada", receita_otb, "moeda0", receita_ly, "neutro", icone="carteira", ref="diárias · vs final 2025"),
    KPI("Reservas", len(reservas_otb), "num", None, icone="calendario", ref="confirmadas na carteira"),
    KPI("ADR da carteira", m.div(receita_otb, len(otb)), "moeda", m.div(receita_ly, len(ly)), icone="tag",
        ref="vs ADR realizado 2025"),
])
ui.aviso("A comparação com 2025 usa o <b>realizado final</b> do ano passado. A carteira ainda vai crescer até as datas "
         "chegarem — a diferença é o <b>gap a vender</b>.", "info")

# ---------------------------------------------------------------- OTB por mês
linhas = []
for mes in pd.period_range(DATA_REF, fim, freq="M"):
    a, b = mes.start_time.normalize(), mes.end_time.normalize()
    d = (b - a).days + 1
    no_mes = noites[(noites["Data"] >= a) & (noites["Data"] <= b)]
    a_ly, b_ly = a - pd.DateOffset(years=1), b - pd.DateOffset(years=1)
    ly_mes = noites[(noites["Data"] >= a_ly) & (noites["Data"] <= b_ly) & noites["Realizada"]]
    o, oly = m.div(len(no_mes), n_un * d), m.div(len(ly_mes), n_un * d)
    linhas.append({"Mes": fmt.mes_ano(a), "OTB": o or 0, "Realizado_LY": oly or 0, "Gap": max((oly or 0) - (o or 0), 0)})
otb_mes = pd.DataFrame(linhas)

c1, c2 = st.columns([5, 7])
with c1:
    with ui.card("Ocupação garantida × ano anterior",
                 "Ocupação do mês com tudo que já está na carteira (para outubro inclui o realizado até 18/10) "
                 "contra a ocupação realizada no mesmo mês de 2025."):
        ui.grafico(ch.barras_otb(otb_mes) if n_un else None, 360)
with c2:
    # pickup de dezembro: noites reservadas acumuladas por antecedência
    def _pickup(ano, atual):
        d1 = pd.Timestamp(f"{ano}-12-01")
        nd = noites[(noites["Data"] >= d1) & (noites["Data"] <= pd.Timestamp(f"{ano}-12-31"))]
        if not len(nd):
            return pd.DataFrame()
        ant = (d1 - nd["Data_Reserva"]).dt.days
        cont = ant.value_counts().sort_index(ascending=False)
        eixo = pd.Index(range(int(max(cont.index.max(), 0)), int(min(cont.index.min(), 0)) - 1, -1))
        acum = cont.reindex(eixo, fill_value=0).cumsum()
        if atual:
            acum = acum[acum.index >= (d1 - DATA_REF).days]
        return pd.DataFrame({"Dias_Antes": acum.index, "Noites_Acum": acum.values,
                             "Serie": f"dez/{str(ano)[-2:]}" + (" (carteira)" if atual else " (realizado)"), "Atual": atual})

    pk = pd.concat([_pickup(DATA_REF.year - 1, False), _pickup(DATA_REF.year, True)], ignore_index=True)
    if len(pk):
        pk = pk[(pk["Dias_Antes"] <= 180) & (pk["Dias_Antes"] >= -31)]
    with ui.card("Pickup de dezembro",
                 "Noites de dezembro reservadas acumuladas conforme a antecedência. "
                 f"Hoje estamos a {(pd.Timestamp(f'{DATA_REF.year}-12-01') - DATA_REF).days} dias de 01/dez."):
        fig = ch.linhas_pickup(pk)
        if fig is not None:
            hoje = (pd.Timestamp(f"{DATA_REF.year}-12-01") - DATA_REF).days
            fig.add_vline(x=hoje, line=dict(color=T.WARNING, dash="dot", width=1.4),
                          annotation_text="hoje", annotation_font_color=T.WARNING)
        ui.grafico(fig, 360)

# ---------------------------------------------------------------- mapa de reservas (Gantt)
g_ini, g_fim = DATA_REF, DATA_REF + pd.Timedelta(days=60)
gt = res[res["Status"].isin(["Confirmada", "Hospedado"]) & (res["Check_out"] > g_ini) & (res["Check_in"] <= g_fim)]
ordem = un_f.sort_values("ID_Unidade")["Unidade"].tolist()
with ui.card("Mapa de reservas — próximos 60 dias",
             "Cada barra é uma reserva (cor = canal). Visual de PMS: linhas vazias são noites livres para vender."):
    altura = max(360, 22 * len(ordem) + 80)
    ui.grafico(ch.gantt(gt, ordem, g_ini, g_fim), altura, "Nenhuma reserva confirmada nos próximos 60 dias para os filtros.")

# ---------------------------------------------------------------- réveillon
rv_noites = pd.date_range(f"{DATA_REF.year}-12-29", f"{DATA_REF.year}-12-31")
rv = noites[noites["Data"].isin(rv_noites)]
rv_ly = noites[noites["Data"].isin(rv_noites - pd.DateOffset(years=1)) & noites["Realizada"]]
cards = []
for cat in ["Total", "Quarto Privativo", "Cama em Dormitório"]:
    n_cat = base["n_unidades"] if cat == "Total" else int((un_f["Categoria"] == cat).sum())
    if n_cat == 0:
        continue
    sel = rv if cat == "Total" else rv[rv["Categoria"] == cat]
    sel_ly = rv_ly if cat == "Total" else rv_ly[rv_ly["Categoria"] == cat]
    o = m.div(len(sel), n_cat * len(rv_noites))
    oly = m.div(len(sel_ly), n_cat * len(rv_noites))
    cor = T.CORES_CATEGORIA.get(cat, T.ACCENT)
    larg = 0 if o is None else min(o, 1) * 100
    cards.append(
        f"<div class='rev'><div class='c'>{cat}</div><div class='v'>{fmt.pct(o)}</div>"
        f"<div class='c'>{fmt.num(len(sel))} de {fmt.num(n_cat * len(rv_noites))} noites · 2025: {fmt.pct(oly)}</div>"
        f"<div class='b'><i style='width:{larg:.0f}%;background:{cor}'></i></div></div>"
    )
with ui.card("Réveillon 2026/27", "Ocupação garantida nas noites de 29, 30 e 31/12 (saída em 01/01), por categoria."):
    st.markdown(f"<div class='rev-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------- insights
frases = []
if len(otb_mes):
    for _, r in otb_mes.iterrows():
        if r["Gap"] > 0:
            frases.append(f"<b>{r['Mes']}</b>: {fmt.pct(r['OTB'])} já garantido contra {fmt.pct(r['Realizado_LY'])} realizado "
                          f"no ano passado — faltam <b class='neg'>{fmt.num(r['Gap'] * 100, 1)} p.p.</b> para empatar.")
        else:
            frases.append(f"<b>{r['Mes']}</b>: carteira já supera o realizado do ano passado "
                          f"(<b class='pos'>{fmt.pct(r['OTB'])}</b> vs {fmt.pct(r['Realizado_LY'])}).")
if len(otb):
    ch_top = otb.groupby("Canal").size().sort_values(ascending=False)
    frases.append(f"<b>{ch_top.index[0]}</b> responde por {fmt.pct(ch_top.iloc[0] / ch_top.sum())} das noites já reservadas.")
ui.insights(frases[:5])
