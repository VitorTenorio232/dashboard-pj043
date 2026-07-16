#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mapas Folium + Earth Engine, sem dependência do geemap.

V3.4:
- Mapa base reduzido para: Claro, Escuro e Satélite.
- Chuva usa máximo calculado a partir do próprio dado no recorte.
- Legenda contínua menor e mais otimizada.
- PNG/JPEG com shapes continuam funcionando.
- Mapa rápido da home: acumulado mensal de Queimadas na América do Sul.
"""

from __future__ import annotations

import ee
import folium
import streamlit as st
from streamlit_folium import st_folium

from modules.products import period_image, PRODUCTS
from modules.regions import (
    get_region,
    map_center,
    south_america_countries_fc,
    admin1_fc,
    selected_city_fc,
    selected_region_fc,
)

BASEMAPS = [
    "Claro",
    "Escuro",
    "Satélite",
]


def _add_ee_layer(self, ee_object, vis_params: dict, name: str) -> None:
    map_id = ee.Image(ee_object).getMapId(vis_params)
    folium.raster_layers.TileLayer(
        tiles=map_id["tile_fetcher"].url_format,
        attr="Google Earth Engine",
        name=name,
        overlay=True,
        control=True,
    ).add_to(self)


def _ensure_folium_ee_method() -> None:
    if not hasattr(folium.Map, "add_ee_layer"):
        folium.Map.add_ee_layer = _add_ee_layer


def _base_map(center: list[float], zoom: int, basemap: str) -> folium.Map:
    """Cria mapa base com apenas três opções limpas."""
    m = folium.Map(location=center, zoom_start=zoom, tiles=None, control_scale=True)

    if basemap in {"Escuro", "Escuro - CartoDB Dark Matter"}:
        folium.TileLayer(
            tiles="CartoDB dark_matter",
            name="Escuro",
            overlay=False,
            control=True,
        ).add_to(m)
        return m

    if basemap in {"Satélite", "Satélite Esri"}:
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles © Esri",
            name="Satélite",
            overlay=False,
            control=True,
        ).add_to(m)
        return m

    folium.TileLayer(
        tiles="OpenStreetMap",
        name="Claro",
        overlay=False,
        control=True,
    ).add_to(m)
    return m


def _paint_outline(feature_collection, color: str, width: int):
    return ee.Image().byte().paint(
        featureCollection=feature_collection,
        color=1,
        width=width,
    ), {"palette": [color], "min": 1, "max": 1}


def _outline_image(feature_collection, color: str = "111111", width: int = 2) -> ee.Image:
    line = ee.Image().byte().paint(featureCollection=feature_collection, color=1, width=width)
    return line.visualize(palette=[color], min=1, max=1)


def _add_outline(m: folium.Map, feature_collection, name: str, color: str, width: int) -> None:
    image, vis = _paint_outline(feature_collection, color, width)
    m.add_ee_layer(image, vis, name)


def _admin1_for_overlay(country_name: str | None, region_name: str):
    if country_name:
        return admin1_fc(country_name)
    if region_name in {"Brasil", "Minas Gerais"}:
        return admin1_fc("Brazil")
    return None


def _add_overlays(
    m: folium.Map,
    region,
    overlays: list[str],
    region_name: str | None = None,
    country_name: str | None = None,
    admin1_name: str | None = None,
    city_name: str | None = None,
) -> None:
    if "América do Sul e países" in overlays:
        _add_outline(m, south_america_countries_fc(), "América do Sul e países", "222222", 2)

    if "Estados/Províncias do país" in overlays:
        fc = _admin1_for_overlay(country_name, region_name or "")
        if fc is not None:
            _add_outline(m, fc, "Estados/Províncias do país", "555555", 1)

    if "Região selecionada" in overlays:
        _add_outline(m, selected_region_fc(region), "Região selecionada", "111111", 3)

    if "Município/Distrito selecionado" in overlays and country_name and admin1_name and city_name:
        _add_outline(m, selected_city_fc(country_name, admin1_name, city_name), f"Município/Distrito: {city_name}", "dc2626", 3)


def _dynamic_vis(product_name: str, image: ee.Image, region) -> dict:
    """Ajusta parâmetros de visualização quando necessário.

    Para CHIRPS, o máximo passa a ser calculado pelo próprio dado no recorte.
    """
    product = PRODUCTS[product_name]
    vis = dict(product.vis)

    if product_name == "Precipitação CHIRPS":
        try:
            stats = image.reduceRegion(
                reducer=ee.Reducer.max(),
                geometry=region,
                scale=product.scale,
                maxPixels=1e13,
                bestEffort=True,
            ).getInfo()
            value = stats.get(product.out_band)
            if value is not None:
                max_value = float(value)
                if max_value > 0:
                    vis["min"] = 0
                    vis["max"] = round(max_value, 2)
        except Exception:
            pass

    return vis


def visual_image_with_overlays(
    image: ee.Image,
    product_name: str,
    region,
    overlays: list[str],
    region_name: str | None = None,
    country_name: str | None = None,
    admin1_name: str | None = None,
    city_name: str | None = None,
) -> ee.Image:
    """Cria imagem RGB para PNG/JPEG com shapes desenhados."""
    vis = _dynamic_vis(product_name, image, region)
    rgb = image.visualize(**vis)

    if "América do Sul e países" in overlays:
        rgb = rgb.blend(_outline_image(south_america_countries_fc(), "222222", 2))

    if "Estados/Províncias do país" in overlays:
        fc = _admin1_for_overlay(country_name, region_name or "")
        if fc is not None:
            rgb = rgb.blend(_outline_image(fc, "555555", 1))

    if "Região selecionada" in overlays:
        rgb = rgb.blend(_outline_image(selected_region_fc(region), "111111", 3))

    if "Município/Distrito selecionado" in overlays and country_name and admin1_name and city_name:
        rgb = rgb.blend(_outline_image(selected_city_fc(country_name, admin1_name, city_name), "dc2626", 3))

    return rgb.clip(region)


def _legend_html(product_name: str, vis_params: dict | None = None) -> str:
    product = PRODUCTS[product_name]
    vis = vis_params or product.vis

    if product_name == "Cobertura do Solo":
        return """
        <div style="position: fixed; bottom: 22px; right: 22px; z-index: 9999;
                    background: white; padding: 7px 9px; border-radius: 10px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.16); font-size: 11px;">
            <b>Cobertura do Solo</b><br>
            <span>ver tabela lateral</span>
        </div>
        """

    palette = vis["palette"]
    gradient = ",".join(f"#{c}" for c in palette)
    min_value = vis.get("min", "")
    max_value = vis.get("max", "")

    return f"""
    <div style="position: fixed; bottom: 22px; right: 22px; z-index: 9999;
                background: white; padding: 8px 9px; border-radius: 10px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.16); font-size: 11px;
                width: 168px;">
        <b style="font-size: 11px;">{product.label}</b><br>
        <span style="font-size: 10px;">{product.unit}</span>
        <div style="height: 8px; margin: 6px 0; border-radius: 999px;
                    background: linear-gradient(to right, {gradient});"></div>
        <div style="display: flex; justify-content: space-between; font-size: 10px;">
            <span>{min_value}</span><span>{max_value}</span>
        </div>
    </div>
    """


def render_map(m: folium.Map, height: int = 650) -> None:
    st_folium(m, height=height, use_container_width=True, returned_objects=[])


def make_map(
    product_name: str,
    start: str,
    end: str,
    region_name: str,
    bounds=None,
    overlays: list[str] | None = None,
    basemap: str = "Claro",
    country_name: str | None = None,
    admin1_name: str | None = None,
    city_name: str | None = None,
):
    _ensure_folium_ee_method()

    overlays = overlays or ["América do Sul e países", "Região selecionada"]
    region = get_region(
        region_name,
        bounds,
        country_name=country_name,
        admin1_name=admin1_name,
        city_name=city_name,
    )
    image = period_image(product_name, start, end, region)
    product = PRODUCTS[product_name]
    center, zoom = map_center(region_name, bounds, region=region)
    vis = _dynamic_vis(product_name, image, region)

    m = _base_map(center, zoom, basemap)
    m.add_ee_layer(image, vis, f"{product.label} — {start} a {end}")
    _add_overlays(
        m,
        region,
        overlays,
        region_name=region_name,
        country_name=country_name,
        admin1_name=admin1_name,
        city_name=city_name,
    )
    m.get_root().html.add_child(folium.Element(_legend_html(product_name, vis)))
    folium.LayerControl(collapsed=False).add_to(m)

    return m, image, region


def example_home_map():
    """Mapa rápido da página inicial: acumulado mensal de Queimadas na América do Sul.

    Usa sempre o último mês completo para evitar mês corrente incompleto.
    """
    from datetime import date, timedelta

    _ensure_folium_ee_method()

    today = date.today()
    first_day_this_month = date(today.year, today.month, 1)
    last_day_previous_month = first_day_this_month - timedelta(days=1)
    start_date = date(last_day_previous_month.year, last_day_previous_month.month, 1)
    end_date = first_day_this_month

    start = start_date.isoformat()
    end = end_date.isoformat()
    month_label = start_date.strftime("%m/%Y")

    region = get_region("América do Sul")
    image = period_image("Queimadas", start, end, region)

    vis = PRODUCTS["Queimadas"].vis
    m = _base_map([-25, -60], 3, "Claro")
    m.add_ee_layer(image, vis, f"Queimadas acumulado mensal — América do Sul — {month_label}")
    _add_overlays(
        m,
        region,
        ["América do Sul e países"],
        region_name="América do Sul",
    )
    m.get_root().html.add_child(folium.Element(_legend_html("Queimadas", vis)))
    folium.LayerControl(collapsed=False).add_to(m)

    return m
