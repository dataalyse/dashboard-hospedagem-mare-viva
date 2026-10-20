"""Página 1 — Visão Geral (cockpit)."""
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
f, rec, rl = ctx.filtros, ctx.rec, ctx.rec_lucro
k = m.kpis(rec)
kl = m.kpis_lucro(rl)
s12 = ctx.serie_12m()

ui.cabecalho_pagina("Visão Geral", "Cockpit do negócio: ocupação, preço, receita, lucro e satisfação num só lugar.")
if ctx.filtro_demanda_ativo:
    ui.aviso("Filtro de canal/temporada ativo — ocupação calculada sobre o inventário total.", "info")


def _sp(col):
    return s12[col].tolist() if len(s12) else []


ui.kpi_row([
    KPI("Ocupação", k["ocupacao"], "pct", ctx.cmp(m.taxa_ocupacao), icone="cama", spark=_sp("Ocupacao")),
    KPI("ADR · diária média", k["adr"], "moeda", ctx.cmp(m.adr), icone="tag", spark=_sp("ADR")),
    KPI("RevPAR", k["revpar"], "moeda", ctx.cmp(m.revpar), icone="grafico", spark=_sp("RevPAR")),
    KPI("Receita total", k["receita_total"], "moeda0", ctx.cmp(m.receita_total), icone="carteira", spark=_sp("Receita_Total")),
    KPI("GOP · lucro operac.", kl["gop"], "moeda0", ctx.cmp(m.gop, lucro=True), icone="tendencia",
        spark=_sp("GOP"), ref=f"margem {fmt.pct(kl['margem'])}" + (" · até set" if ctx.lucro_parcial else "")),
    KPI("Nota média", k["nota"], "nota", ctx.cmp(m.nota_media), icone="estrela", spark=_sp("Nota")),
], ctx.rotulo_curto)

if ctx.lucro_parcial:
    ui.aviso(f"GOP e margem consideram apenas meses com despesa lançada (até {fmt.data(ctx.fim_despesa)}). "
             "Outubro ainda não foi fechado.")

# ---------------------------------------------------------------- linha 1
c1, c2 = st.columns([4, 8])
with c1:
    with ui.card("Ocupação vs meta", "Ocupação realizada no período contra a meta (média dos meses, ponderada pelos dias)."):
        ui.grafico(ch.gauge_ocupacao(k["ocupacao"], k["meta_ocupacao"]), 300)
        ating = m.atingimento(k["ocupacao"], k["meta_ocupacao"])
        st.caption(f"Meta {fmt.pct(k['meta_ocupacao'])} · atingimento {fmt.pct(ating, 0)} · "
                   f"{fmt.num(k['noites_ocupadas'])} de {fmt.num(k['noites_disponiveis'])} noites")

with c2:
    meses = pd.period_range(f.inicio, f.fim, freq="M")
    serie = ctx.serie(f.inicio, f.fim) if len(meses) >= 3 else s12
    with ui.card("Receita × ocupação por mês",
                 "Barras: receita de hospedagem + consumos. Linha: taxa de ocupação (eixo da direita). Tracejado: meta.",
                 None if len(meses) >= 3 else "Últimos 12 meses (período selecionado é curto)"):
        ui.grafico(ch.combo_receita_ocupacao(serie), 330)

# ---------------------------------------------------------------- linha 2
c1, c2, c3 = st.columns(3)
por_canal = m.receita_por(rec, "Canal")
with c1:
    with ui.card("Receita por canal", "Receita de hospedagem (diárias + no-show) por canal de venda."):
        ui.grafico(ch.donut(por_canal, "Canal", "Receita", T.CORES_CANAL,
                            centro=f"<b>{fmt.moeda_compacta(k['receita_hospedagem'])}</b><br><span style='font-size:11px;color:{T.MUTED}'>hospedagem</span>"), 300)

with c2:
    por_tipo = m.receita_por(rec, "Tipo")
    un = ctx.model["unidades"]
    n_tipo = un.groupby("Tipo").size()
    if len(por_tipo):
        por_tipo["RevPAR"] = por_tipo["Receita"] / (por_tipo["Tipo"].map(n_tipo) * rec.dias)
        cat_tipo = un.drop_duplicates("Tipo").set_index("Tipo")["Categoria"]
        por_tipo["Categoria"] = por_tipo["Tipo"].map(cat_tipo)
    with ui.card("RevPAR por tipo de unidade", "Receita de hospedagem ÷ noites disponíveis do tipo no período."):
        ui.grafico(ch.barras_h(por_tipo, "Tipo", "RevPAR", cor="Categoria", cores=T.CORES_CATEGORIA)
                   if len(por_tipo) else None, 300)

with c3:
    with ui.card("Próximos 7 dias", f"Previsão a partir de {fmt.data(DATA_REF)} com base nas reservas confirmadas e hóspedes na casa."):
        dias = pd.date_range(DATA_REF + pd.Timedelta(days=1), periods=7, freq="D")
        r = ctx.base["reservas"]
        ativos = r[r["Status"].isin(["Confirmada", "Hospedado"])]
        n = ctx.base["noites"]
        ocup = n[n["Data"].isin(dias)].groupby("Data").size()
        linhas = []
        for d in dias:
            ci = int((ativos["Check_in"] == d).sum())
            co = int((ativos["Check_out"] == d).sum())
            oc = ocup.get(d, 0) / ctx.base["n_unidades"] if ctx.base["n_unidades"] else None
            larg = 0 if oc is None else int(round(oc * 60))
            linhas.append(
                f"<tr><td>{fmt.dia_semana(d)} {fmt.data_curta(d)}</td><td>{ci}</td><td>{co}</td>"
                f"<td><span class='bar' style='width:{larg}px'></span>{fmt.pct(oc, 0)}</td></tr>"
            )
        st.markdown(
            "<table class='tab7'><thead><tr><th>Dia</th><th>Check-ins</th><th>Check-outs</th><th>Ocupação</th></tr></thead>"
            f"<tbody>{''.join(linhas)}</tbody></table>",
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------- insights
frases = []
serie_p = ctx.serie(f.inicio, f.fim)
fech = serie_p[(serie_p["Dias"] == pd.PeriodIndex(serie_p["Ano_Mes"], freq="M").days_in_month)] if len(serie_p) else serie_p
fech = fech[fech["Noites"] > 0] if len(fech) else fech
if len(fech) and fech["Meta_Ocupacao"].notna().iloc[-1]:
    u = fech.iloc[-1]
    d = u["Ocupacao"] - u["Meta_Ocupacao"]
    mes = fmt.MESES_NOME[int(u["Ano_Mes"][5:7]) - 1]
    cls = "neg" if d < 0 else "pos"
    frases.append(f"Ocupação de {mes} ficou <b class='{cls}'>{fmt.num(abs(d) * 100, 1)} p.p. "
                  f"{'abaixo' if d < 0 else 'acima'} da meta</b> ({fmt.pct(u['Ocupacao'])} vs {fmt.pct(u['Meta_Ocupacao'])}).")
if len(por_canal) and k["receita_hospedagem"]:
    top = por_canal.sort_values("Receita", ascending=False).iloc[0]
    frases.append(f"<b>{top['Canal']}</b> gerou {fmt.pct(top['Receita'] / k['receita_hospedagem'], 0)} da receita de hospedagem, "
                  f"com custo de {fmt.pct(m.div(top['Comissao'], top['Receita']), 0)} em comissões.")
crit = {c: v for c, v in m.media_criterios(rec.avaliacoes).items() if v is not None}
if crit:
    pior = min(crit, key=crit.get)
    melhor = max(crit, key=crit.get)
    frases.append(f"O pior critério nas avaliações é <b class='neg'>{pior} ({fmt.nota(crit[pior])})</b>; "
                  f"o melhor é <b class='pos'>{melhor} ({fmt.nota(crit[melhor])})</b>.")
oc_cmp = ctx.cmp(m.taxa_ocupacao)
if k["ocupacao"] is not None and oc_cmp is not None:
    d = k["ocupacao"] - oc_cmp
    razao_adr = m.div(k["adr"], ctx.cmp(m.adr))
    var_adr = f", com ADR {fmt.var_pct(razao_adr - 1)}" if razao_adr is not None else ""
    frases.append(f"A ocupação está <b class='{'pos' if d >= 0 else 'neg'}'>{fmt.pp(d)}</b> em relação ao "
                  f"{ctx.rotulo_cmp}{var_adr}.")
if len(por_tipo) and "RevPAR" in por_tipo:
    bt = por_tipo.sort_values("RevPAR", ascending=False).iloc[0]
    frases.append(f"O tipo com maior RevPAR é <b>{bt['Tipo']}</b> ({fmt.moeda(bt['RevPAR'])} por noite disponível).")
ui.insights(frases[:5])

# ---------------------------------------------------------------- glossário
with st.expander("📖 Glossário de indicadores"):
    st.markdown("""
| Sigla | Nome | Como ler |
|---|---|---|
| **Ocupação** | Taxa de ocupação | Noites vendidas ÷ noites disponíveis (unidades × dias). |
| **ADR** | *Average Daily Rate* — diária média | Receita das diárias ÷ noites vendidas. Mostra *a que preço* vendo. |
| **RevPAR** | *Revenue per Available Room* | Receita de hospedagem ÷ noites disponíveis. Junta preço e ocupação num só número. |
| **TRevPAR** | *Total RevPAR* | Igual ao RevPAR, mas inclui consumos extras (restaurante, passeios…). |
| **GOP** | *Gross Operating Profit* — lucro operacional | Receita total − comissões − despesas operacionais. |
| **GOPPAR** | GOP por noite disponível | GOP ÷ noites disponíveis. Lucro por unidade/dia, compara períodos de tamanhos diferentes. |
| **CPOR** | Custo por noite ocupada | Despesas ÷ noites vendidas. |
| **LOS** | *Length of Stay* — estadia média | Média de noites por reserva realizada. |
| **OTB** | *On the Books* — carteira | Noites/receita já reservadas para datas futuras. |
| **Pickup** | Ritmo de reservas | Quantas noites entram na carteira a cada dia antes da data de chegada. |
""")
