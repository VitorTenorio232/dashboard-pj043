#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extração de séries temporais para o SIMQA."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd

from modules.products import PRODUCTS, image_count, period_image, reduce_value
from modules.regions import get_region, region_display_name


def _dates_daily(start: date, end_inclusive: date):
    current = start
    while current <= end_inclusive:
        yield current, current
        current += timedelta(days=1)


def _dates_monthly(start: date, end_inclusive: date):
    current = date(start.year, start.month, 1)
    while current <= end_inclusive:
        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)
        interval_start = max(start, current)
        interval_end = min(end_inclusive, next_month - timedelta(days=1))
        yield interval_start, interval_end
        current = next_month


def make_series(
    product_name: str,
    start: date | None,
    end: date | None,
    region_name: str,
    freq: str,
    bounds=None,
    country_name: str | None = None,
    admin1_name: str | None = None,
    city_name: str | None = None,
) -> pd.DataFrame:
    product = PRODUCTS[product_name]
    region = get_region(
        region_name,
        bounds,
        country_name=country_name,
        admin1_name=admin1_name,
        city_name=city_name,
    )
    region_label = region_display_name(region_name, country_name, admin1_name, city_name)
    processed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if product.temporal:
        if start is None or end is None:
            raise ValueError("Datas obrigatórias para produto temporal.")
        intervals = list(_dates_daily(start, end)) if freq == "Diária" else list(_dates_monthly(start, end))
    else:
        # Produto estático: uma única observação, sem datas artificiais na saída.
        intervals = [(None, None)]

    rows: list[dict] = []
    for interval_start, interval_end in intervals:
        if product.temporal:
            assert interval_start is not None and interval_end is not None
            start_text = interval_start.isoformat()
            end_text = interval_end.isoformat()
        else:
            start_text = "2000-01-01"
            end_text = "2000-01-01"

        n_images = image_count(product_name, start_text, end_text, region)
        value = None
        if n_images > 0:
            image = period_image(product_name, start_text, end_text, region)
            value = reduce_value(product_name, image, region)

        rows.append(
            {
                "data_inicio": interval_start.isoformat() if interval_start else None,
                "data_fim_inclusiva": interval_end.isoformat() if interval_end else None,
                "produto": product.key,
                "banco_plataforma": product.group,
                "variavel": product.out_band,
                "valor": value,
                "unidade": product.unit,
                "regiao": region_label,
                "estatistica": product.statistic,
                "escala_m": product.scale,
                "fonte": product.source,
                "colecao_gee": product.collection or product.image_id,
                "banda_gee": ",".join(product.band) if isinstance(product.band, list) else product.band,
                "imagens_no_periodo": n_images,
                "data_processamento_utc": processed_at,
            }
        )

    return pd.DataFrame(rows)
