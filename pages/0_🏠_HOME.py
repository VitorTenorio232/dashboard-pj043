#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

import streamlit as st

from modules.products import PRODUCTS, product_groups
from modules.ui import load_css, product_card_button

SITE_NAME = "SIMQA — Sistema Integrado de Monitoramento de Queimadas e Atmosfera"

load_css("assets/style.css")

st.markdown(
    f"""
    <div class="home-hero">
        <div>
            <p class="eyebrow">Projeto PJ043 • Ciências Atmosféricas</p>
            <h1>🌎 {SITE_NAME}</h1>
            <p class="subtitle">
                Monitoramento integrado de queimadas, gases atmosféricos e variáveis ambientais
                por sensoriamento remoto, com mapas, séries temporais e produtos para download.
            </p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([0.42, 0.58], gap="large", vertical_alignment="center")

with left:
    st.markdown("### Como funciona")
    st.markdown(
        """
        **1. Escolha o produto** e o banco/plataforma de interesse.  
        **2. Defina a região e o período**, quando a variável possuir dimensão temporal.  
        **3. Gere o resultado** em mapa, série temporal ou arquivo para download.
        """
    )
    st.info(
        "O tempo de processamento pode aumentar para produtos de alta resolução, alta frequência temporal "
        "ou análises em áreas de grande extensão.",
        icon="⚙️",
    )
    st.caption(
        "As informações técnicas de cada produto — fonte, unidade, resolução, disponibilidade, cálculo e "
        "limitações — aparecem no painel à direita das páginas de análise."
    )

with right:
    gif_path = Path("assets/home_produtos.gif")
    with st.container(border=True):
        st.markdown("#### Produtos em destaque")
        st.caption("Exemplos reais gerados no SIMQA. A animação é apenas demonstrativa e roda em loop.")
        if gif_path.exists():
            st.image(str(gif_path), use_container_width=True)
        else:
            st.info("Adicione o arquivo `assets/home_produtos.gif` para exibir a animação da página inicial.")

fire_count = sum(1 for p in PRODUCTS.values() if p.kind.startswith("fire_"))
atmos_count = sum(1 for p in PRODUCTS.values() if p.kind == "maiac_aod" or p.group.startswith("Sentinel-5P"))

m1, m2, m3, m4 = st.columns(4)
m1.metric("Produtos disponíveis", len(PRODUCTS))
m2.metric("Bancos / plataformas", len(product_groups()))
m3.metric("Produtos de focos", fire_count)
m4.metric("Produtos atmosféricos", atmos_count)

st.markdown("---")
st.header("Explore os produtos")
st.caption("Os produtos são organizados por tema e permanecem identificados pelo respectivo banco ou plataforma.")

ICON_BY_KIND = {
    "fire_modis": "🔥",
    "fire_viirs": "🔥",
    "fire_goes": "🛰️",
    "maiac_aod": "🌫️",
    "mean_collection": "🧪",
    "lst_modis": "🌡️",
    "ndvi_sentinel2": "🌿",
    "precip_sum": "🌧️",
    "precip_era5land_sum": "🌧️",
    "static_image": "⛰️",
    "static_collection": "🏙️",
    "categorical_last": "🗺️",
}


def theme_for(product) -> str:
    if product.kind.startswith("fire_"):
        return "🔥 Queimadas e focos de calor"
    if product.kind == "maiac_aod" or product.group.startswith("Sentinel-5P"):
        return "🌫️ Atmosfera e qualidade do ar"
    return "🌎 Ambiente e superfície"


for theme in [
    "🔥 Queimadas e focos de calor",
    "🌫️ Atmosfera e qualidade do ar",
    "🌎 Ambiente e superfície",
]:
    theme_keys = [key for key, product in PRODUCTS.items() if theme_for(product) == theme]
    if not theme_keys:
        continue

    st.markdown(f"## {theme}")
    groups = []
    for key in theme_keys:
        group = PRODUCTS[key].group
        if group not in groups:
            groups.append(group)

    for group in groups:
        group_keys = [key for key in theme_keys if PRODUCTS[key].group == group]
        st.markdown(f"#### {group}")
        columns = st.columns(min(3, len(group_keys)))
        for index, product_name in enumerate(group_keys):
            product = PRODUCTS[product_name]
            with columns[index % len(columns)]:
                footer = product.cadence or ("Estático" if not product.temporal else product.statistic)
                product_card_button(
                    product_name,
                    ICON_BY_KIND.get(product.kind, "🌐"),
                    product.label,
                    product.user_note,
                    footer,
                )
    st.markdown("---")

st.markdown(
    """
    <div class="footer">
        SIMQA • Projeto PJ043 • Processamento geoespacial com Google Earth Engine
    </div>
    """,
    unsafe_allow_html=True,
)
