#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regiões e shapes administrativos do dashboard PJ043.

V3.3.2:
- Mantém o recorte de processamento da América do Sul em retângulo simples.
- Remove o contorno quadrado/retangular da visualização.
- Mantém apenas o shape da América do Sul e dos países como contorno inicial.
"""

from __future__ import annotations

import ee
import streamlit as st


GAUL0 = "FAO/GAUL_SIMPLIFIED_500m/2015/level0"
GAUL1 = "FAO/GAUL_SIMPLIFIED_500m/2015/level1"
GAUL2 = "FAO/GAUL_SIMPLIFIED_500m/2015/level2"

SA_COUNTRIES = [
    "Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Ecuador",
    "Guyana", "Paraguay", "Peru", "Suriname", "Uruguay", "Venezuela",
    "French Guiana",
]


def south_america_bbox():
    # Recorte simples para processamento. Não deve aparecer como contorno no mapa.
    return ee.Geometry.Rectangle([-93, -60, -30, 15], proj="EPSG:4326", geodesic=False)


def region_options() -> list[str]:
    return [
        "América do Sul",
        "País da América do Sul",
        "Estado/Província/Departamento",
        "Cidade/Município/Distrito",
        "Brasil",
        "Minas Gerais",
        "Itajubá - raio 20 km",
        "Retângulo personalizado",
    ]


def overlay_options(region_name: str | None = None) -> list[str]:
    # Para América do Sul, não oferece "Região selecionada",
    # porque a região de processamento é um retângulo e ficaria visualmente feia.
    opts = ["América do Sul e países"]

    if region_name != "América do Sul":
        opts.append("Região selecionada")

    if region_name in {
        "Brasil",
        "Minas Gerais",
        "País da América do Sul",
        "Estado/Província/Departamento",
        "Cidade/Município/Distrito",
    }:
        opts.append("Estados/Províncias do país")

    if region_name == "Cidade/Município/Distrito":
        opts.append("Município/Distrito selecionado")

    return opts


def default_overlays(region_name: str | None = None) -> list[str]:
    # América do Sul: mostra só países, sem o quadrado do recorte.
    if region_name == "América do Sul":
        return ["América do Sul e países"]

    if region_name == "Cidade/Município/Distrito":
        return ["América do Sul e países", "Município/Distrito selecionado"]

    return ["América do Sul e países", "Região selecionada"]


def south_america_countries_fc() -> ee.FeatureCollection:
    return ee.FeatureCollection(GAUL0).filter(ee.Filter.inList("ADM0_NAME", SA_COUNTRIES))


def south_america_geometry():
    return south_america_countries_fc().geometry()


@st.cache_data(show_spinner=False)
def south_america_country_names() -> list[str]:
    return list(SA_COUNTRIES)


def country_fc(country_name: str) -> ee.FeatureCollection:
    return ee.FeatureCollection(GAUL0).filter(ee.Filter.eq("ADM0_NAME", country_name))


def country_geometry(country_name: str):
    return country_fc(country_name).geometry()


def admin1_fc(country_name: str) -> ee.FeatureCollection:
    return ee.FeatureCollection(GAUL1).filter(ee.Filter.eq("ADM0_NAME", country_name))


def selected_admin1_fc(country_name: str, admin1_name: str) -> ee.FeatureCollection:
    return (
        ee.FeatureCollection(GAUL1)
        .filter(ee.Filter.eq("ADM0_NAME", country_name))
        .filter(ee.Filter.eq("ADM1_NAME", admin1_name))
    )


def selected_city_fc(country_name: str, admin1_name: str, city_name: str) -> ee.FeatureCollection:
    return (
        ee.FeatureCollection(GAUL2)
        .filter(ee.Filter.eq("ADM0_NAME", country_name))
        .filter(ee.Filter.eq("ADM1_NAME", admin1_name))
        .filter(ee.Filter.eq("ADM2_NAME", city_name))
    )


def selected_region_fc(region) -> ee.FeatureCollection:
    return ee.FeatureCollection([ee.Feature(region)])


@st.cache_data(show_spinner=False)
def admin1_names(country_name: str) -> list[str]:
    names = ee.List(admin1_fc(country_name).aggregate_array("ADM1_NAME")).distinct().sort().getInfo()
    return [str(x) for x in names]


@st.cache_data(show_spinner=False)
def admin2_names(country_name: str, admin1_name: str) -> list[str]:
    fc = (
        ee.FeatureCollection(GAUL2)
        .filter(ee.Filter.eq("ADM0_NAME", country_name))
        .filter(ee.Filter.eq("ADM1_NAME", admin1_name))
    )
    names = ee.List(fc.aggregate_array("ADM2_NAME")).distinct().sort().getInfo()
    return [str(x) for x in names]


@st.cache_data(show_spinner=False)
def brazil_state_names() -> list[str]:
    return admin1_names("Brazil")


@st.cache_data(show_spinner=False)
def brazil_city_names(state_name: str) -> list[str]:
    return admin2_names("Brazil", state_name)


def get_region(
    name: str,
    bounds: tuple[float, float, float, float] | None = None,
    country_name: str | None = None,
    admin1_name: str | None = None,
    city_name: str | None = None,
    state_name: str | None = None,
):
    if name == "América do Sul":
        # Mantém recorte leve para evitar erro de geometria grande no Earth Engine.
        return south_america_bbox()

    if name == "País da América do Sul" and country_name:
        return country_geometry(country_name)

    if name == "Estado/Província/Departamento" and country_name and admin1_name:
        return selected_admin1_fc(country_name, admin1_name).geometry()

    if name == "Cidade/Município/Distrito" and country_name and admin1_name and city_name:
        return selected_city_fc(country_name, admin1_name, city_name).geometry()

    if name == "Brasil":
        return country_geometry("Brazil")

    if name == "Minas Gerais":
        return selected_admin1_fc("Brazil", "Minas Gerais").geometry()

    if name == "Cidade/Município" and state_name and city_name:
        return selected_city_fc("Brazil", state_name, city_name).geometry()

    if name == "Itajubá - raio 20 km":
        return ee.Geometry.Point([-45.452, -22.425]).buffer(20000).bounds()

    if name == "Retângulo personalizado" and bounds:
        lon_min, lat_min, lon_max, lat_max = bounds
        return ee.Geometry.Rectangle([lon_min, lat_min, lon_max, lat_max], proj="EPSG:4326", geodesic=False)

    return south_america_bbox()


def map_center(
    name: str,
    bounds: tuple[float, float, float, float] | None = None,
    region=None,
):
    if name == "Retângulo personalizado" and bounds:
        lon_min, lat_min, lon_max, lat_max = bounds
        return [(lat_min + lat_max) / 2, (lon_min + lon_max) / 2], 6

    if name in {"País da América do Sul", "Estado/Província/Departamento", "Cidade/Município/Distrito"} and region is not None:
        coords = region.centroid(maxError=1000).coordinates().getInfo()
        lon, lat = coords[0], coords[1]
        zoom = 5 if name == "País da América do Sul" else 7 if name == "Estado/Província/Departamento" else 10
        return [lat, lon], zoom

    centers = {
        "América do Sul": ([-25, -60], 3),
        "Brasil": ([-15, -55], 4),
        "Minas Gerais": ([-18.5, -44.5], 6),
        "Itajubá - raio 20 km": ([-22.425, -45.452], 10),
    }
    return centers.get(name, ([-25, -60], 3))


def region_display_name(
    region_name: str,
    country_name: str | None = None,
    admin1_name: str | None = None,
    city_name: str | None = None,
    state_name: str | None = None,
) -> str:
    if region_name == "País da América do Sul" and country_name:
        return country_name
    if region_name == "Estado/Província/Departamento" and country_name and admin1_name:
        return f"{admin1_name} - {country_name}"
    if region_name == "Cidade/Município/Distrito" and country_name and admin1_name and city_name:
        return f"{city_name} - {admin1_name} - {country_name}"
    if region_name == "Cidade/Município" and state_name and city_name:
        return f"{city_name} - {state_name} - Brazil"
    return region_name
