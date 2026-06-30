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
from modules.ui import custom_bounds_ui, load_css, page_title
st.set_page_config(layout='wide', page_title='PJ043 | Séries', page_icon='📈')
load_css('assets/style.css')
initialize_gee()
page_title('📈 Séries Temporais', 'Extraia séries temporais sob demanda por produto, região e período.')
with st.sidebar:
    st.header('Filtros')
    product_name = st.selectbox('Produto', list(PRODUCTS.keys()))
    region_name = st.selectbox('Região', region_options())
    bounds = None
    if region_name == 'Retângulo personalizado':
        bounds = custom_bounds_ui()
    today = date.today()
    start = st.date_input('Data inicial', value=today - timedelta(days=30))
    end = st.date_input('Data final', value=today)
    freq = st.radio('Frequência', ['Diária', 'Mensal'], horizontal=True)
if start >= end:
    st.error('A data inicial precisa ser anterior à data final.')
    st.stop()
if freq == 'Diária' and (end - start).days > 90:
    st.warning('Para frequência diária, escolha no máximo 90 dias para evitar processamento muito pesado.')
    st.stop()
if st.button('Gerar série temporal', type='primary'):
    with st.spinner('Calculando série no Earth Engine...'):
        df = make_series(product_name, start, end, region_name, freq, bounds)
    st.dataframe(df, use_container_width=True)
    fig = px.line(df, x='data_inicio', y='valor', markers=True, title=f'{product_name} — {region_name}', labels={'valor': PRODUCTS[product_name].unit, 'data_inicio': 'Data'})
    fig.update_layout(height=480)
    st.plotly_chart(fig, use_container_width=True)
    st.download_button('Baixar CSV', data=df.to_csv(index=False).encode('utf-8'), file_name=f'serie_{product_name.lower()}_{start}_{end}.csv', mime='text/csv')
else:
    st.info('Configure os filtros e clique em **Gerar série temporal**.')
