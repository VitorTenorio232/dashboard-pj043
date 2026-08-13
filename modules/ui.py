#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st

from modules.products import (
    PRODUCTS,
    Product,
    product_date_bounds,
    product_groups,
    products_in_group,
    latest_available_timestamp,
    safe_filename,
)
from modules.regions import south_america_country_names, admin1_names, admin2_names


LANDCOVER_CLASSES = [
    (0, "#282828", "Desconhecido ou dados insuficientes."),
    (20, "#ffbb22", "Arbustos."),
    (30, "#ffff4c", "Vegetação herbácea."),
    (40, "#f096ff", "Agricultura cultivada e gerenciada."),
    (50, "#fa0000", "Área urbana ou construída."),
    (60, "#b4b4b4", "Vegetação rala ou esparsa."),
    (70, "#f0f0f0", "Neve e gelo."),
    (80, "#0032c8", "Corpos d'água permanentes."),
    (90, "#0096a0", "Pântano herbáceo."),
    (100, "#fae6a0", "Musgo e líquen."),
    (111, "#58481f", "Floresta fechada perene de folhas em forma de agulha."),
    (112, "#009900", "Floresta fechada perene de folhas largas."),
    (113, "#70663e", "Floresta fechada decídua de folhas em forma de agulha."),
    (114, "#00cc00", "Floresta fechada decídua de folhas largas."),
    (115, "#4e751f", "Floresta fechada mista."),
    (116, "#007800", "Outra floresta fechada."),
    (121, "#666000", "Floresta aberta perene de folhas em forma de agulha."),
    (122, "#8db400", "Floresta aberta perene de folhas largas."),
    (123, "#8d7400", "Floresta aberta decídua de folhas em forma de agulha."),
    (124, "#a0dc00", "Floresta aberta decídua de folhas largas."),
    (125, "#929900", "Floresta aberta mista."),
    (126, "#648c00", "Outra floresta aberta."),
    (200, "#000080", "Oceanos e mares."),
]


def load_css(path: str) -> None:
    p = Path(path)
    if p.exists():
        st.markdown(f"<style>{p.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def page_title(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="hero-small">
            <h2>{title}</h2>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def _latest_available_timestamp_cached(product_name: str) -> datetime | None:
    """Evita repetir consultas de disponibilidade ao Earth Engine a cada rerun."""
    try:
        return latest_available_timestamp(product_name)
    except Exception:
        return None


def resolved_product_date_bounds(product: Product) -> tuple[date | None, date | None, datetime | None]:
    """Combina os limites declarados com a última cena realmente existente no GEE."""
    start, declared_end = product_date_bounds(product)
    if not product.temporal:
        return None, None, None

    # Coleções encerradas, como GOES-16, mantêm a data final declarada.
    if product.availability_end:
        return start, declared_end, None

    latest = _latest_available_timestamp_cached(product.key)
    if latest is not None:
        return start, min(latest.date(), date.today()), latest

    # Fallback: mantém o comportamento anterior se a consulta remota falhar.
    return start, declared_end, None


def _availability_text(product: Product, use_dynamic: bool = True) -> str:
    if not product.temporal:
        return "Produto estático — datas não se aplicam."

    if use_dynamic:
        start, end, latest = resolved_product_date_bounds(product)
    else:
        start, end = product_date_bounds(product)
        latest = None
    assert start is not None and end is not None

    if product.availability_end:
        end_text = end.strftime("%d/%m/%Y")
    elif latest is not None and product.kind == "precip_era5land_sum":
        end_text = f"{end.strftime('%d/%m/%Y')} (última cena: {latest.strftime('%H:%M')} UTC)"
    elif latest is not None:
        end_text = f"{end.strftime('%d/%m/%Y')} (último dado detectado no GEE)"
    else:
        end_text = "presente, conforme atualização do catálogo"

    return f"{start.strftime('%d/%m/%Y')} até {end_text}"


def product_metadata(product: Product, compact: bool = False) -> None:
    st.markdown(f"### {product.label}" if not compact else f"#### {product.label}")
    st.write(f"**Banco/plataforma:** {product.group}")
    st.write(f"**Fonte:** {product.source}")
    st.write(f"**Coleção/Imagem GEE:** `{product.collection or product.image_id}`")
    st.write(f"**Banda:** `{','.join(product.band) if isinstance(product.band, list) else product.band}`")
    st.write(f"**Unidade:** `{product.unit}`")
    st.write(f"**Estatística:** {product.statistic}")
    st.write(f"**Escala nominal:** `{product.scale} m`")
    st.write(f"**Disponibilidade:** {_availability_text(product, use_dynamic=not compact)}")
    if product.cadence:
        st.write(f"**Cadência:** {product.cadence}")

    st.markdown("**O que representa**")
    st.write(product.user_note)
    st.markdown("**Cálculo aplicado no sistema**")
    st.write(product.method_note)
    st.markdown("**Limitações e cuidados**")
    st.warning(product.limitations)

    if product.catalog_url:
        st.link_button("Abrir catálogo oficial do Earth Engine", product.catalog_url)


def product_selector_ui(prefix: str, default_product: str | None = None) -> str:
    """Seleciona banco e variável, mantendo corretamente o produto do acesso rápido."""
    groups = product_groups()
    group_key = f"{prefix}_product_group"
    product_key = f"{prefix}_product"

    if default_product in PRODUCTS:
        st.session_state[group_key] = PRODUCTS[default_product].group
        st.session_state[product_key] = default_product

    if st.session_state.get(group_key) not in groups:
        st.session_state[group_key] = groups[0]

    group = st.selectbox("Banco de dados / plataforma", groups, key=group_key)
    options = products_in_group(group)

    if st.session_state.get(product_key) not in options:
        st.session_state[product_key] = options[0]

    product_name = st.selectbox(
        "Variável / produto",
        options,
        format_func=lambda key: PRODUCTS[key].label,
        key=product_key,
    )

    return product_name


def date_range_ui(product: Product, prefix: str) -> tuple[date | None, date | None]:
    if not product.temporal:
        st.info("Este é um produto estático. A seleção de datas foi removida porque não se aplica.", icon="📌")
        return None, None

    min_date, max_date, latest_timestamp = resolved_product_date_bounds(product)
    assert min_date is not None and max_date is not None

    if product.availability_end is None and latest_timestamp is not None:
        if product.kind == "precip_era5land_sum":
            st.caption(
                f"Última cena disponível no Earth Engine: **{latest_timestamp.strftime('%d/%m/%Y %H:%M UTC')}**."
            )
            # Em uma coleção horária, o último dia pode estar incompleto quando a ingestão não chegou às 23 UTC.
            if latest_timestamp.hour < 23:
                st.info(
                    "A última data disponível pode estar incompleta porque a coleção é horária. "
                    "Para acumulados de dias fechados, finalize o período no dia anterior.",
                    icon="🕒",
                )
        else:
            st.caption(f"Último dado disponível no Earth Engine: **{max_date.strftime('%d/%m/%Y')}**.")

        lag_days = (date.today() - max_date).days
        if lag_days >= 7:
            st.warning(
                f"Esta coleção está com aproximadamente **{lag_days} dias de defasagem** no Earth Engine. "
                "O calendário foi limitado automaticamente à última cena realmente disponível.",
                icon="📅",
            )
        elif lag_days >= 1 and product.kind != "precip_era5land_sum":
            st.caption(f"Defasagem atual aproximada em relação a hoje: {lag_days} dia(s).")

    end_default = max_date
    start_default = max(min_date, end_default - timedelta(days=max(product.default_days - 1, 0)))

    token = safe_filename(product.key).lower()
    start_key = f"{prefix}_{token}_start"
    end_key = f"{prefix}_{token}_end"

    start_state = st.session_state.get(start_key)
    end_state = st.session_state.get(end_key)
    if not isinstance(start_state, date) or not (min_date <= start_state <= max_date):
        st.session_state[start_key] = start_default
    if not isinstance(end_state, date) or not (min_date <= end_state <= max_date):
        st.session_state[end_key] = end_default

    start = st.date_input(
        "Data inicial",
        min_value=min_date,
        max_value=max_date,
        key=start_key,
        help=f"Primeira data disponível: {min_date.strftime('%d/%m/%Y')}",
    )
    end = st.date_input(
        "Data final (inclusiva)",
        min_value=min_date,
        max_value=max_date,
        key=end_key,
        help=(
            f"Última data permitida nesta coleção: {max_date.strftime('%d/%m/%Y')}. "
            "A data final é incluída no cálculo."
        ),
    )
    return start, end


def processing_time_warning(product: Product, start: date | None, end: date | None) -> None:
    if not product.temporal or start is None or end is None:
        return

    days = (end - start).days + 1
    if days > 7:
        st.warning(
            f"O período selecionado possui **{days} dias**. O processamento pode levar alguns minutos, "
            "principalmente para áreas extensas, produtos de alta resolução e geração de downloads.",
            icon="⏳",
        )

    if product.kind == "precip_era5land_sum" and days > 14:
        st.warning(
            "ERA5-Land possui uma cena por hora. Períodos longos podem envolver centenas ou milhares de imagens "
            "e exigir mais tempo de processamento, principalmente em regiões extensas.",
            icon="🌧️",
        )

    if product.kind == "fire_goes" and days > 1:
        st.warning(
            "Os produtos GOES possuem imagens a cada 10 minutos. Períodos com vários dias podem envolver "
            "centenas ou milhares de cenas e demorar mais que os demais produtos.",
            icon="🛰️",
        )


def query_dates(product: Product, start: date | None, end: date | None) -> tuple[str, str]:
    if product.temporal:
        if start is None or end is None:
            raise ValueError("Datas ausentes para produto temporal.")
        return start.isoformat(), end.isoformat()
    return "2000-01-01", "2000-01-01"


def custom_bounds_ui():
    st.caption("Informe o retângulo no formato longitude/latitude em graus decimais.")
    c1, c2 = st.columns(2)
    with c1:
        lon_min = st.number_input("Longitude mínima", value=-50.0, format="%.4f")
        lat_min = st.number_input("Latitude mínima", value=-25.0, format="%.4f")
    with c2:
        lon_max = st.number_input("Longitude máxima", value=-40.0, format="%.4f")
        lat_max = st.number_input("Latitude máxima", value=-15.0, format="%.4f")
    return lon_min, lat_min, lon_max, lat_max


def regional_selector_ui(region_name: str):
    country_name = None
    admin1_name = None
    city_name = None
    bounds = None

    if region_name == "País da América do Sul":
        countries = south_america_country_names()
        country_name = st.selectbox("País", countries, index=countries.index("Brazil") if "Brazil" in countries else 0)

    elif region_name == "Estado/Província/Departamento":
        countries = south_america_country_names()
        country_name = st.selectbox("País", countries, index=countries.index("Brazil") if "Brazil" in countries else 0)
        admins = admin1_names(country_name)
        if not admins:
            st.warning("Nenhuma unidade de primeiro nível encontrada para esse país.")
            st.stop()
        default = "Minas Gerais" if country_name == "Brazil" and "Minas Gerais" in admins else admins[0]
        admin1_name = st.selectbox("Estado/Província/Departamento", admins, index=admins.index(default))

    elif region_name == "Cidade/Município/Distrito":
        st.caption("O shape municipal será carregado apenas para a cidade selecionada.")
        countries = south_america_country_names()
        country_name = st.selectbox("País", countries, index=countries.index("Brazil") if "Brazil" in countries else 0)
        admins = admin1_names(country_name)
        if not admins:
            st.warning("Nenhuma unidade de primeiro nível encontrada para esse país.")
            st.stop()
        default_admin = "Minas Gerais" if country_name == "Brazil" and "Minas Gerais" in admins else admins[0]
        admin1_name = st.selectbox("Estado/Província/Departamento", admins, index=admins.index(default_admin))

        cities = admin2_names(country_name, admin1_name)
        if not cities:
            st.warning("Nenhum município/distrito encontrado para essa unidade.")
            st.stop()
        default_city = "Itajubá" if country_name == "Brazil" and "Itajubá" in cities else cities[0]
        city_name = st.selectbox("Cidade/Município/Distrito", cities, index=cities.index(default_city))

    elif region_name == "Retângulo personalizado":
        bounds = custom_bounds_ui()

    return bounds, country_name, admin1_name, city_name


def product_card(icon: str, title: str, text: str, footer: str) -> None:
    st.markdown(
        f"""
        <div class="product-card">
            <div class="product-icon">{icon}</div>
            <h3>{title}</h3>
            <p>{text}</p>
            <span>{footer}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def product_card_button(product_name: str, icon: str, title: str, text: str, footer: str) -> None:
    product_card(icon, title, text, footer)
    if st.button(f"Abrir {title}", key=f"home_open_{safe_filename(product_name)}", use_container_width=True):
        # Define explicitamente os estados da página de mapas. Isso evita que o
        # selectbox volte ao primeiro produto no rerun seguinte.
        st.session_state["produto_rapido"] = product_name
        st.session_state["map_product_group"] = PRODUCTS[product_name].group
        st.session_state["map_product"] = product_name
        st.switch_page("pages/1_🗺️_Mapas_Interativos.py")


def landcover_legend_ui() -> None:
    """Legenda categórica do Copernicus sem exibir códigos hexadecimais ou valores brutos."""
    st.markdown("### Classes de cobertura")
    st.caption(
        "As cores abaixo seguem a tabela oficial do produto Copernicus CGLS-LC100. "
        "Classes de oceano e pixels desconhecidos ficam transparentes no mapa para preservar o mapa base."
    )

    with st.container(border=True):
        for value, color, desc in LANDCOVER_CLASSES:
            if value in {0, 200}:
                continue
            st.markdown(
                f"""
                <div class="lc-row">
                    <span class="lc-swatch" style="background:{color};"></span>
                    <span>{desc}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander("Classes não exibidas sobre o mapa base"):
        st.markdown(
            "- **Desconhecido / dados insuficientes:** mantido transparente.\n"
            "- **Oceanos e mares:** mantidos transparentes para que o mapa base permaneça visível."
        )
