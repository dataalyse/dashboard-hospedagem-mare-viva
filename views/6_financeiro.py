"""Página 6 — Financeiro (DRE gerencial)."""
from io import BytesIO

import pandas as pd
import streamlit as st

from src import charts as ch
from src import components as ui
from src import formatters as fmt
from src import metrics as m
from src import theme as T
from src.components import KPI
from src.filters import get_ctx

ctx = get_ctx()
f = ctx.filtros
rl = ctx.rec_lucro          # período limitado aos meses com despesa lançada
kl = m.kpis_lucro(rl)
sem_lucro = rl.dias <= 0
fim_l = min(f.fim, ctx.fim_despesa)

ui.cabecalho_pagina("Financeiro", "Receitas, custos e lucro operacional — DRE gerencial da pousada.")

if sem_lucro:
    ui.aviso(f"O período selecionado não tem despesas lançadas (último mês fechado: {fmt.mes_ano(ctx.fim_despesa)}). "
             "Escolha um período até setembro/2026 para ver o resultado.")
elif ctx.lucro_parcial:
    ui.aviso(f"O período inclui meses sem despesa lançada. Todos os números desta página consideram "
             f"<b>{fmt.periodo(f.inicio, fim_l)}</b> — outubro ainda não foi fechado.")
if f.categoria != "Todas" or f.tipos:
    ui.aviso(f"Despesas rateadas pela capacidade em leitos do inventário filtrado "
             f"({fmt.pct(ctx.base['fator_despesa'])} do total da pousada).", "info")
if ctx.filtro_demanda_ativo:
    ui.aviso("Filtro de canal/temporada ativo: a receita é filtrada, mas as despesas não são lançadas por canal "
             "nem por temporada — o GOP compara com a despesa do inventário inteiro.", "info")

cmp = lambda fn: ctx.cmp(fn, lucro=True)  # noqa: E731
ui.kpi_row([
    KPI("Receita total", kl["receita_total"], "moeda0", cmp(m.receita_total), icone="carteira"),
    KPI("Comissões", kl["comissoes"], "moeda0", cmp(m.comissoes), melhor="baixo", icone="porcento"),
    KPI("Despesas", kl["despesas"], "moeda0", cmp(m.despesas), melhor="baixo", icone="recibo"),
    KPI("GOP", kl["gop"], "moeda0", cmp(m.gop), icone="tendencia"),
    KPI("Margem GOP", kl["margem"], "pct", cmp(m.margem_gop), icone="grafico"),
    KPI("GOPPAR", kl["goppar"], "moeda", cmp(m.goppar), icone="cama"),
    KPI("CPOR", kl["cpor"], "moeda", cmp(m.cpor), melhor="baixo", icone="lua"),
], ctx.rotulo_curto)

if sem_lucro:
    st.stop()

desp = rl.despesas
d_tipo = desp.groupby("Tipo")["Valor_Periodo"].sum()
serie = ctx.serie(f.inicio, fim_l)

# ---------------------------------------------------------------- DRE em cascata + treemap
c1, c2 = st.columns([7, 5])
with c1:
    linhas = [
        ("Hospedagem", kl["receita_hospedagem"], "relative"),
        ("+ Consumos", kl["receita_consumos"], "relative"),
        ("− Comissões", -kl["comissoes"], "relative"),
        ("− Desp. fixas", -float(d_tipo.get("Fixa", 0)), "relative"),
        ("− Desp. variáveis", -float(d_tipo.get("Variável", 0)), "relative"),
        ("= GOP", kl["gop"], "total"),
    ]
    with ui.card("DRE gerencial", "Da receita de hospedagem ao lucro operacional (GOP), no período com despesas lançadas."):
        ui.grafico(ch.waterfall_dre(linhas), 360)
with c2:
    tm = desp.groupby(["Tipo", "Categoria"])["Valor_Periodo"].sum().reset_index()
    with ui.card("Composição das despesas", "Despesas fixas e variáveis por categoria. Tamanho = valor."):
        ui.grafico(ch.treemap(tm, ["Tipo", "Categoria"], "Valor_Periodo", T.CORES_TIPO_DESPESA, moeda=True), 360)

with ui.card("Despesas por categoria × receita", "Barras: despesas mensais por categoria. Linha: receita total do mês."):
    dm = desp.assign(Valor=desp["Valor_Periodo"])
    ui.grafico(ch.despesas_empilhadas(dm, serie), 380)

c1, c2 = st.columns(2)
with c1:
    cons = rl.consumos.groupby("Categoria_Consumo")["Valor_Total"].sum().reset_index()
    with ui.card("Receita extra por categoria", "Consumos e serviços vendidos além da diária (restaurante, passeios, frigobar…)."):
        ui.grafico(ch.barras_h(cons, "Categoria_Consumo", "Valor_Total", cor=T.ACCENT_2), 340)
with c2:
    with ui.card("Margem GOP mensal", "Pontos vermelhos: margem negativa. Amarelos: abaixo de 15%."):
        ui.grafico(ch.linha_margem(serie), 340)

# ---------------------------------------------------------------- tabela DRE
dm = desp.groupby(["Ano_Mes", "Tipo"])["Valor_Periodo"].sum().unstack(fill_value=0)
dre = serie.set_index("Ano_Mes")[["Receita_Hospedagem", "Consumos", "Receita_Total", "Comissoes"]].copy()
dre["Receita_Liquida"] = dre["Receita_Total"] - dre["Comissoes"]
dre["Despesas_Fixas"] = dm.get("Fixa", pd.Series(dtype=float)).reindex(dre.index).fillna(0)
dre["Despesas_Variaveis"] = dm.get("Variável", pd.Series(dtype=float)).reindex(dre.index).fillna(0)
dre["GOP"] = dre["Receita_Liquida"] - dre["Despesas_Fixas"] - dre["Despesas_Variaveis"]
dre["Margem_GOP"] = dre["GOP"] / dre["Receita_Total"].where(dre["Receita_Total"] != 0)
contas = {
    "Receita_Hospedagem": "Receita de hospedagem", "Consumos": "Receita de consumos", "Receita_Total": "Receita total",
    "Comissoes": "(−) Comissões de canais", "Receita_Liquida": "Receita líquida",
    "Despesas_Fixas": "(−) Despesas fixas", "Despesas_Variaveis": "(−) Despesas variáveis",
    "GOP": "GOP — lucro operacional", "Margem_GOP": "Margem GOP",
}
tab = dre[list(contas)].T
tab["Total"] = [dre[c].sum() if c != "Margem_GOP" else m.div(dre["GOP"].sum(), dre["Receita_Total"].sum()) for c in tab.index]
tab.columns = [fmt.mes_ano_de_chave(c) if c != "Total" else c for c in tab.columns]
tab.index = [contas[c] for c in tab.index]
tab = tab.reset_index(names="Conta")

with ui.card("DRE mensal", "Demonstrativo gerencial mês a mês. Baixe em Excel ou CSV."):
    mostrar = tab.copy()
    for col in mostrar.columns[1:]:
        mostrar[col] = [fmt.pct(v) if conta == "Margem GOP" else fmt.moeda(v) for conta, v in zip(mostrar["Conta"], mostrar[col])]
    st.dataframe(mostrar, hide_index=True, use_container_width=True, height=(len(mostrar) + 1) * 35 + 4,
                 column_config={"Conta": st.column_config.TextColumn("Conta", pinned=True)})
    b1, b2, _ = st.columns([2, 2, 8])
    with b1:
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xw:
            tab.to_excel(xw, sheet_name="DRE mensal", index=False)
            ws = xw.sheets["DRE mensal"]
            ws.column_dimensions["A"].width = 30
            for row in ws.iter_rows(min_row=2, min_col=2):
                for cell in row:
                    cell.number_format = "0.0%" if ws.cell(cell.row, 1).value == "Margem GOP" else '"R$" #,##0.00'
        st.download_button("⤓ Baixar Excel", buf.getvalue(), file_name="dre_mensal_mare_viva.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_dre_xlsx")
    with b2:
        ui.download_csv(tab.round(4), "dre_mensal_mare_viva")

# ---------------------------------------------------------------- insights
frases = []
if kl["margem"] is not None:
    frases.append(f"Margem operacional de <b>{fmt.pct(kl['margem'])}</b> no período "
                  f"(GOP de {fmt.moeda(kl['gop'])}).")
if len(serie) and serie["Margem"].notna().any():
    neg = serie[serie["Margem"] < 0]
    if len(neg):
        frases.append("Meses com prejuízo operacional: <b class='neg'>" + ", ".join(fmt.mes_ano_de_chave(x) for x in neg["Ano_Mes"]) + "</b>.")
    best = serie.loc[serie["Margem"].idxmax()]
    frases.append(f"Melhor mês: <b class='pos'>{fmt.mes_ano_de_chave(best['Ano_Mes'])}</b> com margem de {fmt.pct(best['Margem'])}.")
if len(desp):
    top = desp.groupby("Categoria")["Valor_Periodo"].sum().sort_values(ascending=False)
    frases.append(f"Maior linha de custo: <b>{top.index[0]}</b> ({fmt.pct(top.iloc[0] / top.sum())} das despesas).")
if kl["receita_total"]:
    frases.append(f"Comissões de OTAs consomem <b>{fmt.pct(kl['comissoes'] / kl['receita_total'])}</b> da receita total "
                  f"— {fmt.moeda(kl['comissoes'])} no período.")
ui.insights(frases)
