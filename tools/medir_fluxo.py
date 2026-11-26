#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mede tempo e chamadas ao Earth Engine em fluxos representativos do VIGIA (via AppTest).

Uso (precisa de `earthengine authenticate` ou Secrets válidos, pois chama o GEE de verdade):

    python tools/medir_fluxo.py                 # fluxo completo, saída em tabela
    python tools/medir_fluxo.py --json saida.json

Opções de simulação (aplicadas sobre as chamadas reais):
    --latencia 2.0      acrescenta 2 s a cada chamada HTTP ao GEE (API lenta)

Cada linha mostra o tempo de parede do rerun e quantas chamadas HTTP ao GEE (computeValue,
getMapId, thumbnails...) e downloads HTTP externos (miniatura/mapa base) ocorreram nele.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import ee.data  # noqa: E402
import streamlit as st  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

CALLS: Counter = Counter()
LATENCY = 0.0

_original_execute = ee.data._execute_cloud_call


def _counting_execute(call, num_retries=None):
    method = getattr(call, "methodId", None) or getattr(call, "uri", "?")
    CALLS[f"gee:{str(method).split('?')[0].rsplit('.', 1)[-1]}"] += 1
    if LATENCY:
        time.sleep(LATENCY)
    return _original_execute(call, num_retries)


ee.data._execute_cloud_call = _counting_execute

import modules.export_image as export_image  # noqa: E402

_original_download = export_image._download_bytes


def _counting_download(url):
    CALLS["http:download"] += 1
    return _original_download(url)


export_image._download_bytes = _counting_download

MAPS = "pages/1_🗺️_Mapas_Interativos.py"
SERIES = "pages/2_📈_Series_Temporais.py"


def _by_label(elements, label):
    for element in elements:
        if element.label == label:
            return element
    raise LookupError(label)


def _step(results, name, action):
    CALLS.clear()
    t0 = time.perf_counter()
    at = action()
    elapsed = time.perf_counter() - t0
    gee = sum(v for k, v in CALLS.items() if k.startswith("gee:"))
    http = CALLS.get("http:download", 0)
    errors = [e.value for e in at.error] + [str(e.value)[:200] for e in at.exception]
    entry = {"passo": name, "segundos": round(elapsed, 2), "chamadas_gee": gee,
             "downloads_http": http, "detalhe": dict(CALLS), "erros": errors}
    # Resultado exibido (para comparar antes/depois de otimizações com os mesmos filtros).
    if "Gerar" in name and name.startswith("Mapas") and "vigia_map_result" in at.session_state:
        r = at.session_state["vigia_map_result"]
        entry["resultado"] = {"regiao": r["region_label"], "cenas": r["n_images"], "resumo": r["summary"],
                              "centro": [round(v, 3) for v in r["map"].location]}
    if "Gerar" in name and name.startswith("Séries") and "vigia_last_series" in at.session_state:
        df = at.session_state["vigia_last_series"]["df"]
        entry["resultado"] = {"regiao": df["regiao"].iloc[0], "valores": df["valor"].round(6).tolist(),
                              "cenas": df["imagens_no_periodo"].tolist()}
    results.append(entry)
    print(f"{name:<55} {elapsed:7.2f} s  GEE={gee:<3} HTTP={http:<3} {'ERRO: ' + errors[0][:80] if errors else ''}",
          flush=True)
    return at


def run(results, start: date, end: date):
    st.cache_data.clear()
    st.cache_resource.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=600)

    # ---------------- Mapas ----------------
    at = _step(results, "Mapas: primeira abertura (cache frio)", lambda: at.switch_page(MAPS).run())
    at.selectbox(key="map_product_group").set_value("CHIRPS v3 / UCSB-CHC")
    at = _step(results, "Mapas: escolher CHIRPS", lambda: at.run())
    chave = "precipitacao_chirps"
    at.date_input(key=f"map_dates_{chave}_start").set_value(start)
    at.date_input(key=f"map_dates_{chave}_end").set_value(end)
    at = _step(results, "Mapas: escolher período", lambda: at.run())
    at.selectbox(key="map_region").set_value("Estados do Brasil")
    at = _step(results, "Mapas: região = Estados (MG)", lambda: at.run())
    at = _step(results, "Mapas: Gerar mapa (MG)", lambda: _by_label(at.button, "Gerar mapa").click().run())
    at = _step(results, "Mapas: Gerar mapa de novo (mesma consulta)",
               lambda: _by_label(at.button, "Gerar mapa").click().run())
    _by_label(at.selectbox, "Estado do Brasil").set_value("São Paulo")
    at = _step(results, "Mapas: trocar estado (sem gerar)", lambda: at.run())
    at = _step(results, "Mapas: Gerar mapa (SP)", lambda: _by_label(at.button, "Gerar mapa").click().run())
    at = _step(results, "Mapas: Preparar PNG/JPEG", lambda: _by_label(at.button, "Preparar PNG/JPEG").click().run())
    _by_label(at.selectbox, "Estado do Brasil").set_value("Minas Gerais")
    at = _step(results, "Mapas: voltar para MG e Gerar",
               lambda: _by_label(at.button, "Gerar mapa").click().run())
    at = _step(results, "Mapas: Preparar PNG/JPEG (MG de novo)",
               lambda: _by_label(at.button, "Preparar PNG/JPEG").click().run())

    # ---------------- Séries ----------------
    at = _step(results, "Séries: abrir página", lambda: at.switch_page(SERIES).run())
    at.selectbox(key="series_product_group").set_value("CHIRPS v3 / UCSB-CHC")
    at.selectbox(key="series_region").set_value("Cidades do Brasil")
    at = _step(results, "Séries: CHIRPS + Cidades (Itajubá)", lambda: at.run())
    at.date_input(key=f"series_dates_{chave}_start").set_value(start)
    at.date_input(key=f"series_dates_{chave}_end").set_value(end)
    at = _step(results, "Séries: Gerar série diária",
               lambda: _by_label(at.button, "Gerar série temporal").click().run())
    at = _step(results, "Séries: Gerar de novo (mesma consulta)",
               lambda: _by_label(at.button, "Gerar série temporal").click().run())
    _by_label(at.selectbox, "Cidade do Brasil").set_value("Pouso Alegre")
    at = _step(results, "Séries: trocar cidade e Gerar",
               lambda: _by_label(at.button, "Gerar série temporal").click().run())
    at = _step(results, "Séries: rerun sem mudança (ex.: clique em download)", lambda: at.run())
    last = at.session_state["vigia_last_series"]
    df = last["df"]
    print(f"\nSérie final: {df['regiao'].iloc[0]} · {len(df)} intervalos · "
          f"valores válidos {int(df['valor'].notna().sum())} · zeros {int((df['valor'] == 0).sum())}")
    return at


def main():
    global LATENCY
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", help="Salva os resultados neste arquivo JSON.")
    parser.add_argument("--latencia", type=float, default=0.0, help="Atraso extra (s) por chamada ao GEE.")
    parser.add_argument("--fim", default=None, help="Data final (AAAA-MM-DD). Padrão: hoje - 60 dias.")
    parser.add_argument("--dias", type=int, default=14, help="Tamanho do período em dias (padrão 14).")
    args = parser.parse_args()
    LATENCY = args.latencia
    end = date.fromisoformat(args.fim) if args.fim else date.today() - timedelta(days=60)
    start = end - timedelta(days=args.dias - 1)
    print(f"Período: {start} a {end} · latência extra: {LATENCY}s\n")
    results: list[dict] = []
    run(results, start, end)
    total = sum(r["segundos"] for r in results)
    calls = sum(r["chamadas_gee"] for r in results)
    print(f"\nTotal: {total:.1f} s · {calls} chamadas ao GEE")
    if args.json:
        Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
