# MARÉ VIVA · Painel de Gestão

Dashboard de gestão para pousadas, hostels e hospedagens — ocupação, tarifas, canais, hóspedes,
avaliações, DRE gerencial e carteira futura num painel escuro com cara de produto de tecnologia.

> **Dados fictícios para demonstração — Datalyse.**

<!-- Para mostrar um print: salve a Visão Geral em docs/painel.png e troque esta linha por:
![Visão Geral do painel](docs/painel.png) -->

**Link publicado:** _adicione aqui a URL do Streamlit Community Cloud_

---

## O que o painel responde

| Página | Pergunta do gestor | Destaques |
|---|---|---|
| **Visão Geral** | Como está o negócio? | 6 KPIs com sparkline, gauge de ocupação × meta, receita × ocupação, receita por canal, RevPAR por tipo, próximos 7 dias, insights automáticos e glossário |
| **Ocupação & Tarifas** | Quanto ocupo e a que preço? | Calendário de ocupação, padrão mês × dia da semana, ocupação diária com feriados, bolhas ADR × ocupação, ADR por temporada, 2025 × 2026 |
| **Reservas & Canais** | De onde vêm as reservas e quanto custam? | Sankey canal → categoria → status, mix de canais, rentabilidade por canal, antecedência, estadia, funil, ritmo de vendas |
| **Hóspedes & Mercados** | Quem são meus hóspedes? | Mapa do Brasil por UF, mapa-múndi, treemap país → cidade, pirâmide etária, motivo da viagem, top 10 cidades |
| **Experiência** | Como está a satisfação? | Radar dos 7 critérios, nota mensal × meta, nota por plataforma, matriz de prioridade, distribuição de notas, tipo × critério |
| **Financeiro** | Estou dando lucro? | DRE em cascata, despesas × receita, treemap de despesas, receita extra, margem mensal, DRE mensal com download Excel/CSV |
| **Carteira Futura** | Como está o futuro? | Ocupação garantida × ano anterior, pickup de dezembro, mapa de reservas (Gantt) dos próximos 60 dias, Réveillon |

### KPIs disponíveis

Ocupação · ADR · RevPAR · TRevPAR · Receita total · Receita líquida de canais · Custo de distribuição ·
Despesas · GOP · Margem GOP · GOPPAR · CPOR · Estadia média (LOS) · Antecedência média · Cancelamento ·
No-show · % reservas diretas · Hóspedes-noite · Gasto extra por hóspede · Recorrência · Nota média ·
% Recomendaria · Atingimento de meta.

Todos os cards comparam com o **mesmo período do ano anterior** ou com o **período imediatamente anterior**
(alternável na barra lateral); variações de percentuais aparecem em **p.p.**

---

## Como rodar localmente

Requer Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
```

O painel abre em `http://localhost:8501`.

### Testes

```bash
pip install pytest
pytest
```

- `tests/test_metrics.py` confere os **valores de referência de 2025** (ocupação 60,25%, ADR R$ 271,64,
  RevPAR R$ 165,05, GOP R$ 477.015,98, etc.) e garante que nenhuma unidade tem duas reservas na mesma noite.
- `tests/test_paginas.py` abre as 7 páginas em 8 combinações de filtros — inclusive filtros que zeram os dados.

---

## Deploy no Streamlit Community Cloud

1. Suba esta pasta para um repositório **público** no GitHub (a pasta `data/` vai junto — os dados são fictícios).
2. Em [share.streamlit.io](https://share.streamlit.io), clique em **Create app** → escolha o repositório e o branch.
3. **Main file path:** `app.py` · **Advanced settings → Python version:** 3.11.
4. Clique em **Deploy**. O tema escuro vem de `.streamlit/config.toml`.

---

## Estrutura

```
app.py                 entrada: configuração, tema, filtros e navegação (st.navigation)
src/data_loader.py     leitura do Excel (único ponto que conhece a fonte de dados)
src/model.py           tabela de noites (fNoites), recorte por período, comparativos
src/metrics.py         todas as fórmulas de KPI — funções puras e testáveis
src/filters.py         barra lateral, estado dos filtros e cache
src/charts.py          fábrica de gráficos Plotly com o template visual
src/components.py      cartão de KPI, cards, tabelas, insights, downloads
src/formatters.py      moeda, %, números e datas em pt-BR
src/theme.py           tokens de cor, paletas fixas por canal/categoria, template Plotly
views/                 as 7 páginas
assets/                CSS, logo e GeoJSON dos estados
data/                  base Excel
```

### Regras de negócio importantes

- **Tudo por noite, não por reserva.** Cada reserva é explodida em uma linha por noite
  (`Check_in` até `Check_out − 1`), então uma estadia de 28/01 a 03/02 conta em janeiro e fevereiro.
- **Receita de hospedagem** = diárias das noites realizadas + 1ª diária dos no-shows com check-in no período.
- **Inventário** = unidades no filtro × dias. Filtros de canal e temporada **não** reduzem o inventário.
- **Data de referência:** 18/10/2026. Antes dela é realizado; depois, carteira.
- **Despesas** não são lançadas por unidade: com filtro de categoria/tipo, são rateadas pela capacidade em leitos
  (14 camas de dormitório = 14 de 42 leitos = 33% da despesa; quartos privativos = 67%).
  Filtros de canal/temporada não rateiam despesa.
- **Despesas** existem até set/2026. GOP, margem, GOPPAR e CPOR consideram apenas meses com despesa lançada,
  e a tela avisa quando o período escolhido vai além disso.

### Trocar a fonte de dados

Só `src/data_loader.py` conhece o Excel. Para ler de SharePoint, SQL ou Google Sheets, reescreva
`_ler_fonte()` devolvendo o mesmo dicionário `{nome_da_tabela: DataFrame}` — nenhuma página muda.

---

Desenvolvido por **Datalyse**.
