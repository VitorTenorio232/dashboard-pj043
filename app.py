#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import streamlit as st
from streamlit_folium import st_folium
from modules.auth_gee import initialize_gee
from modules.maps import example_home_map
from modules.ui import load_css

st.set_page_config(layout='wide', page_title='PJ043 Analytics | Início', initial_sidebar_state='collapsed', page_icon='🌎')
load_css('assets/style.css')
initialize_gee()

st.title('🌎 PJ043 Analytics')
st.markdown('##### Plataforma interativa para análise sob demanda de queimadas, monóxido de carbono, aerossóis e metano.')
st.write('---')
col1, col2 = st.columns([0.58, 0.42])
with col1:
    st.markdown('''
    O **PJ043 Analytics** permite gerar produtos ambientais diretamente pelo **Google Earth Engine**.

    A lógica do painel é simples:

    1. escolha o produto;
    2. selecione a região;
    3. defina o período;
    4. clique em gerar;
    5. visualize mapa, série temporal e arquivos para download.

    O dashboard não precisa gerar o banco completo antes. Ele processa apenas o produto solicitado.
    ''')
    st.info('Abra o menu lateral para acessar Mapas, Séries Temporais e Downloads.', icon='💡')
with col2:
    if st.button('Carregar mapa de exemplo', use_container_width=True):
        with st.spinner('Gerando mapa de exemplo no Earth Engine...'):
            mapa = example_home_map()
            st_folium(mapa,height=420,use_container_width=True,)
st.write('---')
st.header('Produtos disponíveis')
c1, c2, c3, c4 = st.columns(4)
with c1:
    with st.container(border=True):
        st.markdown('#### 🔥 Queimadas')
        st.write('Focos de calor via FIRMS no Google Earth Engine.')
        st.caption('Mapa acumulado e série temporal por região.')
with c2:
    with st.container(border=True):
        st.markdown('#### 🌫️ CO')
        st.write('Monóxido de carbono Sentinel-5P.')
        st.caption('Média no período, série temporal e download.')
with c3:
    with st.container(border=True):
        st.markdown('#### 🟤 Aerossóis')
        st.write('Índice de aerossóis absorventes Sentinel-5P.')
        st.caption('Mapas e séries temporais por área.')
with c4:
    with st.container(border=True):
        st.markdown('#### 🟢 Metano')
        st.write('CH₄ Sentinel-5P.')
        st.caption('Estrutura pronta para análise e expansão.')
with st.expander('Como usar'):
    st.markdown('''
    1. Entre em **Mapas Interativos** para gerar mapas.
    2. Entre em **Séries Temporais** para extrair valores médios ou contagens por período.
    3. Entre em **Downloads** para gerar links de download GeoTIFF.
    4. Ajuste região, datas e escala antes de processar.
    ''')
st.markdown('<div class="footer">Desenvolvido para o projeto PJ043 | Ciências Atmosféricas - UNIFEI</div>', unsafe_allow_html=True)
