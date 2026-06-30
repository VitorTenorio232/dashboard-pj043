#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import ee

def region_options() -> list[str]:
    return ['América do Sul','Brasil','Minas Gerais','Itajubá - raio 20 km','Retângulo personalizado']

def get_region(name: str, bounds: tuple[float, float, float, float] | None = None):
    if name == 'América do Sul':
        return ee.Geometry.Rectangle([-93, -60, -30, 15], proj='EPSG:4326', geodesic=False)
    if name == 'Brasil':
        fc = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017')
        return fc.filter(ee.Filter.eq('country_na', 'Brazil')).geometry()
    if name == 'Minas Gerais':
        fc = ee.FeatureCollection('FAO/GAUL_SIMPLIFIED_500m/2015/level1')
        return fc.filter(ee.Filter.eq('ADM0_NAME','Brazil')).filter(ee.Filter.stringContains('ADM1_NAME','Minas')).geometry()
    if name == 'Itajubá - raio 20 km':
        return ee.Geometry.Point([-45.452, -22.425]).buffer(20000).bounds()
    if name == 'Retângulo personalizado' and bounds:
        lon_min, lat_min, lon_max, lat_max = bounds
        return ee.Geometry.Rectangle([lon_min, lat_min, lon_max, lat_max], proj='EPSG:4326', geodesic=False)
    return ee.Geometry.Rectangle([-93, -60, -30, 15], proj='EPSG:4326', geodesic=False)

def map_center(name: str):
    centers = {'América do Sul':([-25,-60],3),'Brasil':([-15,-55],4),'Minas Gerais':([-18.5,-44.5],6),'Itajubá - raio 20 km':([-22.425,-45.452],10),'Retângulo personalizado':([-15,-55],4)}
    return centers.get(name, ([-15,-55],4))
