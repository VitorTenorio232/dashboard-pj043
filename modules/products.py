#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
import ee

@dataclass(frozen=True)
class Product:
    key: str
    label: str
    collection: str
    band: str
    out_band: str
    unit: str
    scale: int
    reducer: str
    vis: dict
    description: str

PRODUCTS = {
    'Queimadas': Product('Queimadas','Queimadas','FIRMS','T21','focos','pixels ativos',1000,'count',{'min':0,'max':8,'palette':['000000','ffeda0','feb24c','f03b20']},'Contagem de pixels ativos de fogo no período.'),
    'CO': Product('CO','Monóxido de Carbono','COPERNICUS/S5P/OFFL/L3_CO','CO_column_number_density','CO_DU','DU',20000,'mean',{'min':0,'max':120,'palette':['1d4ed8','38bdf8','facc15','f97316','dc2626']},'Coluna de CO Sentinel-5P convertida de mol/m² para DU.'),
    'Aerossóis': Product('Aerossóis','Aerossóis','COPERNICUS/S5P/OFFL/L3_AER_AI','absorbing_aerosol_index','AER_AI','índice',20000,'mean',{'min':-1,'max':3,'palette':['1d4ed8','ffffff','facc15','f97316','dc2626']},'Índice de aerossóis absorventes Sentinel-5P.'),
    'Metano': Product('Metano','Metano','COPERNICUS/S5P/OFFL/L3_CH4','CH4_column_volume_mixing_ratio_dry_air','CH4','ppb',20000,'mean',{'min':1750,'max':1950,'palette':['0f172a','2563eb','22c55e','fde047','ef4444']},'Razão de mistura de CH₄ Sentinel-5P.'),
}

def collection(product_name: str, start: str, end: str, region) -> ee.ImageCollection:
    p = PRODUCTS[product_name]
    return ee.ImageCollection(p.collection).filterDate(start, end).filterBounds(region).select(p.band)

def period_image(product_name: str, start: str, end: str, region) -> ee.Image:
    p = PRODUCTS[product_name]
    col = collection(product_name, start, end, region)
    if product_name == 'Queimadas':
        img = col.count().rename(p.out_band)
    else:
        img = col.mean().rename(p.out_band)
        if product_name == 'CO':
            img = img.multiply(2241.15).rename(p.out_band)
    return img.clip(region)

def image_count(product_name: str, start: str, end: str, region) -> int:
    return int(collection(product_name, start, end, region).size().getInfo())
