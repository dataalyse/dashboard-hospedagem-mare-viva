"""MARÉ VIVA · Painel de Gestão — ponto de entrada (streamlit run app.py)."""
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="MARÉ VIVA · Painel de Gestão",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

from src import components as ui  # noqa: E402
from src import formatters as fmt  # noqa: E402
from src import theme  # noqa: E402,F401  (registra o template Plotly)
from src.filters import get_model, montar_contexto, render_sidebar  # noqa: E402
from src.model import DATA_REF  # noqa: E402

RAIZ = Path(__file__).parent

css = (RAIZ / "assets" / "style.css").read_text(encoding="utf-8")
st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
ui.reset_cards()
st.logo(str(RAIZ / "assets" / "logo.svg"), size="large", icon_image=str(RAIZ / "assets" / "logo_icone.svg"))

paginas = [
    st.Page("views/1_visao_geral.py", title="Visão Geral", icon=":material/space_dashboard:", default=True),
    st.Page("views/2_ocupacao_tarifas.py", title="Ocupação & Tarifas", icon=":material/hotel:"),
    st.Page("views/3_reservas_canais.py", title="Reservas & Canais", icon=":material/hub:"),
    st.Page("views/4_hospedes.py", title="Hóspedes & Mercados", icon=":material/public:"),
    st.Page("views/5_experiencia.py", title="Experiência", icon=":material/star:"),
    st.Page("views/6_financeiro.py", title="Financeiro", icon=":material/payments:"),
    st.Page("views/7_carteira_futura.py", title="Carteira Futura", icon=":material/event_upcoming:"),
]
pg = st.navigation(paginas)

model = get_model()
filtros = render_sidebar(model)
ctx = montar_contexto(model, filtros)
st.session_state["_ctx"] = ctx

chips = [f'<span class="chip"><span class="dot"></span>{fmt.periodo(filtros.inicio, filtros.fim)}</span>']
if filtros.categoria != "Todas" or filtros.tipos:
    chips.append(f'<span class="chip muted">{filtros.categoria if not filtros.tipos else ", ".join(filtros.tipos)}</span>')
if filtros.canais:
    chips.append(f'<span class="chip muted">{len(filtros.canais)} canal(is)</span>')
chips.append(f'<span class="chip muted">Atualizado até {fmt.data(DATA_REF)}</span>')
st.markdown(
    '<div class="app-top"><div class="marca">MARÉ VIVA <span>·</span> <small>Painel de Gestão</small></div>'
    f'<div class="chips">{"".join(chips)}</div></div>',
    unsafe_allow_html=True,
)

pg.run()
