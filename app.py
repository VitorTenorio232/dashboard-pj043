#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import streamlit as st

from modules.auth_gee import initialize_gee
from modules.maps import example_home_map, render_map
from modules.ui import load_css, product_card_button

st.set_page_config(
    layout="wide",
    page_title="PJ043 Analytics | Início",
    initial_sidebar_state="collapsed",
    page_icon="🌎",
    menu_items={
        "About": "Dashboard PJ043 para análise sob demanda de produtos ambientais com Google Earth Engine.",
    },
)

load_css("assets/style.css")
initialize_gee()

st.markdown(
    """
    <div class="home-hero">
        <div>
            <p class="eyebrow">Projeto PJ043 • Ciências Atmosféricas</p>
            <h1>🌎 PJ043 Analytics</h1>
            <p class="subtitle">
                Geração sob demanda de mapas, séries temporais e downloads para produtos atmosféricos,
                vegetação, relevo, precipitação, cobertura do solo e modificação humana.
            </p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2 = st.columns([0.57, 0.43], gap="large")

with col1:
    st.markdown(
        """
        ### Como o painel funciona

        O dashboard **processa sob demanda**, gerando somente o produto solicitado.

        1. escolha o produto ambiental;
        2. selecione América do Sul, país, estado/província ou cidade;
        3. visualize mapas, séries ou downloads.
        """
    )
    st.info(
        "O mapa rápido ao lado carrega automaticamente o **acumulado mensal de Queimadas na América do Sul** "
        "para o último mês completo disponível.",
        icon="🔥",
    )

with col2:
    with st.container(border=True):
        st.markdown("#### Mapa rápido")
        st.caption("Acumulado mensal de queimadas na América do Sul, com shape dos países.")
        with st.spinner("Carregando acumulado mensal de queimadas..."):
            render_map(example_home_map(), height=390)

st.markdown("---")
st.header("Acesso rápido aos produtos principais")

c1, c2, c3, c4 = st.columns(4)

with c1:
    product_card_button("Queimadas", "🔥", "Queimadas", "Focos ativos via FIRMS.", "Contagem mensal")
with c2:
    product_card_button("CO", "🌫️", "CO", "Monóxido de carbono Sentinel-5P.", "Média")
with c3:
    product_card_button("Aerossóis", "🟤", "Aerossóis", "Índice de aerossóis absorventes.", "Média")
with c4:
    product_card_button("Metano", "🟢", "Metano", "CH₄ Sentinel-5P com paleta inferno.", "Média")

st.markdown("### Produtos ambientais adicionais")

d1, d2, d3, d4, d5, d6 = st.columns(6)

with d1:
    product_card_button("Temperatura", "🌡️", "Temperatura", "LST MODIS em °C.", "MODIS")
with d2:
    product_card_button("NDVI", "🌿", "NDVI", "Calculado por Sentinel-2.", "B8/B4")
with d3:
    product_card_button("Precipitação CHIRPS", "🌧️", "Chuva", "Precipitação acumulada.", "CHIRPS")
with d4:
    product_card_button("Relevo", "⛰️", "Relevo", "Elevação SRTM.", "SRTM")
with d5:
    product_card_button("Modificação Humana", "🏙️", "Modificação", "Índice gHM.", "CSP")
with d6:
    product_card_button("Cobertura do Solo", "🗺️", "Cobertura", "Classes Copernicus.", "Copernicus")

st.markdown("---")

with st.expander("Guia rápido para o usuário"):
    st.markdown(
        """
        - **Mapas Interativos:** gera o mapa espacial do produto selecionado.
        - **Séries Temporais:** extrai valores por dia ou por mês e permite baixar CSV.
        - **Downloads:** gera GeoTIFF, PNG, JPEG, CSV, JSON e HTML.
        - **Cidade/Município/Distrito:** permite selecionar unidades em países da América do Sul.
        - Produtos estáticos, como relevo e modificação humana, não dependem do período.
        - O mapa rápido da página inicial usa sempre o último mês completo para queimadas.
        """
    )

st.markdown(
    """
    <div class="footer">
        Desenvolvido para o projeto PJ043 | UNIFEI
    </div>
    """,
    unsafe_allow_html=True,
)
