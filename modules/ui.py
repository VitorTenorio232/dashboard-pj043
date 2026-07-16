#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

import streamlit as st

from modules.regions import (
    south_america_country_names,
    admin1_names,
    admin2_names,
)


LANDCOVER_CLASSES = [
    (0, "#282828", "Desconhecido. Não há dados de satélite disponíveis ou eles são insuficientes."),
    (20, "#ffbb22", "Arbustos. Plantas perenes lenhosas com caules persistentes e lenhosos e sem um caule principal definido com menos de 5 m de altura."),
    (30, "#ffff4c", "Vegetação herbácea. Plantas sem caule ou brotos persistentes acima do solo e sem estrutura firme definida."),
    (40, "#f096ff", "Vegetação/agricultura cultivada e gerenciada. Terras cobertas com plantações temporárias."),
    (50, "#fa0000", "Urbana/construída. Terreno coberto por edifícios e outras estruturas feitas pelo homem."),
    (60, "#b4b4b4", "Vegetação rala ou esparsa. Terras com solo, areia ou rochas expostos e até 10 % de cobertura vegetal."),
    (70, "#f0f0f0", "Neve e gelo. Terras cobertas de neve ou gelo durante todo o ano."),
    (80, "#0032c8", "Corpos d'água permanentes. Lagos, reservatórios e rios."),
    (90, "#0096a0", "Pântano herbáceo. Mistura permanente de água e vegetação herbácea ou lenhosa."),
    (100, "#fae6a0", "Musgo e líquen."),
    (111, "#58481f", "Floresta fechada, perene com folhas em forma de agulha."),
    (112, "#009900", "Floresta fechada, perene de folhas largas."),
    (113, "#70663e", "Floresta fechada, folha de agulha decídua."),
    (114, "#00cc00", "Floresta fechada, folha larga decídua."),
    (115, "#4e751f", "Floresta fechada, mista."),
    (116, "#007800", "Floresta fechada que não corresponde a nenhuma das outras definições."),
    (121, "#666000", "Floresta aberta, perene com folhas em forma de agulha."),
    (122, "#8db400", "Floresta aberta, perene de folhas largas."),
    (123, "#8d7400", "Floresta aberta, folha de agulha decídua."),
    (124, "#a0dc00", "Floresta aberta, folha larga decídua."),
    (125, "#929900", "Floresta aberta, mista."),
    (126, "#648c00", "Floresta aberta que não corresponde a nenhuma das outras definições."),
    (200, "#000080", "Oceanos, mares. Podem ser de água doce ou salgada."),
]


def load_css(path: str) -> None:
    p = Path(path)
    if p.exists():
        st.markdown(f"<style>{p.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def custom_bounds_ui():
    st.caption("Informe o retângulo no formato longitude/latitude em graus decimais.")
    c1, c2 = st.columns(2)
    with c1:
        lon_min = st.number_input("Longitude mínima", value=-50.0, format="%.4f")
        lat_min = st.number_input("Latitude mínima", value=-25.0, format="%.4f")
    with c2:
        lon_max = st.number_input("Longitude máxima", value=-40.0, format="%.4f")
        lat_max = st.number_input("Latitude máxima", value=-15.0, format="%.4f")
    return lon_min, lat_min, lon_max, lat_max


def regional_selector_ui(region_name: str):
    country_name = None
    admin1_name = None
    city_name = None
    bounds = None

    if region_name == "País da América do Sul":
        countries = south_america_country_names()
        country_name = st.selectbox("País", countries, index=countries.index("Brazil") if "Brazil" in countries else 0)

    elif region_name == "Estado/Província/Departamento":
        countries = south_america_country_names()
        country_name = st.selectbox("País", countries, index=countries.index("Brazil") if "Brazil" in countries else 0)
        admins = admin1_names(country_name)
        if not admins:
            st.warning("Nenhuma unidade de primeiro nível encontrada para esse país.")
            st.stop()
        default = "Minas Gerais" if country_name == "Brazil" and "Minas Gerais" in admins else admins[0]
        admin1_name = st.selectbox("Estado/Província/Departamento", admins, index=admins.index(default))

    elif region_name == "Cidade/Município/Distrito":
        st.caption("O shape municipal será carregado apenas para a cidade selecionada.")
        countries = south_america_country_names()
        country_name = st.selectbox("País", countries, index=countries.index("Brazil") if "Brazil" in countries else 0)
        admins = admin1_names(country_name)
        if not admins:
            st.warning("Nenhuma unidade de primeiro nível encontrada para esse país.")
            st.stop()
        default_admin = "Minas Gerais" if country_name == "Brazil" and "Minas Gerais" in admins else admins[0]
        admin1_name = st.selectbox("Estado/Província/Departamento", admins, index=admins.index(default_admin))

        cities = admin2_names(country_name, admin1_name)
        if not cities:
            st.warning("Nenhum município/distrito encontrado para essa unidade.")
            st.stop()
        default_city = "Itajubá" if country_name == "Brazil" and "Itajubá" in cities else cities[0]
        city_name = st.selectbox("Cidade/Município/Distrito", cities, index=cities.index(default_city))

    elif region_name == "Retângulo personalizado":
        bounds = custom_bounds_ui()

    return bounds, country_name, admin1_name, city_name


def city_selector_ui():
    countries = south_america_country_names()
    country_name = "Brazil" if "Brazil" in countries else countries[0]
    admins = admin1_names(country_name)
    default_admin = "Minas Gerais" if "Minas Gerais" in admins else admins[0]
    admin1_name = st.selectbox("Estado", admins, index=admins.index(default_admin))
    cities = admin2_names(country_name, admin1_name)
    default_city = "Itajubá" if "Itajubá" in cities else cities[0]
    city_name = st.selectbox("Cidade/Município", cities, index=cities.index(default_city))
    return admin1_name, city_name


def page_title(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="hero-small">
            <h2>{title}</h2>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def product_card(icon: str, title: str, text: str, footer: str) -> None:
    st.markdown(
        f"""
        <div class="product-card">
            <div class="product-icon">{icon}</div>
            <h3>{title}</h3>
            <p>{text}</p>
            <span>{footer}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def product_card_button(product_name: str, icon: str, title: str, text: str, footer: str) -> None:
    product_card(icon, title, text, footer)
    if st.button(f"Abrir {title}", key=f"home_open_{product_name}", use_container_width=True):
        st.session_state["produto_rapido"] = product_name
        st.switch_page("pages/1_🗺️_Mapas_Interativos.py")


def product_metadata(product) -> None:
    st.markdown("### Detalhes do produto")
    st.write(f"**Produto:** {product.label}")
    st.write(f"**Fonte:** {product.source}")
    st.write(f"**Coleção/Imagem GEE:** `{product.collection or product.image_id}`")
    st.write(f"**Banda:** `{','.join(product.band) if isinstance(product.band, list) else product.band}`")
    st.write(f"**Unidade:** `{product.unit}`")
    st.write(f"**Estatística:** {product.statistic}")
    st.write(f"**Escala padrão:** `{product.scale} m`")
    st.caption(product.user_note)


def landcover_legend_ui() -> None:
    """Tabela lateral compacta para Cobertura do Solo Copernicus."""
    rows = []
    for value, color, desc in LANDCOVER_CLASSES:
        rows.append(
            f"""
            <tr>
                <td style="font-weight:700; width:42px;">{value}</td>
                <td style="width:34px;">
                    <span style="display:inline-block; width:18px; height:18px;
                                 background:{color}; border:1px solid #999; border-radius:4px;"></span>
                </td>
                <td style="font-size:11px; line-height:1.25;">{desc}</td>
            </tr>
            """
        )

    html = f"""
    <div style="max-height: 430px; overflow-y: auto; border: 1px solid #e5e7eb;
                border-radius: 12px; padding: 8px; background: #ffffff;">
        <table style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr>
                    <th style="text-align:left; font-size:11px;">Valor</th>
                    <th style="text-align:left; font-size:11px;">Cor</th>
                    <th style="text-align:left; font-size:11px;">Descrição</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </div>
    """
    st.markdown("### Classes de cobertura")
    st.markdown(html, unsafe_allow_html=True)
