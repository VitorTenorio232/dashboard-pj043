#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import ee
import folium
import branca.colormap as cm

from modules.products import period_image, PRODUCTS
from modules.regions import get_region, map_center

def add_ee_layer(m, ee_object, vis_params, name):
    """
    Adiciona imagem ou camada do Google Earth Engine no mapa Folium.
    Substitui o m.addLayer() do geemap.
    """
    map_id_dict = ee.Image(ee_object).getMapId(vis_params)

    folium.raster_layers.TileLayer(
        tiles=map_id_dict["tile_fetcher"].url_format,
        attr="Google Earth Engine",
        name=name,
        overlay=True,
        control=True,
    ).add_to(m)


def add_region_layer(m, region, name="Região"):
    """
    Adiciona o contorno da região no Folium usando Earth Engine.
    Substitui m.addLayer(region, {'color':'white'}, 'Região').
    """
    region_outline = ee.Image().byte().paint(featureCollection=region,color=1,width=2,)
    add_ee_layer(m,region_outline,{"palette": ["white"]},name,)


def add_colorbar(m, vis_params, label=""):
    """
    Adiciona barra de cores simples no mapa Folium.
    Substitui m.add_colorbar() do geemap.
    """
    palette = vis_params.get("palette", [])
    palette = [color if color.startswith("#") else f"#{color}"for color in palette]
    colormap = cm.LinearColormap(colors=palette,vmin=vis_params.get("min", 0),vmax=vis_params.get("max", 1),caption=label,)
    colormap.add_to(m)

def make_map(product_name: str, start: str, end: str, region_name: str, bounds=None):
    region = get_region(region_name, bounds)
    image = period_image(product_name, start, end, region)

    product = PRODUCTS[product_name]
    vis_params = product.vis

    center, zoom = map_center(region_name)

    m = folium.Map(location=center,zoom_start=zoom,tiles=None,control_scale=True,)

    folium.TileLayer(tiles="OpenStreetMap",name="OpenStreetMap",control=True,).add_to(m)
    folium.TileLayer(tiles="CartoDB dark_matter",name="CartoDB DarkMatter",control=True,).add_to(m)

    add_ee_layer(m,image,vis_params,product_name,)
    add_region_layer(m,region,"Região",)
    add_colorbar(m,vis_params,label=product.unit,)

    folium.LayerControl().add_to(m)

    return m, image, region

def example_home_map():
    region = get_region("Brasil")

    image = (
        ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_CO")
        .filterDate("2024-08-01", "2024-08-31")
        .filterBounds(region)
        .select("CO_column_number_density")
        .mean()
        .clip(region)
    )

    vis = {"min": 0,"max": 0.05,"palette": ["1d4ed8", "38bdf8", "facc15", "f97316", "dc2626"],}

    m = folium.Map(location=[-15, -55],zoom_start=4,tiles=None,control_scale=True,)

    folium.TileLayer(tiles="OpenStreetMap",name="OpenStreetMap",control=True,).add_to(m)
    folium.TileLayer(tiles="CartoDB dark_matter",name="CartoDB DarkMatter",control=True,).add_to(m)

    add_ee_layer(m,image,vis,"CO médio — ago/2024",)
    add_region_layer(m,region,"Brasil",)
    add_colorbar(m,vis,label="mol/m²",)

    folium.LayerControl().add_to(m)

    return m
