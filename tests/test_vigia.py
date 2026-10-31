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
        assert img.size == (1600, 1456)
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


def test_trava_de_area_do_ndvi():
    from modules.products import heavy_request_message

    minas = 586_000
    assert heavy_request_message("NDVI", minas, 30) is None
    assert heavy_request_message("NDVI", 300, 365) is None  # município, 1 ano
    message = heavy_request_message("NDVI", 17_800_000, 30)  # América do Sul (retângulo)
    assert message is not None and "2 dia" in message
    assert "68 dia" in heavy_request_message("NDVI", minas, 90)
    # Produtos sem limite nunca são bloqueados.
    assert heavy_request_message("Umidade do Solo SMAP", 17_800_000, 365) is None


def test_busca_da_ultima_data_comeca_por_janelas_recentes():
    from modules.products import LATEST_SEARCH_WINDOWS_DAYS

    assert LATEST_SEARCH_WINDOWS_DAYS[0] <= 15
    assert list(LATEST_SEARCH_WINDOWS_DAYS) == sorted(LATEST_SEARCH_WINDOWS_DAYS)


def test_calculo_da_escala():
    from modules.export_image import center_latitude, format_distance, meters_per_pixel, nice_scale

    # Valor de referência da Web Mercator: 156.543,03 m/px no equador, zoom 0.
    assert meters_per_pixel(0, 0) == pytest.approx(156_543.03, rel=1e-6)
    assert meters_per_pixel(60, 3) == pytest.approx(156_543.03 * 0.5 / 8, rel=1e-6)

    distance, length = nice_scale(-22.4, 10, 220)  # Itajubá, zoom 10 (~144,7 m/px)
    assert str(int(distance))[0] in "12345" and 110 <= length <= 220
    assert length * meters_per_pixel(-22.4, 10) == pytest.approx(distance, rel=0.01)

    assert format_distance(500) == "500 m"
    assert format_distance(2000) == "2 km"
    assert format_distance(1_000_000) == "1.000 km"
    # Centro em Mercator: entre 0° e -60° fica abaixo de -30° (o eixo estica perto dos polos).
    assert -40 < center_latitude(-60, 0) < -30
    assert center_latitude(-10, 10) == pytest.approx(0, abs=1e-9)


def test_prancha_tem_barra_de_escala_entre_mapa_e_cards():
    from modules.export_image import SCALE_STRIP

    product = PRODUCTS["Umidade do Solo SMAP"]
    png = render_board(
        Image.new("RGB", (1450, 720), "#dae9df"), product.key, "Minas Gerais - Brazil",
        "2026-10-16", "2026-10-22", product.source, [], product.vis,
        {"short": "x", "headline": "x"}, "Claro", 6.6, scale_lat=-18.6,
    )
    with Image.open(BytesIO(png)) as img:
        rgb = img.convert("RGB")
        # Faixa abaixo do mapa (y 897–925+SCALE_STRIP): tem a barra escura desenhada à esquerda.
        strip = rgb.crop((75, 920, 420, 945))
        dark = sum(1 for p in strip.getdata() if sum(p) < 150)
        assert dark > 200
        # Os cards começam depois da faixa: a linha logo acima deles continua com a cor de fundo.
        assert rgb.getpixel((700, 925 + SCALE_STRIP - 3)) == (244, 247, 249)
