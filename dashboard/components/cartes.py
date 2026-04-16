from __future__ import annotations

from dataclasses import dataclass
from html import escape

import streamlit as st

from dashboard.config import DashboardSettings, get_dashboard_settings


@dataclass(frozen=True)
class KpiCard:
    label: str
    value: str
    hint: str
    tone: str = "accent"


def load_dashboard_css() -> None:
    settings = get_dashboard_settings()
    css_path = settings.assets_dir / "main.css"
    st.markdown(
        f"<style>{css_path.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )


def render_sidebar_brand(settings: DashboardSettings) -> None:
    st.markdown(
        f"""
        <div class="sidebar-brand">
          <div class="sidebar-brand__top">
            <div>
              <div class="sidebar-brand__title">{escape(settings.app_title)}</div>
              <div class="sidebar-brand__subtitle">{escape(settings.app_subtitle)}</div>
            </div>
            <div class="sidebar-brand__sigle">{escape(settings.course_sigle)}</div>
          </div>
          <div class="sidebar-brand__caption">Supervision reseau</div>
          <div class="sidebar-live-pill">LIVE ACTIF</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str, pills: list[str] | None = None) -> None:
    pill_html = "".join(pills or [])
    st.markdown(
        f"""
        <section class="page-header">
          <div class="page-header__content">
            <h1>{escape(title)}</h1>
            <p>{escape(subtitle)}</p>
          </div>
          <div class="page-header__sigle">INF4523 | Projet IPS IA</div>
          <div class="page-header__pills">{pill_html}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_cards(cards: list[KpiCard]) -> None:
    columns = st.columns(len(cards))
    for column, card in zip(columns, cards, strict=True):
        column.markdown(
            f"""
            <div class="kpi-card">
              <div class="kpi-card__tone kpi-card__tone--{escape(card.tone)}"></div>
              <div class="kpi-card__label">{escape(card.label)}</div>
              <div class="kpi-card__value">{escape(card.value)}</div>
              <div class="kpi-card__hint">{escape(card.hint)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_panel_title(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="panel-title">
          <h3>{escape(title)}</h3>
          <p>{escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_detail_list(title: str, subtitle: str, rows: list[tuple[str, str, str]]) -> None:
    items = "".join(
        (
            "<div class='detail-row'>"
            f"<div class='detail-row__label'>{escape(label)}</div>"
            f"<div class='detail-row__value detail-row__value--{escape(tone)}'>{escape(value)}</div>"
            "</div>"
        )
        for label, value, tone in rows
    )
    st.markdown(
        f"""
        <div class="detail-card">
          <div class="panel-title">
            <h3>{escape(title)}</h3>
            <p>{escape(subtitle)}</p>
          </div>
          {items}
        </div>
        """,
        unsafe_allow_html=True,
    )
