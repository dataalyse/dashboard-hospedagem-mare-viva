"""Smoke test: as 7 páginas abrem sem erro em combinações de filtros (inclusive as que zeram dados)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parent.parent
PAGINAS = [
    "views/1_visao_geral.py", "views/2_ocupacao_tarifas.py", "views/3_reservas_canais.py", "views/4_hospedes.py",
    "views/5_experiencia.py", "views/6_financeiro.py", "views/7_carteira_futura.py",
]
CENARIOS = {
    "padrao": {},
    "2025": {"f_periodo": "2025 completo"},
    "este_mes": {"f_periodo": "Este mês"},
    "ultimo_mes": {"f_periodo": "Último mês fechado", "f_comparar": "anterior"},
    "dormitorio_airbnb": {"f_categoria": "Cama em Dormitório", "f_canais": ["Airbnb"], "f_temporadas": ["Alta"]},
    "zera_dados": {"f_categoria": "Cama em Dormitório", "f_canais": ["Agência/Operadora"], "f_periodo": "Este mês",
                   "f_temporadas": ["Baixa"]},
    "futuro": {"f_periodo": "Personalizado", "f_custom": (__import__("datetime").date(2026, 11, 1),
                                                         __import__("datetime").date(2026, 12, 31))},
    "um_dia": {"f_periodo": "Personalizado", "f_custom": (__import__("datetime").date(2025, 1, 1),
                                                         __import__("datetime").date(2025, 1, 1))},
}


@pytest.mark.parametrize("cenario", list(CENARIOS))
@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_abre(pagina, cenario):
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=120)
    for k, v in CENARIOS[cenario].items():
        at.session_state[k] = v
    at.switch_page(pagina)
    at.run()
    assert not at.exception, f"{pagina} [{cenario}]: {[e.value for e in at.exception]}"
