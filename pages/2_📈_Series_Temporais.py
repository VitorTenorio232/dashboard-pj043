#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from datetime import date, timedelta
import plotly.express as px
import streamlit as st

from modules.auth_gee import initialize_gee
from modules.products import PRODUCTS
from modules.regions import region_options
from modules.series import make_series
from modules.ui import regional_selector_ui, load_css, page_title, product_metadata

st.set_page_config(layout="wide", page_title="PJ043 | Séries", page_icon="📈")
load_css("assets/style.css")
initialize_gee()

page_title("📈 Séries Temporais", "Extraia séries por produto, país, estado/província, cidade e período.")

with st.sidebar:
    st.header("Filtros da série")
    product_name = st.selectbox("Produto", list(PRODUCTS.keys()))
    region_name = st.selectbox("Região", region_options())
    bounds, country_name, admin1_name, city_name = regional_selector_ui(region_name)
    today = date.today()
    start = st.date_input("Data inicial", value=today - timedelta(days=30))
    end = st.date_input("Data final", value=today)
    freq = st.radio("Frequência", ["Diária", "Mensal"], horizontal=True)

product = PRODUCTS[product_name]
if start >= end:
    st.error("A data inicial precisa ser anterior à data final.")
    st.stop()
if freq == "Diária" and (end - start).days > 90:
    st.warning("Para frequência diária, escolha no máximo 90 dias.")
    st.stop()

c1, c2 = st.columns([0.70, 0.30], gap="large")
with c2:
    product_metadata(product)
    st.info("Para séries diárias longas, prefira reduzir o período ou usar frequência mensal.", icon="💡")

with c1:
    if st.button("Gerar série temporal", type="primary"):
        try:
            with st.spinner("Calculando série no Earth Engine..."):
                df = make_series(product_name, start, end, region_name, freq, bounds, country_name=country_name, admin1_name=admin1_name, city_name=city_name)
            st.dataframe(df, use_container_width=True)
            fig = px.line(df, x="data_inicio", y="valor", markers=True, title=f"{product_name} — {region_name}", labels={"valor": product.unit, "data_inicio": "Data"})
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
            st.download_button("Baixar CSV da série", data=df.to_csv(index=False).encode("utf-8"), file_name=f"PJ043_serie_{product_name}_{start}_{end}.csv", mime="text/csv")
        except Exception as exc:
            st.error("Não foi possível gerar a série.")
            st.exception(exc)
    else:
        st.info("Configure os filtros e clique em **Gerar série temporal**.")
