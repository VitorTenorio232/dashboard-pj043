#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extração de séries temporais para o VIGIA.

Cada intervalo vira uma ``ee.Feature`` com o valor regional e o número de cenas; os intervalos são
enviados ao Earth Engine em lotes (uma única ``getInfo`` por lote, com lotes em paralelo), em vez de
duas consultas sequenciais por dia.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import time

import ee
import pandas as pd

from modules.products import PRODUCTS, collection, period_image, reducer_for_product, _raw_collection
from modules.regions import get_region, region_display_name

BATCH_SIZE = 31
SMALL_BATCH_SIZE = 4
MAX_WORKERS = 2


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


def series_intervals(product_name: str, start: date | None, end: date | None, freq: str):
    """Intervalos (início, fim inclusivo) da série; produto estático gera um único intervalo vazio."""
    if not PRODUCTS[product_name].temporal:
        return [(None, None)]
    if start is None or end is None:
        raise ValueError("Datas obrigatórias para produto temporal.")
    return list(_dates_daily(start, end)) if freq == "Diária" else list(_dates_monthly(start, end))


def _interval_feature(product_name: str, start_text: str, end_text: str, region, index: int) -> ee.Feature:
    product = PRODUCTS[product_name]
    if product.kind == "static_image":
        n_images = ee.Number(1)
    elif product.kind == "static_collection":
        n_images = _raw_collection(product_name, region).size()
    else:
        n_images = collection(product_name, start_text, end_text, region).size()

    stats = period_image(product_name, start_text, end_text, region).reduceRegion(
        reducer=reducer_for_product(product_name),
        geometry=region,
        scale=product.scale,
        maxPixels=1e13,
        bestEffort=True,
    )
    # If é avaliado de forma preguiçosa no servidor: intervalos sem cenas não chegam a reduzir a imagem vazia.
    value = ee.Algorithms.If(n_images.gt(0), stats.get(product.out_band), None)
    return ee.Feature(None, {"i": index, "n": n_images, "valor": value})


def _is_capacity_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(token in message for token in ("too many concurrent", "429", "rate limit", "quota", "memory limit"))


def _fetch_batch(features: list[ee.Feature], attempt: int = 0) -> list[dict]:
    """Calcula um lote; se o GEE recusar por carga, divide o lote ao meio e tenta de novo."""
    try:
        info = ee.FeatureCollection(features).getInfo()
        return [feature["properties"] for feature in info["features"]]
    except ee.EEException as exc:
        if not _is_capacity_error(exc):
            raise
        if len(features) > 1:
            middle = len(features) // 2
            return _fetch_batch(features[:middle]) + _fetch_batch(features[middle:])
        if attempt >= 4:
            raise
        time.sleep(2 ** attempt)
        return _fetch_batch(features, attempt + 1)


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
    intervals = series_intervals(product_name, start, end, freq)

    features = []
    for index, (interval_start, interval_end) in enumerate(intervals):
        if interval_start is not None and interval_end is not None:
            start_text, end_text = interval_start.isoformat(), interval_end.isoformat()
        else:
            start_text = end_text = "2000-01-01"
        features.append(_interval_feature(product_name, start_text, end_text, region, index))

    # Produtos de alta resolução (VIIRS 375 m, NDVI 10 m...) estouram o limite de agregações
    # simultâneas do GEE com lotes grandes; para eles, lotes pequenos são mais rápidos.
    batch_size = BATCH_SIZE if product.scale >= 1000 else SMALL_BATCH_SIZE
    batches = [features[i:i + batch_size] for i in range(0, len(features), batch_size)]
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(batches))) as pool:
        results = {props["i"]: props for batch in pool.map(_fetch_batch, batches) for props in batch}

    rows: list[dict] = []
    for index, (interval_start, interval_end) in enumerate(intervals):
        props = results.get(index, {})
        rows.append(
            {
                "data_inicio": interval_start.isoformat() if interval_start else None,
                "data_fim_inclusiva": interval_end.isoformat() if interval_end else None,
                "produto": product.key,
                "banco_plataforma": product.group,
                "variavel": product.out_band,
                "valor": props.get("valor"),
                "unidade": product.unit,
                "regiao": region_label,
                "estatistica": product.statistic,
                "escala_m": product.scale,
                "fonte": product.source,
                "colecao_gee": product.collection or product.image_id,
                "banda_gee": ",".join(product.band) if isinstance(product.band, list) else product.band,
                "imagens_no_periodo": int(props.get("n") or 0),
                "data_processamento_utc": processed_at,
            }
        )

    return pd.DataFrame(rows)
