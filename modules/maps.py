#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mapas Folium + Earth Engine do VIGIA."""

from __future__ import annotations

import ee
import folium
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
    """Mantém a escala visual fixa definida no catálogo de produtos."""
    product = PRODUCTS[product_name]
    return dict(product.vis)


def _display_image_and_vis(product_name: str, image: ee.Image, region) -> tuple[ee.Image, dict]:
    if product_name != "Cobertura do Solo":
        return image, _dynamic_vis(product_name, image, region)

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


def _fmt_number(value: float | int | None, decimals: int = 2) -> str:
    if value is None:
        return "n/d"
    if isinstance(value, (int,)):
        return f"{value:,}".replace(",", ".")
    magnitude = abs(value)
    if 0 < magnitude < 0.01:
        # Colunas de gases (mol/m²) ficam em 1e-4–1e-5: com 2 casas viravam "0,00".
        return f"{value:.2e}".replace(".", ",")
    if decimals == 2 and magnitude < 1:
        decimals = 3
    text = f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return text


# Resumo do card: com bestEffort, o GEE aumenta a escala sozinho quando a área passaria deste
# número de pixels (ex.: NDVI 10 m num estado inteiro levava >10 min e falhava).
SUMMARY_MAX_PIXELS = 1e7


def summarize_image(product_name: str, image: ee.Image, region) -> dict:
    """Resume o conteúdo do produto dentro da área selecionada."""
    product = PRODUCTS[product_name]
    band = product.out_band

    if product_name == "Cobertura do Solo":
        try:
            hist = image.reduceRegion(
                reducer=ee.Reducer.frequencyHistogram(),
                geometry=region,
                scale=product.scale,
                maxPixels=SUMMARY_MAX_PIXELS,
                bestEffort=True,
            ).getInfo() or {}
            h = hist.get(band) or {}
            filtered = {k: v for k, v in h.items() if str(k) not in {"0", "200"} and float(v) > 0}
            n_classes = len(filtered)
            return {
                "headline": f"{n_classes} classe(s) presente(s)",
                "short": f"{n_classes} classe(s)",
                "details": [
                    f"Classes distintas no recorte: {n_classes}",
                    "Escala visual fixa conforme o catálogo do produto.",
                ],
            }
        except Exception:
            return {
                "headline": "Resumo indisponível",
                "short": "n/d",
                "details": ["Não foi possível calcular as classes presentes."],
            }

    if product.kind.startswith("fire_"):
        try:
            # Focos: soma exata na resolução nativa (pixels esparsos; aumentar a escala distorceria a contagem).
            stats = image.unmask(0).reduceRegion(
                reducer=ee.Reducer.sum().combine(reducer2=ee.Reducer.max(), sharedInputs=True),
                geometry=region,
                scale=product.scale,
                maxPixels=1e13,
                bestEffort=True,
            ).getInfo() or {}
            total = int(round(float(stats.get(f"{band}_sum") or 0)))
            max_pixel = float(stats.get(f"{band}_max") or 0)
            return {
                "headline": f"{total} foco(s) rasterizado(s)",
                "short": f"{total} foco(s)",
                "details": [
                    f"Total no recorte: {total}",
                    f"Máximo por pixel no período: {_fmt_number(max_pixel, 0)}",
                ],
            }
        except Exception:
            return {
                "headline": "Resumo indisponível",
                "short": "n/d",
                "details": ["Não foi possível calcular o total de detecções."],
            }

    try:
        stats = image.reduceRegion(
            reducer=ee.Reducer.minMax().combine(reducer2=ee.Reducer.mean(), sharedInputs=True),
            geometry=region,
            scale=product.scale,
            maxPixels=SUMMARY_MAX_PIXELS,
            bestEffort=True,
        ).getInfo() or {}
        vmin = stats.get(f"{band}_min")
        vmax = stats.get(f"{band}_max")
        vmean = stats.get(f"{band}_mean")
        if vmin is None and vmax is None and vmean is None:
            return {
                "headline": "Sem pixels válidos",
                "short": "sem dados",
                "details": ["Não há dados válidos nesse recorte/período."],
            }
        return {
            "headline": f"mín {_fmt_number(vmin)} • máx {_fmt_number(vmax)}",
            "short": f"mín {_fmt_number(vmin)} • máx {_fmt_number(vmax)}",
            "details": [
                f"Média na área: {_fmt_number(vmean)} {product.unit}",
                f"Faixa na área: {_fmt_number(vmin)} a {_fmt_number(vmax)} {product.unit}",
            ],
        }
    except Exception:
        return {
            "headline": "Resumo indisponível",
            "short": "n/d",
            "details": ["Não foi possível calcular estatísticas da área."],
        }


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


def quicklook_download_links(
    image: ee.Image,
    product_name: str,
    region,
    overlays: list[str],
    region_name: str | None = None,
    country_name: str | None = None,
    admin1_name: str | None = None,
    city_name: str | None = None,
    dimensions: int = 1600,
) -> dict[str, str]:
    """Gera links rápidos de PNG/JPEG para o mapa atualmente visualizado."""
    visual = visual_image_with_overlays(
        image,
        product_name,
        region,
        overlays,
        region_name=region_name,
        country_name=country_name,
        admin1_name=admin1_name,
        city_name=city_name,
    )
    region_bounds = region.bounds(maxError=1000).getInfo()["coordinates"]
    return {
        "PNG": visual.getThumbURL({"region": region_bounds, "dimensions": dimensions, "format": "png"}),
        "JPEG": visual.getThumbURL({"region": region_bounds, "dimensions": dimensions, "format": "jpg"}),
    }


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

    # A legenda flutuante e o controle de camadas foram removidos a pedido do usuário.
    # As informações do mapa são exibidas abaixo do mapa na própria página.
    return m, image, region
