from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def _color_label(value: Any) -> str:
    text = str(value)
    if text == "Normal":
        return "color: #4fbf8f; font-weight: 600;"
    if text == "Suspect":
        return "color: #f0b35a; font-weight: 600;"
    return ""


def _color_severity(value: Any) -> str:
    text = str(value)
    mapping = {
        "Critique": "#ff9ab0",
        "Elevee": "#f0b35a",
        "Moyenne": "#6cb6ff",
        "Faible": "#4fbf8f",
        "Normale": "#8aa0bb",
    }
    color = mapping.get(text)
    return f"color: {color}; font-weight: 600;" if color else ""


def _color_score(value: Any) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return ""
    if score >= 0.99:
        return "color: #ff9ab0; font-weight: 600;"
    if score >= 0.95:
        return "color: #f0b35a; font-weight: 600;"
    if score >= 0.80:
        return "color: #6cb6ff; font-weight: 600;"
    return ""


def render_dataframe(df: pd.DataFrame, *, height: int = 420) -> None:
    if df.empty:
        st.info("Aucune donnee disponible pour cette vue.")
        return

    styled = df.style.hide(axis="index")
    if "Label" in df.columns:
        styled = styled.map(_color_label, subset=["Label"])
    if "Severite" in df.columns:
        styled = styled.map(_color_severity, subset=["Severite"])
    if "Score" in df.columns:
        styled = styled.map(_color_score, subset=["Score"])
    if "Risque" in df.columns:
        styled = styled.map(_color_score, subset=["Risque"])

    styled = styled.set_properties(
        **{
            "background-color": "#101929",
            "color": "#eef3f8",
            "border": "1px solid #182235",
        }
    )
    st.dataframe(styled, use_container_width=True, height=height)
