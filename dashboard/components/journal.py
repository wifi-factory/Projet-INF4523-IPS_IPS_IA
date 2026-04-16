from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st


def _tone_for_level(level: str) -> str:
    mapping = {
        "INFO": "accent",
        "NORMAL": "success",
        "SUSPECT": "warning",
        "ALERTE": "warning",
        "BLOCAGE": "danger",
        "ERROR": "danger",
    }
    return mapping.get(level, "neutral")


def render_timeline(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("Aucune ligne de journal disponible.")
        return

    entries: list[str] = []
    for row in df.to_dict(orient="records"):
        tone = _tone_for_level(str(row.get("Niveau", "INFO")).upper())
        heure = escape(str(row.get("Heure", "-")))
        niveau = escape(str(row.get("Niveau", "-")))
        kind = escape(str(row.get("Type", "-")))
        message = escape(str(row.get("Message", "-")))
        entries.append(
            (
                f"<div class='timeline-entry'>"
                f"<div class='timeline-entry__dot timeline-entry__dot--{tone}'></div>"
                f"<div class='timeline-entry__content'>"
                f"<div class='timeline-entry__meta'>"
                f"<span class='timeline-entry__time'>{heure}</span>"
                f"<span class='timeline-entry__level timeline-entry__level--{tone}'>{niveau}</span>"
                f"<span class='timeline-entry__type'>{kind}</span>"
                f"</div>"
                f"<div class='timeline-entry__message'>{message}</div>"
                f"</div>"
                f"</div>"
            )
        )
    st.markdown(
        "<div class='timeline-stream'>" + "".join(entries) + "</div>",
        unsafe_allow_html=True,
    )
