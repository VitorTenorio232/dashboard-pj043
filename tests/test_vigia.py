"""Testes sem credenciais do Earth Engine: catálogo, SMAP, séries, exportação e regiões."""
from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from PIL import Image

from modules.export_image import (
    GEOTIFF_LIMIT_MB, geotiff_size_estimate, render_board, request_size_from_error, suggested_scale_for_size,
)
from modules.products import PRODUCTS, product_groups, products_in_group
from modules.regions import SA_COUNTRIES, _clean_names, _gaul_country
from modules.series import _is_capacity_error, series_intervals


def test_smap_no_catalogo():
    assert "NASA / SMAP" in product_groups()
    smap = products_in_group("NASA / SMAP")
    assert smap == ["Umidade do Solo SMAP", "Anomalia Umidade SMAP"]
    for key in smap:
        product = PRODUCTS[key]
        assert product.collection == "NASA/SMAP/SPL3SMP_E/006"
        assert product.kind == "soil_moisture_smap"
        assert product.scale == 9000
        assert product.unit == "m³/m³"
        assert product.availability_start == "2015-03-31"
        # Cada banda precisa da flag de qualidade da mesma passagem (am/pm).
        assert {"_am" in b for b in product.band} == {True, False}


def test_anomalia_smap_com_escala_simetrica():
    vis = PRODUCTS["Anomalia Umidade SMAP"].vis
    assert vis["min"] == -vis["max"]


def test_intervalos_diarios_e_mensais():
    daily = series_intervals("Umidade do Solo SMAP", date(2026, 1, 30), date(2026, 2, 2), "Diária")
    assert len(daily) == 4 and daily[0] == (date(2026, 1, 30), date(2026, 1, 30))

    monthly = series_intervals("Umidade do Solo SMAP", date(2025, 11, 15), date(2026, 2, 10), "Mensal")
    assert monthly == [
        (date(2025, 11, 15), date(2025, 11, 30)),
        (date(2025, 12, 1), date(2025, 12, 31)),
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 10)),
    ]
    assert series_intervals("Relevo", None, None, "Estática") == [(None, None)]
    with pytest.raises(ValueError):
        series_intervals("Umidade do Solo SMAP", None, None, "Diária")


def test_erro_de_capacidade_do_gee():
    assert _is_capacity_error(Exception("Too many concurrent aggregations."))
    assert not _is_capacity_error(Exception("Image.clip: The geometry for image clipping must not be empty."))


def _bounds(lon_min, lat_min, lon_max, lat_max):
    return [[[lon_min, lat_min], [lon_max, lat_min], [lon_max, lat_max], [lon_min, lat_max], [lon_min, lat_min]]]


def test_estimativa_do_geotiff():
    minas = _bounds(-51.0, -22.9, -39.9, -14.2)
    size, suggested = geotiff_size_estimate(minas, 9000)
    assert size < GEOTIFF_LIMIT_MB and suggested == 9000

    size, suggested = geotiff_size_estimate(minas, 10)
    assert size > GEOTIFF_LIMIT_MB
    # A escala sugerida precisa caber no limite.
    assert geotiff_size_estimate(minas, suggested)[0] <= GEOTIFF_LIMIT_MB


def test_tamanho_lido_do_erro_do_gee():
    message = "Total request size (70589736 bytes) must be less than or equal to 50331648 bytes."
    size = request_size_from_error(message)
    assert size == pytest.approx(67.32, abs=0.01)
    # Mesmo caso medido no GEE: 392 m recusado → a sugestão precisa ficar acima de ~465 m.
    assert suggested_scale_for_size(392, size) >= 470
    assert request_size_from_error("outro erro") is None


def test_titulo_longo_nao_quebra_a_prancha():
    product = PRODUCTS["Anomalia Umidade SMAP"]
    png = render_board(
        Image.new("RGB", (1450, 720), "#dae9df"), product.key, "Minas Gerais - Brazil",
        "2026-10-16", "2026-10-22", product.source, [], product.vis,
        {"short": "mín -0,11 • máx 0,17", "headline": "mín -0,11 • máx 0,17"}, "Claro", 6.6,
    )
    with Image.open(BytesIO(png)) as img:
        assert img.size == (1600, 1400)
        # Faixa entre o cabeçalho e o mapa (y 120–134) deve continuar vazia (cor de fundo).
        band = img.convert("RGB").crop((60, 120, 1100, 134))
        assert band.getcolors(maxcolors=4) == [(1040 * 14, (244, 247, 249))]


def test_nomes_administrativos():
    assert _clean_names(["Sergipe", "São Paulo", "Name Unknown", "Acre", "São Paulo", None]) == [
        "Acre", "São Paulo", "Sergipe",
    ]
    assert _gaul_country("Bolivia").startswith("Bolivia (")
    assert _gaul_country("Brazil") == "Brazil"
    assert "French Guiana" in SA_COUNTRIES
