"""Componentes visuais: cartão de KPI, cabeçalho de página, cards de gráfico, insights."""
from __future__ import annotations

import html
import re
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import formatters as fmt
from src.theme import ACCENT, MUTED, NEGATIVE, POSITIVE

# ícones de linha (24×24, stroke)
_ICONES = {
    "cama": '<path d="M3 18v-7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v7M3 14h18M7 9V6h4v3M3 18v2M21 18v2"/>',
    "tag": '<path d="M20 12l-8 8-9-9V3h8z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
    "grafico": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "carteira": '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M16 12h2M3 10h18"/>',
    "tendencia": '<path d="M3 17l6-6 4 4 8-8M15 7h6v6"/>',
    "estrela": '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
    "pessoas": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M21.5 20a6.5 6.5 0 0 0-4-6"/>',
    "calendario": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "porcento": '<path d="M19 5L5 19"/><circle cx="7" cy="7" r="2.5"/><circle cx="17" cy="17" r="2.5"/>',
    "relogio": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "globo": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    "recibo": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6"/>',
    "lua": '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    "x": '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "seta": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "repetir": '<path d="M17 2l4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 0 1-3 3H3"/>',
    "joinha": '<path d="M7 11v9H4v-9zM7 11l4-8a2 2 0 0 1 3 2l-1 5h6a2 2 0 0 1 2 2l-2 7a2 2 0 0 1-2 1H7"/>',
    "cifrao": '<path d="M12 2v20M17 6H9.5a3 3 0 0 0 0 6h5a3 3 0 0 1 0 6H6"/>',
}


def icone(nome: str) -> str:
    corpo = _ICONES.get(nome, _ICONES["grafico"])
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round">{corpo}</svg>')


def _sparkline(valores, cor: str = ACCENT) -> str:
    v = [x for x in (valores or []) if x is not None and not (isinstance(x, float) and np.isnan(x))]
    if len(v) < 2:
        return ""
    w, h, pad = 120, 40, 3
    lo, hi = min(v), max(v)
    rng = (hi - lo) or 1
    pts = [(pad + i * (w - 2 * pad) / (len(v) - 1), h - pad - (x - lo) / rng * (h - 2 * pad)) for i, x in enumerate(v)]
    linha = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{pts[0][0]:.1f},{h} " + linha + f" {pts[-1][0]:.1f},{h}"
    gid = f"g{abs(hash(linha)) % 10**8}"
    return (
        f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{cor}" stop-opacity=".35"/><stop offset="1" stop-color="{cor}" stop-opacity="0"/>'
        f'</linearGradient></defs>'
        f'<polygon points="{area}" fill="url(#{gid})"/>'
        f'<polyline points="{linha}" fill="none" stroke="{cor}" stroke-width="1.6" stroke-linejoin="round"/>'
        f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="2.4" fill="{cor}"/></svg>'
    )


@dataclass
class KPI:
    rotulo: str
    valor: float | None
    formato: str = "num"          # moeda | moeda0 | pct | num | num1 | nota | dias | noites
    atual_cmp: float | None = None  # valor do período comparativo
    melhor: str = "alto"          # alto | baixo
    icone: str = "grafico"
    spark: list = field(default_factory=list)
    sufixo: str = ""
    ref: str = ""                 # texto auxiliar (ex.: "margem 25,4%")

    def valor_fmt(self) -> str:
        v = self.valor
        f = self.formato
        if f == "moeda":
            return fmt.moeda(v)
        if f == "moeda0":
            txt = fmt.moeda_compacta(v)
            for un in (" mil", " mi"):
                if txt.endswith(un):
                    return f"{txt[: -len(un)]}<small>{un.strip()}</small>"
            return txt
        if f == "pct":
            return fmt.pct(v)
        if f == "num1":
            return fmt.num(v, 1)
        if f == "nota":
            return fmt.nota(v)
        if f == "dias":
            return f"{fmt.num(v, 1)}<small>dias</small>" if v is not None else "—"
        if f == "noites":
            return f"{fmt.num(v, 2)}<small>noites</small>" if v is not None else "—"
        return fmt.num(v, 0)

    def variacao(self) -> tuple[str, str]:
        a, b = self.valor, self.atual_cmp
        if a is None or b is None or (isinstance(b, float) and np.isnan(b)):
            return "neu", "— sem base"
        if self.formato == "pct":
            d = a - b
            txt = fmt.pp(d)
        elif self.formato == "nota":
            d = a - b
            txt = ("+" if d > 0 else "") + fmt.num(d, 2)
        else:
            if b == 0:
                return "neu", "— sem base"
            d = a / b - 1 if b > 0 else (a - b) / abs(b)
            txt = fmt.var_pct(d)
        if abs(d) < 1e-9 or self.melhor == "neutro":
            return "neu", ("▲ " if d > 0 else "▼ " if d < 0 else "• ") + txt
        bom = (d > 0) == (self.melhor == "alto")
        seta = "▲" if d > 0 else "▼"
        return ("pos" if bom else "neg"), f"{seta} {txt}"


def kpi_row(kpis: list[KPI], rotulo_cmp: str = "") -> None:
    cards = []
    for k in kpis:
        cls, txt = k.variacao()
        cor = {"pos": POSITIVE, "neg": NEGATIVE}.get(cls, ACCENT)
        ref = html.escape(k.ref) if k.ref else (f"vs {html.escape(rotulo_cmp)}" if rotulo_cmp else "")
        cards.append(
            f'<div class="kpi"><div class="rot">{icone(k.icone)}<span>{html.escape(k.rotulo)}</span></div>'
            f'<div class="val">{k.valor_fmt()}</div>'
            f'<div class="linha"><span class="pill {cls}">{txt}</span><span class="ref">{ref}</span></div>'
            f'{_sparkline(k.spark, ACCENT)}</div>'
        )
    n = len(kpis) if len(kpis) <= 6 else (len(kpis) + 1) // 2  # 7 cards → 4 + 3
    st.markdown(
        f'<div class="kpi-grid" style="grid-template-columns: repeat({n}, minmax(0, 1fr));">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


def cabecalho_pagina(titulo: str, subtitulo: str) -> None:
    st.markdown(
        f'<div class="pg-head"><h1>{html.escape(titulo)}</h1><p>{html.escape(subtitulo)}</p></div>',
        unsafe_allow_html=True,
    )


def _chave_card(titulo: str) -> str:
    base = "card_" + re.sub(r"[^a-z0-9]+", "_", unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode().lower()).strip("_")
    usados = st.session_state.setdefault("_cards_usados", set())
    chave, i = base, 2
    while chave in usados:
        chave, i = f"{base}_{i}", i + 1
    usados.add(chave)
    return chave


def reset_cards() -> None:
    """Chamar uma vez no início de cada execução do app."""
    st.session_state["_cards_usados"] = set()


@contextmanager
def card(titulo: str, ajuda: str | None = None, subtitulo: str | None = None):
    """Container com visual de card; o título fica fora do gráfico."""
    with st.container(key=_chave_card(titulo)):
        st.markdown(f'<div class="card-tit">{html.escape(titulo)}</div>', help=ajuda, unsafe_allow_html=True)
        if subtitulo:
            st.markdown(f'<div class="card-sub">{html.escape(subtitulo)}</div>', unsafe_allow_html=True)
        yield


def vazio(msg: str = "Nenhum dado para os filtros selecionados.") -> None:
    st.markdown(f'<div class="vazio">∅ {html.escape(msg)}<br><small>Ajuste o período ou limpe os filtros na barra lateral.</small></div>',
                unsafe_allow_html=True)


def grafico(fig: go.Figure | None, altura: int = 320, msg_vazio: str | None = None) -> None:
    if fig is None:
        vazio(msg_vazio or "Nenhum dado para os filtros selecionados.")
        return
    fig.update_layout(height=altura)
    st.plotly_chart(fig, use_container_width=True, theme=None,
                    config={"displaylogo": False, "displayModeBar": False, "locale": "pt-BR"})


def insights(frases: list[str], titulo: str = "Insights automáticos") -> None:
    if not frases:
        return
    itens = "".join(f"<li>{f}</li>" for f in frases)
    st.markdown(f'<div class="insights"><div class="tit">✦ {titulo}</div><ul>{itens}</ul></div>', unsafe_allow_html=True)


def aviso(msg: str, tipo: str = "warn") -> None:
    cls = "aviso info" if tipo == "info" else "aviso"
    st.markdown(f'<div class="{cls}">{msg}</div>', unsafe_allow_html=True)


_FMT_COL = {
    "moeda": fmt.moeda,
    "moeda0": lambda v: fmt.moeda(v, 0),
    "pct": fmt.pct,
    "num": lambda v: fmt.num(v, 0),
    "num1": lambda v: fmt.num(v, 1),
    "num2": lambda v: fmt.num(v, 2),
    "nota": lambda v: fmt.num(v, 2),
    "texto": lambda v: "" if v is None else str(v),
}


def tabela(df: pd.DataFrame, formatos: dict, rotulos: dict | None = None, altura: int | None = None) -> None:
    """st.dataframe ordenável com números em pt-BR (formatação via Styler)."""
    if df is None or df.empty:
        vazio()
        return
    rotulos = rotulos or {}
    sty = df.style.format({c: _FMT_COL[f] for c, f in formatos.items() if c in df}, na_rep="—")
    cfg = {c: st.column_config.Column(rotulos.get(c, c)) for c in df.columns}
    kw = {"height": altura} if altura else {}
    st.dataframe(sty, hide_index=True, use_container_width=True, column_config=cfg, **kw)


def tabela_barras(df: pd.DataFrame, formatos: dict, rotulos: dict | None = None, barras: list | None = None,
                  cores_linha: dict | None = None) -> None:
    """Tabela HTML com barras de dados nas colunas indicadas (números sempre em pt-BR).

    `cores_linha`: {valor da 1ª coluna: cor} — pinta um marcador ao lado do rótulo da linha.
    """
    if df is None or df.empty:
        vazio()
        return
    rotulos = rotulos or {}
    barras = barras or []
    maximos = {c: float(pd.to_numeric(df[c], errors="coerce").abs().max() or 0) for c in barras if c in df}
    cab = "".join(f"<th>{html.escape(rotulos.get(c, c))}</th>" for c in df.columns)
    corpo = []
    primeira = df.columns[0]
    for _, lin in df.iterrows():
        tds = []
        for c in df.columns:
            v = lin[c]
            txt = _FMT_COL.get(formatos.get(c, "texto"), _FMT_COL["texto"])(v) if pd.notna(v) else "—"
            if c == primeira:
                cor = (cores_linha or {}).get(v)
                dot = f"<i class='dot' style='background:{cor}'></i>" if cor else ""
                tds.append(f"<td>{dot}{html.escape(txt)}</td>")
            elif c in maximos and pd.notna(v) and maximos[c] > 0:
                larg = max(2, abs(float(v)) / maximos[c] * 100)
                tds.append(f"<td class='cb'><div class='db'><span style='width:{larg:.1f}%'></span></div>{txt}</td>")
            else:
                tds.append(f"<td>{txt}</td>")
        corpo.append(f"<tr>{''.join(tds)}</tr>")
    st.markdown(f"<div class='tbx'><table class='tb'><thead><tr>{cab}</tr></thead><tbody>{''.join(corpo)}</tbody></table></div>",
                unsafe_allow_html=True)


def download_csv(df: pd.DataFrame, nome: str, rotulo: str = "Baixar CSV") -> None:
    if df is None or df.empty:
        return
    csv = df.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(f"⤓ {rotulo}", csv, file_name=f"{nome}.csv", mime="text/csv", key=f"dl_{nome}")
