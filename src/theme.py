"""Tokens de cor, paletas fixas e template Plotly do painel."""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# ---------------------------------------------------------------- tokens
BG = "#0A1628"
SURFACE = "#111F36"
SURFACE_2 = "#16294A"
BORDER = "#1F3557"
TEXT = "#E6EDF7"
MUTED = "#8CA0BF"
ACCENT = "#22D3EE"
ACCENT_2 = "#A78BFA"
POSITIVE = "#34D399"
NEGATIVE = "#F87171"
WARNING = "#FBBF24"

FONT = "Inter, -apple-system, Segoe UI, sans-serif"

# ---------------------------------------------------------------- paletas categóricas fixas
CORES_CANAL = {
    "Booking.com": "#60A5FA",
    "Airbnb": "#F472B6",
    "Direto (WhatsApp/Telefone)": "#34D399",
    "Site Próprio": "#22D3EE",
    "Expedia": "#FBBF24",
    "Hostelworld": "#FB923C",
    "Agência/Operadora": "#A78BFA",
}
CORES_CATEGORIA = {
    "Quarto Privativo": "#22D3EE",
    "Cama em Dormitório": "#A78BFA",
}
CORES_STATUS = {
    "Concluída": "#34D399",
    "Hospedado": "#22D3EE",
    "Confirmada": "#60A5FA",
    "Cancelada": "#F87171",
    "No-show": "#FBBF24",
}
CORES_TEMPORADA = {"Alta": "#F472B6", "Média": "#FBBF24", "Baixa": "#60A5FA"}
CORES_TIPO_DESPESA = {"Fixa": "#A78BFA", "Variável": "#22D3EE"}
# fallback para itens fora das paletas fixas (tipos de unidade, plataformas, etc.)
SEQ_CATEGORICA = [
    "#22D3EE", "#A78BFA", "#60A5FA", "#F472B6", "#34D399",
    "#FBBF24", "#FB923C", "#2DD4BF", "#C084FC", "#94A3B8",
]

ESCALA_SEQ = [[0.0, "#111F36"], [0.35, "#0E7490"], [0.7, "#22D3EE"], [1.0, "#CFFAFE"]]
# versão mais escura para heatmaps com rótulo de texto claro dentro da célula
ESCALA_TEXTO = [[0.0, "#111F36"], [0.45, "#155E75"], [1.0, "#0891B2"]]
ESCALA_DIV =[[0.0, "#F87171"], [0.5, "#16294A"], [1.0, "#34D399"]]


def rgba(hexcor: str, alfa: float = 0.35) -> str:
    h = hexcor.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alfa})"


def cor_canal(canal: str) -> str:
    if canal in CORES_CANAL:
        return CORES_CANAL[canal]
    for chave, cor in CORES_CANAL.items():  # tolera nomes abreviados ("Direto", "Agência")
        if chave.split(" ")[0].lower() == str(canal).split(" ")[0].lower():
            return cor
    return MUTED


def mapa_cores(itens, fixo: dict | None = None) -> dict:
    """Mapeia itens a cores: usa a paleta fixa quando existe, senão a sequência padrão."""
    fixo = fixo or {}
    out, i = {}, 0
    for it in itens:
        if it in fixo:
            out[it] = fixo[it]
        else:
            out[it] = SEQ_CATEGORICA[i % len(SEQ_CATEGORICA)]
            i += 1
    return out


# ---------------------------------------------------------------- template Plotly
def _registrar_template() -> None:
    grid = "rgba(31,53,87,0.5)"
    eixo = dict(
        gridcolor=grid, zerolinecolor=grid, linecolor=BORDER,
        tickfont=dict(color=MUTED, size=11), title=dict(font=dict(color=MUTED, size=11)),
        showline=False, automargin=True,
    )
    t = go.layout.Template()
    t.layout = go.Layout(
        paper_bgcolor=SURFACE,  # o Streamlit troca fundo transparente pelo fundo da página
        plot_bgcolor=SURFACE,
        font=dict(family=FONT, color=MUTED, size=12),
        separators=",.",
        colorway=SEQ_CATEGORICA,
        margin=dict(l=8, r=8, t=16, b=8),
        xaxis=eixo,
        yaxis=eixo,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(color=MUTED, size=11), bgcolor="rgba(0,0,0,0)", title=None,
        ),
        hoverlabel=dict(
            bgcolor=SURFACE_2, bordercolor=ACCENT,
            font=dict(family=FONT, color=TEXT, size=12),
        ),
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(gridcolor=grid, linecolor=BORDER, tickfont=dict(color=MUTED, size=10)),
            angularaxis=dict(gridcolor=grid, linecolor=BORDER, tickfont=dict(color=TEXT, size=11)),
        ),
        geo=dict(
            bgcolor="rgba(0,0,0,0)", showframe=False, landcolor=SURFACE_2,
            lakecolor=BG, oceancolor=BG, showocean=True, coastlinecolor=BORDER,
            countrycolor=BORDER, subunitcolor=BORDER,
        ),
        coloraxis=dict(colorbar=dict(tickfont=dict(color=MUTED), outlinewidth=0, thickness=10)),
        bargap=0.25,
        hovermode="closest",
    )
    pio.templates["mareviva"] = t
    pio.templates.default = "mareviva"


_registrar_template()
