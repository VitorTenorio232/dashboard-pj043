#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import datetime, timezone
import json
import pandas as pd
import streamlit as st
from modules.auth_gee import initialize_gee
from modules.maps import BASEMAPS, make_map, visual_image_with_overlays, _display_image_and_vis, summarize_image
from modules.export_image import styled_map_bytes, png_to_jpeg
from modules.products import PRODUCTS, image_count, period_image, safe_filename
from modules.regions import default_overlays, get_region, overlay_options, region_display_name, region_options
from modules.ui import (
    date_range_ui, landcover_legend_ui, load_css, page_title, processing_time_warning,
    product_metadata, product_selector_ui, query_dates, regional_selector_ui, sidebar_brand,
)

load_css("assets/style.css")
initialize_gee()
page_title("Downloads", "Gere GeoTIFF analítico, imagens padronizadas do VIGIA, mapa HTML e metadados documentados.")
with st.sidebar:
    sidebar_brand()
    st.markdown("**01  ·  Fonte de dados**")
    product_name = product_selector_ui("download")
    product = PRODUCTS[product_name]
    st.divider()
    st.markdown("**02  ·  Área de interesse**")
    region_name = st.selectbox("Região", region_options(), key="download_region")
    bounds, country_name, admin1_name, city_name = regional_selector_ui(region_name)
    st.divider()
    st.markdown("**03  ·  Período**")
    start, end = date_range_ui(product, "download_dates")
    processing_time_warning(product, start, end)
    st.divider()
    st.markdown("**04  ·  Exportação**")
    scale = st.number_input("Escala do GeoTIFF (m)", min_value=10, max_value=60000, value=int(product.scale), step=100 if product.scale < 1000 else 1000)
    overlays = st.multiselect("Contornos no PNG/JPEG/HTML", overlay_options(region_name), default=default_overlays(region_name), key=f"download_overlays_{region_name}")
    st.markdown("**Formatos desejados**")
    want_tif = st.checkbox("GeoTIFF analítico", value=True)
    want_png = st.checkbox("PNG padronizado do VIGIA", value=True)
    want_jpeg = st.checkbox("JPEG padronizado do VIGIA", value=False)
    want_csv = st.checkbox("CSV de metadados", value=True)
    want_json = st.checkbox("JSON de metadados", value=True)
    want_html = st.checkbox("HTML do mapa interativo", value=True)
    basemap = st.selectbox("Mapa base do HTML e do PNG/JPEG", BASEMAPS, index=0)

if product.temporal and start is not None and end is not None and start > end:
    st.error("A data inicial precisa ser anterior ou igual à data final.")
    st.stop()

left, right = st.columns([0.68, 0.32], gap="large")
with right:
    product_metadata(product)
    if product_name == "Cobertura do Solo":
        landcover_legend_ui()
    st.warning("O GeoTIFF preserva valores analíticos. PNG/JPEG são pranchas do VIGIA com fundo do mapa, legenda, resumo na área e rodapé institucional.", icon="⚠️")

with left:
    st.markdown("### Exportação de resultados")
    st.caption("Selecione os formatos e gere os arquivos. Produtos de alta resolução podem levar alguns minutos.")
    if st.button("Gerar opções de download", type="primary", width="stretch"):
        try:
            with st.spinner("Preparando os produtos no Earth Engine..."):
                start_text, end_text = query_dates(product, start, end)
                region = get_region(region_name, bounds, country_name=country_name, admin1_name=admin1_name, city_name=city_name)
                n_images = image_count(product_name, start_text, end_text, region)
                if n_images == 0:
                    st.warning("Nenhuma imagem foi encontrada para os filtros selecionados.")
                    st.stop()
                image = period_image(product_name, start_text, end_text, region)
                region_bounds = region.bounds(maxError=1000).getInfo()["coordinates"]
                region_label = region_display_name(region_name, country_name, admin1_name, city_name)
                summary = summarize_image(product_name, image, region)
                date_token = f"{start_text}_{end_text}" if product.temporal else "estatico"
                base_name = f"VIGIA_{safe_filename(product_name)}_{safe_filename(region_label)}_{date_token}_{safe_filename(product.statistic)}"
                metadata = {
                    "arquivo_base": base_name, "produto": product.key, "banco_plataforma": product.group,
                    "variavel": product.out_band, "unidade": product.unit, "regiao": region_label,
                    "data_inicio": start_text if product.temporal else None, "data_fim_inclusiva": end_text if product.temporal else None,
                    "estatistica": product.statistic, "metodo": product.method_note, "limitacoes": product.limitations,
                    "resumo_area": summary.get('headline'),
                    "detalhe_1": (summary.get('details') or [None])[0],
                    "detalhe_2": (summary.get('details') or [None, None])[1] if len(summary.get('details') or []) > 1 else None,
                    "escala_m": int(scale), "fonte": product.source, "colecao_gee": product.collection or product.image_id,
                    "banda_gee": ",".join(product.band) if isinstance(product.band, list) else product.band,
                    "imagens_no_periodo": n_images, "contornos_png_jpeg_html": ", ".join(overlays), "mapa_base_html": basemap,
                    "processamento_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
                metadata_df = pd.DataFrame([metadata])
                links: dict[str, str] = {}
                file_payloads: dict[str, bytes] = {}
                if want_tif:
                    links["GeoTIFF"] = image.getDownloadURL({"name": base_name, "scale": int(scale), "region": region_bounds, "crs": "EPSG:4326", "filePerBand": False, "format": "GEO_TIFF"})
                if want_png or want_jpeg:
                    visual = visual_image_with_overlays(image, product_name, region, overlays, region_name=region_name, country_name=country_name, admin1_name=admin1_name, city_name=city_name)
                    _, vis = _display_image_and_vis(product_name, image, region)
                    # VIGIA V5.5.11: falha PNG isolada das demais exportações.
                    try:
                        board_png = styled_map_bytes(image=image, product_name=product_name, region=region, region_label=region_label, start_text=start_text, end_text=end_text, unit=product.unit, source_label=product.source, overlays=overlays, visual_image=visual, vis=vis, summary=summary, basemap=basemap, output_format="PNG")
                        if want_png:
                            file_payloads["PNG"] = board_png
                        if want_jpeg:
                            file_payloads["JPEG"] = png_to_jpeg(board_png)
                    except Exception as thumb_exc:
                        st.warning("PNG/JPEG não puderam ser preparados nesta tentativa. Os demais formatos continuam disponíveis.")
                        st.caption(f"Detalhe técnico da exportação: {type(thumb_exc).__name__}: {thumb_exc}")
                html_bytes = None
                if want_html:
                    map_object, _, _ = make_map(product_name, start_text, end_text, region_name, bounds=bounds, overlays=overlays, basemap=basemap, country_name=country_name, admin1_name=admin1_name, city_name=city_name)
                    html_bytes = map_object.get_root().render().encode("utf-8")
            st.success("Opções de download geradas.")
            c1, c2, c3 = st.columns(3)
            with c1:
                if "GeoTIFF" in links:
                    st.link_button("Baixar GeoTIFF", links["GeoTIFF"], width="stretch")
<<<<<<< HEAD
                if "PNG" in links:
                    st.link_button("Baixar PNG", links["PNG"], width="stretch")
            with c2:
                if "JPEG" in links:
                    st.link_button("Baixar JPEG", links["JPEG"], width="stretch")
                if want_csv:
                    st.download_button(
                        "Baixar CSV de metadados",
                        metadata_df.to_csv(index=False).encode("utf-8"),
                        file_name=f"{base_name}_metadados.csv",
                        mime="text/csv",
                        width="stretch",
                    )
            with c3:
                if want_json:
                    st.download_button(
                        "Baixar JSON de metadados",
                        json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
                        file_name=f"{base_name}_metadados.json",
                        mime="application/json",
                        width="stretch",
                    )
                if html_bytes is not None:
                    st.download_button(
                        "Baixar HTML do mapa",
                        html_bytes,
                        file_name=f"{base_name}_mapa.html",
                        mime="text/html",
                        width="stretch",
                    )

=======
                if "PNG" in file_payloads:
                    st.download_button("Baixar PNG", file_payloads["PNG"], file_name=f"{base_name}.png", mime="image/png", width="stretch")
            with c2:
                if "JPEG" in file_payloads:
                    st.download_button("Baixar JPEG", file_payloads["JPEG"], file_name=f"{base_name}.jpg", mime="image/jpeg", width="stretch")
                if want_csv:
                    st.download_button("Baixar CSV de metadados", metadata_df.to_csv(index=False).encode("utf-8"), file_name=f"{base_name}_metadados.csv", mime="text/csv", width="stretch")
            with c3:
                if want_json:
                    st.download_button("Baixar JSON de metadados", json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"), file_name=f"{base_name}_metadados.json", mime="application/json", width="stretch")
                if html_bytes is not None:
                    st.download_button("Baixar HTML do mapa", html_bytes, file_name=f"{base_name}_mapa.html", mime="text/html", width="stretch")
>>>>>>> 2194994 (release: VIGIA v5.5.10 - identidade visual e melhorias)
            st.markdown("### Metadados")
            st.dataframe(metadata_df, width="stretch", hide_index=True)
        except Exception as exc:
            st.error("Não foi possível gerar os downloads com os filtros selecionados.")
            st.exception(exc)
    else:
        st.info("Escolha os filtros e clique em **Gerar opções de download**.")
