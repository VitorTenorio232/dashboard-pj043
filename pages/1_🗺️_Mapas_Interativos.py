#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from modules.auth_gee import initialize_gee
from modules.maps import BASEMAPS, make_map, render_map
from modules.products import PRODUCTS, image_count
from modules.regions import region_options, overlay_options, default_overlays, get_region
from modules.ui import regional_selector_ui, load_css, page_title, product_metadata, landcover_legend_ui

st.set_page_config(layout="wide", page_title="PJ043 | Mapas", page_icon="🗺️")
load_css("assets/style.css")
initialize_gee()

page_title("🗺️ Mapas Interativos", "Gere mapas com América do Sul, países, estados/províncias e municípios quando selecionados.")

with st.sidebar:
    st.header("Filtros do mapa")

    product_names = list(PRODUCTS.keys())
    quick_product = st.session_state.pop("produto_rapido", None)
    default_product_index = product_names.index(quick_product) if quick_product in product_names else 0

    product_name = st.selectbox("Produto", product_names, index=default_product_index)
    region_name = st.selectbox("Região", region_options())

    bounds, country_name, admin1_name, city_name = regional_selector_ui(region_name)

    today = date.today()
    start = st.date_input("Data inicial", value=today - timedelta(days=30))
    end = st.date_input("Data final", value=today)

    basemap = st.selectbox("Mapa base", BASEMAPS, index=0)

    overlays = st.multiselect(
        "Camadas de contorno",
        overlay_options(region_name),
        default=default_overlays(region_name),
        help="O shape da América do Sul e dos países aparece por padrão. O município/distrito só aparece quando essa região é selecionada.",
    )

product = PRODUCTS[product_name]

if start >= end:
    st.error("A data inicial precisa ser anterior à data final.")
    st.stop()

c1, c2 = st.columns([0.72, 0.28], gap="large")

with c2:
    product_metadata(product)
    if product_name == "Cobertura do Solo":
        landcover_legend_ui()
    st.info(
        "Para chuva, o máximo da legenda é calculado a partir do próprio dado no recorte selecionado.",
        icon="ℹ️",
    )
    run = st.button("Gerar mapa", type="primary", use_container_width=True)

with c1:
    if run:
        try:
            with st.spinner("Processando no Google Earth Engine..."):
                region = get_region(
                    region_name,
                    bounds,
                    country_name=country_name,
                    admin1_name=admin1_name,
                    city_name=city_name,
                )
                n = image_count(product_name, start.isoformat(), end.isoformat(), region)

                if n == 0:
                    st.warning(
                        "Nenhuma imagem encontrada para o produto, região e período selecionados. "
                        "Tente um período mais antigo ou uma região maior."
                    )
                    st.stop()

                mapa, image, region = make_map(
                    product_name,
                    start.isoformat(),
                    end.isoformat(),
                    region_name,
                    bounds=bounds,
                    overlays=overlays,
                    basemap=basemap,
                    country_name=country_name,
                    admin1_name=admin1_name,
                    city_name=city_name,
                )
                st.success(f"Imagens encontradas/usadas no período: {n}")
                render_map(mapa, height=680)
        except Exception as exc:
            st.error("Não foi possível gerar o mapa com os filtros selecionados.")
            st.exception(exc)
    else:
        st.info("Configure os filtros na barra lateral e clique em **Gerar mapa**.")
