#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import plotly.express as px
import streamlit as st

from modules.auth_gee import initialize_gee
from modules.products import PRODUCTS, safe_filename
from modules.regions import region_options
from modules.series import make_series
from modules.ui import (
    date_range_ui,
    load_css,
    page_title,
    processing_time_warning,
    product_metadata,
    product_selector_ui,
    regional_selector_ui,
)

load_css("assets/style.css")
initialize_gee()

page_title(
    "📈 Séries temporais",
    "Extraia estatísticas por dia ou mês para produtos de queimadas, atmosfera e superfície.",
)

with st.sidebar:
    st.header("Filtros da série")
    product_name = product_selector_ui("series")
    product = PRODUCTS[product_name]

    region_name = st.selectbox("Região", region_options(), key="series_region")
    bounds, country_name, admin1_name, city_name = regional_selector_ui(region_name)

    start, end = date_range_ui(product, "series_dates")
    processing_time_warning(product, start, end)

    if product.temporal:
        frequency = st.radio("Frequência", ["Diária", "Mensal"], horizontal=True)
    else:
        frequency = "Estática"

if product.temporal and start is not None and end is not None:
    if start > end:
        st.error("A data inicial precisa ser anterior ou igual à data final.")
        st.stop()
    if frequency == "Diária" and (end - start).days + 1 > 90:
        st.warning("Para séries diárias, selecione no máximo 90 dias ou use frequência mensal.")
        st.stop()

left, right = st.columns([0.70, 0.30], gap="large")
with right:
    product_metadata(product)
    if product.kind.startswith("fire_"):
        st.info(
            "Nas séries de focos, o valor regional é a soma das detecções rasterizadas. "
            "Não representa incêndios únicos.",
            icon="🔥",
        )

with left:
    if st.button("Gerar série temporal", type="primary"):
        try:
            with st.spinner("Calculando no Earth Engine..."):
                dataframe = make_series(
                    product_name,
                    start,
                    end,
                    region_name,
                    frequency,
                    bounds,
                    country_name=country_name,
                    admin1_name=admin1_name,
                    city_name=city_name,
                )

            st.dataframe(dataframe, use_container_width=True, hide_index=True)

            if product.temporal:
                figure = px.line(
                    dataframe,
                    x="data_inicio",
                    y="valor",
                    markers=True,
                    title=f"{product.label} — {region_name}",
                    labels={"valor": product.unit, "data_inicio": "Data"},
                )
                figure.update_layout(height=500)
                st.plotly_chart(figure, use_container_width=True)
            else:
                value = dataframe.iloc[0]["valor"] if not dataframe.empty else None
                st.metric(product.label, "Sem dados" if value is None else f"{value:.4g} {product.unit}")

            filename = f"SIMQA_serie_{safe_filename(product_name)}.csv"
            st.download_button(
                "Baixar CSV da série",
                data=dataframe.to_csv(index=False).encode("utf-8"),
                file_name=filename,
                mime="text/csv",
            )
        except Exception as exc:
            st.error("Não foi possível gerar a série.")
            st.exception(exc)
    else:
        st.info("Configure os filtros e clique em **Gerar série temporal**.")
