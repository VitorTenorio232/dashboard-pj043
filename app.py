#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ponto de entrada e navegação principal do SIMQA."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    layout="wide",
    page_title="SIMQA",
    page_icon="🌎",
    initial_sidebar_state="expanded",
    menu_items={
        "About": (
            "SIMQA — Sistema Integrado de Monitoramento de Queimadas e Atmosfera. "
            "Projeto PJ043 com processamento geoespacial no Google Earth Engine."
        ),
    },
)

pages = [
    st.Page("pages/0_🏠_HOME.py", title="HOME", icon="🏠", default=True),
    st.Page("pages/1_🗺️_Mapas_Interativos.py", title="Mapas Interativos", icon="🗺️"),
    st.Page("pages/2_📈_Series_Temporais.py", title="Séries Temporais", icon="📈"),
    st.Page("pages/3_📥_Downloads.py", title="Downloads", icon="📥"),
    st.Page("pages/4_ℹ️_Sobre_o_Sistema.py", title="Sobre o Sistema", icon="ℹ️"),
]

navigation = st.navigation(pages, position="sidebar")
navigation.run()
