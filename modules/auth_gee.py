#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import logging
import os
import tempfile

import ee
import streamlit as st


LOGGER = logging.getLogger("vigia")

# Sem prazo (padrão do earthengine-api: deadline 0), uma resposta que nunca chega deixa a sessão
# presa indefinidamente. 300 s acompanha o limite das consultas interativas do Earth Engine.
DEFAULT_DEADLINE_SECONDS = 300.0


def ee_deadline_ms() -> int:
    """Prazo por requisição ao GEE, configurável por EE_DEADLINE_SECONDS (0 desliga)."""
    try:
        seconds = float(os.environ.get("EE_DEADLINE_SECONDS", DEFAULT_DEADLINE_SECONDS))
    except ValueError:
        seconds = DEFAULT_DEADLINE_SECONDS
    return max(0, int(seconds * 1000))


def _earthengine_secrets() -> dict | None:
    """Lê a seção [earthengine] dos Secrets; sem secrets.toml, devolve None."""
    try:
        if "earthengine" in st.secrets:
            return dict(st.secrets["earthengine"])
    except Exception:
        # Streamlit lança StreamlitSecretNotFoundError quando não há nenhum secrets.toml.
        pass
    return None


@st.cache_resource(show_spinner=False)
def initialize_gee() -> bool:
    """Inicializa o Google Earth Engine localmente ou no Streamlit Cloud."""
    temporary_key_path: str | None = None
    try:
        info = _earthengine_secrets()
        if info is not None:
            project_id = info.pop("gee_project_id", None) or info.get("project_id")
            if not project_id:
                raise ValueError("O campo gee_project_id/project_id não foi encontrado nos Secrets.")
            if not info.get("client_email"):
                raise ValueError("O campo client_email não foi encontrado nos Secrets.")

            # O Earth Engine aceita a chave da conta de serviço em arquivo. O arquivo
            # temporário é apagado imediatamente após a inicialização para não manter
            # uma cópia desnecessária da credencial no sistema.
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as handle:
                json.dump(info, handle)
                temporary_key_path = handle.name

            credentials = ee.ServiceAccountCredentials(info["client_email"], temporary_key_path)
            ee.Initialize(credentials, project=project_id)
        else:
            project_id = os.environ.get("EE_PROJECT", "eng-scene-497515-t2")
            ee.Initialize(project=project_id)

        ee.data.setDeadline(ee_deadline_ms())
        return True

    except Exception as exc:
        # A mensagem pode citar projeto, conta de serviço ou caminho da chave: vai só para o log.
        LOGGER.error("Falha ao inicializar o Earth Engine", exc_info=(type(exc), exc, exc.__traceback__))
        st.error(f"Erro ao inicializar o Google Earth Engine ({type(exc).__name__}).")
        st.info(
            "No Streamlit Cloud, configure os Secrets em Settings > Secrets. "
            "Localmente, use `earthengine authenticate` e defina `EE_PROJECT`.",
            icon="🔐",
        )
        st.stop()
    finally:
        if temporary_key_path:
            try:
                os.remove(temporary_key_path)
            except OSError:
                pass
