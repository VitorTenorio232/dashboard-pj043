# VIGIA — Visualização Integrada de Gases, Incêndios e Atmosfera

**Projeto PJ043** · Painel web para explorar dados de queimadas, composição atmosférica, umidade do solo
e outras variáveis ambientais, processados sob demanda no **Google Earth Engine**. Feito com Python e Streamlit.

[![Testes do site](../../actions/workflows/tests.yml/badge.svg)](../../actions/workflows/tests.yml)

Site: <https://vigia-dashboard.streamlit.app/>

## O que o site oferece

| Página | O que faz |
|---|---|
| 🏠 **HOME** | Catálogo pesquisável dos 25 produtos, separados em focos de calor, atmosfera e ambiente/superfície. |
| 🗺️ **Mapas interativos** | Mapa do produto para América do Sul, país, estado, município ou retângulo, com resumo na área e prancha PNG/JPEG. |
| 📈 **Séries temporais** | Valor regional dia a dia (até 1 ano; 90 dias para produtos de alta resolução) ou mês a mês, com CSV. |
| 📥 **Downloads** | GeoTIFF analítico, prancha PNG/JPEG, mapa HTML e metadados CSV/JSON. |
| ℹ️ **Sobre** | Como interpretar cada produto e ficha técnica de cada um. |

### Fontes de dados

FIRMS (MODIS e VIIRS), GOES-16/19 (focos), MODIS (AOD MAIAC e temperatura da superfície), Sentinel-5P
(gases e aerossóis, NRTI e OFFL), CHIRPS v3 e ERA5-Land (precipitação), **NASA SMAP (umidade do solo e
anomalia)**, Sentinel-2 (NDVI), SRTM (relevo), Copernicus (cobertura do solo) e gHM (modificação humana).
Detalhes de cada produto em [CATALOGO_PRODUTOS.md](CATALOGO_PRODUTOS.md).

Limites: países do **LSIB** (Departamento de Estado dos EUA); estados e municípios da **GAUL 2025** (FAO).

## Rodar no seu computador

Requer Python 3.11 ou mais novo e uma conta Google com acesso ao Earth Engine.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    |    Linux/Mac: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
earthengine authenticate
streamlit run app.py
```

Sem `secrets.toml`, o site usa o login do `earthengine authenticate` e o projeto da variável `EE_PROJECT`
(padrão: o projeto do PJ043).

## Publicar no Streamlit Community Cloud

1. Em [share.streamlit.io](https://share.streamlit.io), aponte para este repositório, branch `main`, arquivo `app.py`.
2. Em **Settings → Secrets**, cole o conteúdo de `.streamlit/secrets.toml.example` preenchido com a chave da
   conta de serviço do Earth Engine. **Nunca envie a chave `.json` nem o `secrets.toml` ao GitHub.**
3. Cada `push` na `main` atualiza o site automaticamente.

## Estrutura

```text
app.py                  # navegação entre as páginas
pages/                  # HOME, Mapas, Séries, Downloads, Sobre
modules/
  products.py           # catálogo dos produtos e cálculo de cada um no Earth Engine
  regions.py            # países, estados, municípios e retângulo
  maps.py               # mapa Folium, resumo na área e contornos
  series.py             # séries temporais (consultas em lote ao GEE)
  export_image.py       # prancha PNG/JPEG e estimativa do GeoTIFF
  ui.py, auth_gee.py    # componentes da interface e login no GEE
assets/                 # logos, GIF da HOME e CSS
tests/                  # testes automáticos (não precisam de credenciais)
tools/auditar_catalogo.py  # auditoria do catálogo (opcional: --gee para checar datas reais)
docs/historico/         # notas de versões antigas
```

## Testes

```bash
python -m pytest -q                                             # testes automáticos
python -m ruff check app.py modules pages tests tools --select F  # erros de código
python tools/auditar_catalogo.py --project . --gee              # confere o catálogo no Earth Engine
```

Os testes rodam no GitHub a cada `push` (aba **Actions → Testes do site**).

## Aviso científico

Focos de calor são detecções rasterizadas e não equivalem ao número de incêndios únicos. Produtos NRT/NRTI
podem ser revistos. O sistema apoia consulta e divulgação; não substitui serviços oficiais de alerta.

Histórico de mudanças: [CHANGELOG.md](CHANGELOG.md).
