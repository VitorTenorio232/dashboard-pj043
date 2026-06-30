# PJ043 Analytics — Dashboard sob demanda

Dashboard Streamlit para gerar mapas, séries temporais e downloads usando Google Earth Engine.

## Produtos

- Queimadas: FIRMS
- CO: Sentinel-5P OFFL L3 CO
- Aerossóis: Sentinel-5P OFFL L3 AER_AI
- Metano: Sentinel-5P OFFL L3 CH4

## Rodar localmente

```bash
cd dashboard_pj043_sob_demanda
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

export EE_PROJECT=eng-scene-497515-t2
earthengine authenticate

streamlit run app.py
```

## Publicar no GitHub

```bash
git init
git add .
git commit -m "dashboard PJ043 sob demanda"
git branch -M main
git remote add origin https://github.com/VitorTenorio232/Projeto-PJ043-2026.git
git push -u origin main
```

## Streamlit Community Cloud

- Repository: `VitorTenorio232/Projeto-PJ043-2026`
- Branch: `main`
- Main file path: `app.py`

Depois configure os Secrets no painel do Streamlit Cloud.

## Atenção

Não envie `.streamlit/secrets.toml` nem arquivos `.json` para o GitHub.
Use `.streamlit/secrets.toml.example` apenas como modelo.
