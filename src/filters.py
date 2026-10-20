"""Filtros globais da barra lateral e contexto compartilhado pelas páginas."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from src import formatters as fmt
from src import metrics as m
from src.data_loader import load_data
from src.model import (
    DATA_REF, Recorte, build_model, filtrar_dimensoes, periodo_comparativo, recortar,
    ultimo_dia_com_despesa,
)

PERIODOS = [
    "Este mês", "Último mês fechado", "Últimos 3 meses", "Ano atual (YTD)",
    "Últimos 12 meses", "2025 completo", "Personalizado",
]
PERIODO_PADRAO = "Ano atual (YTD)"
CATEGORIAS = ["Todas", "Quarto Privativo", "Cama em Dormitório"]
TEMPORADAS = ["Alta", "Média", "Baixa"]
COMPARAR = {"yoy": "Mesmo período do ano anterior", "anterior": "Período anterior"}
DATA_MIN, DATA_MAX = pd.Timestamp("2025-01-01"), pd.Timestamp("2026-12-31")

_PADROES = {
    "f_periodo": PERIODO_PADRAO,
    "f_custom": (pd.Timestamp("2026-01-01").date(), DATA_REF.date()),
    "f_categoria": "Todas",
    "f_tipos": [],
    "f_canais": [],
    "f_temporadas": [],
    "f_comparar": "yoy",
}


# ---------------------------------------------------------------- dados em cache
@st.cache_resource(show_spinner="Montando o modelo de dados…")
def get_model() -> dict:
    return build_model(load_data())


@st.cache_resource(max_entries=64, show_spinner=False)
def get_base(unidades: tuple | None, canais: tuple | None, temporadas: tuple | None) -> dict:
    return filtrar_dimensoes(
        get_model(),
        list(unidades) if unidades is not None else None,
        list(canais) if canais is not None else None,
        list(temporadas) if temporadas is not None else None,
    )


@st.cache_resource(max_entries=64, show_spinner=False)
def get_serie(unidades, canais, temporadas, inicio: pd.Timestamp, fim: pd.Timestamp) -> pd.DataFrame:
    return m.serie_mensal(get_base(unidades, canais, temporadas), inicio, fim)


# ---------------------------------------------------------------- período
def intervalo_periodo(rotulo: str, custom=None) -> tuple[pd.Timestamp, pd.Timestamp]:
    ref = DATA_REF
    if rotulo == "Este mês":
        return ref.replace(day=1), ref
    if rotulo == "Último mês fechado":
        fim = ref.replace(day=1) - pd.Timedelta(days=1)
        return fim.replace(day=1), fim
    if rotulo == "Últimos 3 meses":
        return ref - pd.DateOffset(months=3) + pd.Timedelta(days=1), ref
    if rotulo == "Últimos 12 meses":
        return ref - pd.DateOffset(years=1) + pd.Timedelta(days=1), ref
    if rotulo == "2025 completo":
        return pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31")
    if rotulo == "Personalizado" and custom:
        ini, fim = (list(custom) + [custom[0]])[:2] if isinstance(custom, (list, tuple)) else (custom, custom)
        ini, fim = pd.Timestamp(ini), pd.Timestamp(fim)
        if fim < ini:
            ini, fim = fim, ini
        return max(ini, DATA_MIN), min(fim, DATA_MAX)
    return pd.Timestamp(f"{ref.year}-01-01"), ref


# ---------------------------------------------------------------- estado
@dataclass
class Filtros:
    periodo: str
    inicio: pd.Timestamp
    fim: pd.Timestamp
    categoria: str
    tipos: list
    canais: list
    temporadas: list
    comparar: str

    @property
    def rotulo_periodo(self) -> str:
        return fmt.periodo(self.inicio, self.fim)


def _limpar():
    for k, v in _PADROES.items():
        st.session_state[k] = v


def _init_estado():
    for k, v in _PADROES.items():
        st.session_state.setdefault(k, v)


def render_sidebar(model: dict) -> Filtros:
    _init_estado()
    un = model["unidades"]
    canais_all = sorted(model["reservas"]["Canal"].dropna().unique())
    sb = st.sidebar
    sb.markdown('<div class="sb-secao">Período</div>', unsafe_allow_html=True)
    periodo = sb.selectbox("Período", PERIODOS, key="f_periodo", label_visibility="collapsed")
    custom = None
    if periodo == "Personalizado":
        custom = sb.date_input(
            "Intervalo", key="f_custom", min_value=DATA_MIN.date(), max_value=DATA_MAX.date(),
            format="DD/MM/YYYY",
        )
    ini, fim = intervalo_periodo(periodo, custom)
    sb.caption(f"{fmt.data(ini)} → {fmt.data(fim)}")

    sb.markdown('<div class="sb-secao">Inventário</div>', unsafe_allow_html=True)
    categoria = sb.selectbox("Categoria", CATEGORIAS, key="f_categoria")
    tipos_opc = un["Tipo"].unique().tolist() if categoria == "Todas" else un.loc[un["Categoria"] == categoria, "Tipo"].unique().tolist()
    st.session_state["f_tipos"] = [t for t in st.session_state.get("f_tipos", []) if t in tipos_opc]
    tipos = sb.multiselect("Tipo de unidade", tipos_opc, key="f_tipos", placeholder="Todos os tipos")

    sb.markdown('<div class="sb-secao">Demanda</div>', unsafe_allow_html=True)
    canais = sb.multiselect("Canal", canais_all, key="f_canais", placeholder="Todos os canais")
    temporadas = sb.multiselect("Temporada", TEMPORADAS, key="f_temporadas", placeholder="Todas as temporadas")

    sb.markdown('<div class="sb-secao">Comparação</div>', unsafe_allow_html=True)
    comparar = sb.radio("Comparar com", list(COMPARAR), format_func=COMPARAR.get, key="f_comparar",
                        label_visibility="collapsed")

    sb.button("↺ Limpar filtros", on_click=_limpar, use_container_width=True)
    sb.markdown(
        f'<div class="sb-rodape">Dados atualizados até <b>{fmt.data(DATA_REF)}</b><br>'
        f'Dados fictícios para demonstração.'
        f'<div class="assina">Desenvolvido por <span>Datalyse</span></div></div>',
        unsafe_allow_html=True,
    )
    return Filtros(periodo, ini, fim, categoria, tipos, canais, temporadas, comparar)


# ---------------------------------------------------------------- contexto
@dataclass
class Contexto:
    model: dict
    filtros: Filtros
    chave: tuple                 # (unidades, canais, temporadas) — para cache
    base: dict
    rec: Recorte
    rec_cmp: Recorte | None
    rec_lucro: Recorte
    rec_lucro_cmp: Recorte | None
    fim_despesa: pd.Timestamp
    rotulo_cmp: str

    @property
    def rotulo_curto(self) -> str:
        if self.filtros.comparar == "yoy":
            a, b = self.filtros.inicio.year - 1, self.filtros.fim.year - 1
            return f"{a}" if a == b else f"{a}–{str(b)[-2:]}"
        return "período anterior"

    @property
    def filtro_demanda_ativo(self) -> bool:
        return bool(self.filtros.canais or self.filtros.temporadas)

    @property
    def lucro_parcial(self) -> bool:
        return self.filtros.fim > self.fim_despesa

    def serie(self, inicio, fim) -> pd.DataFrame:
        return get_serie(*self.chave, pd.Timestamp(inicio), pd.Timestamp(fim))

    def serie_12m(self) -> pd.DataFrame:
        fim = self.filtros.fim
        ini = (fim - pd.DateOffset(months=11)).replace(day=1)
        return self.serie(max(ini, DATA_MIN), fim)

    def recorte(self, inicio, fim) -> Recorte:
        return recortar(self.base, inicio, fim)

    def cmp(self, func, lucro: bool = False):
        """Aplica uma função de métrica ao recorte comparativo (None se não houver base)."""
        r = self.rec_lucro_cmp if lucro else self.rec_cmp
        return func(r) if r is not None else None


def montar_contexto(model: dict, f: Filtros) -> Contexto:
    un = model["unidades"]
    sel = un
    if f.categoria != "Todas":
        sel = sel[sel["Categoria"] == f.categoria]
    if f.tipos:
        sel = sel[sel["Tipo"].isin(f.tipos)]
    unidades = None if len(sel) == len(un) else tuple(sorted(sel["ID_Unidade"]))
    canais = tuple(sorted(f.canais)) if f.canais else None
    temporadas = tuple(sorted(f.temporadas)) if f.temporadas else None
    chave = (unidades, canais, temporadas)
    base = get_base(*chave)

    ci, cf = periodo_comparativo(f.inicio, f.fim, f.comparar)
    fim_desp = ultimo_dia_com_despesa(model)
    lf = min(f.fim, fim_desp)
    lci, lcf = periodo_comparativo(f.inicio, lf, f.comparar)
    if f.comparar == "yoy":
        rot = f"mesmo período de {f.inicio.year - 1}" if f.inicio.year == f.fim.year else "ano anterior"
    else:
        rot = "período anterior"
    # comparativo só existe se cair inteiro dentro da base (sem 2024)
    def _cmp(a, b):
        return recortar(base, a, b) if a >= DATA_MIN else None

    return Contexto(
        model=model, filtros=f, chave=chave, base=base,
        rec=recortar(base, f.inicio, f.fim),
        rec_cmp=_cmp(ci, cf),
        rec_lucro=recortar(base, f.inicio, lf),
        rec_lucro_cmp=_cmp(lci, lcf) if lf >= f.inicio else None,
        fim_despesa=fim_desp,
        rotulo_cmp=rot,
    )


def get_ctx() -> Contexto:
    return st.session_state["_ctx"]
