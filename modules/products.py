#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Catálogo e processamento dos produtos do SIMQA.

Principais mudanças desta revisão:
- produtos agrupados por banco/plataforma;
- disponibilidade máxima consultada diretamente no Earth Engine;
- CHIRPS atualizado para a versão 3 Daily Reanalysis;
- ERA5-Land Hourly adicionado para precipitação recente;
- acumulado ERA5-Land soma a banda horária desagregada e converte metros para milímetros;
- produtos estáticos sem seleção temporal;
- contagem de focos revisada e descrita como detecções rasterizadas;
- data final da interface tratada como inclusiva.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import re
import unicodedata

import ee


SPECTRAL_PALETTE = [
    "000004", "1b0c41", "4a0c6b", "781c6d", "a52c60",
    "cf4446", "ed6925", "fb9b06", "f7d13d", "fcffa4",
]

ATMOS_PALETTE = ["000004", "2c115f", "721f81", "b73779", "f1605d", "feb078", "fcfdbf"]
FIRE_PALETTE = ["ffffcc", "ffeda0", "fed976", "feb24c", "fd8d3c", "f03b20", "bd0026", "800026"]

LANDCOVER_VALUES = [
    0, 20, 30, 40, 50, 60, 70, 80, 90, 100,
    111, 112, 113, 114, 115, 116, 121, 122, 123, 124, 125, 126, 200,
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
    group: str
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
    method_note: str
    limitations: str
    availability_start: str | None = None
    availability_end: str | None = None
    cadence: str = ""
    catalog_url: str = ""
    fallback_to_latest: bool = False
    default_days: int = 30
    confidence_min: float | None = None
    value_scale: float = 1.0
    value_offset: float = 0.0


GROUP_ORDER = [
    "FIRMS / MODIS",
    "FIRMS / VIIRS NOAA-20",
    "FIRMS / VIIRS S-NPP",
    "NOAA / GOES-16",
    "NOAA / GOES-19",
    "MODIS / NASA",
    "Sentinel-5P NRTI",
    "Sentinel-5P OFFL",
    "CHIRPS v3 / UCSB-CHC",
    "Copernicus / ERA5-Land",
    "Sentinel-2",
    "SRTM",
    "Copernicus Land",
    "CSP gHM",
]


PRODUCTS: dict[str, Product] = {
    "Focos FIRMS MODIS": Product(
        key="Focos FIRMS MODIS",
        label="Focos de calor — FIRMS MODIS",
        group="FIRMS / MODIS",
        source="NASA LANCE FIRMS / MODIS",
        collection="FIRMS",
        image_id=None,
        band="T21",
        out_band="deteccoes",
        unit="detecções rasterizadas",
        scale=1000,
        statistic="soma de detecções rasterizadas",
        reducer_name="sum",
        vis={"min": 0, "max": 8, "palette": FIRE_PALETTE},
        kind="fire_modis",
        temporal=True,
        user_note=(
            "Cada pixel representa uma detecção ativa rasterizada do produto FIRMS/MODIS. "
            "O resultado não corresponde necessariamente ao número de incêndios únicos."
        ),
        method_note=(
            "Para cada imagem diária, são mantidos pixels com confiança MODIS ≥ 30%. "
            "Cada detecção válida recebe valor 1 e os valores são somados no período."
        ),
        limitations=(
            "Produto quase em tempo real e não considerado de qualidade científica definitiva. "
            "Detecções repetidas do mesmo incêndio em dias diferentes são contabilizadas novamente; "
            "o formato raster também pode consolidar pontos sobrepostos."
        ),
        availability_start="2000-11-01",
        cadence="Diária",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/FIRMS",
        fallback_to_latest=False,
        default_days=7,
        confidence_min=30,
    ),
    "Focos VIIRS NOAA-20": Product(
        key="Focos VIIRS NOAA-20",
        label="Focos de calor — VIIRS NOAA-20",
        group="FIRMS / VIIRS NOAA-20",
        source="NASA LANCE FIRMS / VIIRS NOAA-20",
        collection="NASA/LANCE/NOAA20_VIIRS/C2",
        image_id=None,
        band="Bright_ti4",
        out_band="deteccoes",
        unit="detecções rasterizadas",
        scale=375,
        statistic="soma de detecções rasterizadas",
        reducer_name="sum",
        vis={"min": 0, "max": 8, "palette": FIRE_PALETTE},
        kind="fire_viirs",
        temporal=True,
        user_note=(
            "Detecções ativas VIIRS a 375 m. O mapa representa ocorrências rasterizadas no tempo, "
            "não incêndios únicos."
        ),
        method_note=(
            "São mantidos apenas pixels de confiança nominal ou alta (confidence ≥ 1). "
            "Cada detecção válida recebe valor 1 e é somada no período."
        ),
        limitations=(
            "Produto NRT, sujeito a falsos positivos e revisões. A mesma ocorrência pode ser detectada "
            "em passagens sucessivas."
        ),
        availability_start="2023-10-08",
        cadence="Diária",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/NASA_LANCE_NOAA20_VIIRS_C2",
        fallback_to_latest=False,
        default_days=7,
        confidence_min=1,
    ),
    "Focos VIIRS S-NPP": Product(
        key="Focos VIIRS S-NPP",
        label="Focos de calor — VIIRS S-NPP",
        group="FIRMS / VIIRS S-NPP",
        source="NASA LANCE FIRMS / VIIRS Suomi NPP",
        collection="NASA/LANCE/SNPP_VIIRS/C2",
        image_id=None,
        band="Bright_ti4",
        out_band="deteccoes",
        unit="detecções rasterizadas",
        scale=375,
        statistic="soma de detecções rasterizadas",
        reducer_name="sum",
        vis={"min": 0, "max": 8, "palette": FIRE_PALETTE},
        kind="fire_viirs",
        temporal=True,
        user_note=(
            "Detecções ativas VIIRS/S-NPP a 375 m. O resultado representa observações rasterizadas, "
            "não eventos de incêndio individualizados."
        ),
        method_note=(
            "São mantidos pixels de confiança nominal ou alta (confidence ≥ 1), convertidos para 1 "
            "e somados no período."
        ),
        limitations=(
            "Produto NRT e não de qualidade científica definitiva. A mesma frente de fogo pode gerar "
            "várias detecções ao longo do período."
        ),
        availability_start="2023-09-03",
        cadence="Diária",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/NASA_LANCE_SNPP_VIIRS_C2",
        fallback_to_latest=False,
        default_days=7,
        confidence_min=1,
    ),
    "Focos GOES-16": Product(
        key="Focos GOES-16",
        label="Focos de calor — GOES-16 ABI FDCF",
        group="NOAA / GOES-16",
        source="NOAA GOES-16 ABI L2 FDCF",
        collection="NOAA/GOES/16/FDCF",
        image_id=None,
        band="Mask",
        out_band="deteccoes",
        unit="detecções por varredura",
        scale=2000,
        statistic="soma de detecções conservadoras",
        reducer_name="sum",
        vis={"min": 0, "max": 30, "palette": FIRE_PALETTE},
        kind="fire_goes",
        temporal=True,
        user_note=(
            "Produto geoestacionário com alta frequência temporal. O valor acumulado representa "
            "quantas varreduras identificaram fogo em cada pixel, não o número de incêndios únicos."
        ),
        method_note=(
            "Usa somente as classes mais conservadoras do Mask: 10, 11, 30 e 31 "
            "(fogo processado ou saturado, com e sem filtro temporal)."
        ),
        limitations=(
            "Uma mesma ocorrência pode ser contada muitas vezes por causa da cadência de 10 minutos. "
            "O GOES-16 foi substituído operacionalmente pelo GOES-19 em 7 de abril de 2025; "
            "esta coleção é histórica após essa data."
        ),
        availability_start="2017-05-24",
        availability_end="2025-04-07",
        cadence="10 minutos",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/NOAA_GOES_16_FDCF",
        default_days=1,
    ),
    "Focos GOES-19": Product(
        key="Focos GOES-19",
        label="Focos de calor — GOES-19 ABI FDCF",
        group="NOAA / GOES-19",
        source="NOAA GOES-19 ABI L2 FDCF",
        collection="NOAA/GOES/19/FDCF",
        image_id=None,
        band="Mask",
        out_band="deteccoes",
        unit="detecções por varredura",
        scale=2000,
        statistic="soma de detecções conservadoras",
        reducer_name="sum",
        vis={"min": 0, "max": 30, "palette": FIRE_PALETTE},
        kind="fire_goes",
        temporal=True,
        user_note=(
            "Continuação operacional do monitoramento geoestacionário no setor GOES East. "
            "O acumulado representa varreduras com detecção em cada pixel, não incêndios únicos."
        ),
        method_note=(
            "Usa somente as classes conservadoras do Mask: 10, 11, 30 e 31 "
            "e soma as detecções das varreduras de 10 minutos."
        ),
        limitations=(
            "Uma ocorrência persistente pode ser contabilizada em muitas varreduras; mesmo as classes "
            "conservadoras podem conter alarmes falsos. Dados anteriores ao início operacional podem ser provisórios."
        ),
        availability_start="2025-04-07",
        cadence="10 minutos",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/NOAA_GOES_19_FDCF",
        default_days=1,
    ),
    "AOD MAIAC": Product(
        key="AOD MAIAC",
        label="AOD 0,55 µm — MODIS MAIAC MCD19A2.061",
        group="MODIS / NASA",
        source="MODIS Terra & Aqua MAIAC / NASA LP DAAC",
        collection="MODIS/061/MCD19A2_GRANULES",
        image_id=None,
        band="Optical_Depth_055",
        out_band="AOD_055",
        unit="AOD adimensional",
        scale=1000,
        statistic="média temporal",
        reducer_name="mean",
        vis={"min": 0, "max": 1.5, "palette": ATMOS_PALETTE},
        kind="maiac_aod",
        temporal=True,
        user_note="Profundidade óptica de aerossóis sobre o continente em 0,55 µm, resolução nominal de 1 km.",
        method_note=(
            "Aplica fator de escala 0,001 à banda Optical_Depth_055 e mantém apenas pixels com "
            "QA de AOD igual a 0 (melhor qualidade; bits 8–11 do AOD_QA). Depois calcula a média no período."
        ),
        limitations=(
            "AOD pode ficar ausente sob nuvens, neve ou condições inadequadas de recuperação. "
            "O produto representa carga óptica integrada na coluna, não concentração em superfície."
        ),
        availability_start="2000-02-24",
        cadence="Diária",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD19A2_GRANULES",
        fallback_to_latest=False,
        default_days=7,
    ),
    "Temperatura": Product(
        key="Temperatura",
        label="Temperatura da superfície — MODIS Terra",
        group="MODIS / NASA",
        source="MODIS Terra LST / NASA LP DAAC",
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
        user_note="Temperatura radiométrica diurna da superfície; não equivale à temperatura do ar a 2 m.",
        method_note="Calcula a média temporal, aplica escala 0,02 K e converte de Kelvin para °C.",
        limitations="Composto de 8 dias; nuvens e qualidade de recuperação podem gerar lacunas ou viés.",
        availability_start="2000-02-18",
        cadence="8 dias",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD11A2",
        fallback_to_latest=False,
    ),
    "NDVI": Product(
        key="NDVI",
        label="NDVI — Sentinel-2 SR Harmonized",
        group="Sentinel-2",
        source="Sentinel-2 Surface Reflectance Harmonized / ESA Copernicus",
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
        user_note="Índice de vegetação calculado com B8 (infravermelho próximo) e B4 (vermelho).",
        method_note="NDVI = (B8 − B4) / (B8 + B4); filtra cenas com CLOUDY_PIXEL_PERCENTAGE ≤ 40 e calcula a média.",
        limitations="O filtro de nuvem por metadado é simples e pode manter nuvens residuais ou sombras.",
        availability_start="2017-03-28",
        cadence="Aproximadamente 5 dias",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED",
        fallback_to_latest=False,
    ),
    "Precipitação CHIRPS": Product(
        key="Precipitação CHIRPS",
        label="Precipitação acumulada — CHIRPS v3 Daily Reanalysis",
        group="CHIRPS v3 / UCSB-CHC",
        source="UCSB Climate Hazards Center — CHIRPS v3",
        collection="UCSB-CHC/CHIRPS/V3/DAILY_RNL",
        image_id=None,
        band="precipitation",
        out_band="precipitation",
        unit="mm",
        scale=5566,
        statistic="soma temporal por pixel; média espacial nas séries",
        reducer_name="mean",
        vis={"min": 0, "max": 250, "palette": ["ffffff", "c7e9f1", "41b6c4", "225ea8", "08306b"]},
        kind="precip_sum",
        temporal=True,
        user_note=(
            "Precipitação diária CHIRPS v3 em grade de 0,05°, combinando estimativas por satélite "
            "e observações de estações. O SIMQA usa a versão Daily Reanalysis (ERA5-based) para o histórico."
        ),
        method_note=(
            "Soma os campos diários de precipitação (mm/dia) em cada pixel. Nas séries regionais, "
            "calcula a média espacial do acumulado, preservando a unidade em milímetros."
        ),
        limitations=(
            "Produto terrestre entre aproximadamente 60°S e 60°N. A ingestão no Earth Engine pode apresentar "
            "defasagem em relação à data corrente; o SIMQA consulta automaticamente a última cena disponível."
        ),
        availability_start="1981-01-01",
        cadence="Diária",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHC_CHIRPS_V3_DAILY_RNL",
        fallback_to_latest=False,
        default_days=30,
    ),
    "Precipitação ERA5-Land": Product(
        key="Precipitação ERA5-Land",
        label="Precipitação acumulada — ERA5-Land Hourly",
        group="Copernicus / ERA5-Land",
        source="Copernicus Climate Change Service / ECMWF — ERA5-Land",
        collection="ECMWF/ERA5_LAND/HOURLY",
        image_id=None,
        band="total_precipitation_hourly",
        out_band="precipitation",
        unit="mm",
        scale=11132,
        statistic="acumulado temporal por pixel; média espacial nas séries",
        reducer_name="mean",
        vis={
            "min": 0,
            "max": 100,
            "palette": ["ffffff", "c7e9f1", "41b6c4", "225ea8", "08306b", "4d004b"],
        },
        kind="precip_era5land_sum",
        temporal=True,
        user_note=(
            "Precipitação horária da reanálise ERA5-Land. É indicada no SIMQA para acompanhamento "
            "mais recente quando produtos observacionais/satélites apresentam maior defasagem no catálogo."
        ),
        method_note=(
            "O Earth Engine fornece a banda total_precipitation_hourly em metros de água para cada hora, "
            "já desagregada a partir dos acumulados do ERA5-Land. O SIMQA multiplica cada cena por 1000 "
            "para converter m em mm e soma todas as horas do período. Nas séries regionais, calcula a "
            "média espacial do acumulado, mantendo a unidade em milímetros."
        ),
        limitations=(
            "ERA5-Land é uma reanálise, isto é, combina modelagem e observações e não corresponde a uma "
            "medição direta de chuva por pluviômetro ou satélite. A resolução nominal no Earth Engine é "
            "aproximadamente 11 km e a ingestão pode apresentar alguns dias de latência. O SIMQA consulta "
            "automaticamente a última cena disponível."
        ),
        availability_start="1950-01-01",
        cadence="Horária",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY",
        fallback_to_latest=False,
        default_days=7,
    ),
    "Relevo": Product(
        key="Relevo",
        label="Relevo / Elevação — SRTM",
        group="SRTM",
        source="NASA/USGS/JPL-Caltech SRTM",
        collection=None,
        image_id="USGS/SRTMGL1_003",
        band="elevation",
        out_band="elevation",
        unit="m",
        scale=30,
        statistic="média espacial",
        reducer_name="mean",
        vis={"min": 0, "max": 2500, "palette": ["0b5d1e", "72b043", "f6e27f", "b77b3a", "ffffff"]},
        kind="static_image",
        temporal=False,
        user_note="Modelo digital de elevação estático; por isso a interface não solicita datas.",
        method_note="Seleciona a banda elevation e recorta a região escolhida.",
        limitations="Não representa mudanças recentes do terreno e possui limitações em áreas íngremes ou com vazios.",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/USGS_SRTMGL1_003",
    ),
    "Modificação Humana": Product(
        key="Modificação Humana",
        label="Modificação Humana Global — gHM",
        group="CSP gHM",
        source="CSP Global Human Modification",
        collection="CSP/HM/GlobalHumanModification",
        image_id=None,
        band="gHM",
        out_band="gHM",
        unit="índice 0–1",
        scale=1000,
        statistic="média espacial",
        reducer_name="mean",
        vis={"min": 0, "max": 1, "palette": ["0b3d02", "7fbf3f", "fee08b", "f46d43", "7f0000"]},
        kind="static_collection",
        temporal=False,
        user_note="Índice estático de modificação humana, baseado principalmente em estressores circa 2016.",
        method_note="Mosaica a coleção gHM e recorta a região selecionada.",
        limitations="Não deve ser interpretado como monitoramento anual ou em tempo real.",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/CSP_HM_GlobalHumanModification",
    ),
    "Cobertura do Solo": Product(
        key="Cobertura do Solo",
        label="Cobertura do solo — Copernicus CGLS 100 m",
        group="Copernicus Land",
        source="Copernicus Global Land Service",
        collection="COPERNICUS/Landcover/100m/Proba-V-C3/Global",
        image_id=None,
        band="discrete_classification",
        out_band="landcover",
        unit="classe",
        scale=100,
        statistic="classe mais recente no período",
        reducer_name="mode",
        vis={"min": 0, "max": 200, "palette": LANDCOVER_PALETTE},
        kind="categorical_last",
        temporal=True,
        user_note="Produto anual; a seleção temporal é limitada ao período 2015–2019.",
        method_note=(
            "Seleciona a imagem anual mais recente dentro do período e usa a banda de classe discreta. "
            "Na visualização, as classes são remapeadas temporariamente para aplicar exatamente as cores oficiais; "
            "os valores analíticos originais são preservados nos resultados e GeoTIFFs."
        ),
        limitations="A coleção Proba-V C3 termina em 2019; não representa mudanças posteriores.",
        availability_start="2015-01-01",
        availability_end="2019-12-31",
        cadence="Anual",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_Landcover_100m_Proba-V-C3_Global",
        fallback_to_latest=False,
        default_days=365,
    ),
    "AER AI OFFL": Product(
        key="AER AI OFFL",
        label="Índice de aerossóis absorventes — Sentinel-5P OFFL",
        group="Sentinel-5P OFFL",
        source="Sentinel-5P TROPOMI OFFL / ESA Copernicus",
        collection="COPERNICUS/S5P/OFFL/L3_AER_AI",
        image_id=None,
        band="absorbing_aerosol_index",
        out_band="AER_AI",
        unit="índice",
        scale=1113,
        statistic="média",
        reducer_name="mean",
        vis={"min": -1, "max": 3, "palette": ATMOS_PALETTE},
        kind="mean_collection",
        temporal=True,
        user_note="Índice UV de aerossóis absorventes; valores positivos destacam fumaça, poeira e cinzas.",
        method_note="Calcula a média das imagens OFFL no período.",
        limitations="É um índice qualitativo de absorção e não uma concentração de aerossol em superfície.",
        availability_start="2018-07-04",
        cadence="Revisita de 2 dias",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_AER_AI",
        fallback_to_latest=False,
    ),
    "CO OFFL": Product(
        key="CO OFFL",
        label="Monóxido de carbono — Sentinel-5P OFFL",
        group="Sentinel-5P OFFL",
        source="Sentinel-5P TROPOMI OFFL / ESA Copernicus",
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
        user_note="Coluna vertical integrada de CO convertida de mol/m² para Dobson Unit.",
        method_note="Calcula a média temporal e multiplica por 2241,15 para converter mol/m² em DU.",
        limitations="A coluna total não equivale à concentração respirada ao nível do solo.",
        availability_start="2018-06-28",
        cadence="Revisita de 2 dias",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_CO",
        fallback_to_latest=False,
        value_scale=2241.15,
    ),
    "Metano OFFL": Product(
        key="Metano OFFL",
        label="Metano — Sentinel-5P OFFL",
        group="Sentinel-5P OFFL",
        source="Sentinel-5P TROPOMI OFFL / ESA Copernicus",
        collection="COPERNICUS/S5P/OFFL/L3_CH4",
        image_id=None,
        band="CH4_column_volume_mixing_ratio_dry_air",
        out_band="CH4",
        unit="ppb",
        scale=7000,
        statistic="média",
        reducer_name="mean",
        vis={"min": 1750, "max": 1950, "palette": SPECTRAL_PALETTE},
        kind="mean_collection",
        temporal=True,
        user_note="Razão de mistura de CH₄ na coluna de ar seco; produto disponível somente em versão OFFL.",
        method_note="Calcula a média das imagens no período.",
        limitations="Pode apresentar faixas e lacunas; não corresponde diretamente à concentração em superfície.",
        availability_start="2019-02-08",
        cadence="Revisita de 2 dias",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_CH4",
        fallback_to_latest=False,
    ),
    "AER AI NRTI": Product(
        key="AER AI NRTI",
        label="Índice UV de aerossóis — Sentinel-5P NRTI",
        group="Sentinel-5P NRTI",
        source="Sentinel-5P TROPOMI NRTI / ESA Copernicus",
        collection="COPERNICUS/S5P/NRTI/L3_AER_AI",
        image_id=None,
        band="absorbing_aerosol_index",
        out_band="AER_AI",
        unit="índice",
        scale=1113,
        statistic="média",
        reducer_name="mean",
        vis={"min": -1, "max": 2, "palette": ATMOS_PALETTE},
        kind="mean_collection",
        temporal=True,
        user_note="Produto quase em tempo real para acompanhamento de plumas absorventes, como fumaça e poeira.",
        method_note="Calcula a média do absorbing_aerosol_index no período.",
        limitations="O NRTI aparece mais rapidamente, mas cobre áreas menores por ativo e pode ser revisto posteriormente.",
        availability_start="2018-07-10",
        cadence="Revisita de 2 dias",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_AER_AI",
        fallback_to_latest=False,
        default_days=3,
    ),
    "Nuvens NRTI": Product(
        key="Nuvens NRTI",
        label="Fração de nuvens — Sentinel-5P NRTI",
        group="Sentinel-5P NRTI",
        source="Sentinel-5P TROPOMI NRTI CLOUD / ESA Copernicus",
        collection="COPERNICUS/S5P/NRTI/L3_CLOUD",
        image_id=None,
        band="cloud_fraction",
        out_band="cloud_fraction",
        unit="fração 0–1",
        scale=1113,
        statistic="média",
        reducer_name="mean",
        vis={"min": 0, "max": 1, "palette": ["0b132b", "1c7293", "9bd1e5", "ffffff"]},
        kind="mean_collection",
        temporal=True,
        user_note="Fração radiométrica efetiva de nuvens recuperada pelos algoritmos OCRA/ROCINN.",
        method_note="Calcula a média da banda cloud_fraction no período.",
        limitations="Não é uma medida direta de cobertura observada em superfície; depende do algoritmo e da geometria da observação.",
        availability_start="2018-07-05",
        cadence="Revisita de 2 dias",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_CLOUD",
        fallback_to_latest=False,
        default_days=3,
    ),
    "CO NRTI": Product(
        key="CO NRTI",
        label="Monóxido de carbono — Sentinel-5P NRTI",
        group="Sentinel-5P NRTI",
        source="Sentinel-5P TROPOMI NRTI / ESA Copernicus",
        collection="COPERNICUS/S5P/NRTI/L3_CO",
        image_id=None,
        band="CO_column_number_density",
        out_band="CO_column_number_density",
        unit="mol/m²",
        scale=1113,
        statistic="média",
        reducer_name="mean",
        vis={"min": 0, "max": 0.05, "palette": ATMOS_PALETTE},
        kind="mean_collection",
        temporal=True,
        user_note="Coluna vertical integrada de CO em versão quase em tempo real.",
        method_note="Calcula a média da banda CO_column_number_density no período.",
        limitations="Coluna total, não concentração ao nível do solo; valores negativos pequenos podem ocorrer por ruído.",
        availability_start="2018-11-22",
        cadence="Revisita de 2 dias",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_CO",
        fallback_to_latest=False,
        default_days=3,
    ),
    "HCHO NRTI": Product(
        key="HCHO NRTI",
        label="Formaldeído — Sentinel-5P NRTI",
        group="Sentinel-5P NRTI",
        source="Sentinel-5P TROPOMI NRTI / ESA Copernicus",
        collection="COPERNICUS/S5P/NRTI/L3_HCHO",
        image_id=None,
        band="tropospheric_HCHO_column_number_density",
        out_band="HCHO",
        unit="mol/m²",
        scale=1113,
        statistic="média",
        reducer_name="mean",
        vis={"min": 0, "max": 0.0003, "palette": ATMOS_PALETTE},
        kind="mean_collection",
        temporal=True,
        user_note="Coluna troposférica de formaldeído, útil como indicador de emissões de compostos orgânicos voláteis.",
        method_note="Calcula a média da coluna troposférica de HCHO no período.",
        limitations="Valores negativos pequenos podem ocorrer por ruído; não é concentração em superfície.",
        availability_start="2018-10-02",
        cadence="Revisita de 2 dias",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_HCHO",
        fallback_to_latest=False,
        default_days=3,
    ),
    "NO2 NRTI": Product(
        key="NO2 NRTI",
        label="Dióxido de nitrogênio troposférico — Sentinel-5P NRTI",
        group="Sentinel-5P NRTI",
        source="Sentinel-5P TROPOMI NRTI / ESA Copernicus",
        collection="COPERNICUS/S5P/NRTI/L3_NO2",
        image_id=None,
        band="tropospheric_NO2_column_number_density",
        out_band="NO2_tropospheric",
        unit="mol/m²",
        scale=1113,
        statistic="média",
        reducer_name="mean",
        vis={"min": 0, "max": 0.0002, "palette": ATMOS_PALETTE},
        kind="mean_collection",
        temporal=True,
        user_note="Coluna vertical troposférica de NO₂, relacionada a combustão, queimadas, raios e processos do solo.",
        method_note="Calcula a média da banda tropospheric_NO2_column_number_density no período.",
        limitations="Não equivale à concentração de superfície; valores negativos pequenos podem ocorrer por ruído.",
        availability_start="2018-07-10",
        cadence="Revisita de 2 dias",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_NO2",
        fallback_to_latest=False,
        default_days=3,
    ),
    "O3 NRTI": Product(
        key="O3 NRTI",
        label="Ozônio total — Sentinel-5P NRTI",
        group="Sentinel-5P NRTI",
        source="Sentinel-5P TROPOMI NRTI / ESA Copernicus",
        collection="COPERNICUS/S5P/NRTI/L3_O3",
        image_id=None,
        band="O3_column_number_density",
        out_band="O3",
        unit="mol/m²",
        scale=1113,
        statistic="média",
        reducer_name="mean",
        vis={"min": 0.12, "max": 0.15, "palette": ATMOS_PALETTE},
        kind="mean_collection",
        temporal=True,
        user_note="Coluna total de ozônio entre a superfície e o topo da atmosfera.",
        method_note="Calcula a média da banda O3_column_number_density no período.",
        limitations="É ozônio total, majoritariamente estratosférico; não representa diretamente ozônio troposférico de superfície.",
        availability_start="2018-07-10",
        cadence="Revisita de 2 dias",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_O3",
        fallback_to_latest=False,
        default_days=3,
    ),
    "SO2 NRTI": Product(
        key="SO2 NRTI",
        label="Dióxido de enxofre — Sentinel-5P NRTI",
        group="Sentinel-5P NRTI",
        source="Sentinel-5P TROPOMI NRTI / ESA Copernicus",
        collection="COPERNICUS/S5P/NRTI/L3_SO2",
        image_id=None,
        band="SO2_column_number_density",
        out_band="SO2",
        unit="mol/m²",
        scale=1113,
        statistic="média",
        reducer_name="mean",
        vis={"min": 0, "max": 0.0005, "palette": ATMOS_PALETTE},
        kind="mean_collection",
        temporal=True,
        user_note="Coluna atmosférica de SO₂, associada a fontes industriais, combustão e vulcanismo.",
        method_note="Calcula a média da banda SO2_column_number_density no período.",
        limitations="Valores negativos pequenos podem ocorrer por ruído; não é concentração em superfície.",
        availability_start="2018-07-10",
        cadence="Revisita de 2 dias",
        catalog_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_SO2",
        fallback_to_latest=False,
        default_days=3,
    ),
}


def safe_filename(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "arquivo"


def product_groups() -> list[str]:
    present = {product.group for product in PRODUCTS.values()}
    ordered = [group for group in GROUP_ORDER if group in present]
    ordered.extend(sorted(present.difference(ordered)))
    return ordered


def products_in_group(group: str) -> list[str]:
    return [key for key, product in PRODUCTS.items() if product.group == group]


def product_date_bounds(product: Product) -> tuple[date | None, date | None]:
    """Limites declarados no catálogo interno, usados como fallback da interface."""
    if not product.temporal:
        return None, None
    start = date.fromisoformat(product.availability_start) if product.availability_start else date(1970, 1, 1)
    end = date.fromisoformat(product.availability_end) if product.availability_end else date.today()
    return start, min(end, date.today())


def latest_available_timestamp(product_name: str) -> datetime | None:
    """Consulta a cena mais recente existente na coleção do Earth Engine.

    A consulta é deliberadamente feita na coleção completa, sem filtro espacial, para que
    a interface não presuma que um produto temporal esteja atualizado até o dia corrente.
    O cache é aplicado na camada de UI.
    """
    product = PRODUCTS[product_name]
    if not product.temporal or not product.collection:
        return None

    value = ee.ImageCollection(product.collection).aggregate_max("system:time_start").getInfo()
    if value is None:
        return None

    try:
        milliseconds = float(value)
    except (TypeError, ValueError):
        return None

    return datetime.fromtimestamp(milliseconds / 1000.0, tz=timezone.utc)


def _exclusive_end(end_inclusive: str) -> str:
    return (date.fromisoformat(end_inclusive) + timedelta(days=1)).isoformat()


def _raw_collection(product_name: str, region=None) -> ee.ImageCollection:
    product = PRODUCTS[product_name]

    if product.kind == "static_image":
        return ee.ImageCollection([ee.Image(product.image_id)])

    if not product.collection:
        return ee.ImageCollection([])

    col = ee.ImageCollection(product.collection)
    if region is not None and product.temporal:
        col = col.filterBounds(region)
    return col


def collection(product_name: str, start: str, end: str, region) -> ee.ImageCollection:
    """Retorna a coleção considerando que ``end`` é uma data inclusiva."""
    product = PRODUCTS[product_name]

    if product.kind in {"static_image", "static_collection"}:
        return _raw_collection(product_name, region)

    raw = _raw_collection(product_name, region)
    end_exclusive = _exclusive_end(end)
    col = raw.filterDate(start, end_exclusive)

    if not product.fallback_to_latest:
        return col

    earliest = product.availability_start or "1900-01-01"
    latest_before_end = raw.filterDate(earliest, end_exclusive).sort("system:time_start", False).limit(1)
    return ee.ImageCollection(ee.Algorithms.If(col.size().gt(0), col, latest_before_end))


def image_count(product_name: str, start: str, end: str, region) -> int:
    product = PRODUCTS[product_name]

    if product.kind == "static_image":
        return 1
    if product.kind == "static_collection":
        return int(_raw_collection(product_name, region).size().getInfo())

    raw = _raw_collection(product_name, region)
    end_exclusive = _exclusive_end(end)
    n = int(raw.filterDate(start, end_exclusive).size().getInfo())

    if n == 0 and product.fallback_to_latest:
        earliest = product.availability_start or "1900-01-01"
        return int(
            raw.filterDate(earliest, end_exclusive)
            .sort("system:time_start", False)
            .limit(1)
            .size()
            .getInfo()
        )
    return n


def _fire_detection_image(img: ee.Image, product: Product) -> ee.Image:
    if product.kind == "fire_modis":
        base = img.select("T21")
        valid = base.gt(0).And(img.select("confidence").gte(product.confidence_min or 30))
        return base.multiply(0).add(1).updateMask(valid).rename(product.out_band)

    if product.kind == "fire_viirs":
        base = img.select("Bright_ti4")
        valid = base.gt(0).And(img.select("confidence").gte(product.confidence_min or 1))
        return base.multiply(0).add(1).updateMask(valid).rename(product.out_band)

    if product.kind == "fire_goes":
        mask_band = img.select("Mask")
        conservative = mask_band.remap([10, 11, 30, 31], [1, 1, 1, 1], 0).eq(1)
        return mask_band.multiply(0).add(1).updateMask(conservative).rename(product.out_band)

    raise ValueError(f"Tipo de fogo desconhecido: {product.kind}")


def _maiac_aod_image(img: ee.Image, product: Product) -> ee.Image:
    raw = img.select("Optical_Depth_055")
    qa = img.select("AOD_QA")
    qa_aod = qa.rightShift(8).bitwiseAnd(15)
    best_quality = qa_aod.eq(0)
    valid_value = raw.gte(0)
    return raw.multiply(0.001).updateMask(best_quality.And(valid_value)).rename(product.out_band)


def _era5land_hourly_accumulation(img: ee.Image, product: Product) -> ee.Image:
    """Converte a precipitação horária ERA5-Land de metros para milímetros."""
    return img.select(product.band).multiply(1000.0).rename(product.out_band)


def _static_image(product: Product) -> ee.Image:
    return ee.Image(product.image_id).select(product.band).rename(product.out_band)


def _static_collection_image(product: Product) -> ee.Image:
    return ee.ImageCollection(product.collection).select(product.band).mosaic().rename(product.out_band)


def _ndvi_sentinel2_image(col: ee.ImageCollection, out_band: str) -> ee.Image:
    def add_ndvi(img):
        ndvi = img.normalizedDifference(["B8", "B4"]).rename(out_band)
        return ndvi.copyProperties(img, ["system:time_start"])

    return col.filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", 40)).map(add_ndvi).mean().rename(out_band)


def period_image(product_name: str, start: str, end: str, region) -> ee.Image:
    product = PRODUCTS[product_name]

    if product.kind == "static_image":
        img = _static_image(product)

    elif product.kind == "static_collection":
        img = _static_collection_image(product)

    else:
        col = collection(product_name, start, end, region)

        if product.kind in {"fire_modis", "fire_viirs", "fire_goes"}:
            img = col.map(lambda source: _fire_detection_image(source, product)).sum().rename(product.out_band)

        elif product.kind == "maiac_aod":
            img = col.map(lambda source: _maiac_aod_image(source, product)).mean().rename(product.out_band)

        elif product.kind == "precip_sum":
            img = col.select(product.band).sum().rename(product.out_band)

        elif product.kind == "precip_era5land_sum":
            img = col.map(lambda source: _era5land_hourly_accumulation(source, product)).sum().rename(product.out_band)

        elif product.kind == "lst_modis":
            img = col.select(product.band).mean().multiply(0.02).subtract(273.15).rename(product.out_band)

        elif product.kind == "ndvi_sentinel2":
            img = _ndvi_sentinel2_image(col, product.out_band)

        elif product.kind == "categorical_last":
            img = ee.Image(col.sort("system:time_start", False).first()).select(product.band).rename(product.out_band)

        else:
            img = col.select(product.band).mean().rename(product.out_band)
            if product.value_scale != 1.0 or product.value_offset != 0.0:
                img = img.multiply(product.value_scale).add(product.value_offset).rename(product.out_band)

    metadata_start = start if product.temporal else "não se aplica"
    metadata_end = end if product.temporal else "não se aplica"

    return (
        img.clip(region)
        .set({
            "produto": product.key,
            "variavel": product.out_band,
            "unidade": product.unit,
            "estatistica": product.statistic,
            "escala_m": product.scale,
            "fonte": product.source,
            "colecao_gee": product.collection or product.image_id,
            "banda_gee": ",".join(product.band) if isinstance(product.band, list) else product.band,
            "data_inicio": metadata_start,
            "data_fim_inclusiva": metadata_end,
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
