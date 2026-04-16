from __future__ import annotations

from typing import Any

import httpx


class BackendUnavailableError(RuntimeError):
    """Erreur de connectivite backend."""


class BackendClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self._client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BackendUnavailableError(str(exc)) from exc

    def _post(self, path: str, *, json_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=json_payload)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BackendUnavailableError(str(exc)) from exc

    def get_health(self) -> dict[str, Any]:
        return self._get("/health")

    def get_live_interfaces(self) -> dict[str, Any]:
        return self._get("/live/interfaces")

    def get_live_status(self) -> dict[str, Any]:
        return self._get("/live/status")

    def get_live_events(self, *, limit: int) -> dict[str, Any]:
        return self._get("/live/events", params={"limit": limit})

    def get_live_alerts(self, *, limit: int) -> dict[str, Any]:
        return self._get("/live/alerts", params={"limit": limit})

    def get_live_alerts_recent(self, *, since: str | None = None) -> dict[str, Any]:
        params = {"since": since} if since else None
        return self._get("/live/alerts/recent", params=params)

    def get_live_blocking(self, *, limit: int) -> dict[str, Any]:
        return self._get("/live/blocking", params={"limit": limit})

    def get_live_logs(self, *, limit: int) -> dict[str, Any]:
        return self._get("/live/logs", params={"limit": limit})

    def start_live_monitoring(
        self,
        *,
        interface_name: str | None,
        capture_filter: str | None,
    ) -> dict[str, Any]:
        payload = {
            "interface_name": interface_name,
            "capture_filter": capture_filter,
        }
        return self._post("/live/start", json_payload=payload)

    def stop_live_monitoring(self) -> dict[str, Any]:
        return self._post("/live/stop", json_payload={})
