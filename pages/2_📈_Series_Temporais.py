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
    regional_selector_ui, region_picker_ui, sidebar_brand,
)

load_css("assets/style.css")
initialize_gee()

page_title(
    "Séries temporais",
    "Extraia estatísticas por dia ou mês para produtos de queimadas, atmosfera e superfície.",
)

with st.sidebar:
    sidebar_brand()
    st.markdown("**01  ·  Fonte de dados**")
    product_name = product_selector_ui("series")
    product = PRODUCTS[product_name]

    st.divider()
    st.markdown("**02  ·  Área de interesse**")
    region_name = region_picker_ui("series_region")
    bounds, country_name, admin1_name, city_name = regional_selector_ui(region_name)

    st.divider()
    st.markdown("**03  ·  Período**")
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
    run_series = st.button("Gerar série temporal", type="primary", width="stretch")
    if run_series:
        try:
            with st.spinner("Calculando no Google Earth Engine..."):
                dataframe = make_series(
                    product_name, start, end, region_name, frequency, bounds,
                    country_name=country_name, admin1_name=admin1_name, city_name=city_name,
                )
<<<<<<< HEAD

            st.dataframe(dataframe, width="stretch", hide_index=True)

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
                st.plotly_chart(figure, width="stretch")
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
=======
            st.session_state["vigia_last_series"] = {
                "df": dataframe, "product": product_name, "region": region_name,
                "frequency": frequency,
            }
>>>>>>> 2194994 (release: VIGIA v5.5.10 - identidade visual e melhorias)
        except Exception as exc:
            st.error("Não foi possível gerar a série.")
            st.exception(exc)

    last_series = st.session_state.get("vigia_last_series")
    if not last_series:
        with st.container(border=True):
            st.info("Defina os filtros e clique em **Gerar série temporal** para iniciar.")
    else:
        df = last_series["df"]
        last_product = PRODUCTS[last_series["product"]]
        st.markdown(f"### {last_product.label}")
        st.caption(f"Região: {last_series['region']} · Frequência: {last_series['frequency']}")
        if last_series["product"] != product_name or last_series["region"] != region_name:
            st.info("Os filtros foram alterados. A tabela ainda representa a última série gerada.")
        with st.container(border=True):
            if not df.empty and last_product.temporal:
                fig = px.line(df, x="data_inicio", y="valor", markers=True,
                              labels={"valor": last_product.unit, "data_inicio": "Data"})
                fig.update_traces(line_color="#0a796b", marker_color="#d86c36")
                fig.update_layout(height=400, margin=dict(l=10,r=10,t=30,b=15),
                                  paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, width="stretch")
            elif not df.empty:
                value = df.iloc[0]["valor"]
                st.metric(last_product.label, "Sem dados" if value is None else f"{value:.4g} {last_product.unit}")
            st.dataframe(df, width="stretch", hide_index=True)
            st.download_button("Baixar CSV da série", data=df.to_csv(index=False).encode("utf-8"),
                               file_name=f"VIGIA_serie_{safe_filename(last_series['product'])}.csv",
                               mime="text/csv", width="stretch")
