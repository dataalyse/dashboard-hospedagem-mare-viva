"""Fábrica de gráficos Plotly com o template visual do painel.

Cada função recebe um DataFrame pronto e devolve uma figura (ou None quando
não há dados — o componente `grafico` mostra o estado vazio).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src import formatters as fmt
from src import theme as T

GEOJSON_BR = Path(__file__).resolve().parent.parent / "assets" / "br_states.geojson"

HOV_MOEDA = "R$ %{y:,.2f}"


def _vazio(df) -> bool:
    return df is None or len(df) == 0


def _base(fig: go.Figure, **kw) -> go.Figure:
    # fundo explícito: o Streamlit sobrescreve o fundo herdado do template
    fig.update_layout(template="mareviva", paper_bgcolor=T.SURFACE, plot_bgcolor=T.SURFACE, **kw)
    return fig


def rotulos_mes(serie: pd.Series) -> list[str]:
    return [fmt.mes_ano_de_chave(x) for x in serie]


def eixo_moeda(fig: go.Figure, vmin: float, vmax: float, n: int = 5, **seletor) -> None:
    """Ticks 'redondos' com rótulos em pt-BR (R$ 50 mil, R$ 1,2 mi) — o formato SI do Plotly sai em inglês."""
    vmin, vmax = min(float(vmin), 0.0), max(float(vmax), 0.0)
    if vmax == vmin:
        return
    bruto = (vmax - vmin) / max(n - 1, 1)
    mag = 10 ** np.floor(np.log10(bruto))
    passo = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= bruto), default=10 * mag)
    ticks = np.arange(np.floor(vmin / passo) * passo, vmax + passo * 0.999, passo)
    fig.update_yaxes(tickvals=ticks, ticktext=[fmt.moeda_eixo(t) for t in ticks], tickprefix="", **seletor)


# ================================================================ página 1
def gauge_ocupacao(ocup, meta) -> go.Figure | None:
    if ocup is None:
        return None
    v = ocup * 100
    mt = (meta or 0) * 100
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta" if meta else "gauge+number",
        value=v,
        number=dict(suffix="%", valueformat=",.1f", font=dict(size=40, color=T.TEXT)),
        delta=dict(reference=mt, valueformat=",.1f", suffix=" p.p.",
                   increasing=dict(color=T.POSITIVE), decreasing=dict(color=T.NEGATIVE)) if meta else None,
        gauge=dict(
            axis=dict(range=[0, 100], ticksuffix="%", tickcolor=T.MUTED, tickfont=dict(color=T.MUTED, size=10)),
            bar=dict(color=T.ACCENT, thickness=0.28),
            bgcolor="rgba(0,0,0,0)", borderwidth=0,
            steps=[
                dict(range=[0, 100], color="rgba(31,53,87,.55)"),
                *([dict(range=[max(mt - 3, 0), min(mt + 3, 100)], color="rgba(251,191,36,.18)")] if meta else []),
            ],
            threshold=dict(line=dict(color=T.WARNING, width=3), thickness=0.85, value=mt) if meta else None,
        ),
    ))
    return _base(fig, margin=dict(l=36, r=36, t=24, b=0))


def combo_receita_ocupacao(s: pd.DataFrame) -> go.Figure | None:
    if _vazio(s):
        return None
    x = rotulos_mes(s["Ano_Mes"])
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=x, y=s["Receita_Hospedagem"], name="Hospedagem", marker_color=T.ACCENT,
                hovertemplate="%{x}<br>Hospedagem: R$ %{y:,.2f}<extra></extra>")
    fig.add_bar(x=x, y=s["Consumos"], name="Consumos", marker_color=T.ACCENT_2,
                hovertemplate="%{x}<br>Consumos: R$ %{y:,.2f}<extra></extra>")
    fig.add_scatter(x=x, y=s["Ocupacao"], name="Ocupação", mode="lines+markers", secondary_y=True,
                    line=dict(color=T.TEXT, width=2.2), marker=dict(size=6, color=T.TEXT),
                    hovertemplate="%{x}<br>Ocupação: %{y:.1%}<extra></extra>")
    if s["Meta_Ocupacao"].notna().any():
        fig.add_scatter(x=x, y=s["Meta_Ocupacao"], name="Meta de ocupação", mode="lines", secondary_y=True,
                        line=dict(color=T.WARNING, width=1.6, dash="dash"),
                        hovertemplate="%{x}<br>Meta: %{y:.1%}<extra></extra>")
    fig.update_layout(barmode="stack", hovermode="x unified")
    eixo_moeda(fig, 0, float((s["Receita_Hospedagem"] + s["Consumos"]).max()), secondary_y=False)
    fig.update_yaxes(tickformat=".0%", range=[0, 1.05], dtick=0.25, showgrid=False, secondary_y=True)
    return _base(fig)


def donut(df: pd.DataFrame, nomes: str, valores: str, cores: dict | None = None,
          centro: str = "", hover_moeda: bool = True) -> go.Figure | None:
    if _vazio(df) or df[valores].sum() == 0:
        return None
    df = df.sort_values(valores, ascending=False)
    mapa = T.mapa_cores(df[nomes], cores)
    ht = ("%{label}<br>R$ %{value:,.2f} · %{percent}<extra></extra>" if hover_moeda
          else "%{label}<br>%{value:,.0f} · %{percent}<extra></extra>")
    fig = go.Figure(go.Pie(
        labels=df[nomes], values=df[valores], hole=0.62, sort=False,
        marker=dict(colors=[mapa[n] for n in df[nomes]], line=dict(color=T.SURFACE, width=2)),
        textinfo="percent", textfont=dict(color="#06101F", size=11), hovertemplate=ht,
    ))
    if centro:
        fig.add_annotation(text=centro, showarrow=False, font=dict(size=15, color=T.TEXT))
    fig.update_layout(legend=dict(orientation="h", y=-0.05, yanchor="top", x=0.5, xanchor="center",
                                  font=dict(size=10.5)),
                      margin=dict(l=0, r=0, t=8, b=8))
    return _base(fig)


def barras_h(df: pd.DataFrame, y: str, x: str, cor=None, cores: dict | None = None,
             fmt_x: str = "moeda", texto: list | None = None, hover_extra: str = "") -> go.Figure | None:
    if _vazio(df):
        return None
    df = df.sort_values(x)
    if cores is not None:
        cor = [cores.get(v, T.ACCENT) for v in (df[cor] if isinstance(cor, str) else df[y])]
    tick = dict(moeda=dict(tickprefix="R$ ", tickformat=",.0f"), pct=dict(tickformat=".0%"),
                num=dict(tickformat=",.0f"), nota=dict(tickformat=",.1f"))[fmt_x]
    hov = dict(moeda="R$ %{x:,.2f}", pct="%{x:.1%}", num="%{x:,.0f}", nota="%{x:,.2f}")[fmt_x]
    if texto is None:
        texto = [_fmt_valor(v, fmt_x) for v in df[x]]
    fig = go.Figure(go.Bar(
        x=df[x], y=df[y], orientation="h", marker_color=cor or T.ACCENT,
        text=texto, textposition="outside", textfont=dict(color=T.TEXT, size=11), cliponaxis=False,
        hovertemplate=f"%{{y}}<br>{hov}{hover_extra}<extra></extra>",
    ))
    fig.update_xaxes(showgrid=False, showticklabels=False, **tick)
    fig.update_yaxes(tickfont=dict(color=T.TEXT, size=11))
    return _base(fig, margin=dict(l=8, r=60, t=8, b=8), showlegend=False)


def _fmt_valor(v, f):
    return {"moeda": fmt.moeda, "pct": fmt.pct, "num": lambda z: fmt.num(z, 0), "nota": lambda z: fmt.num(z, 2)}[f](v)


# ================================================================ página 2
def heatmap_calendario(d: pd.DataFrame, feriados: dict) -> go.Figure | None:
    if _vazio(d):
        return None
    d = d.copy()
    d["dow"] = d["Data"].dt.weekday
    semana0 = d["Data"].min() - pd.to_timedelta(d["Data"].min().weekday(), unit="D")
    d["sem"] = ((d["Data"] - semana0).dt.days // 7).astype(int)
    n_sem = d["sem"].max() + 1
    z = np.full((7, n_sem), np.nan)
    txt = np.full((7, n_sem), "", dtype=object)
    for r in d.itertuples():
        z[r.dow, r.sem] = r.Ocupacao
        fer = feriados.get(r.Data)
        txt[r.dow, r.sem] = (
            f"<b>{fmt.data(r.Data)}</b> ({fmt.dia_semana(r.Data)})<br>Ocupação: {fmt.pct(r.Ocupacao)}"
            f"<br>ADR: {fmt.moeda(r.ADR)}" + (f"<br>🎉 {fer}" if fer else "")
        )
    inicio_sem = [semana0 + pd.Timedelta(weeks=i) for i in range(n_sem)]
    ticks = [i for i, s in enumerate(inicio_sem) if s.day <= 7 or i == 0]
    fig = go.Figure(go.Heatmap(
        z=z, x=list(range(n_sem)), y=fmt.DIAS_SEMANA_ABREV, text=txt, hoverinfo="text",
        hovertemplate="%{text}<extra></extra>",
        colorscale=T.ESCALA_SEQ, zmin=0, zmax=1, xgap=3, ygap=3,
        colorbar=dict(tickformat=".0%", thickness=8, len=0.9, outlinewidth=0, tickfont=dict(color=T.MUTED, size=10)),
    ))
    fig.update_xaxes(tickvals=ticks, ticktext=[fmt.mes_ano(inicio_sem[i] + pd.Timedelta(days=6)) for i in ticks],
                     showgrid=False, side="top", tickangle=0)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return _base(fig, margin=dict(l=8, r=8, t=28, b=8))


def heatmap_mes_dow(d: pd.DataFrame) -> go.Figure | None:
    if _vazio(d):
        return None
    d = d.copy()
    d["Ano_Mes"] = d["Data"].dt.strftime("%Y-%m")
    d["dow"] = d["Data"].dt.weekday
    pv = d.pivot_table(index="dow", columns="Ano_Mes", values="Ocupacao", aggfunc="mean").reindex(range(7))
    fig = go.Figure(go.Heatmap(
        z=pv.values, x=rotulos_mes(pv.columns), y=fmt.DIAS_SEMANA_ABREV,
        colorscale=T.ESCALA_TEXTO, zmin=0, zmax=1, xgap=2, ygap=2,
        text=np.vectorize(lambda v: "" if np.isnan(v) else fmt.pct(v, 0))(pv.values),
        texttemplate="%{text}", textfont=dict(size=10, color=T.TEXT),
        hovertemplate="%{x} · %{y}<br>Ocupação média: %{z:.1%}<extra></extra>",
        colorbar=dict(tickformat=".0%", thickness=8, outlinewidth=0, tickfont=dict(color=T.MUTED, size=10)),
    ))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(showgrid=False, tickangle=0)
    return _base(fig)


def linha_ocupacao_diaria(d: pd.DataFrame, feriados: dict) -> go.Figure | None:
    if _vazio(d):
        return None
    d = d.copy()
    d["MM7"] = d["Ocupacao"].rolling(7, min_periods=1).mean()
    custom = np.stack([d["Data"].dt.strftime("%d/%m/%Y"), d["Noites"]], axis=-1)
    fig = go.Figure()
    for dt, nome in feriados.items():
        if d["Data"].min() <= dt <= d["Data"].max():
            fig.add_vrect(x0=dt - pd.Timedelta(hours=12), x1=dt + pd.Timedelta(hours=12),
                          fillcolor=T.WARNING, opacity=0.13, line_width=0, layer="below")
    fig.add_scatter(x=d["Data"], y=d["Ocupacao"], mode="lines", name="Ocupação diária",
                    line=dict(color="rgba(34,211,238,.35)", width=1), customdata=custom,
                    hovertemplate="%{customdata[0]}<br>Ocupação: %{y:.1%} · %{customdata[1]} noites<extra></extra>")
    fig.add_scatter(x=d["Data"], y=d["MM7"], mode="lines", name="Média móvel 7 dias",
                    line=dict(color=T.ACCENT, width=2.4), hovertemplate="MM7: %{y:.1%}<extra></extra>")
    fx = [dt for dt in feriados if d["Data"].min() <= dt <= d["Data"].max()]
    if fx:
        fig.add_scatter(x=fx, y=[1.02] * len(fx), mode="markers", name="Feriado",
                        marker=dict(symbol="triangle-down", color=T.WARNING, size=7),
                        text=[feriados[x] for x in fx], hovertemplate="%{text}<extra></extra>")
    fig.update_yaxes(tickformat=".0%", range=[0, 1.06])
    fig.update_xaxes(tickformat="%d/%m", showgrid=False)
    return _base(fig, hovermode="x unified")


def bolhas_adr_ocupacao(df: pd.DataFrame) -> go.Figure | None:
    if _vazio(df):
        return None
    tam = df["Receita"].clip(lower=1)
    sizeref = 2.0 * tam.max() / (44 ** 2)
    df = df.assign(Rotulo=df["Tipo"].str.replace("Dormitório", "Dorm.", regex=False)
                   .str.replace(r"\s*\(\d+ camas\)", "", regex=True))
    df = df.sort_values("ADR")
    df["Pos"] = ["middle right" if i % 2 == 0 else "middle left" for i in range(len(df))]
    fig = go.Figure()
    for cat, g in df.groupby("Categoria"):
        fig.add_scatter(
            x=g["Ocupacao"], y=g["ADR"], mode="markers+text", name=cat, text=g["Rotulo"],
            textposition=g["Pos"].tolist(), textfont=dict(color=T.TEXT, size=10.5),
            marker=dict(size=g["Receita"].clip(lower=1), sizemode="area", sizeref=sizeref, sizemin=8,
                        color=T.CORES_CATEGORIA.get(cat, T.ACCENT), opacity=0.75, line=dict(color=T.BG, width=1)),
            customdata=np.stack([g["Receita"], g["Noites"]], axis=-1),
            hovertemplate="<b>%{text}</b><br>Ocupação: %{x:.1%}<br>ADR: R$ %{y:,.2f}"
                          "<br>Receita: R$ %{customdata[0]:,.2f} · %{customdata[1]:,.0f} noites<extra></extra>",
        )
    pad = max((df["Ocupacao"].max() - df["Ocupacao"].min()) * 0.35, 0.03)
    fig.update_xaxes(tickformat=".0%", title="Ocupação", range=[df["Ocupacao"].min() - pad, df["Ocupacao"].max() + pad])
    fig.update_yaxes(tickprefix="R$ ", tickformat=",.0f", title="ADR", rangemode="tozero")
    return _base(fig)


def barras_agrupadas(df: pd.DataFrame, x: str, y: str, cor: str, cores: dict, ordem_x: list | None = None,
                     fmt_y: str = "moeda") -> go.Figure | None:
    if _vazio(df):
        return None
    fig = go.Figure()
    for k, g in df.groupby(cor, sort=False):
        if ordem_x:
            g = g.set_index(x).reindex(ordem_x).reset_index()
        txt = [_fmt_valor(v, fmt_y) if pd.notna(v) else "" for v in g[y]]
        hov = "R$ %{y:,.2f}" if fmt_y == "moeda" else "%{y:.1%}"
        fig.add_bar(x=g[x], y=g[y], name=k, marker_color=cores.get(k, T.ACCENT), text=txt,
                    textposition="outside", textfont=dict(size=10, color=T.TEXT), cliponaxis=False,
                    hovertemplate=f"%{{x}} · {k}<br>{hov}<extra></extra>")
    fig.update_layout(barmode="group")
    if fmt_y == "moeda":
        fig.update_yaxes(tickprefix="R$ ", tickformat=",.0f")
    else:
        fig.update_yaxes(tickformat=".0%")
    return _base(fig)


def linhas_ano_contra_ano(s: pd.DataFrame, col: str = "Ocupacao", fmt_y: str = "pct") -> go.Figure | None:
    if _vazio(s):
        return None
    s = s.copy()
    s["Ano"] = s["Ano_Mes"].str[:4]
    s["Mes"] = s["Ano_Mes"].str[5:7].astype(int)
    fig = go.Figure()
    cores = {"2025": T.ACCENT_2, "2026": T.ACCENT}
    for ano, g in s.groupby("Ano"):
        g = g[g[col].notna()]
        fig.add_scatter(x=[fmt.MESES_ABREV[m - 1] for m in g["Mes"]], y=g[col], name=ano, mode="lines+markers",
                        line=dict(color=cores.get(ano, T.MUTED), width=2.4, dash="dot" if ano == "2025" else "solid"),
                        marker=dict(size=6),
                        hovertemplate=f"%{{x}}/{ano[-2:]}: " + ("%{y:.1%}" if fmt_y == "pct" else "R$ %{y:,.2f}") + "<extra></extra>")
    fig.update_xaxes(categoryorder="array", categoryarray=fmt.MESES_ABREV, showgrid=False)
    fig.update_yaxes(tickformat=".0%" if fmt_y == "pct" else ",.0f")
    return _base(fig, hovermode="x unified")


# ================================================================ página 3
def sankey(res: pd.DataFrame) -> go.Figure | None:
    if _vazio(res):
        return None
    canais = res["Canal"].value_counts().index.tolist()
    cats = res["Categoria"].dropna().unique().tolist()
    stats = [s for s in ["Concluída", "Hospedado", "Confirmada", "No-show", "Cancelada"] if s in set(res["Status"])]
    nos = canais + cats + stats
    idx = {n: i for i, n in enumerate(nos)}
    cores_nos = ([T.cor_canal(c) for c in canais] + [T.CORES_CATEGORIA.get(c, T.ACCENT) for c in cats]
                 + [T.CORES_STATUS.get(s, T.MUTED) for s in stats])
    a = res.groupby(["Canal", "Categoria"]).size().reset_index(name="n")
    b = res.groupby(["Categoria", "Status"]).size().reset_index(name="n")
    _rgba = T.rgba

    src = [idx[c] for c in a["Canal"]] + [idx[c] for c in b["Categoria"]]
    tgt = [idx[c] for c in a["Categoria"]] + [idx[s] for s in b["Status"]]
    val = a["n"].tolist() + b["n"].tolist()
    cor_l = [_rgba(T.cor_canal(c)) for c in a["Canal"]] + [_rgba(T.CORES_STATUS.get(s, T.MUTED)) for s in b["Status"]]
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=nos, color=cores_nos, pad=14, thickness=14, line=dict(width=0),
                  hovertemplate="%{label}<br>%{value:,.0f} reservas<extra></extra>"),
        link=dict(source=src, target=tgt, value=val, color=cor_l,
                  hovertemplate="%{source.label} → %{target.label}<br>%{value:,.0f} reservas<extra></extra>"),
        textfont=dict(color=T.TEXT, size=11, family=T.FONT),
    ))
    return _base(fig, margin=dict(l=4, r=4, t=8, b=8))


def barras_100(df: pd.DataFrame, x: str, cor: str, valor: str, cores: dict) -> go.Figure | None:
    if _vazio(df):
        return None
    pv = df.pivot_table(index=x, columns=cor, values=valor, aggfunc="sum").fillna(0).sort_index()
    tot = pv.sum(axis=1).replace(0, np.nan)
    sh = pv.div(tot, axis=0)
    xl = rotulos_mes(sh.index)
    fig = go.Figure()
    for c in sh.sum().sort_values(ascending=False).index:
        fig.add_bar(x=xl, y=sh[c], name=c, marker_color=cores.get(c, T.cor_canal(c)),
                    customdata=pv[c], hovertemplate=f"%{{x}} · {c}<br>%{{y:.1%}} · %{{customdata:,.0f}} reservas<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.18)
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    return _base(fig)


def box_por_grupo(df: pd.DataFrame, grupo: str, valor: str, cores: dict, sufixo: str = "dias") -> go.Figure | None:
    if _vazio(df):
        return None
    ordem = df.groupby(grupo)[valor].median().sort_values().index
    fig = go.Figure()
    for g in ordem:
        v = df.loc[df[grupo] == g, valor]
        cor = cores.get(g, T.ACCENT)
        fig.add_box(y=v, name=g, marker_color=cor, line=dict(color=cor, width=1.4), fillcolor=T.rgba(cor, 0.2),
                    boxmean=True, marker=dict(size=3, opacity=0.4),
                    hovertemplate=f"{g}<br>%{{y:,.0f}} {sufixo}<extra></extra>")
    fig.update_yaxes(title=sufixo.capitalize())
    fig.update_xaxes(tickfont=dict(size=10.5, color=T.TEXT))
    return _base(fig, showlegend=False)


def histograma(df: pd.DataFrame, valor: str, cor: str | None, cores: dict, nbins: int | None = None,
               rotulo: str = "", xbins: dict | None = None, linha_corte: float | None = None) -> go.Figure | None:
    if _vazio(df):
        return None
    fig = go.Figure()
    grupos = df.groupby(cor) if cor else [("Todas", df)]
    for k, g in grupos:
        fig.add_histogram(x=g[valor], name=k, marker_color=cores.get(k, T.ACCENT), opacity=0.85,
                          nbinsx=nbins, xbins=xbins,
                          hovertemplate=f"{k}<br>{rotulo} %{{x}}<br>%{{y:,.0f}} registros<extra></extra>")
    if linha_corte is not None:
        fig.add_vline(x=linha_corte, line=dict(color=T.WARNING, dash="dash", width=1.6),
                      annotation_text=f"corte {fmt.num(linha_corte, 1)}", annotation_font_color=T.WARNING)
    fig.update_layout(barmode="stack", bargap=0.08)
    fig.update_xaxes(title=rotulo)
    return _base(fig, showlegend=bool(cor))


def funil(etapas: list[tuple[str, int]]) -> go.Figure | None:
    if not etapas or etapas[0][1] == 0:
        return None
    fig = go.Figure(go.Funnel(
        y=[e[0] for e in etapas], x=[e[1] for e in etapas],
        texttemplate="%{value:,.0f} · %{percentInitial:.0%}", textfont=dict(color="#06101F", size=12),
        marker=dict(color=[T.ACCENT, "#2BB7D9", T.ACCENT_2, "#C4B5FD"][: len(etapas)]),
        connector=dict(fillcolor="rgba(31,53,87,.6)", line=dict(width=0)),
        hovertemplate="%{y}<br>%{value:,.0f} reservas · %{percentInitial:.1%} do total<extra></extra>",
    ))
    fig.update_yaxes(tickfont=dict(color=T.TEXT))
    return _base(fig, margin=dict(l=8, r=8, t=8, b=8))


def linha_semanal(df: pd.DataFrame, x: str, y: str, nome: str = "Reservas criadas") -> go.Figure | None:
    if _vazio(df):
        return None
    df = df.copy()
    df["MM4"] = df[y].rolling(4, min_periods=1).mean()
    fig = go.Figure()
    fig.add_bar(x=df[x], y=df[y], name=nome, marker_color="rgba(34,211,238,.35)",
                customdata=df[x].dt.strftime("%d/%m/%Y"),
                hovertemplate="Semana de %{customdata}<br>%{y:,.0f} reservas<extra></extra>")
    fig.add_scatter(x=df[x], y=df["MM4"], name="Média 4 semanas", mode="lines",
                    line=dict(color=T.ACCENT, width=2.4), hovertemplate="Média 4 sem.: %{y:,.1f}<extra></extra>")
    fig.update_xaxes(tickformat="%d/%m/%y", showgrid=False)
    return _base(fig, hovermode="x unified", bargap=0.1)


# ================================================================ página 4
def carregar_geojson_br():
    if not GEOJSON_BR.exists():
        return None
    try:
        with open(GEOJSON_BR, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def mapa_brasil(df: pd.DataFrame, geo) -> go.Figure | None:
    if _vazio(df) or geo is None:
        return None
    # inclui as UFs sem hóspedes (valor 0) para desenhar o país inteiro
    todas = pd.DataFrame({"UF": [ft["properties"]["sigla"] for ft in geo["features"]]})
    df = todas.merge(df, on="UF", how="left").fillna({"Hospedes": 0, "Noites": 0, "Receita": 0})
    fig = go.Figure(go.Choropleth(
        geojson=geo, featureidkey="properties.sigla", locations=df["UF"], z=df["Hospedes"],
        colorscale=T.ESCALA_SEQ, marker_line_color=T.BORDER, marker_line_width=0.6,
        customdata=np.stack([df["Noites"], df["Receita"]], axis=-1),
        hovertemplate="<b>%{location}</b><br>%{z:,.0f} hóspedes<br>%{customdata[0]:,.0f} noites"
                      "<br>R$ %{customdata[1]:,.2f}<extra></extra>",
        colorbar=dict(thickness=8, outlinewidth=0, tickfont=dict(color=T.MUTED, size=10), title=None),
    ))
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
    return _base(fig, margin=dict(l=0, r=0, t=0, b=0))


PAISES_EN = {
    "Brasil": "Brazil", "Argentina": "Argentina", "Chile": "Chile", "Alemanha": "Germany",
    "Uruguai": "Uruguay", "Estados Unidos": "United States", "França": "France", "Portugal": "Portugal",
    "Espanha": "Spain", "Reino Unido": "United Kingdom", "Itália": "Italy", "Holanda": "Netherlands",
    "Canadá": "Canada", "Paraguai": "Paraguay", "Colômbia": "Colombia", "Peru": "Peru", "México": "Mexico",
}


def mapa_mundi(df: pd.DataFrame) -> go.Figure | None:
    if _vazio(df):
        return None
    df = df.copy()
    df["EN"] = df["Pais"].map(PAISES_EN).fillna(df["Pais"])
    fig = go.Figure(go.Choropleth(
        locations=df["EN"], locationmode="country names", z=df["Hospedes"], text=df["Pais"],
        colorscale=[[0, "#4C1D95"], [0.5, T.ACCENT_2], [1, "#EDE9FE"]],
        marker_line_color=T.BG, marker_line_width=0.5,
        customdata=np.stack([df["Noites"], df["Receita"]], axis=-1),
        hovertemplate="<b>%{text}</b><br>%{z:,.0f} hóspedes<br>%{customdata[0]:,.0f} noites"
                      "<br>R$ %{customdata[1]:,.2f}<extra></extra>",
        colorbar=dict(thickness=8, outlinewidth=0, tickfont=dict(color=T.MUTED, size=10)),
    ))
    fig.update_geos(projection_type="natural earth", showcountries=True, showland=True,
                    landcolor=T.SURFACE_2, countrycolor=T.BORDER, showocean=True, oceancolor="rgba(0,0,0,0)",
                    showframe=False, showcoastlines=False, lataxis_range=[-58, 75], bgcolor="rgba(0,0,0,0)")
    return _base(fig, margin=dict(l=0, r=0, t=0, b=0))


def treemap(df: pd.DataFrame, caminho: list[str], valor: str, cores_raiz: dict | None = None,
            unidade: str = "noites", moeda: bool = False) -> go.Figure | None:
    if _vazio(df) or df[valor].sum() == 0:
        return None
    fig = px.treemap(df, path=[px.Constant("Total")] + caminho, values=valor, color=caminho[0],
                     color_discrete_map={**(cores_raiz or {}), "(?)": T.SURFACE_2})
    ht = ("<b>%{label}</b><br>R$ %{value:,.2f} · %{percentRoot:.1%} do total<extra></extra>" if moeda
          else f"<b>%{{label}}</b><br>%{{value:,.0f}} {unidade} · %{{percentRoot:.1%}} do total<extra></extra>")
    fig.update_traces(hovertemplate=ht, marker=dict(line=dict(color=T.BG, width=1.5)),
                      textfont=dict(color="#06101F", family=T.FONT), root_color=T.SURFACE,
                      texttemplate="<b>%{label}</b><br>%{percentRoot:.1%}")
    return _base(fig, margin=dict(l=0, r=0, t=4, b=0))


def piramide(df: pd.DataFrame, faixa: str, grupo: str, valor: str, esq: str, dir_: str) -> go.Figure | None:
    if _vazio(df):
        return None
    ordem = sorted(df[faixa].dropna().unique())
    pv = df.pivot_table(index=faixa, columns=grupo, values=valor, aggfunc="sum").reindex(ordem).fillna(0)
    tot = pv.sum()
    sh = pv / tot.replace(0, np.nan)
    fig = go.Figure()
    for lado, sinal in [(esq, -1), (dir_, 1)]:
        if lado not in sh:
            continue
        fig.add_bar(y=sh.index, x=sh[lado] * sinal, name=lado, orientation="h",
                    marker_color=T.CORES_CATEGORIA.get(lado, T.ACCENT), customdata=np.stack([sh[lado], pv[lado]], axis=-1),
                    text=[fmt.pct(v, 0) for v in sh[lado]], textposition="outside", textfont=dict(size=10, color=T.TEXT),
                    hovertemplate=f"{lado} · %{{y}}<br>%{{customdata[0]:.1%}} · %{{customdata[1]:,.0f}} hóspedes<extra></extra>")
    m = float(np.nanmax(sh.values)) if sh.size else 0.5
    fig.update_layout(barmode="relative", bargap=0.15)
    fig.update_xaxes(range=[-m * 1.3, m * 1.3], tickvals=[-m, -m / 2, 0, m / 2, m],
                     ticktext=[fmt.pct(abs(v), 0) for v in [-m, -m / 2, 0, m / 2, m]], showgrid=False)
    fig.update_yaxes(title="Faixa etária", tickfont=dict(color=T.TEXT))
    return _base(fig)


# ================================================================ página 5
def radar(atual: dict, comparativo: dict | None, rot_atual: str, rot_cmp: str) -> go.Figure | None:
    if not atual or all(v is None or np.isnan(v) for v in atual.values()):
        return None
    cats = list(atual)
    fig = go.Figure()
    if comparativo and any(v is not None and not np.isnan(v) for v in comparativo.values()):
        vals = [comparativo.get(c) for c in cats]
        fig.add_scatterpolar(r=vals + vals[:1], theta=cats + cats[:1], name=rot_cmp, fill="toself",
                             line=dict(color=T.ACCENT_2, width=1.6, dash="dot"), fillcolor="rgba(167,139,250,.12)",
                             hovertemplate="%{theta}: %{r:,.2f}<extra>" + rot_cmp + "</extra>")
    vals = [atual[c] for c in cats]
    fig.add_scatterpolar(r=vals + vals[:1], theta=cats + cats[:1], name=rot_atual, fill="toself",
                         line=dict(color=T.ACCENT, width=2.2), fillcolor="rgba(34,211,238,.18)",
                         hovertemplate="%{theta}: %{r:,.2f}<extra>" + rot_atual + "</extra>")
    todos = [v for v in vals if v is not None and not np.isnan(v)]
    lo = max(0, np.floor(min(todos) - 0.6)) if todos else 0
    fig.update_polars(radialaxis=dict(range=[lo, 10], tickformat=",.1f", angle=90, tickangle=90))
    return _base(fig, margin=dict(l=40, r=40, t=24, b=40),
                 legend=dict(orientation="h", y=-0.12, yanchor="top", x=0.5, xanchor="center"))


def linha_com_meta(s: pd.DataFrame, col: str, meta_col: str | None, fmt_y: str = "nota",
                   nome: str = "Nota média", meta_fixa: float | None = None) -> go.Figure | None:
    if _vazio(s) or s[col].notna().sum() == 0:
        return None
    x = rotulos_mes(s["Ano_Mes"])
    hov = {"nota": "%{y:,.2f}", "pct": "%{y:.1%}", "moeda": "R$ %{y:,.2f}"}[fmt_y]
    fig = go.Figure()
    fig.add_scatter(x=x, y=s[col], name=nome, mode="lines+markers", line=dict(color=T.ACCENT, width=2.4),
                    marker=dict(size=7), connectgaps=False, hovertemplate=f"%{{x}}<br>{nome}: {hov}<extra></extra>")
    if meta_fixa is not None:
        fig.add_hline(y=meta_fixa, line=dict(color=T.WARNING, dash="dash", width=1.6),
                      annotation_text=f"meta {fmt.num(meta_fixa, 1)}", annotation_font_color=T.WARNING,
                      annotation_position="top left")
    elif meta_col and s[meta_col].notna().any():
        fig.add_scatter(x=x, y=s[meta_col], name="Meta", mode="lines", line=dict(color=T.WARNING, dash="dash", width=1.6),
                        hovertemplate=f"Meta: {hov}<extra></extra>")
    if fmt_y == "pct":
        fig.update_yaxes(tickformat=".0%")
    elif fmt_y == "nota":
        fig.update_yaxes(tickformat=",.1f")
    return _base(fig, hovermode="x unified")


def matriz_prioridade(df: pd.DataFrame) -> go.Figure | None:
    if _vazio(df) or df["Correlacao"].isna().all():
        return None
    xm, ym = df["Nota"].mean(), df["Correlacao"].mean()
    fig = go.Figure()
    x0, x1 = df["Nota"].min() - 0.15, df["Nota"].max() + 0.15
    y0, y1 = df["Correlacao"].min() - 0.05, df["Correlacao"].max() + 0.05
    fig.add_shape(type="rect", x0=x0, x1=xm, y0=ym, y1=y1, fillcolor="rgba(248,113,113,.09)", line_width=0, layer="below")
    fig.add_annotation(x=x0, y=y1, text="CORRIGIR PRIMEIRO", showarrow=False, xanchor="left", yanchor="top",
                       font=dict(color=T.NEGATIVE, size=10.5))
    fig.add_annotation(x=x1, y=y1, text="MANTER", showarrow=False, xanchor="right", yanchor="top",
                       font=dict(color=T.POSITIVE, size=10.5))
    fig.add_annotation(x=x0, y=y0, text="MONITORAR", showarrow=False, xanchor="left", yanchor="bottom",
                       font=dict(color=T.MUTED, size=10.5))
    fig.add_vline(x=xm, line=dict(color=T.BORDER, dash="dot"))
    fig.add_hline(y=ym, line=dict(color=T.BORDER, dash="dot"))
    cor = [T.NEGATIVE if (n < xm and c > ym) else (T.POSITIVE if n >= xm and c > ym else T.ACCENT)
           for n, c in zip(df["Nota"], df["Correlacao"])]
    ordem = df["Nota"].rank(method="first").astype(int)
    pos = ["top center" if r % 2 else "bottom center" for r in ordem]
    fig.add_scatter(x=df["Nota"], y=df["Correlacao"], mode="markers+text", text=df["Criterio"],
                    textposition=pos, textfont=dict(color=T.TEXT, size=11),
                    marker=dict(size=16, color=cor, line=dict(color=T.BG, width=1.5)),
                    hovertemplate="<b>%{text}</b><br>Nota: %{x:,.2f}<br>Correlação com a nota geral: %{y:,.2f}<extra></extra>")
    fig.update_xaxes(title="Nota média do critério", tickformat=",.1f", range=[x0, x1])
    fig.update_yaxes(title="Impacto (correlação)", tickformat=",.2f", range=[y0, y1])
    return _base(fig, showlegend=False)


def heatmap_simples(pv: pd.DataFrame, fmt_z: str = "nota", escala=None, zmin=None, zmax=None) -> go.Figure | None:
    if pv is None or pv.empty:
        return None
    txt = np.vectorize(lambda v: "" if pd.isna(v) else fmt.num(v, 1))(pv.values.astype(float))
    fig = go.Figure(go.Heatmap(
        z=pv.values, x=list(pv.columns), y=list(pv.index), colorscale=escala or T.ESCALA_SEQ,
        zmin=zmin, zmax=zmax, xgap=2, ygap=2, text=txt, texttemplate="%{text}",
        textfont=dict(size=11, color=T.TEXT),
        hovertemplate="%{y} · %{x}<br>Nota: %{z:,.2f}<extra></extra>",
        colorbar=dict(thickness=8, outlinewidth=0, tickfont=dict(color=T.MUTED, size=10)),
    ))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=T.TEXT))
    fig.update_xaxes(showgrid=False, side="top", tickfont=dict(color=T.TEXT))
    return _base(fig, margin=dict(l=8, r=8, t=30, b=8))


# ================================================================ página 6
def waterfall_dre(linhas: list[tuple[str, float, str]]) -> go.Figure | None:
    """linhas: (rótulo, valor, 'relative' | 'total')"""
    if not linhas or all(v == 0 for _, v, _ in linhas):
        return None
    fig = go.Figure(go.Waterfall(
        x=[l[0] for l in linhas], y=[l[1] for l in linhas], measure=[l[2] for l in linhas],
        text=[fmt.moeda_compacta(l[1]) for l in linhas], textposition="outside",
        textfont=dict(color=T.TEXT, size=11), cliponaxis=False,
        increasing=dict(marker=dict(color=T.ACCENT)), decreasing=dict(marker=dict(color=T.NEGATIVE)),
        totals=dict(marker=dict(color=T.POSITIVE)),
        connector=dict(line=dict(color=T.BORDER, width=1, dash="dot")),
        hovertemplate="%{x}<br>R$ %{y:,.2f}<extra></extra>",
    ))
    acum = np.cumsum([v if mde == "relative" else 0 for _, v, mde in linhas])
    topo = max(max(acum), max(v for _, v, _ in linhas))
    eixo_moeda(fig, min(min(acum), 0), topo * 1.12)
    fig.update_xaxes(tickfont=dict(color=T.TEXT))
    return _base(fig, showlegend=False, margin=dict(l=8, r=8, t=24, b=8))


def despesas_empilhadas(desp: pd.DataFrame, receita: pd.DataFrame) -> go.Figure | None:
    if _vazio(desp):
        return None
    pv = desp.pivot_table(index="Ano_Mes", columns="Categoria", values="Valor", aggfunc="sum").fillna(0).sort_index()
    ordem = list(pv.sum().sort_values(ascending=False).index)
    if len(ordem) > 7:  # mantém as 6 maiores e agrupa o resto
        resto = ordem[6:]
        pv["Outras"] = pv[resto].sum(axis=1)
        pv = pv.drop(columns=resto)
        ordem = ordem[:6] + ["Outras"]
    cores = T.mapa_cores(ordem, {"Outras": "#475569"})
    x = rotulos_mes(pv.index)
    fig = go.Figure()
    for c in ordem:
        fig.add_bar(x=x, y=pv[c], name=c, marker_color=cores[c],
                    hovertemplate=f"{c}<br>R$ %{{y:,.2f}}<extra></extra>")
    if receita is not None and len(receita):
        r = receita.set_index("Ano_Mes").reindex(pv.index)
        fig.add_scatter(x=x, y=r["Receita_Total"], name="Receita total", mode="lines+markers",
                        line=dict(color=T.TEXT, width=2.2), marker=dict(size=6),
                        hovertemplate="Receita total: R$ %{y:,.2f}<extra></extra>")
    fig.update_layout(barmode="stack", hovermode="x unified",
                      legend=dict(font=dict(size=10)))
    topo = pv.sum(axis=1).max()
    if receita is not None and len(receita):
        topo = max(topo, float(r["Receita_Total"].max()))
    eixo_moeda(fig, 0, topo)
    return _base(fig)


def linha_margem(s: pd.DataFrame, limite: float = 0.15) -> go.Figure | None:
    if _vazio(s) or s["Margem"].notna().sum() == 0:
        return None
    s = s[s["Margem"].notna()]
    x = rotulos_mes(s["Ano_Mes"])
    cor = [T.NEGATIVE if v < 0 else (T.WARNING if v < limite else T.POSITIVE) for v in s["Margem"]]
    fig = go.Figure()
    fig.add_hrect(y0=min(s["Margem"].min(), 0) - 0.05, y1=0, fillcolor="rgba(248,113,113,.07)", line_width=0, layer="below")
    fig.add_hline(y=limite, line=dict(color=T.WARNING, dash="dash", width=1.4),
                  annotation_text=f"referência {fmt.pct(limite, 0)}", annotation_font_color=T.WARNING,
                  annotation_position="top left")
    fig.add_scatter(x=x, y=s["Margem"], mode="lines+markers", name="Margem GOP",
                    line=dict(color=T.ACCENT, width=2.2), marker=dict(size=10, color=cor, line=dict(color=T.BG, width=1.5)),
                    customdata=s["GOP"], hovertemplate="%{x}<br>Margem: %{y:.1%}<br>GOP: R$ %{customdata:,.2f}<extra></extra>")
    fig.update_yaxes(tickformat=".0%", zeroline=True, zerolinecolor=T.MUTED)
    return _base(fig, showlegend=False)


# ================================================================ página 7
def barras_otb(df: pd.DataFrame) -> go.Figure | None:
    if _vazio(df):
        return None
    fig = go.Figure()
    fig.add_bar(x=df["Mes"], y=df["Realizado_LY"], name="Realizado no ano anterior", marker_color="rgba(167,139,250,.45)",
                text=[fmt.pct(v) for v in df["Realizado_LY"]], textposition="outside", textfont=dict(color=T.MUTED, size=11),
                hovertemplate="%{x} (ano anterior)<br>Ocupação realizada: %{y:.1%}<extra></extra>")
    fig.add_bar(x=df["Mes"], y=df["OTB"], name="Já garantido (carteira)", marker_color=T.ACCENT,
                text=[fmt.pct(v) for v in df["OTB"]], textposition="outside", textfont=dict(color=T.TEXT, size=11),
                customdata=df["Gap"],
                hovertemplate="%{x}<br>Ocupação garantida: %{y:.1%}<br>Gap a vender: %{customdata:.1%}<extra></extra>")
    fig.update_layout(barmode="group", bargap=0.3)
    fig.update_yaxes(tickformat=".0%", range=[0, max(1.0, float(df[["OTB", "Realizado_LY"]].max().max()) * 1.15)])
    return _base(fig)


def gantt(df: pd.DataFrame, ordem_unidades: list[str], inicio, fim) -> go.Figure | None:
    if _vazio(df):
        return None
    df = df.copy()
    df["Entrada"] = df["Check_in"].dt.strftime("%d/%m")
    df["Saida"] = df["Check_out"].dt.strftime("%d/%m")
    df["Valor"] = df["Valor_Hospedagem"].map(fmt.moeda)
    fig = px.timeline(
        df, x_start="Check_in", x_end="Check_out", y="Unidade", color="Canal",
        color_discrete_map={c: T.cor_canal(c) for c in df["Canal"].unique()},
        custom_data=["ID_Reserva", "Entrada", "Saida", "Noites", "Qtd_Hospedes", "Valor", "Canal"],
        category_orders={"Unidade": ordem_unidades},
    )
    fig.update_traces(
        marker=dict(line=dict(color=T.BG, width=1.2)), opacity=0.92,
        hovertemplate="<b>%{y}</b> · %{customdata[0]}<br>%{customdata[1]} → %{customdata[2]} · %{customdata[3]} noites"
                      "<br>%{customdata[4]} hóspede(s) · %{customdata[5]}<br>%{customdata[6]}<extra></extra>",
    )
    fig.update_xaxes(range=[pd.Timestamp(inicio), pd.Timestamp(fim)], tickformat="%d/%m", dtick=7 * 86400000,
                     showgrid=True)
    fig.update_yaxes(title=None, tickfont=dict(size=10, color=T.TEXT), showgrid=True, gridcolor="rgba(31,53,87,.35)")
    fig.add_vline(x=pd.Timestamp(inicio), line=dict(color=T.WARNING, width=1.4, dash="dot"))
    return _base(fig, bargap=0.25, legend_title_text="")


def linhas_pickup(df: pd.DataFrame) -> go.Figure | None:
    if _vazio(df):
        return None
    fig = go.Figure()
    estilos = {"atual": dict(color=T.ACCENT, width=2.6), "anterior": dict(color=T.ACCENT_2, width=2, dash="dot")}
    for serie, g in df.groupby("Serie", sort=False):
        k = "atual" if g["Atual"].iloc[0] else "anterior"
        fig.add_scatter(x=g["Dias_Antes"], y=g["Noites_Acum"], name=serie, mode="lines", line=estilos[k],
                        hovertemplate=f"{serie}<br>%{{x}} dias antes do mês<br>%{{y:,.0f}} noites reservadas<extra></extra>")
    fig.update_xaxes(autorange="reversed", title="Dias antes de 01/dez")
    fig.update_yaxes(title="Noites reservadas (acumulado)", tickformat=",.0f")
    return _base(fig, hovermode="x unified")
