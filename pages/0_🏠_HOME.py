#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HOME do VIGIA: interface editorial leve, sem consultas ao Earth Engine."""
from __future__ import annotations

from pathlib import Path
import base64
import unicodedata
import streamlit as st
from modules.products import PRODUCTS, product_groups
from modules.ui import load_css, product_card_button, section_header

load_css("assets/style.css")

def normalized(value: str) -> str:
    return "".join(
        letter for letter in unicodedata.normalize("NFKD", str(value).casefold())
        if not unicodedata.combining(letter)
    )

_home_logo = Path(__file__).resolve().parents[1] / "assets" / "logo_vigia.png"
if _home_logo.is_file():
    _home_encoded = base64.b64encode(_home_logo.read_bytes()).decode("ascii")
    _home_logo_markup = (
        f'<div class="vigia-home-logo-slot"><img src="data:image/png;base64,{_home_encoded}" '
        'alt="VIGIA — Visualização Integrada de Gases, Incêndios e Atmosfera"></div>'
    )
else:
    _home_logo_markup = '<h1>VIGIA<span class="vigia-title-period">.</span></h1>'

# Hero editorial: a animação usa apenas um arquivo local, sem gerar tiles Earth Engine.
intro, showcase = st.columns([0.56, 0.44], gap="large", vertical_alignment="center")
with intro:
    st.markdown(
        f"""
        <div class="vigia-hero">
          <div class="vigia-hero-eyebrow"><span class="vigia-live-mark"></span> OBSERVATÓRIO AMBIENTAL <span class="vigia-dot-divider">/</span> PROJETO PJ043</div>
          {_home_logo_markup}
          <div class="vigia-hero-subtitle">Visualização Integrada de Gases, Incêndios e Atmosfera</div>
          <p class="vigia-hero-copy">Do dado ao território. Explore focos de calor, gases atmosféricos e condições ambientais em uma plataforma científica aberta à sociedade.</p>
          <div class="vigia-hero-rule"></div>
          <div class="vigia-hero-smallprint">SATÉLITES &nbsp;·&nbsp; REANÁLISES &nbsp;·&nbsp; GOOGLE EARTH ENGINE</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    a, b = st.columns(2, gap="small")
    with a:
        st.page_link("pages/1_🗺️_Mapas_Interativos.py", label="Explorar mapas", icon="🗺️", width="stretch")
    with b:
        st.page_link("pages/2_📈_Series_Temporais.py", label="Séries temporais", icon="📈", width="stretch")
with showcase:
    st.markdown('<div class="vigia-visual-label"><span>01 / IMAGENS DO SISTEMA</span><span>EXEMPLOS DE PRODUTOS</span></div>', unsafe_allow_html=True)
    gif = Path("assets/home_produtos.gif")
    if gif.exists():
        st.image(str(gif), width="stretch")
    else:
        st.info("Exemplos visuais ainda não disponíveis.")
    st.markdown('<div class="vigia-media-credit"><span class="vigia-signal"></span> Visualizações ilustrativas, não são dados em tempo real.</div>', unsafe_allow_html=True)

st.markdown('<div class="vigia-separator"></div>', unsafe_allow_html=True)
st.markdown('<div class="vigia-overline">UMA PLATAFORMA, DIFERENTES PERSPECTIVAS DO AMBIENTE</div>', unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4, gap="small")
fire_count = sum(1 for prod in PRODUCTS.values() if prod.kind.startswith("fire_"))
atmos_count = sum(1 for prod in PRODUCTS.values() if prod.kind == "maiac_aod" or prod.group.startswith("Sentinel-5P"))
for col, value, label, detail in [
    (k1, len(PRODUCTS), "Produtos", "Catálogo geoespacial"),
    (k2, len(product_groups()), "Fontes", "Bancos e plataformas"),
    (k3, fire_count, "Focos de calor", "Sensores orbitais"),
    (k4, atmos_count, "Atmosfera", "Gases e aerossóis"),
]:
    with col:
        st.markdown(f'<div class="vigia-stat"><div class="vigia-stat-number">{value:02d}</div><div class="vigia-stat-label">{label}</div><div class="vigia-stat-detail">{detail}</div></div>', unsafe_allow_html=True)

section_header("Como utilizar o VIGIA", "Três etapas, sem programação")
steps = [
    ("01", "Escolha os dados", "Selecione a fonte e o produto ambiental no catálogo."),
    ("02", "Delimite o estudo", "Informe região, coordenadas e período disponível."),
    ("03", "Explore e compartilhe", "Gere mapas, séries, estatísticas e arquivos."),
]
for col, (number, name, desc) in zip(st.columns(3, gap="medium"), steps):
    with col:
        st.markdown(f'<div class="vigia-guide-step"><span>{number} / ETAPA</span><strong>{name}</strong><p>{desc}</p></div>', unsafe_allow_html=True)

st.info(
    "O tempo de processamento depende da resolução dos dados, da frequência de observação, "
    "do período escolhido e da extensão da área analisada.", icon="ℹ️",
)

section_header("Catálogo de produtos", "Busque por tema, fonte ou variável")
search = st.text_input("Buscar no catálogo", placeholder="Ex.: VIIRS, metano, NDVI, precipitação…", key="vigia_home_search")
st.caption("Cada produto possui fonte, unidade, resolução, método de cálculo e limitações na página de análise.")

ICONS = {
    "fire_modis": "🔥", "fire_viirs": "🔥", "fire_goes": "🛰️", "maiac_aod": "🌫️",
    "mean_collection": "🧪", "lst_modis": "🌡️", "ndvi_sentinel2": "🌿",
    "precip_sum": "🌧️", "precip_era5land_sum": "🌧️", "static_image": "⛰️",
    "static_collection": "🏙️", "categorical_last": "🗺️", "soil_moisture_smap": "💧",
}

def get_theme(prod):
    if prod.kind.startswith("fire_"):
        return "Focos de calor"
    if prod.kind == "maiac_aod" or prod.group.startswith("Sentinel-5P"):
        return "Atmosfera e gases"
    return "Ambiente e superfície"

themes = ["Focos de calor", "Atmosfera e gases", "Ambiente e superfície"]
tabs = st.tabs(["🔥 Focos de calor", "🌫️ Atmosfera e gases", "🌎 Ambiente e superfície"])
for tab, theme in zip(tabs, themes):
    with tab:
        keys = [key for key, prod in PRODUCTS.items() if get_theme(prod) == theme]
        if search.strip():
            needle = normalized(search.strip())
            keys = [
                k for k in keys
                if needle in normalized(" ".join([
                    PRODUCTS[k].label, PRODUCTS[k].group, PRODUCTS[k].source,
                    PRODUCTS[k].user_note, k,
                ]))
            ]
        groups = list(dict.fromkeys(PRODUCTS[k].group for k in keys))
        if keys:
            options = ["Todos"] + groups
            widget_key = f"vigia_theme_{theme}"
            if st.session_state.get(widget_key) not in options:
                st.session_state[widget_key] = "Todos"
            group = st.selectbox("Filtrar por banco ou plataforma", options, key=widget_key)
            keys = [k for k in keys if group == "Todos" or PRODUCTS[k].group == group]
            st.caption(f"{len(keys)} produto(s) disponíveis nesta seleção")
            for idx in range(0, len(keys), 3):
                columns = st.columns(3, gap="medium")
                for col, key in zip(columns, keys[idx:idx+3]):
                    product = PRODUCTS[key]
                    footer = f"{product.group} · {product.cadence or ('Estático' if not product.temporal else product.statistic)}"
                    with col:
                        product_card_button(key, ICONS.get(product.kind, "🌐"), product.label, product.user_note, footer)
        else:
            st.info("Nenhum produto corresponde à busca neste tema. Tente outro termo.")

st.markdown(
    '<footer class="vigia-footer"><strong>VIGIA</strong><span>PROJETO PJ043 &nbsp;·&nbsp; DIVULGAÇÃO CIENTÍFICA &nbsp;·&nbsp; DADOS PROCESSADOS SOB DEMANDA</span></footer>',
    unsafe_allow_html=True,
)
