"""Regressões da revisão de confiabilidade/segurança. Rodam sem credenciais do Earth Engine:
as chamadas ao GEE são substituídas por dados fixos.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone

import folium
import pandas as pd
import pytest
import streamlit as st
from streamlit import config as st_config
from streamlit.testing.v1 import AppTest

import modules.auth_gee as auth_gee
import modules.maps as maps
import modules.series as series
import modules.ui as ui
from modules.products import PRODUCTS, freshness_token

APP = os.path.abspath("app.py")
MAPS = "pages/1_🗺️_Mapas_Interativos.py"
SERIES = "pages/2_📈_Series_Temporais.py"
LATEST = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
CENTERS = {"Minas Gerais": [-18.45, -44.66], "São Paulo": [-22.26, -48.73]}


@pytest.fixture(autouse=True)
def _limpa_cache_e_config():
    st.cache_data.clear()
    original = st_config.get_option("client.showErrorDetails")
    yield
    st.cache_data.clear()
    st_config.set_option("client.showErrorDetails", original)


@pytest.fixture
def gee_falso(monkeypatch):
    """Substitui o GEE nas páginas: listas administrativas, última data, mapa e resumo fixos."""
    monkeypatch.setattr(auth_gee, "initialize_gee", lambda: True)
    monkeypatch.setattr(ui, "latest_available_timestamp", lambda name: LATEST)
    monkeypatch.setattr(ui, "admin1_names", lambda country: ["Minas Gerais", "São Paulo"])
    monkeypatch.setattr(ui, "admin2_names", lambda country, state: ["Itajubá", "Pouso Alegre"])
    monkeypatch.setattr(maps, "cached_image_count", lambda *a, **k: 7)
    monkeypatch.setattr(maps, "cached_summary", lambda *a, **k: {"headline": "ok", "details": []})
    monkeypatch.setattr(maps, "_display_image_and_vis", lambda p, image, region: (image, dict(PRODUCTS[p].vis)))

    def fake_make_map(product_name, start, end, region_name, bounds=None, overlays=None, basemap="Claro",
                      country_name=None, admin1_name=None, city_name=None):
        return folium.Map(location=list(CENTERS.get(admin1_name, [-25, -60])), zoom_start=6), "img", "reg"

    monkeypatch.setattr(maps, "make_map", fake_make_map)


def _label(elements, label):
    return next(e for e in elements if e.label == label)


def _textos(at):
    return [e.value for e in (*at.info, *at.warning, *at.error)]


# ------------------------------------------------------------------ cache e falhas temporárias
def test_falha_temporaria_da_ultima_data_nao_fica_no_cache(monkeypatch):
    produto = PRODUCTS["Precipitação CHIRPS"]
    chamadas = {"n": 0}

    def instavel(name):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise TimeoutError("Read timed out")
        return LATEST

    monkeypatch.setattr(ui, "latest_available_timestamp", instavel)
    assert ui.resolved_product_date_bounds(produto)[2] is None  # 1ª: GEE fora, usa o catálogo
    # Antes da correção o None ficava 6 h no cache; agora a 2ª consulta já recupera a data real.
    assert ui.resolved_product_date_bounds(produto)[2] == LATEST
    assert ui.resolved_product_date_bounds(produto)[2] == LATEST and chamadas["n"] == 2


def test_freshness_token():
    agora = datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc)
    assert freshness_token("Relevo", None, agora) == "estatico"
    assert freshness_token("Precipitação CHIRPS", "2026-09-27", agora) == "historico"
    recente = freshness_token("Focos GOES-19", "2026-11-26", agora)
    assert recente.startswith("recente-")
    assert freshness_token("Focos GOES-19", "2026-11-26", agora + timedelta(minutes=16)) != recente


def test_chave_do_cache_do_mapa_inclui_regiao_periodo_e_produto(monkeypatch):
    chamadas = []
    monkeypatch.setattr(maps, "get_region", lambda *a, **k: ("regiao", a, tuple(sorted(k.items()))))
    monkeypatch.setattr(maps, "image_count", lambda p, s, e, r: chamadas.append((p, s, e, r)) or 3)
    mg = maps.region_key("Estados do Brasil", None, "Brazil", "Minas Gerais")
    sp = maps.region_key("Estados do Brasil", None, "Brazil", "São Paulo")
    for _ in range(2):  # repetição não chama o GEE de novo
        maps.cached_image_count("Precipitação CHIRPS", "2026-09-01", "2026-09-07", mg, "historico")
    maps.cached_image_count("Precipitação CHIRPS", "2026-09-01", "2026-09-07", sp, "historico")
    maps.cached_image_count("Precipitação CHIRPS", "2026-09-01", "2026-09-08", mg, "historico")
    maps.cached_image_count("Precipitação ERA5-Land", "2026-09-01", "2026-09-07", mg, "historico")
    maps.cached_image_count("Precipitação CHIRPS", "2026-09-01", "2026-09-07", mg, "recente-1")
    assert len(chamadas) == 5


def test_chave_do_cache_da_serie_inclui_cidade_periodo_e_frequencia(monkeypatch):
    chamadas = []

    def fake_make_series(product_name, start, end, region_name, freq, bounds=None, country_name=None,
                         admin1_name=None, city_name=None):
        chamadas.append((start, end, freq, city_name))
        return pd.DataFrame({"regiao": [city_name], "valor": [1.0]})

    monkeypatch.setattr(series, "make_series", fake_make_series)
    args = ("Precipitação CHIRPS", date(2026, 9, 1), date(2026, 9, 7), "Cidades do Brasil")
    a = series.cached_series(*args, "Diária", None, "Brazil", "Minas Gerais", "Itajubá")
    b = series.cached_series(*args, "Diária", None, "Brazil", "Minas Gerais", "Itajubá")
    c = series.cached_series(*args, "Diária", None, "Brazil", "Minas Gerais", "Pouso Alegre")
    series.cached_series(*args, "Mensal", None, "Brazil", "Minas Gerais", "Itajubá")
    assert len(chamadas) == 3
    assert a.equals(b) and c["regiao"].iloc[0] == "Pouso Alegre"
    b.loc[0, "valor"] = 99  # o DataFrame devolvido é uma cópia: mexer nele não altera o cache
    assert series.cached_series(*args, "Diária", None, "Brazil", "Minas Gerais", "Itajubá")["valor"].iloc[0] == 1.0


def test_resumo_com_falha_nao_e_cacheado(monkeypatch):
    estado = {"falhar": True}
    monkeypatch.setattr(maps, "_region_from_key", lambda key: "regiao")
    monkeypatch.setattr(maps, "period_image", lambda *a: "imagem")

    def resumo(product_name, image, region, strict=False):
        if estado["falhar"]:
            raise TimeoutError("deadline exceeded")
        return {"headline": "mín 0 • máx 3", "details": []}

    monkeypatch.setattr(maps, "summarize_image", resumo)
    key = maps.region_key("Estados do Brasil", None, "Brazil", "Minas Gerais")
    assert maps.cached_summary("Precipitação CHIRPS", "2026-09-01", "2026-09-07", key)["headline"] == "Resumo indisponível"
    estado["falhar"] = False
    assert maps.cached_summary("Precipitação CHIRPS", "2026-09-01", "2026-09-07", key)["headline"] == "mín 0 • máx 3"


# ------------------------------------------------------------------ validação e erros
@pytest.mark.parametrize("bounds, ok", [
    ((-50, -25, -40, -15), True),
    ((-40, -25, -50, -15), False),   # longitude invertida (antes: traceback do GEE na tela)
    ((-50, -15, -40, -25), False),   # latitude invertida
    ((-50, -95, -40, -15), False),   # latitude fora da Terra (antes: aceita sem aviso)
    ((-190, -25, -40, -15), False),
])
def test_validacao_do_retangulo(bounds, ok):
    assert (ui.bounds_error(bounds) is None) is ok


def _script_com_erro(kind: str):
    import streamlit as st  # noqa: F401
    from modules.ui import report_exception

    exc = TimeoutError("Read timed out") if kind == "timeout" else ValueError("projects/segredo-interno/xyz")
    try:
        raise exc
    except Exception as error:
        report_exception("Não foi possível gerar o mapa.", error)


def test_erro_nao_expoe_traceback_ao_visitante():
    st_config.set_option("client.showErrorDetails", "type")
    at = AppTest.from_function(_script_com_erro, args=("generico",)).run()
    assert not at.exception
    assert [e.value for e in at.error] == ["Não foi possível gerar o mapa."]
    assert "segredo-interno" not in json.dumps([c.value for c in at.caption])
    assert any("ValueError" in c.value for c in at.caption)


def test_timeout_mostra_mensagem_propria():
    st_config.set_option("client.showErrorDetails", "type")
    at = AppTest.from_function(_script_com_erro, args=("timeout",)).run()
    assert not at.exception and not at.error
    assert "demorou demais" in at.warning[0].value


def test_traceback_continua_disponivel_para_depuracao():
    st_config.set_option("client.showErrorDetails", "full")
    at = AppTest.from_function(_script_com_erro, args=("generico",)).run()
    assert at.exception


def test_prazo_do_gee_configuravel(monkeypatch):
    monkeypatch.delenv("EE_DEADLINE_SECONDS", raising=False)
    assert auth_gee.ee_deadline_ms() == 300_000
    monkeypatch.setenv("EE_DEADLINE_SECONDS", "30")
    assert auth_gee.ee_deadline_ms() == 30_000
    monkeypatch.setenv("EE_DEADLINE_SECONDS", "abc")
    assert auth_gee.ee_deadline_ms() == 300_000


def test_lista_de_estados_com_gee_fora_e_depois_recuperado(gee_falso, monkeypatch):
    def fora(country):
        raise TimeoutError("Read timed out")

    monkeypatch.setattr(ui, "admin1_names", fora)
    at = AppTest.from_file(APP, default_timeout=60)
    at.switch_page(MAPS).run()
    at.selectbox(key="map_region").set_value("Estados do Brasil").run()
    assert not at.exception  # antes: traceback do Earth Engine na página
    assert any("lista de estados" in t for t in _textos(at))

    monkeypatch.setattr(ui, "admin1_names", lambda country: ["Minas Gerais", "São Paulo"])
    at.run()
    assert not at.exception and _label(at.selectbox, "Estado do Brasil").value == "Minas Gerais"


# ------------------------------------------------------------------ fluxos das páginas
def test_mapa_novo_nao_herda_o_centro_de_outro_estado(gee_falso):
    at = AppTest.from_file(APP, default_timeout=60)
    at.switch_page(MAPS).run()
    at.selectbox(key="map_region").set_value("Estados do Brasil").run()
    _label(at.button, "Gerar mapa").click().run()
    assert at.session_state["vigia_map_result"]["region_label"] == "Minas Gerais - Brazil"
    # Simula o st_folium devolvendo a vista do usuário sobre MG.
    at.session_state["vigia_map_view"] = {"center": {"lat": -18.45, "lng": -44.66}, "zoom": 7}

    _label(at.selectbox, "Estado do Brasil").set_value("São Paulo").run()
    _label(at.button, "Gerar mapa").click().run()
    result = at.session_state["vigia_map_result"]
    assert result["region_label"] == "São Paulo - Brazil"
    assert result["map"].location == CENTERS["São Paulo"]  # antes: continuava em MG

    # Mesma área: o zoom/centro escolhido pelo usuário é mantido.
    at.session_state["vigia_map_view"] = {"center": {"lat": -23.5, "lng": -46.6}, "zoom": 9}
    _label(at.button, "Gerar mapa").click().run()
    assert at.session_state["vigia_map_result"]["map"].location == [-23.5, -46.6]


def test_aviso_quando_tela_e_download_sao_de_outra_selecao(gee_falso):
    at = AppTest.from_file(APP, default_timeout=60)
    at.switch_page(MAPS).run()
    at.selectbox(key="map_region").set_value("Estados do Brasil").run()
    _label(at.button, "Gerar mapa").click().run()
    assert not any("alterou os filtros" in t for t in _textos(at))

    start_key = next(d.key for d in at.date_input if d.label == "Data inicial")
    original = at.date_input(key=start_key).value
    at.date_input(key=start_key).set_value(original - timedelta(days=1)).run()
    assert any("alterou os filtros" in t for t in _textos(at))  # antes: nenhum aviso ao mudar a data

    at.date_input(key=start_key).set_value(original).run()
    assert not any("alterou os filtros" in t for t in _textos(at))
    _label(at.selectbox, "Estado do Brasil").set_value("São Paulo").run()
    assert any("alterou os filtros" in t for t in _textos(at))  # antes: nenhum aviso ao mudar o estado


def _fixture_series(monkeypatch):
    """Três dias fixos: 0 mm (chuva zero), dia sem cena (observação ausente) e 12,5 mm."""
    monkeypatch.setattr(series, "get_region", lambda *a, **k: "regiao")
    monkeypatch.setattr(series, "_interval_feature", lambda p, s, e, r, i: i)
    props = {0: {"i": 0, "n": 1, "valor": 0.0}, 1: {"i": 1, "n": 0, "valor": None}, 2: {"i": 2, "n": 1, "valor": 12.5}}
    monkeypatch.setattr(series, "_fetch_batch", lambda batch: [props[i] for i in batch])


def test_serie_distingue_chuva_zero_de_observacao_ausente(monkeypatch):
    _fixture_series(monkeypatch)
    df = series.make_series("Precipitação CHIRPS", date(2026, 9, 1), date(2026, 9, 3), "Cidades do Brasil",
                            "Diária", country_name="Brazil", admin1_name="Minas Gerais", city_name="Itajubá")
    assert df["valor"].iloc[0] == 0.0 and pd.isna(df["valor"].iloc[1]) and df["valor"].iloc[2] == 12.5
    assert df["imagens_no_periodo"].tolist() == [1, 0, 1]
    assert set(df["unidade"]) == {"mm"}
    assert df["data_processamento_utc"].iloc[0].endswith("Z")
    linhas = df.to_csv(index=False).splitlines()
    assert ",0.0,mm," in linhas[1]   # zero exportado como 0.0
    assert ",,mm," in linhas[2]      # ausente exportado vazio (não 0)


def test_pagina_de_series_grafico_csv_e_duas_sessoes(gee_falso, monkeypatch):
    _fixture_series(monkeypatch)

    def abrir(cidade):
        at = AppTest.from_file(APP, default_timeout=60)
        at.switch_page(SERIES).run()
        at.selectbox(key="series_product_group").set_value("CHIRPS v3 / UCSB-CHC")
        at.selectbox(key="series_region").set_value("Cidades do Brasil").run()
        _label(at.selectbox, "Cidade do Brasil").set_value(cidade)
        start_key = next(d.key for d in at.date_input if d.label == "Data inicial")
        end_key = next(d.key for d in at.date_input if d.label == "Data final (inclusiva)")
        at.date_input(key=start_key).set_value(date(2026, 9, 1))
        at.date_input(key=end_key).set_value(date(2026, 9, 3)).run()
        return at

    s1, s2 = abrir("Itajubá"), abrir("Pouso Alegre")
    _label(s1.button, "Gerar série temporal").click().run()
    _label(s2.button, "Gerar série temporal").click().run()
    s1.run()  # rerun da sessão 1 depois da sessão 2 gerar outra cidade
    assert s1.session_state["vigia_last_series"]["df"]["regiao"].iloc[0].startswith("Itajubá")
    assert s2.session_state["vigia_last_series"]["df"]["regiao"].iloc[0].startswith("Pouso Alegre")

    spec = json.loads(s1.get("plotly_chart")[0].proto.spec)
    trace = spec["data"][0]
    assert trace.get("connectgaps") is False  # chuva: dia sem observação não vira linha contínua
    y = trace["y"]
    if isinstance(y, dict):  # plotly >= 6 serializa arrays numéricos em base64
        import base64

        import numpy as np
        y = np.frombuffer(base64.b64decode(y["bdata"]), dtype=y["dtype"]).tolist()
    assert y[0] == 0 and (y[1] is None or y[1] != y[1]) and y[2] == 12.5  # 0 mm, ausente (NaN), 12,5 mm

    download = s1.get("download_button")[0].proto
    assert "Itaj" in download.label or download.label == "Baixar CSV da série"
    caption = " ".join(c.value for c in s1.caption)
    assert "Intervalos com dado: 2 de 3" in caption  # 0 mm conta como dado; ausente não
