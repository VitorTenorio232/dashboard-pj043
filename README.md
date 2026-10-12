# VIGIA — Visualização Integrada de Gases, Incêndios e Atmosfera

**Projeto PJ043 · Interface v5.5**

Plataforma web para exploração e divulgação de dados de queimadas, composição atmosférica e variáveis ambientais, processados sob demanda no Google Earth Engine.

## Funcionalidades

- HOME editorial com exemplos reais e catálogo pesquisável
- Mapas interativos com recortes por país, estado, município e coordenadas
- Séries temporais e downloads de produtos ambientais
- Fontes FIRMS, VIIRS, GOES, Sentinel-5P, MODIS, CHIRPS, ERA5-Land e outras
- Painéis com fonte, unidade, resolução, método e limitações

## Execução

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Configure as credenciais do Earth Engine no arquivo local `.streamlit/secrets.toml` ou no painel Secrets do Streamlit Community Cloud. **Não publique credenciais no GitHub.**

## Atualização

Leia `GUIA_ATUALIZACAO.md`. O instalador V5.5 altera somente a camada visual, preservando os módulos científicos existentes e as credenciais.

## Aviso científico

Detecções de focos de calor são observações rasterizadas que não equivalem ao número de incêndios únicos. O sistema apoia consulta e divulgação, não substitui os serviços oficiais de alerta.

## Design

Leia `DESIGN.md` para o conjunto de tokens, padrões de acessibilidade e referências externas.
