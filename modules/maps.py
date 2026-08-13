#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mapas Folium + Earth Engine do SIMQA."""

from __future__ import annotations

import ee
import folium
import streamlit as st
from streamlit_folium import st_folium

from modules.products import LANDCOVER_PALETTE, LANDCOVER_VALUES, PRODUCTS, period_image
from modules.regions import (
    get_region,
    map_center,
    south_america_countries_fc,
    admin1_fc,
    selected_city_fc,
    selected_region_fc,
)


BASEMAPS = ["Claro", "Escuro", "Satélite"]


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
    m = folium.Map(location=center, zoom_start=zoom, tiles=None, control_scale=True)

    if basemap == "Escuro":
        folium.TileLayer(tiles="CartoDB dark_matter", name="Escuro", overlay=False, control=True).add_to(m)
        return m

    if basemap == "Satélite":
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles © Esri",
            name="Satélite",
            overlay=False,
            control=True,
        ).add_to(m)
        return m

    folium.TileLayer(tiles="OpenStreetMap", name="Claro", overlay=False, control=True).add_to(m)
    return m


def _paint_outline(feature_collection, color: str, width: int):
    return ee.Image().byte().paint(featureCollection=feature_collection, color=1, width=width), {
        "palette": [color],
        "min": 1,
        "max": 1,
    }


def _outline_image(feature_collection, color: str = "111111", width: int = 2) -> ee.Image:
    return ee.Image().byte().paint(featureCollection=feature_collection, color=1, width=width).visualize(
        palette=[color], min=1, max=1
    )


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
        _add_outline(
            m,
            selected_city_fc(country_name, admin1_name, city_name),
            f"Município/Distrito: {city_name}",
            "dc2626",
            3,
        )


def _dynamic_vis(product_name: str, image: ee.Image, region) -> dict:
    product = PRODUCTS[product_name]
    vis = dict(product.vis)

    if product.kind in {"precip_sum", "precip_era5land_sum"} or product.kind.startswith("fire_"):
        try:
            stats = image.reduceRegion(
                reducer=ee.Reducer.max(),
                geometry=region,
                scale=product.scale,
                maxPixels=1e13,
                bestEffort=True,
            ).getInfo()
            value = stats.get(product.out_band)
            if value is not None and float(value) > 0:
                maximum = float(value)
                vis["min"] = 0
                vis["max"] = max(1, round(maximum, 2))
        except Exception:
            pass

    return vis


def _display_image_and_vis(product_name: str, image: ee.Image, region) -> tuple[ee.Image, dict]:
    """Retorna a imagem/visualização usada apenas no mapa.

    Para cobertura do solo, os códigos originais são esparsos (0, 20, 30, ..., 200).
    Uma paleta contínua aplicada diretamente de 0 a 200 interpola cores entre classes e
    não respeita a tabela categórica. Para o mapa, os códigos são remapeados para índices
    consecutivos e então recebem exatamente as cores oficiais. Os dados analíticos
    originais permanecem inalterados fora desta função.
    """
    if product_name != "Cobertura do Solo":
        return image, _dynamic_vis(product_name, image, region)

    # Oceano (200) e desconhecido (0) ficam transparentes para preservar o mapa base.
    mask = image.neq(0).And(image.neq(200))
    indexed = (
        image.updateMask(mask)
        .remap(LANDCOVER_VALUES, list(range(len(LANDCOVER_VALUES))), -1)
        .rename("landcover_display")
    )
    indexed = indexed.updateMask(indexed.gte(0))
    vis = {
        "min": 0,
        "max": len(LANDCOVER_VALUES) - 1,
        "palette": LANDCOVER_PALETTE,
    }
    return indexed, vis


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
    display_image, vis = _display_image_and_vis(product_name, image, region)
    rgb = display_image.visualize(**vis)

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
            <b>Cobertura do solo</b><br><span>classes categóricas • legenda lateral</span>
        </div>
        """

    palette = vis["palette"]
    gradient = ",".join(f"#{color}" for color in palette)
    min_value = vis.get("min", "")
    max_value = vis.get("max", "")

    return f"""
    <div style="position: fixed; bottom: 22px; right: 22px; z-index: 9999;
                background: white; padding: 8px 9px; border-radius: 10px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.16); font-size: 11px; width: 190px;">
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
    display_image, vis = _display_image_and_vis(product_name, image, region)

    layer_name = product.label if not product.temporal else f"{product.label} — {start} a {end}"
    m = _base_map(center, zoom, basemap)
    m.add_ee_layer(display_image, vis, layer_name)
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
