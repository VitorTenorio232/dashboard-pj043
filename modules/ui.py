#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import streamlit as st

def load_css(path: str) -> None:
    p = Path(path)
    if p.exists():
        st.markdown(f'<style>{p.read_text(encoding="utf-8")}</style>', unsafe_allow_html=True)

def custom_bounds_ui():
    c1, c2 = st.columns(2)
    with c1:
        lon_min = st.number_input('Longitude mínima', value=-50.0)
        lat_min = st.number_input('Latitude mínima', value=-25.0)
    with c2:
        lon_max = st.number_input('Longitude máxima', value=-40.0)
        lat_max = st.number_input('Latitude máxima', value=-15.0)
    return lon_min, lat_min, lon_max, lat_max

def page_title(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="hero-small"><h2>{title}</h2><p>{subtitle}</p></div>', unsafe_allow_html=True)
