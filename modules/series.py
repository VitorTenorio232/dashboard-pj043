#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

import pandas as pd

from modules.products import image_count, period_image, PRODUCTS, reduce_value
from modules.regions import get_region, region_display_name


def _dates_daily(start: date, end: date):
    current = start
    while current < end:
        nxt = current + timedelta(days=1)
        yield current, nxt
        current = nxt


def _dates_monthly(start: date, end: date):
    current = date(start.year, start.month, 1)
    while current < end:
        if current.month == 12:
            nxt = date(current.year + 1, 1, 1)
        else:
            nxt = date(current.year, current.month + 1, 1)
        yield current, min(nxt, end)
        current = nxt


def make_series(
    product_name: str,
    start: date,
    end: date,
    region_name: str,
    freq: str,
    bounds=None,
    country_name: str | None = None,
    admin1_name: str | None = None,
    city_name: str | None = None,
) -> pd.DataFrame:
    region = get_region(
        region_name,
        bounds,
        country_name=country_name,
        admin1_name=admin1_name,
        city_name=city_name,
    )
    reg_label = region_display_name(region_name, country_name, admin1_name, city_name)
    product = PRODUCTS[product_name]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not product.temporal:
        intervals = [(start, end)]
    else:
        intervals = list(_dates_daily(start, end)) if freq == "Diária" else list(_dates_monthly(start, end))

    rows = []
    for d0, d1 in intervals:
        n_images = image_count(product_name, d0.isoformat(), d1.isoformat(), region)
        value = None
        if n_images > 0:
            img = period_image(product_name, d0.isoformat(), d1.isoformat(), region)
            value = reduce_value(product_name, img, region)
        rows.append({
            "data_inicio": d0.isoformat(),
            "data_fim": d1.isoformat(),
            "produto": product.key,
            "variavel": product.out_band,
            "valor": value,
            "unidade": product.unit,
            "regiao": reg_label,
            "estatistica": product.statistic,
            "escala_m": product.scale,
            "fonte": product.source,
            "colecao_gee": product.collection or product.image_id,
            "banda_gee": ",".join(product.band) if isinstance(product.band, list) else product.band,
            "imagens_no_periodo": n_images,
            "data_processamento_utc": now,
        })
    return pd.DataFrame(rows)
