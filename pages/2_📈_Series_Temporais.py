#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.auth_gee import initialize_gee
from modules.maps import cached_region_area_km2, region_key
from modules.products import PRODUCTS, heavy_request_message, safe_filename
from modules.series import cached_series
from modules.ui import (
    date_range_ui,
    load_css,
    page_title,
    processing_time_warning,
    product_metadata,
    product_selector_ui,
    regional_selector_ui, region_picker_ui, report_exception, selection_differs, sidebar_brand,
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
    # Produtos de alta resolução ou alta cadência (GOES a cada 10 min) pesam mais por dia.
    heavy = product.scale < 1000 or product.kind == "fire_goes"
    max_daily = 90 if heavy else 366
    if frequency == "Diária" and (end - start).days + 1 > max_daily:
        st.warning(f"Para séries diárias deste produto, selecione no máximo {max_daily} dias ou use frequência mensal.")
        st.stop()

area_key = region_key(region_name, bounds, country_name, admin1_name, city_name)
current_selection = (product_name, area_key, start, end, frequency)

left, right = st.columns([0.70, 0.30], gap="large")
with right:
    product_metadata(product)
    if product.kind.startswith("fire_"):
        st.info(
            "Nas séries de focos, o valor regional é a soma das detecções rasterizadas. "
            "Não representa incêndios únicos.",
            icon="🔥",
        )

def series_file_name(last: dict, region_label: str) -> str:
    """Inclui período e frequência: séries de períodos diferentes não geram arquivos com o mesmo nome."""
    period = f"{last['start']}_{last['end']}_{last['frequency']}" if last.get("start") else "estatico"
    return f"VIGIA_serie_{safe_filename(last['product'])}_{safe_filename(region_label)}_{safe_filename(period)}.csv"


with left:
    run_series = st.button("Gerar série temporal", type="primary", width="stretch")
    if run_series:
        try:
            heavy = None
            if product.max_area_days and start is not None and end is not None:
                heavy = heavy_request_message(product_name, cached_region_area_km2(area_key), (end - start).days + 1)
            if heavy:
                st.warning(heavy, icon="🐢")
            else:
                with st.spinner("Calculando no Google Earth Engine..."):
                    dataframe = cached_series(
                        product_name, start, end, region_name, frequency, bounds,
                        country_name=country_name, admin1_name=admin1_name, city_name=city_name,
                    )
                st.session_state["vigia_last_series"] = {
                    "df": dataframe, "product": product_name, "region": region_name,
                    "frequency": frequency, "selection": current_selection,
                    "start": start, "end": end,
                }
        except Exception as exc:
            report_exception("Não foi possível gerar a série.", exc)

    last_series = st.session_state.get("vigia_last_series")
    if not last_series:
        with st.container(border=True):
            st.info("Defina os filtros e clique em **Gerar série temporal** para iniciar.")
    else:
        df = last_series["df"]
        last_product = PRODUCTS[last_series["product"]]
        st.markdown(f"### {last_product.label}")
        region_label = df["regiao"].iloc[0] if not df.empty else last_series["region"]
        valid = df["valor"].notna().sum() if not df.empty else 0
        st.caption(
            f"Região: **{region_label}** · Frequência: {last_series['frequency']} · "
            f"Intervalos com dado: {valid} de {len(df)}"
        )
        if selection_differs(last_series, current_selection):
            st.info("Os filtros foram alterados. O gráfico, a tabela e o CSV ainda representam a última série gerada.")
        with st.container(border=True):
            if not df.empty and last_product.temporal:
                fig = px.line(df, x="data_inicio", y="valor", markers=True,
                              labels={"valor": last_product.unit, "data_inicio": "Data"})
                # connectgaps só no SMAP (dias sem passagem são esperados). Nos demais produtos, como chuva,
                # uma linha atravessando o dia sem observação parecia um valor medido.
                fig.update_traces(line_color="#0a796b", marker_color="#d86c36",
                                  connectgaps=last_product.kind == "soil_moisture_smap")
                fig.update_layout(height=400, margin=dict(l=10,r=10,t=30,b=15),
                                  paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, width="stretch")
            elif not df.empty:
                value = df.iloc[0]["valor"]
                st.metric(last_product.label, "Sem dados" if pd.isna(value) else f"{value:.4g} {last_product.unit}")
            st.dataframe(df, width="stretch", hide_index=True)
            st.download_button("Baixar CSV da série", data=df.to_csv(index=False).encode("utf-8"),
                               file_name=series_file_name(last_series, region_label),
                               mime="text/csv", width="stretch", on_click="ignore")
