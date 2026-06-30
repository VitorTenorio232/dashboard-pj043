#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import date, timedelta
import streamlit as st
from streamlit_folium import st_folium
from modules.auth_gee import initialize_gee
from modules.maps import make_map
from modules.products import PRODUCTS, image_count
from modules.regions import region_options, get_region
from modules.ui import custom_bounds_ui, load_css, page_title

st.set_page_config(layout='wide', page_title='PJ043 | Mapas', page_icon='🗺️')
load_css('assets/style.css')
initialize_gee()
page_title('🗺️ Mapas Interativos', 'Gere mapas sob demanda usando o Google Earth Engine.')

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
    st.caption(PRODUCTS[product_name].description)

if start >= end:
    st.error('A data inicial precisa ser anterior à data final.')
    st.stop()
c1, c2 = st.columns([0.72, 0.28])

with c2:
    st.markdown('### Produto')
    st.write(f'**{PRODUCTS[product_name].label}**')
    st.write(f'Unidade: `{PRODUCTS[product_name].unit}`')
    st.write(f'Escala: `{PRODUCTS[product_name].scale} m`')
    if st.button('Gerar mapa', type='primary', use_container_width=True):
        st.session_state['run_map'] = True

with c1:
    if st.session_state.get('run_map', False):
        with st.spinner('Processando no Google Earth Engine...'):
            region = get_region(region_name, bounds)
            n = image_count(product_name, start.isoformat(), end.isoformat(), region)
            mapa, image, region = make_map(product_name, start.isoformat(), end.isoformat(), region_name, bounds)
            st.success(f'Imagens encontradas no período: {n}')
            st_folium(mapa,height=680,use_container_width=True,)
    else:
        st.info('Configure os filtros e clique em **Gerar mapa**.')
