from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from ..config import Settings
from ..core.logging import get_logger


PROTO_MAP = {1: "ICMP", 6: "TCP", 17: "UDP"}


def protocol_name(proto_num: int) -> str:
    return PROTO_MAP.get(proto_num, f"IP_{proto_num}")


@dataclass(frozen=True)
class PacketEvent:
    timestamp: float
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    packet_length: int
    syn: int = 0
    ack: int = 0
    rst: int = 0
    fin: int = 0
    psh: int = 0
    icmp_type: int = -1


@dataclass
class FlowState:
    capture_id: str
    session_id: str
    protocol: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    start_ts: float
    end_ts: float
    last_ts: float
    packet_count_total: int = 0
    packet_count_fwd: int = 0
    packet_count_bwd: int = 0
    byte_count_total: int = 0
    byte_count_fwd: int = 0
    byte_count_bwd: int = 0
    pkt_len_min: int = 10**9
    pkt_len_max: int = 0
    pkt_len_sum: float = 0.0
    pkt_len_sq_sum: float = 0.0
    iat_count: int = 0
    iat_min_ms: float = 10**12
    iat_max_ms: float = 0.0
    iat_sum_ms: float = 0.0
    iat_sq_sum_ms: float = 0.0
    syn_count: int = 0
    ack_count: int = 0
    rst_count: int = 0
    fin_count: int = 0
    psh_count: int = 0
    icmp_echo_req_count: int = 0
    icmp_echo_reply_count: int = 0

    def update(self, packet: PacketEvent, direction: str) -> None:
        if packet.timestamp > self.last_ts:
            iat_ms = (packet.timestamp - self.last_ts) * 1000.0
            self.iat_count += 1
            self.iat_min_ms = min(self.iat_min_ms, iat_ms)
            self.iat_max_ms = max(self.iat_max_ms, iat_ms)
            self.iat_sum_ms += iat_ms
            self.iat_sq_sum_ms += iat_ms * iat_ms

        self.last_ts = packet.timestamp
        self.end_ts = packet.timestamp
        self.packet_count_total += 1
        self.byte_count_total += packet.packet_length
        self.pkt_len_min = min(self.pkt_len_min, packet.packet_length)
        self.pkt_len_max = max(self.pkt_len_max, packet.packet_length)
        self.pkt_len_sum += packet.packet_length
        self.pkt_len_sq_sum += packet.packet_length * packet.packet_length

        if direction == "fwd":
            self.packet_count_fwd += 1
            self.byte_count_fwd += packet.packet_length
        else:
            self.packet_count_bwd += 1
            self.byte_count_bwd += packet.packet_length

        self.syn_count += packet.syn
        self.ack_count += packet.ack
        self.rst_count += packet.rst
        self.fin_count += packet.fin
        self.psh_count += packet.psh
        if packet.icmp_type == 8:
            self.icmp_echo_req_count += 1
        elif packet.icmp_type == 0:
            self.icmp_echo_reply_count += 1

    def finalize(self, flow_index: int) -> dict[str, Any]:
        packet_mean = self.pkt_len_sum / max(1, self.packet_count_total)
        packet_variance = max(
            0.0,
            (self.pkt_len_sq_sum / max(1, self.packet_count_total)) - (packet_mean**2),
        )
        packet_std = math.sqrt(packet_variance)

        if self.iat_count:
            iat_mean = self.iat_sum_ms / self.iat_count
            iat_variance = max(
                0.0,
                (self.iat_sq_sum_ms / self.iat_count) - (iat_mean**2),
            )
            iat_std = math.sqrt(iat_variance)
            iat_min = self.iat_min_ms
            iat_max = self.iat_max_ms
        else:
            iat_mean = 0.0
            iat_std = 0.0
            iat_min = 0.0
            iat_max = 0.0

        return {
            "flow_id": f"{self.capture_id}__{flow_index:06d}",
            "capture_id": self.capture_id,
            "session_id": self.session_id,
            "scenario_id": "LIVE",
            "scenario_family": "live",
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "start_time": datetime.fromtimestamp(self.start_ts, UTC).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_ts, UTC).isoformat(),
            "protocol": self.protocol,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "duration_ms": round((self.end_ts - self.start_ts) * 1000.0, 3),
            "packet_count_total": self.packet_count_total,
            "packet_count_fwd": self.packet_count_fwd,
            "packet_count_bwd": self.packet_count_bwd,
            "byte_count_total": self.byte_count_total,
            "byte_count_fwd": self.byte_count_fwd,
            "byte_count_bwd": self.byte_count_bwd,
            "pkt_len_min": 0 if self.packet_count_total == 0 else self.pkt_len_min,
            "pkt_len_max": self.pkt_len_max,
            "pkt_len_mean": round(packet_mean, 6),
            "pkt_len_std": round(packet_std, 6),
            "iat_min_ms": round(iat_min, 6),
            "iat_max_ms": round(iat_max, 6),
            "iat_mean_ms": round(iat_mean, 6),
            "iat_std_ms": round(iat_std, 6),
            "syn_count": self.syn_count,
            "ack_count": self.ack_count,
            "rst_count": self.rst_count,
            "fin_count": self.fin_count,
            "psh_count": self.psh_count,
            "icmp_echo_req_count": self.icmp_echo_req_count,
            "icmp_echo_reply_count": self.icmp_echo_reply_count,
            "connections_per_1s": 0,
            "connections_per_5s": 0,
            "distinct_dst_ports_per_5s": 0,
            "distinct_dst_ips_per_5s": 0,
            "icmp_packets_per_1s": 0,
            "failed_connection_ratio": 0.0,
            "label_family": None,
            "severity": None,
        }


class FlowAggregationService:
    def __init__(
        self,
        settings: Settings,
        *,
        session_id: str,
        capture_id: str,
    ) -> None:
        self.settings = settings
        self.session_id = session_id
        self.capture_id = capture_id
        self.logger = get_logger(self.__class__.__name__)
        self._active: dict[tuple[Any, ...], FlowState] = {}
        self._flow_index = 0
        self._context_frame = pd.DataFrame()

    def ingest_packet(self, packet: PacketEvent) -> list[dict[str, Any]]:
        completed = self.expire_flows(packet.timestamp)
        key = self._build_key(packet)
        flow = self._active.get(key)
        timeout = self._timeout_for_protocol(packet.protocol)

        if flow is None or (packet.timestamp - flow.last_ts) > timeout:
            if flow is not None:
                completed.append(self._finalize_flow(key))
            flow = self._new_flow(packet)
            self._active[key] = flow

        direction = (
            "fwd"
            if (
                packet.src_ip,
                packet.src_port,
                packet.dst_ip,
                packet.dst_port,
            )
            == (flow.src_ip, flow.src_port, flow.dst_ip, flow.dst_port)
            else "bwd"
        )
        flow.update(packet, direction)

        if self._should_finalize_immediately(flow, packet):
            completed.append(self._finalize_flow(key))

        return completed

    def expire_flows(self, current_ts: float | None = None) -> list[dict[str, Any]]:
        now = current_ts if current_ts is not None else datetime.now(UTC).timestamp()
        completed: list[dict[str, Any]] = []
        for key, flow in list(self._active.items()):
            timeout = self._timeout_for_protocol(flow.protocol)
            expired = (now - flow.last_ts) > timeout
            too_long = (now - flow.start_ts) > self.settings.live_max_flow_duration_seconds
            if expired or too_long:
                completed.append(self._finalize_flow(key))
        return completed

    def flush_all(self) -> list[dict[str, Any]]:
        completed: list[dict[str, Any]] = []
        for key in list(self._active):
            completed.append(self._finalize_flow(key))
        return completed

    def prepare_rows(self, rows: list[dict[str, Any]]) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame()

        new_rows = pd.DataFrame(rows).copy()
        new_rows["_is_new"] = 1
        if self._context_frame.empty:
            combined = new_rows
        else:
            context_rows = self._context_frame.copy()
            context_rows["_is_new"] = 0
            combined = pd.concat([context_rows, new_rows], ignore_index=True, sort=False)

        combined = self._add_window_features(combined)
        prepared = (
            combined.loc[combined["_is_new"].eq(1)]
            .drop(columns=["_is_new"])
            .reset_index(drop=True)
        )

        max_ts = float(combined["start_ts"].max())
        self._context_frame = (
            combined.loc[combined["start_ts"] >= max_ts - 5.1]
            .drop(columns=["_is_new"])
            .reset_index(drop=True)
        )
        return prepared

    def active_flow_count(self) -> int:
        return len(self._active)

    def _build_key(self, packet: PacketEvent) -> tuple[Any, ...]:
        endpoint_a = (packet.src_ip, packet.src_port)
        endpoint_b = (packet.dst_ip, packet.dst_port)
        canon_a, canon_b = sorted([endpoint_a, endpoint_b])
        return (packet.protocol, canon_a[0], canon_a[1], canon_b[0], canon_b[1])

    def _new_flow(self, packet: PacketEvent) -> FlowState:
        return FlowState(
            capture_id=self.capture_id,
            session_id=self.session_id,
            protocol=packet.protocol,
            src_ip=packet.src_ip,
            dst_ip=packet.dst_ip,
            src_port=packet.src_port,
            dst_port=packet.dst_port,
            start_ts=packet.timestamp,
            end_ts=packet.timestamp,
            last_ts=packet.timestamp,
        )

    def _finalize_flow(self, key: tuple[Any, ...]) -> dict[str, Any]:
        flow = self._active.pop(key)
        row = flow.finalize(self._flow_index)
        self._flow_index += 1
        self.logger.info(
            "Flow finalized",
            extra={
                "context": {
                    "flow_id": row["flow_id"],
                    "protocol": row["protocol"],
                    "src_ip": row["src_ip"],
                    "dst_ip": row["dst_ip"],
                    "duration_ms": row["duration_ms"],
                    "packet_count_total": row["packet_count_total"],
                }
            },
        )
        return row

    def _timeout_for_protocol(self, protocol: str) -> float:
        mapping = {
            "TCP": self.settings.live_tcp_idle_timeout_seconds,
            "UDP": self.settings.live_udp_idle_timeout_seconds,
            "ICMP": self.settings.live_icmp_idle_timeout_seconds,
        }
        return mapping.get(protocol, self.settings.live_udp_idle_timeout_seconds)

    def _should_finalize_immediately(self, flow: FlowState, packet: PacketEvent) -> bool:
        if flow.protocol == "TCP" and (packet.fin > 0 or packet.rst > 0):
            return True
        return (
            (flow.end_ts - flow.start_ts)
            >= self.settings.live_max_flow_duration_seconds
        )

    @staticmethod
    def _add_window_features(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame.copy()

        frame = frame.sort_values(["session_id", "src_ip", "start_ts"]).reset_index(drop=True)
        connections_1s = [0] * len(frame)
        connections_5s = [0] * len(frame)
        distinct_ports_5s = [0] * len(frame)
        distinct_ips_5s = [0] * len(frame)
        icmp_packets_1s = [0] * len(frame)

        for _, indices in frame.groupby(["session_id", "src_ip"], sort=False).groups.items():
            positions = list(indices)
            times = frame.loc[positions, "start_ts"].tolist()
            dst_ports = frame.loc[positions, "dst_port"].tolist()
            dst_ips = frame.loc[positions, "dst_ip"].tolist()
            protocols = frame.loc[positions, "protocol"].tolist()
            packet_counts = frame.loc[positions, "packet_count_total"].tolist()

            left_1s = 0
            left_5s = 0
            for local_index, global_index in enumerate(positions):
                current_ts = times[local_index]
                while current_ts - times[left_1s] > 1.0:
                    left_1s += 1
                while current_ts - times[left_5s] > 5.0:
                    left_5s += 1

                window_1s = range(left_1s, local_index + 1)
                window_5s = range(left_5s, local_index + 1)
                connections_1s[global_index] = len(list(window_1s))
                connections_5s[global_index] = len(list(window_5s))
                distinct_ports_5s[global_index] = len({dst_ports[item] for item in window_5s})
                distinct_ips_5s[global_index] = len({dst_ips[item] for item in window_5s})
                icmp_packets_1s[global_index] = sum(
                    packet_counts[item]
                    for item in window_1s
                    if protocols[item] == "ICMP"
                )

        frame["connections_per_1s"] = connections_1s
        frame["connections_per_5s"] = connections_5s
        frame["distinct_dst_ports_per_5s"] = distinct_ports_5s
        frame["distinct_dst_ips_per_5s"] = distinct_ips_5s
        frame["icmp_packets_per_1s"] = icmp_packets_1s
        frame["failed_connection_ratio"] = frame.apply(
            lambda row: round(
                1.0
                if (
                    row["protocol"] == "TCP"
                    and row["syn_count"] > 0
                    and row["ack_count"] == 0
                )
                else (
                    min(1.0, row["rst_count"] / max(1, row["syn_count"]))
                    if row["protocol"] == "TCP"
                    else 0.0
                ),
                6,
            ),
            axis=1,
        )
        return frame
