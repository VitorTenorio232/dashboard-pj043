#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import date, timedelta
import streamlit as st
from modules.auth_gee import initialize_gee
from modules.products import PRODUCTS, period_image
from modules.regions import get_region, region_options
from modules.ui import custom_bounds_ui, load_css, page_title
st.set_page_config(layout='wide', page_title='PJ043 | Downloads', page_icon='📥')
load_css('assets/style.css')
initialize_gee()
page_title('📥 Downloads', 'Gere links de download GeoTIFF para produtos processados sob demanda.')
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
    scale = st.number_input('Escala do download (m)', min_value=1000, max_value=50000, value=PRODUCTS[product_name].scale, step=1000)
if start >= end:
    st.error('A data inicial precisa ser anterior à data final.')
    st.stop()
st.warning('Downloads grandes podem falhar. Para América do Sul inteira, use escala maior ou período menor.')
if st.button('Gerar link GeoTIFF', type='primary'):
    with st.spinner('Criando link no Earth Engine...'):
        region = get_region(region_name, bounds)
        image = period_image(product_name, start.isoformat(), end.isoformat(), region)
        url = image.getDownloadURL({'name': f'PJ043_{product_name}_{start}_{end}', 'scale': int(scale), 'region': region, 'crs': 'EPSG:4326', 'filePerBand': False})
    st.success('Link gerado.')
    st.link_button('Baixar GeoTIFF', url)
