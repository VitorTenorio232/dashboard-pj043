#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import streamlit as st

from modules.auth_gee import initialize_gee
from modules.maps import BASEMAPS, make_map, render_map
from modules.products import PRODUCTS, image_count
from modules.regions import default_overlays, get_region, overlay_options, region_options
from modules.ui import (
    date_range_ui,
    landcover_legend_ui,
    load_css,
    page_title,
    processing_time_warning,
    product_metadata,
    product_selector_ui,
    query_dates,
    regional_selector_ui,
)

load_css("assets/style.css")
initialize_gee()

page_title(
    "🗺️ Mapas interativos",
    "Monitore focos de calor, aerossóis, gases atmosféricos e variáveis ambientais por banco de dados.",
)

with st.sidebar:
    st.header("Filtros do mapa")

    # O acesso rápido grava o produto nestas chaves antes de trocar de página.
    quick_product = st.session_state.pop("produto_rapido", None)
    product_name = product_selector_ui("map", default_product=quick_product)
    product = PRODUCTS[product_name]

    region_name = st.selectbox("Região", region_options(), key="map_region")
    bounds, country_name, admin1_name, city_name = regional_selector_ui(region_name)

    basemap = st.selectbox("Mapa base", BASEMAPS, index=0, key="map_basemap")
    overlays = st.multiselect(
        "Camadas de contorno",
        overlay_options(region_name),
        default=default_overlays(region_name),
        key=f"map_overlays_{region_name}",
        help="O município/distrito aparece somente quando essa região é selecionada.",
    )

    start, end = date_range_ui(product, "map_dates")
    processing_time_warning(product, start, end)

    # O botão fica no lado esquerdo, imediatamente abaixo do bloco temporal/aviso.
    run = st.button("Gerar mapa", type="primary", use_container_width=True)

if product.temporal and start is not None and end is not None and start > end:
    st.error("A data inicial precisa ser anterior ou igual à data final.")
    st.stop()

left, right = st.columns([0.72, 0.28], gap="large")

with right:
    product_metadata(product)
    if product_name == "Cobertura do Solo":
        landcover_legend_ui()
    if product.kind in {"precip_sum", "precip_era5land_sum"}:
        st.info(
            "O máximo da legenda é calculado automaticamente com os dados do recorte selecionado.",
            icon="ℹ️",
        )

with left:
    if not run:
        st.info("Configure os filtros na barra lateral e clique em **Gerar mapa**.")
    else:
        try:
            with st.spinner("Processando no Google Earth Engine..."):
                start_text, end_text = query_dates(product, start, end)
                region = get_region(
                    region_name,
                    bounds,
                    country_name=country_name,
                    admin1_name=admin1_name,
                    city_name=city_name,
                )
                n_images = image_count(product_name, start_text, end_text, region)
                if n_images == 0:
                    st.warning(
                        "Nenhuma imagem foi encontrada para o produto, a região e o período selecionados. "
                        "Confira a disponibilidade no painel de informações à direita ou escolha outro período."
                    )
                    st.stop()

                map_object, _, _ = make_map(
                    product_name,
                    start_text,
                    end_text,
                    region_name,
                    bounds=bounds,
                    overlays=overlays,
                    basemap=basemap,
                    country_name=country_name,
                    admin1_name=admin1_name,
                    city_name=city_name,
                )

            if product.temporal:
                st.success(f"Imagens encontradas/usadas no período: {n_images}")
            else:
                st.success("Produto estático carregado com sucesso.")
            render_map(map_object, height=680)
        except Exception as exc:
            st.error("Não foi possível gerar o mapa com os filtros selecionados.")
            st.exception(exc)
