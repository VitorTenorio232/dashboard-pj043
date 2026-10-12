#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ponto de entrada e navegação principal do VIGIA."""

from __future__ import annotations

import streamlit as st
from pathlib import Path

st.set_page_config(
    layout="wide",
    page_title="VIGIA | Monitoramento Ambiental",
    page_icon=str(Path(__file__).resolve().parent / "assets" / "favicon_vigia.png"),
    initial_sidebar_state="expanded",
    menu_items={
        "About": (
            "VIGIA — Visualização Integrada de Gases, Incêndios e Atmosfera. "
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
