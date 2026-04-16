from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from dashboard.config import DashboardSettings, get_dashboard_settings
from dashboard.services.backend_client import BackendClient, BackendUnavailableError
from dashboard.utils.formatage import (
    format_compact_number,
    format_duration_seconds,
    format_percent,
    format_score,
    format_timestamp,
    humanize_action,
    humanize_event_status,
    humanize_label,
    humanize_runtime_status,
    humanize_severity,
    normalize_backend_status,
    protocol_label,
)


@dataclass(frozen=True)
class PagePayload:
    backend_ok: bool
    backend_status: str
    backend_error: str | None
    live_status: dict[str, Any]
    dataframes: dict[str, pd.DataFrame]
    summaries: dict[str, Any]


@dataclass(frozen=True)
class RuntimeControlPayload:
    backend_ok: bool
    backend_status: str
    backend_error: str | None
    interfaces_error: str | None
    live_status: dict[str, Any]
    interfaces: list[dict[str, Any]]


@dataclass(frozen=True)
class RecentAlertPayload:
    backend_ok: bool
    backend_error: str | None
    api_exposed_at: str | None
    total_available: int
    new_alert_count: int
    latest_alert: dict[str, Any] | None


class LiveProvider:
    def __init__(self, client: BackendClient, settings: DashboardSettings) -> None:
        self.client = client
        self.settings = settings

    def get_overview_payload(self) -> PagePayload:
        health = self._safe_fetch(self.client.get_health)
        status = self._safe_fetch(self.client.get_live_status)
        events = self._safe_fetch(
            self.client.get_live_events,
            limit=min(8, self.settings.events_limit),
        )
        alerts = self._safe_fetch(
            self.client.get_live_alerts,
            limit=min(4, self.settings.alerts_limit),
        )

        events_df = self._events_frame(events).head(6)
        alerts_df = self._alerts_frame(alerts).head(4)
        predictions = int(status.get("predictions", 0) or 0)
        alerts_count = int(status.get("alerts", 0) or 0)
        summaries = {
            "runtime_label": humanize_runtime_status(status.get("status")),
            "finalized_flows": format_compact_number(status.get("finalized_flows", 0)),
            "alerts": format_compact_number(alerts_count),
            "blocking": format_compact_number(status.get("block_decisions", 0)),
            "suspect_rate": format_percent(alerts_count, predictions),
        }
        return self._build_payload(
            health=health,
            status=status,
            dataframes={
                "events": events_df,
                "alerts": alerts_df,
            },
            summaries=summaries,
        )

    def get_runtime_payload(self) -> PagePayload:
        health = self._safe_fetch(self.client.get_health)
        status = self._safe_fetch(self.client.get_live_status)
        interfaces = self._safe_fetch(self.client.get_live_interfaces)
        logs = self._safe_fetch(
            self.client.get_live_logs,
            limit=min(12, self.settings.logs_limit),
        )

        logs_df = self._logs_frame(
            logs,
            categories={"runtime", "blocking", "detection"},
        ).head(12)
        summaries = {
            "runtime_label": humanize_runtime_status(status.get("status")),
            "uptime": format_duration_seconds(status.get("uptime_seconds", 0)),
            "interfaces": interfaces.get("interfaces", []),
        }
        return self._build_payload(
            health=health,
            status=status,
            dataframes={"logs": logs_df},
            summaries=summaries,
        )

    def get_runtime_control_payload(self) -> RuntimeControlPayload:
        health = self._safe_fetch(self.client.get_health)
        status = self._safe_fetch(self.client.get_live_status)
        interfaces = self._safe_fetch(self.client.get_live_interfaces)
        backend_status = normalize_backend_status(health.get("status"))
        status_error = status.get("error")
        interfaces_error = interfaces.get("error")
        backend_error = health.get("error") or status_error
        return RuntimeControlPayload(
            backend_ok=backend_status == "OK" and not status_error,
            backend_status="OK" if backend_status == "OK" and not status_error else "NOK",
            backend_error=str(backend_error) if backend_error else None,
            interfaces_error=str(interfaces_error) if interfaces_error else None,
            live_status=status,
            interfaces=list(interfaces.get("interfaces", [])),
        )

    def get_alerts_payload(self) -> PagePayload:
        health = self._safe_fetch(self.client.get_health)
        status = self._safe_fetch(self.client.get_live_status)
        alerts = self._safe_fetch(
            self.client.get_live_alerts,
            limit=self.settings.alerts_limit,
        )
        blocking = self._safe_fetch(
            self.client.get_live_blocking,
            limit=self.settings.blocking_limit,
        )

        alerts_df = self._alerts_frame(alerts)
        blocking_df = self._blocking_frame(blocking)
        severity_counts = alerts_df["Severite"].value_counts().to_dict() if not alerts_df.empty else {}
        summaries = {
            "critical_count": int(severity_counts.get("Critique", 0)),
            "high_count": int(severity_counts.get("Elevee", 0)),
            "medium_count": int(severity_counts.get("Moyenne", 0)),
            "unique_sources": int(alerts_df["Source"].nunique()) if not alerts_df.empty else 0,
            "recent_alert": alerts_df.iloc[0].to_dict() if not alerts_df.empty else {},
            "blocking_count": int(status.get("block_decisions", 0) or 0),
        }
        return self._build_payload(
            health=health,
            status=status,
            dataframes={"alerts": alerts_df, "blocking": blocking_df},
            summaries=summaries,
        )

    def get_events_payload(self) -> PagePayload:
        health = self._safe_fetch(self.client.get_health)
        status = self._safe_fetch(self.client.get_live_status)
        events = self._safe_fetch(
            self.client.get_live_events,
            limit=self.settings.events_limit,
        )

        events_df = self._events_frame(events)
        suspect_df = events_df[events_df["Label"] == "Suspect"] if not events_df.empty else events_df
        suspect_scores = (
            pd.to_numeric(suspect_df["Score"], errors="coerce").dropna()
            if not suspect_df.empty
            else pd.Series(dtype=float)
        )
        summaries = {
            "normal_count": int((events_df["Label"] == "Normal").sum()) if not events_df.empty else 0,
            "suspect_count": int((events_df["Label"] == "Suspect").sum()) if not events_df.empty else 0,
            "mean_suspect_score": format_score(suspect_scores.mean()) if not suspect_scores.empty else "0.00",
            "protocol_count": int(events_df["Proto"].nunique()) if not events_df.empty else 0,
            "selected_event": events_df.iloc[0].to_dict() if not events_df.empty else {},
        }
        return self._build_payload(
            health=health,
            status=status,
            dataframes={"events": events_df},
            summaries=summaries,
        )

    def get_journal_payload(self) -> PagePayload:
        health = self._safe_fetch(self.client.get_health)
        status = self._safe_fetch(self.client.get_live_status)
        events = self._safe_fetch(
            self.client.get_live_events,
            limit=min(60, self.settings.events_limit),
        )
        alerts = self._safe_fetch(
            self.client.get_live_alerts,
            limit=min(40, self.settings.alerts_limit),
        )
        blocking = self._safe_fetch(
            self.client.get_live_blocking,
            limit=min(40, self.settings.blocking_limit),
        )
        logs = self._safe_fetch(
            self.client.get_live_logs,
            limit=self.settings.logs_limit,
        )

        journal_df = self._journal_frame(
            events_payload=events,
            alerts_payload=alerts,
            blocking_payload=blocking,
            logs_payload=logs,
        )
        summaries = {
            "line_count": len(journal_df),
            "info_count": int((journal_df["Niveau"] == "INFO").sum()) if not journal_df.empty else 0,
            "alert_count": int(journal_df["Niveau"].isin(["ALERTE", "SUSPECT"]).sum()) if not journal_df.empty else 0,
            "blocking_count": int((journal_df["Niveau"] == "BLOCAGE").sum()) if not journal_df.empty else 0,
            "focus": journal_df.iloc[0].to_dict() if not journal_df.empty else {},
        }
        return self._build_payload(
            health=health,
            status=status,
            dataframes={"journal": journal_df},
            summaries=summaries,
        )

    def get_recent_alert_payload(self, *, since: str | None = None) -> RecentAlertPayload:
        pulse = self._safe_fetch(self.client.get_live_alerts_recent, since=since)
        backend_error = pulse.get("error")
        latest_alert = pulse.get("latest_alert")
        return RecentAlertPayload(
            backend_ok=backend_error is None,
            backend_error=str(backend_error) if backend_error else None,
            api_exposed_at=str(pulse.get("api_exposed_at")) if pulse.get("api_exposed_at") else None,
            total_available=int(pulse.get("total_available", 0) or 0),
            new_alert_count=int(pulse.get("new_alert_count", 0) or 0),
            latest_alert=latest_alert if isinstance(latest_alert, dict) else None,
        )

    def _build_payload(
        self,
        *,
        health: dict[str, Any],
        status: dict[str, Any],
        dataframes: dict[str, pd.DataFrame],
        summaries: dict[str, Any],
    ) -> PagePayload:
        backend_status = normalize_backend_status(health.get("status"))
        backend_error = health.get("error") or status.get("error")
        return PagePayload(
            backend_ok=backend_status == "OK",
            backend_status=backend_status,
            backend_error=str(backend_error) if backend_error else None,
            live_status=status,
            dataframes=dataframes,
            summaries=summaries,
        )

    @staticmethod
    def _safe_fetch(fn: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return fn(**kwargs)
        except BackendUnavailableError as exc:
            return {"status": "nok", "error": str(exc)}

    @staticmethod
    def _empty_frame(columns: list[str]) -> pd.DataFrame:
        return pd.DataFrame(columns=columns)

    def _events_frame(self, payload: dict[str, Any]) -> pd.DataFrame:
        records = payload.get("events", [])
        if not records:
            return self._empty_frame(
                ["Heure", "Label", "Score", "Proto", "Source", "Destination", "Port src", "Port dst", "Action", "Statut"]
            )
        rows: list[dict[str, Any]] = []
        for item in records:
            rows.append(
                {
                    "Horodatage": item.get("timestamp"),
                    "Heure": format_timestamp(item.get("timestamp")),
                    "Label": humanize_label(item.get("prediction_label")),
                    "Score": format_score(item.get("risk_score")),
                    "Proto": protocol_label(item.get("protocol")),
                    "Source": item.get("src_ip", "-"),
                    "Destination": item.get("dst_ip", "-"),
                    "Port src": item.get("src_port"),
                    "Port dst": item.get("dst_port"),
                    "Action": humanize_action(item.get("action_taken")),
                    "Statut": humanize_event_status(item.get("status")),
                }
            )
        df = pd.DataFrame(rows)
        return (
            df.sort_values("Horodatage", ascending=False)
            .drop(columns=["Horodatage"])
            .reset_index(drop=True)
        )

    def _alerts_frame(self, payload: dict[str, Any]) -> pd.DataFrame:
        records = payload.get("alerts", [])
        if not records:
            return self._empty_frame(
                ["Heure", "Severite", "Type", "Source", "Destination", "Action", "Statut", "Score"]
            )
        rows: list[dict[str, Any]] = []
        for item in records:
            rows.append(
                {
                    "Horodatage": item.get("timestamp"),
                    "Heure": format_timestamp(item.get("timestamp")),
                    "Severite": humanize_severity(item.get("severity")),
                    "Type": item.get("attack_type", "-"),
                    "Source": item.get("src_ip", "-"),
                    "Destination": item.get("dst_ip", "-"),
                    "Action": humanize_action(item.get("action_taken")),
                    "Statut": humanize_event_status(item.get("status")),
                    "Score": format_score(item.get("risk_score")),
                }
            )
        df = pd.DataFrame(rows)
        return (
            df.sort_values("Horodatage", ascending=False)
            .drop(columns=["Horodatage"])
            .reset_index(drop=True)
        )

    def _blocking_frame(self, payload: dict[str, Any]) -> pd.DataFrame:
        records = payload.get("blocking_events", [])
        if not records:
            return self._empty_frame(
                ["Heure", "Source", "Destination", "Proto", "Confiance", "Action", "Statut"]
            )
        rows: list[dict[str, Any]] = []
        for item in records:
            rows.append(
                {
                    "Horodatage": item.get("timestamp"),
                    "Heure": format_timestamp(item.get("timestamp")),
                    "Source": item.get("src_ip", "-"),
                    "Destination": item.get("dst_ip", "-"),
                    "Proto": protocol_label(item.get("protocol")),
                    "Confiance": format_score(item.get("confidence")),
                    "Action": "Blocage" if item.get("triggered") else "Alerte",
                    "Statut": humanize_event_status(item.get("status")),
                }
            )
        df = pd.DataFrame(rows)
        return (
            df.sort_values("Horodatage", ascending=False)
            .drop(columns=["Horodatage"])
            .reset_index(drop=True)
        )

    def _logs_frame(
        self,
        payload: dict[str, Any],
        *,
        categories: set[str] | None = None,
    ) -> pd.DataFrame:
        records = payload.get("logs", [])
        if not records:
            return self._empty_frame(["Heure", "Niveau", "Type", "Message"])
        rows: list[dict[str, Any]] = []
        for item in records:
            category = str(item.get("category", "")).lower()
            if categories is not None and category not in categories:
                continue
            rows.append(
                {
                    "Horodatage": item.get("timestamp"),
                    "Heure": format_timestamp(item.get("timestamp")),
                    "Niveau": str(item.get("level", "INFO")).upper(),
                    "Type": item.get("component", "-"),
                    "Message": item.get("message", "-"),
                }
            )
        if not rows:
            return self._empty_frame(["Heure", "Niveau", "Type", "Message"])
        df = pd.DataFrame(rows)
        return (
            df.sort_values("Horodatage", ascending=False)
            .drop(columns=["Horodatage"])
            .reset_index(drop=True)
        )

    def _journal_frame(
        self,
        *,
        events_payload: dict[str, Any],
        alerts_payload: dict[str, Any],
        blocking_payload: dict[str, Any],
        logs_payload: dict[str, Any],
    ) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []

        for item in logs_payload.get("logs", []):
            level = str(item.get("level", "INFO")).upper()
            rows.append(
                {
                    "Horodatage": item.get("timestamp"),
                    "Heure": format_timestamp(item.get("timestamp")),
                    "Niveau": level,
                    "Type": item.get("category", "runtime").title(),
                    "Message": item.get("message", "-"),
                }
            )
        for item in events_payload.get("events", []):
            label = humanize_label(item.get("prediction_label"))
            level = "NORMAL" if label == "Normal" else "SUSPECT"
            rows.append(
                {
                    "Horodatage": item.get("timestamp"),
                    "Heure": format_timestamp(item.get("timestamp")),
                    "Niveau": level,
                    "Type": "Prediction",
                    "Message": (
                        f"{label} {protocol_label(item.get('protocol'))} "
                        f"{item.get('src_ip', '-')} -> {item.get('dst_ip', '-')}"
                    ),
                }
            )
        for item in alerts_payload.get("alerts", []):
            rows.append(
                {
                    "Horodatage": item.get("timestamp"),
                    "Heure": format_timestamp(item.get("timestamp")),
                    "Niveau": "ALERTE",
                    "Type": "Detection",
                    "Message": item.get("description", "-"),
                }
            )
        for item in blocking_payload.get("blocking_events", []):
            rows.append(
                {
                    "Horodatage": item.get("timestamp"),
                    "Heure": format_timestamp(item.get("timestamp")),
                    "Niveau": "BLOCAGE" if item.get("triggered") else "ACTION",
                    "Type": "Action",
                    "Message": item.get("reason", "-"),
                }
            )

        if not rows:
            return self._empty_frame(["Heure", "Niveau", "Type", "Message"])

        df = pd.DataFrame(rows)
        df["Horodatage"] = pd.to_datetime(df["Horodatage"], errors="coerce")
        return (
            df.sort_values("Horodatage", ascending=False)
            .drop(columns=["Horodatage"])
            .reset_index(drop=True)
        )


def build_live_provider(settings: DashboardSettings | None = None) -> LiveProvider:
    resolved_settings = settings or get_dashboard_settings()
    client = BackendClient(
        resolved_settings.backend_base_url,
        timeout=resolved_settings.request_timeout_seconds,
    )
    return LiveProvider(client=client, settings=resolved_settings)


def fetch_overview_payload(settings: DashboardSettings | None = None) -> PagePayload:
    provider = build_live_provider(settings)
    try:
        return provider.get_overview_payload()
    finally:
        provider.client.close()


def fetch_runtime_payload(settings: DashboardSettings | None = None) -> PagePayload:
    provider = build_live_provider(settings)
    try:
        return provider.get_runtime_payload()
    finally:
        provider.client.close()


def fetch_runtime_control_payload(settings: DashboardSettings | None = None) -> RuntimeControlPayload:
    provider = build_live_provider(settings)
    try:
        return provider.get_runtime_control_payload()
    finally:
        provider.client.close()


def fetch_alerts_payload(settings: DashboardSettings | None = None) -> PagePayload:
    provider = build_live_provider(settings)
    try:
        return provider.get_alerts_payload()
    finally:
        provider.client.close()


def fetch_events_payload(settings: DashboardSettings | None = None) -> PagePayload:
    provider = build_live_provider(settings)
    try:
        return provider.get_events_payload()
    finally:
        provider.client.close()


def fetch_journal_payload(settings: DashboardSettings | None = None) -> PagePayload:
    provider = build_live_provider(settings)
    try:
        return provider.get_journal_payload()
    finally:
        provider.client.close()


def fetch_recent_alert_payload(
    settings: DashboardSettings | None = None,
    *,
    since: str | None = None,
) -> RecentAlertPayload:
    provider = build_live_provider(settings)
    try:
        return provider.get_recent_alert_payload(since=since)
    finally:
        provider.client.close()


def fetch_live_interfaces(settings: DashboardSettings | None = None) -> list[dict[str, Any]]:
    provider = build_live_provider(settings)
    try:
        payload = provider._safe_fetch(provider.client.get_live_interfaces)
        return list(payload.get("interfaces", []))
    finally:
        provider.client.close()


def start_live_capture(
    *,
    interface_name: str | None,
    capture_filter: str | None,
    settings: DashboardSettings | None = None,
) -> dict[str, Any]:
    provider = build_live_provider(settings)
    try:
        return provider.client.start_live_monitoring(
            interface_name=interface_name,
            capture_filter=capture_filter,
        )
    finally:
        provider.client.close()


def stop_live_capture(settings: DashboardSettings | None = None) -> dict[str, Any]:
    provider = build_live_provider(settings)
    try:
        return provider.client.stop_live_monitoring()
    finally:
        provider.client.close()
