"""Leitura da base e tipagem das colunas.

Único ponto do projeto que conhece a fonte de dados. Para trocar o Excel por
SharePoint, SQL ou Google Sheets basta reescrever `_ler_fonte` mantendo o
mesmo dicionário de DataFrames como retorno.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

CAMINHO_PADRAO = Path(__file__).resolve().parent.parent / "data" / "base_dashboard_hospedagem_mare_viva.xlsx"

TABELAS = [
    "dUnidades", "dHospedes", "dCalendario", "fReservas",
    "fConsumos", "fAvaliacoes", "fDespesas", "fMetas",
]

COLUNAS_DATA = {
    "dHospedes": ["Data_Cadastro"],
    "dCalendario": ["Data"],
    "fReservas": ["Data_Reserva", "Check_in", "Check_out", "Data_Cancelamento"],
    "fConsumos": ["Data"],
    "fAvaliacoes": ["Data_Avaliacao"],
    "fDespesas": ["Data_Lancamento"],
}

COLUNAS_NUM = {
    "dUnidades": ["Capacidade", "Tarifa_Base"],
    "fReservas": [
        "Noites", "Qtd_Hospedes", "Tarifa_Media_Diaria", "Valor_Bruto_Estadia", "Desconto",
        "Valor_Hospedagem", "Receita_Hospedagem", "Taxa_Comissao", "Valor_Comissao",
        "Receita_Liquida", "Antecedencia_Dias",
    ],
    "fConsumos": ["Quantidade", "Valor_Unitario", "Valor_Total"],
    "fAvaliacoes": [
        "Nota_Geral", "Limpeza", "Atendimento", "Localizacao", "Conforto",
        "Cafe_da_Manha", "Custo_Beneficio", "Wifi",
    ],
    "fDespesas": ["Valor"],
    "fMetas": ["Meta_Ocupacao", "Meta_Receita_Hospedagem", "Meta_ADR", "Meta_Nota_Media"],
}


def _ler_fonte(caminho: Path) -> dict[str, pd.DataFrame]:
    return pd.read_excel(caminho, sheet_name=TABELAS, engine="openpyxl")


def _ano_mes(serie: pd.Series) -> pd.Series:
    """Normaliza Ano_Mes para texto 'AAAA-MM' (o Excel pode entregar data ou texto)."""
    if pd.api.types.is_datetime64_any_dtype(serie):
        return serie.dt.strftime("%Y-%m")
    conv = pd.to_datetime(serie.astype(str).str.slice(0, 7), format="%Y-%m", errors="coerce")
    return conv.dt.strftime("%Y-%m").fillna(serie.astype(str))


def _tipar(dfs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    out = {}
    for nome, df in dfs.items():
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        for c in COLUNAS_DATA.get(nome, []):
            if c in df:
                df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True).dt.normalize()
        for c in COLUNAS_NUM.get(nome, []):
            if c in df:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "Ano_Mes" in df:
            df["Ano_Mes"] = _ano_mes(df["Ano_Mes"])
        for c in df.columns:
            s = df[c]
            if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s):
                continue
            vazio = s.isna()
            df[c] = s.astype(str).str.strip().where(~vazio, None)
            df.loc[df[c] == "", c] = None
        out[nome] = df
    return out


@st.cache_data(show_spinner="Carregando base de dados…")
def load_data(caminho: str | None = None) -> dict[str, pd.DataFrame]:
    """Lê todas as abas de uma vez e devolve {nome_tabela: DataFrame} já tipado."""
    return _tipar(_ler_fonte(Path(caminho) if caminho else CAMINHO_PADRAO))


def load_data_sem_cache(caminho: str | None = None) -> dict[str, pd.DataFrame]:
    """Versão sem Streamlit, usada nos testes."""
    return _tipar(_ler_fonte(Path(caminho) if caminho else CAMINHO_PADRAO))
