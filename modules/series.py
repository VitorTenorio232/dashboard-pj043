#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import date, timedelta
import ee
import pandas as pd
from modules.products import period_image, PRODUCTS
from modules.regions import get_region

def _dates_daily(start: date, end: date):
    current = start
    while current < end:
        nxt = current + timedelta(days=1)
        yield current, nxt
        current = nxt

def _dates_monthly(start: date, end: date):
    current = date(start.year, start.month, 1)
    while current < end:
        nxt = date(current.year + 1, 1, 1) if current.month == 12 else date(current.year, current.month + 1, 1)
        yield current, min(nxt, end)
        current = nxt

def make_series(product_name: str, start: date, end: date, region_name: str, freq: str, bounds=None) -> pd.DataFrame:
    region = get_region(region_name, bounds)
    product = PRODUCTS[product_name]
    intervals = list(_dates_daily(start, end)) if freq == 'Diária' else list(_dates_monthly(start, end))
    rows = []
    for d0, d1 in intervals:
        img = period_image(product_name, d0.isoformat(), d1.isoformat(), region)
        reducer = ee.Reducer.sum() if product_name == 'Queimadas' else ee.Reducer.mean()
        stats = img.reduceRegion(reducer=reducer, geometry=region, scale=product.scale, maxPixels=1e13, bestEffort=True).getInfo()
        rows.append({'data_inicio': d0.isoformat(), 'data_fim': d1.isoformat(), 'produto': product_name, 'valor': stats.get(product.out_band), 'unidade': product.unit})
    return pd.DataFrame(rows)
