"""Formatação de números, moedas, percentuais e datas no padrão pt-BR."""
from __future__ import annotations

import math
from datetime import date, datetime

import pandas as pd

MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_NOME = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
DIAS_SEMANA_ABREV = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _vazio(v) -> bool:
    if v is None:
        return True
    try:
        return bool(pd.isna(v)) or (isinstance(v, float) and math.isinf(v))
    except (TypeError, ValueError):
        return False


def _br(texto: str) -> str:
    """Troca separadores do padrão en-US para pt-BR (1,234.5 -> 1.234,5)."""
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def num(v, casas: int = 0) -> str:
    if _vazio(v):
        return "—"
    return _br(f"{v:,.{casas}f}")


def moeda(v, casas: int = 2) -> str:
    if _vazio(v):
        return "—"
    sinal = "-" if v < 0 else ""
    return f"{sinal}R$ {num(abs(v), casas)}"


def moeda_compacta(v) -> str:
    """R$ 1,51 mi · R$ 375,2 mil · R$ 312,40"""
    if _vazio(v):
        return "—"
    a = abs(v)
    sinal = "-" if v < 0 else ""
    if a >= 1_000_000:
        return f"{sinal}R$ {num(a / 1_000_000, 2)} mi"
    if a >= 10_000:
        return f"{sinal}R$ {num(a / 1_000, 1)} mil"
    return moeda(v)


def moeda_eixo(v) -> str:
    """Rótulo curto para eixo: R$ 0 · R$ 50 mil · R$ 1,2 mi"""
    if _vazio(v):
        return ""
    a = abs(v)
    sinal = "-" if v < 0 else ""
    if a >= 1_000_000:
        x = a / 1_000_000
        return f"{sinal}R$ {num(x, 0 if x == int(x) else 1)} mi"
    if a >= 1_000:
        x = a / 1_000
        return f"{sinal}R$ {num(x, 0 if x == int(x) else 1)} mil"
    return f"{sinal}R$ {num(a, 0)}"


def pct(v, casas: int = 1) -> str:
    """Recebe fração (0,612) e devolve '61,2%'."""
    if _vazio(v):
        return "—"
    return f"{num(v * 100, casas)}%"


def pp(v, casas: int = 1) -> str:
    """Variação em pontos percentuais. Recebe diferença de frações."""
    if _vazio(v):
        return "—"
    sinal = "+" if v > 0 else ""
    return f"{sinal}{num(v * 100, casas)} p.p."


def var_pct(v, casas: int = 1) -> str:
    if _vazio(v):
        return "—"
    sinal = "+" if v > 0 else ""
    return f"{sinal}{num(v * 100, casas)}%"


def nota(v) -> str:
    return num(v, 1) if not _vazio(v) else "—"


def data(d) -> str:
    if _vazio(d):
        return "—"
    if isinstance(d, (pd.Timestamp, datetime, date)):
        return d.strftime("%d/%m/%Y")
    return str(d)


def data_curta(d) -> str:
    if _vazio(d):
        return "—"
    return f"{d.day:02d}/{d.month:02d}"


def mes_ano(d) -> str:
    """jan/26"""
    if _vazio(d):
        return "—"
    d = pd.Timestamp(d)
    return f"{MESES_ABREV[d.month - 1]}/{str(d.year)[-2:]}"


def mes_ano_de_chave(chave: str) -> str:
    """'2026-01' -> 'jan/26'"""
    ano, mes = str(chave).split("-")[:2]
    return f"{MESES_ABREV[int(mes) - 1]}/{ano[-2:]}"


def periodo(inicio, fim) -> str:
    return f"{data(inicio)} a {data(fim)}"


def dia_semana(d) -> str:
    return DIAS_SEMANA_ABREV[pd.Timestamp(d).weekday()]
