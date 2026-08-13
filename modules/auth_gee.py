#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import tempfile

import ee
import streamlit as st


@st.cache_resource(show_spinner=False)
def initialize_gee() -> bool:
    """Inicializa o Google Earth Engine localmente ou no Streamlit Cloud."""
    temporary_key_path: str | None = None
    try:
        if "earthengine" in st.secrets:
            info = dict(st.secrets["earthengine"])
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

        return True

    except Exception as exc:
        st.error("Erro ao inicializar o Google Earth Engine.")
        st.error(str(exc))
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
