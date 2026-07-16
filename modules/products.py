#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Catálogo de produtos do dashboard PJ043.

V3.2.2 — NDVI calculado por Sentinel-2:
- Troca NDVI pronto MODIS por NDVI calculado:
  NDVI = (NIR - Red) / (NIR + Red)
- Usa Sentinel-2 Surface Reflectance Harmonized:
  COPERNICUS/S2_SR_HARMONIZED
- Bandas:
  NIR = B8
  Red = B4
- Mantém correções da V3.2.1:
  CHIRPS estável, gHM como ImageCollection, Cobertura do Solo com fallback.
- Não força grade de 20 km.
- Não usa reduceResolution/reproject.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import unicodedata

import ee


INFERNO_PALETTE = [
    "000004", "1b0c41", "4a0c6b", "781c6d", "a52c60",
    "cf4446", "ed6925", "fb9b06", "f7d13d", "fcffa4",
]


LANDCOVER_PALETTE = [
    "282828", "ffbb22", "ffff4c", "f096ff", "fa0000", "b4b4b4",
    "f0f0f0", "0032c8", "0096a0", "fae6a0", "58481f", "009900",
    "70663e", "00cc00", "4e751f", "007800", "666000", "8db400",
    "8d7400", "a0dc00", "929900", "648c00", "000080",
]


@dataclass(frozen=True)
class Product:
    key: str
    label: str
    source: str
    collection: str | None
    image_id: str | None
    band: str | list[str]
    out_band: str
    unit: str
    scale: int
    statistic: str
    reducer_name: str
    vis: dict
    kind: str
    temporal: bool
    user_note: str
    fallback_to_latest: bool = False


PRODUCTS = {
    "Queimadas": Product(
        key="Queimadas",
        label="Queimadas",
        source="FIRMS / Google Earth Engine",
        collection="FIRMS",
        image_id=None,
        band="T21",
        out_band="focos",
        unit="pixels/focos ativos",
        scale=1000,
        statistic="contagem",
        reducer_name="sum",
        vis={"min": 0, "max": 8, "palette": ["fff7bc", "fec44f", "fe9929", "ec7014", "cc4c02", "8c2d04"]},
        kind="fire_count",
        temporal=True,
        user_note="Representa focos/pixels ativos detectados por satélite, não área queimada.",
    ),
    "CO": Product(
        key="CO",
        label="Monóxido de Carbono",
        source="Sentinel-5P / Google Earth Engine",
        collection="COPERNICUS/S5P/OFFL/L3_CO",
        image_id=None,
        band="CO_column_number_density",
        out_band="CO_DU",
        unit="DU",
        scale=7000,
        statistic="média",
        reducer_name="mean",
        vis={"min": 0, "max": 120, "palette": ["1d4ed8", "38bdf8", "facc15", "f97316", "dc2626"]},
        kind="mean_collection",
        temporal=True,
        user_note="CO convertido de mol/m² para Dobson Unit multiplicando por 2241.15.",
    ),
    "Aerossóis": Product(
        key="Aerossóis",
        label="Aerossóis",
        source="Sentinel-5P / Google Earth Engine",
        collection="COPERNICUS/S5P/OFFL/L3_AER_AI",
        image_id=None,
        band="absorbing_aerosol_index",
        out_band="AER_AI",
        unit="índice",
        scale=7000,
        statistic="média",
        reducer_name="mean",
        vis={"min": -1, "max": 3, "palette": ["1d4ed8", "ffffff", "facc15", "f97316", "dc2626"]},
        kind="mean_collection",
        temporal=True,
        user_note="Índice de aerossóis absorventes; valores maiores indicam maior presença de aerossóis absorventes.",
    ),
    "Metano": Product(
        key="Metano",
        label="Metano",
        source="Sentinel-5P / Google Earth Engine",
        collection="COPERNICUS/S5P/OFFL/L3_CH4",
        image_id=None,
        band="CH4_column_volume_mixing_ratio_dry_air",
        out_band="CH4",
        unit="ppb",
        scale=7000,
        statistic="média",
        reducer_name="mean",
        vis={"min": 1750, "max": 1950, "palette": INFERNO_PALETTE},
        kind="mean_collection",
        temporal=True,
        user_note="CH₄ em ppb com paleta inferno para facilitar contraste visual.",
    ),

    "Temperatura": Product(
        key="Temperatura",
        label="Temperatura da Superfície",
        source="MODIS Terra LST / Google Earth Engine",
        collection="MODIS/061/MOD11A2",
        image_id=None,
        band="LST_Day_1km",
        out_band="LST_C",
        unit="°C",
        scale=1000,
        statistic="média",
        reducer_name="mean",
        vis={"min": 10, "max": 45, "palette": ["313695", "74add1", "ffffbf", "fdae61", "a50026"]},
        kind="lst_modis",
        temporal=True,
        user_note="Temperatura da superfície terrestre diurna MODIS: escala 0.02 K convertida para °C. Se não houver imagem no período, usa a imagem mais recente disponível antes da data final.",
        fallback_to_latest=True,
    ),
    "NDVI": Product(
        key="NDVI",
        label="NDVI Sentinel-2",
        source="Sentinel-2 SR Harmonized / Google Earth Engine",
        collection="COPERNICUS/S2_SR_HARMONIZED",
        image_id=None,
        band=["B8", "B4"],
        out_band="NDVI",
        unit="índice",
        scale=10,
        statistic="média",
        reducer_name="mean",
        vis={"min": -0.2, "max": 0.9, "palette": ["8c510a", "d8b365", "f6e8c3", "c7eae5", "5ab4ac", "01665e"]},
        kind="ndvi_sentinel2",
        temporal=True,
        user_note="NDVI calculado por Sentinel-2: (B8 - B4) / (B8 + B4), onde B8 é NIR e B4 é vermelho. Aplica filtro simples de nuvem pela propriedade CLOUDY_PIXEL_PERCENTAGE.",
        fallback_to_latest=True,
    ),
    "Precipitação CHIRPS": Product(
        key="Precipitação CHIRPS",
        label="Precipitação CHIRPS",
        source="UCSB CHG CHIRPS Daily / Google Earth Engine",
        collection="UCSB-CHG/CHIRPS/DAILY",
        image_id=None,
        band="precipitation",
        out_band="precipitation",
        unit="mm",
        scale=5566,
        statistic="soma",
        reducer_name="sum",
        vis={"min": 0, "max": 250, "palette": ["ffffff", "c7e9f1", "41b6c4", "225ea8", "08306b"]},
        kind="precip_sum",
        temporal=True,
        user_note="Soma da precipitação diária no período selecionado. Se o período selecionado ainda não tiver dados no Earth Engine, usa o dado diário mais recente disponível antes da data final.",
        fallback_to_latest=True,
    ),
    "Relevo": Product(
        key="Relevo",
        label="Relevo / Elevação",
        source="NASA/USGS/JPL-Caltech SRTM / Google Earth Engine",
        collection=None,
        image_id="USGS/SRTMGL1_003",
        band="elevation",
        out_band="elevation",
        unit="m",
        scale=30,
        statistic="média",
        reducer_name="mean",
        vis={"min": 0, "max": 2500, "palette": ["0b5d1e", "72b043", "f6e27f", "b77b3a", "ffffff"]},
        kind="static_image",
        temporal=False,
        user_note="Modelo digital de elevação SRTM, produto estático.",
    ),
    "Modificação Humana": Product(
        key="Modificação Humana",
        label="Modificação Humana Global",
        source="CSP gHM / Google Earth Engine",
        collection="CSP/HM/GlobalHumanModification",
        image_id=None,
        band="gHM",
        out_band="gHM",
        unit="índice 0–1",
        scale=1000,
        statistic="média",
        reducer_name="mean",
        vis={"min": 0, "max": 1, "palette": ["0b3d02", "7fbf3f", "fee08b", "f46d43", "7f0000"]},
        kind="static_collection",
        temporal=False,
        user_note="Índice cumulativo de modificação humana das áreas terrestres, variando de 0 a 1. Produto carregado como ImageCollection.",
    ),
    "Cobertura do Solo": Product(
        key="Cobertura do Solo",
        label="Cobertura do Solo Copernicus",
        source="Copernicus Global Land Service / Google Earth Engine",
        collection="COPERNICUS/Landcover/100m/Proba-V-C3/Global",
        image_id=None,
        band="discrete_classification",
        out_band="landcover",
        unit="classe",
        scale=100,
        statistic="classe predominante",
        reducer_name="mode",
        vis={"min": 0, "max": 200, "palette": LANDCOVER_PALETTE},
        kind="categorical_last",
        temporal=True,
        user_note="Classe discreta de cobertura do solo. O produto é anual e disponível no catálogo para 2015–2019. Fora desse intervalo, usa o ano mais recente disponível.",
        fallback_to_latest=True,
    ),
}


def safe_filename(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "arquivo"


def _select_bands(col: ee.ImageCollection, band: str | list[str]) -> ee.ImageCollection:
    if isinstance(band, list):
        return col.select(band)
    return col.select(band)


def _raw_collection(product_name: str, region=None) -> ee.ImageCollection:
    product = PRODUCTS[product_name]

    if product.kind == "static_image":
        return ee.ImageCollection([ee.Image(product.image_id).select(product.band)])

    if product.collection:
        col = ee.ImageCollection(product.collection)

        if product.kind == "ndvi_sentinel2":
            col = col.filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", 40))
            col = col.select(["B8", "B4"])
        else:
            col = _select_bands(col, product.band)

        if region is not None and product.temporal:
            col = col.filterBounds(region)

        return col

    return ee.ImageCollection([])


def collection(product_name: str, start: str, end: str, region) -> ee.ImageCollection:
    product = PRODUCTS[product_name]

    if product.kind in {"static_image", "static_collection"}:
        return _raw_collection(product_name, region)

    col = _raw_collection(product_name, region).filterDate(start, end)

    if not product.fallback_to_latest:
        return col

    latest_before_end = (
        _raw_collection(product_name, region)
        .filterDate("1900-01-01", end)
        .sort("system:time_start", False)
        .limit(1)
    )

    return ee.ImageCollection(ee.Algorithms.If(col.size().gt(0), col, latest_before_end))


def image_count(product_name: str, start: str, end: str, region) -> int:
    product = PRODUCTS[product_name]

    if product.kind == "static_image":
        return 1

    if product.kind == "static_collection":
        return int(_raw_collection(product_name, region).size().getInfo())

    n = int(_raw_collection(product_name, region).filterDate(start, end).size().getInfo())

    if n == 0 and product.fallback_to_latest:
        latest_n = int(
            _raw_collection(product_name, region)
            .filterDate("1900-01-01", end)
            .sort("system:time_start", False)
            .limit(1)
            .size()
            .getInfo()
        )
        return latest_n

    return n


def _static_image(product: Product) -> ee.Image:
    return ee.Image(product.image_id).select(product.band).rename(product.out_band)


def _static_collection_image(product: Product) -> ee.Image:
    return (
        ee.ImageCollection(product.collection)
        .select(product.band)
        .mosaic()
        .rename(product.out_band)
    )


def _ndvi_sentinel2_image(col: ee.ImageCollection, out_band: str) -> ee.Image:
    def add_ndvi(img):
        ndvi = img.normalizedDifference(["B8", "B4"]).rename(out_band)
        return ndvi.copyProperties(img, ["system:time_start"])

    return col.map(add_ndvi).mean().rename(out_band)


def period_image(product_name: str, start: str, end: str, region) -> ee.Image:
    product = PRODUCTS[product_name]

    if product.kind == "static_image":
        img = _static_image(product)

    elif product.kind == "static_collection":
        img = _static_collection_image(product)

    else:
        col = collection(product_name, start, end, region)

        if product.kind == "fire_count":
            img = col.count().rename(product.out_band)

        elif product.kind == "precip_sum":
            img = col.sum().rename(product.out_band)

        elif product.kind == "lst_modis":
            img = (
                col.mean()
                .multiply(0.02)
                .subtract(273.15)
                .rename(product.out_band)
            )

        elif product.kind == "ndvi_sentinel2":
            img = _ndvi_sentinel2_image(col, product.out_band)

        elif product.kind == "categorical_last":
            img = col.sort("system:time_start", False).first().rename(product.out_band)

        else:
            img = col.mean().rename(product.out_band)

            if product_name == "CO":
                img = img.multiply(2241.15).rename(product.out_band)

    return (
        img
        .clip(region)
        .set({
            "produto": product.key,
            "variavel": product.out_band,
            "unidade": product.unit,
            "estatistica": product.statistic,
            "escala_m": product.scale,
            "fonte": product.source,
            "colecao_gee": product.collection or product.image_id,
            "banda_gee": ",".join(product.band) if isinstance(product.band, list) else product.band,
            "data_inicio": start,
            "data_fim": end,
            "processado_em_utc": datetime.now(timezone.utc).isoformat(),
        })
    )


def reducer_for_product(product_name: str):
    product = PRODUCTS[product_name]
    if product.reducer_name == "sum":
        return ee.Reducer.sum()
    if product.reducer_name == "mode":
        return ee.Reducer.mode()
    return ee.Reducer.mean()


def reduce_value(product_name: str, image: ee.Image, region):
    product = PRODUCTS[product_name]
    stats = image.reduceRegion(
        reducer=reducer_for_product(product_name),
        geometry=region,
        scale=product.scale,
        maxPixels=1e13,
        bestEffort=True,
    ).getInfo()

    return stats.get(product.out_band)
