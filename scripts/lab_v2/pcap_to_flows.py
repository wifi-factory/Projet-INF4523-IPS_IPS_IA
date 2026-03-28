from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from backend.app.config import build_settings
from backend.app.services.flow_aggregation_service import FlowAggregationService
from backend.app.services.live_capture_service import TSHARK_FIELDS, LiveCaptureService


DISPLAY_FILTER = "ip and not arp and not dhcp and not bootp"


def resolve_tshark(tshark_path: str) -> str:
    candidate = Path(tshark_path)
    if candidate.exists():
        return str(candidate)
    resolved = shutil.which(tshark_path)
    if resolved:
        return resolved
    raise FileNotFoundError(f"tshark executable not found: {tshark_path}")


def build_tshark_read_command(executable: str, pcap_path: Path) -> list[str]:
    command = [
        executable,
        "-r",
        str(pcap_path),
        "-n",
        "-Y",
        DISPLAY_FILTER,
        "-T",
        "fields",
        "-E",
        "header=n",
        "-E",
        "separator=,",
        "-E",
        "quote=d",
    ]
    for field in TSHARK_FIELDS:
        command.extend(["-e", field])
    return command


def scenario_defaults(scenario_id: str) -> tuple[str, str | None]:
    mapping = {
        "N01": ("normal_icmp", None),
        "N02": ("normal_http", None),
        "N03": ("normal_http", None),
        "N06": ("normal_dns", None),
        "N07": ("normal_bulk_tcp", None),
        "N11": ("normal_wget", None),
        "N20": ("normal_http_short", None),
        "N21": ("normal_http_short", None),
        "N22": ("normal_dns_burst", None),
        "N23": ("normal_ssh_short", None),
        "N24": ("normal_wget_burst", None),
        "N25": ("normal_bulk_tcp", None),
        "N30": ("normal_https_short", None),
        "N31": ("normal_https_download", None),
        "N35": ("normal_scp", None),
        "N36": ("normal_admin_mixed", None),
        "S01": ("scan_syn", "medium"),
        "S02": ("scan_connect", "medium"),
        "S03": ("scan_udp", "medium"),
        "S05": ("syn_burst", "high"),
        "S06": ("icmp_burst", "high"),
        "S20": ("scan_syn_large", "medium"),
        "S21": ("scan_connect_large", "medium"),
        "S22": ("scan_udp_large", "medium"),
        "S23": ("syn_burst_multiport", "high"),
        "S24": ("failed_connection_burst", "medium"),
        "S25": ("scan_syn_slow", "medium"),
        "S30": ("ssh_bruteforce_light", "medium"),
        "S31": ("web_probe_https", "medium"),
    }
    return mapping.get(scenario_id, ("unknown", None))


def load_manifest(manifest_path: Path) -> dict[str, dict[str, str]]:
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {row["pcap_name"]: row for row in reader}


def iter_pcap_packets(tshark_executable: str, pcap_path: Path) -> Iterable:
    command = build_tshark_read_command(tshark_executable, pcap_path)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        packet = LiveCaptureService.parse_packet_line(line)
        if packet is not None:
            yield packet
    stderr = ""
    if process.stderr is not None:
        stderr = process.stderr.read()
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(
            f"tshark failed for {pcap_path.name}: {stderr.strip() or 'unknown error'}"
        )


def is_control_plane_packet(
    packet,
    *,
    manifest_row: dict[str, str],
    kali_lab_host: str,
) -> bool:
    if manifest_row.get("label_binary") != "normal":
        return False
    source_host = manifest_row.get("source_host", "").strip()
    if not source_host or source_host == kali_lab_host:
        return False
    endpoint_set = {packet.src_ip, packet.dst_ip}
    if endpoint_set != {source_host, kali_lab_host}:
        return False
    if packet.protocol != "TCP":
        return False
    return 22 in {packet.src_port, packet.dst_port}


def convert_capture(
    *,
    tshark_executable: str,
    campaign_id: str,
    pcap_path: Path,
    manifest_row: dict[str, str],
    kali_lab_host: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    settings = build_settings()
    capture_id = pcap_path.stem
    aggregator = FlowAggregationService(
        settings,
        session_id=campaign_id,
        capture_id=capture_id,
    )

    completed_rows: list[dict[str, object]] = []
    packet_count = 0
    for packet in iter_pcap_packets(tshark_executable, pcap_path):
        if is_control_plane_packet(packet, manifest_row=manifest_row, kali_lab_host=kali_lab_host):
            continue
        packet_count += 1
        completed_rows.extend(aggregator.ingest_packet(packet))
    completed_rows.extend(aggregator.flush_all())

    prepared = aggregator.prepare_rows(completed_rows)
    scenario_id = manifest_row.get("scenario_id", "UNKNOWN")
    scenario_family, default_severity = scenario_defaults(scenario_id)
    label_binary = manifest_row.get("label_binary", "unknown")
    severity = manifest_row.get("severity") or default_severity

    if not prepared.empty:
        prepared["scenario_id"] = scenario_id
        prepared["scenario_family"] = manifest_row.get("scenario_family") or scenario_family
        prepared["label_binary"] = label_binary
        prepared["label_family"] = prepared["scenario_family"]
        prepared["severity"] = severity
        prepared["capture_id"] = capture_id
        prepared["session_id"] = campaign_id

    summary = {
        "campaign_id": campaign_id,
        "capture_id": capture_id,
        "pcap_name": pcap_path.name,
        "scenario_id": scenario_id,
        "scenario_family": manifest_row.get("scenario_family") or scenario_family,
        "label_binary": label_binary,
        "packet_count": packet_count,
        "flow_count": int(len(prepared)),
        "status": manifest_row.get("status", "unknown"),
        "source_host": manifest_row.get("source_host"),
        "target_host": manifest_row.get("target_host"),
        "started_at_utc": manifest_row.get("started_at_utc"),
        "notes": manifest_row.get("notes"),
    }
    return prepared, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert lab_v2 campaign pcaps to flow-level parquet using the live aggregation logic.")
    parser.add_argument("--campaign-dir", required=True, help="Path to a raw campaign directory containing pcaps and manifest.csv")
    parser.add_argument(
        "--output-dir",
        default=str(Path("data") / "lab_v2" / "processed"),
        help="Root directory for processed outputs.",
    )
    parser.add_argument(
        "--tshark-path",
        default=None,
        help="Optional tshark executable path. Defaults to IPS_LIVE_TSHARK_PATH or settings.",
    )
    parser.add_argument("--kali-lab-host", default="172.30.1.20", help="Lab IP used by Kali on PentestNet.")
    args = parser.parse_args()

    settings = build_settings()
    tshark_executable = resolve_tshark(args.tshark_path or settings.live_tshark_path)

    campaign_dir = Path(args.campaign_dir).resolve()
    manifest_path = campaign_dir / "manifest.csv"
    if not manifest_path.exists():
      raise FileNotFoundError(f"manifest.csv not found in {campaign_dir}")

    output_root = Path(args.output_dir).resolve()
    campaign_output_dir = output_root / campaign_dir.name
    campaign_output_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(manifest_path)
    all_frames: list[pd.DataFrame] = []
    summaries: list[dict[str, object]] = []

    for pcap_path in sorted(campaign_dir.glob("*.pcap")):
        row = manifest.get(pcap_path.name, {})
        frame, summary = convert_capture(
            tshark_executable=tshark_executable,
            campaign_id=campaign_dir.name,
            pcap_path=pcap_path,
            manifest_row=row,
            kali_lab_host=args.kali_lab_host,
        )
        summaries.append(summary)
        if not frame.empty:
            all_frames.append(frame)

    if all_frames:
        combined = pd.concat(all_frames, ignore_index=True, sort=False)
    else:
        combined = pd.DataFrame()

    flows_path = campaign_output_dir / "flows.parquet"
    summary_path = campaign_output_dir / "capture_summary.csv"
    stats_path = campaign_output_dir / "stats.json"

    if not combined.empty:
        combined.to_parquet(flows_path, index=False)
    pd.DataFrame(summaries).to_csv(summary_path, index=False)
    stats_path.write_text(
        json.dumps(
            {
                "campaign_id": campaign_dir.name,
                "capture_count": len(summaries),
                "flow_count": int(len(combined)),
                "label_counts": (
                    pd.DataFrame(summaries)["label_binary"].value_counts().to_dict()
                    if summaries
                    else {}
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Processed campaign: {campaign_dir.name}")
    print(f"Flows parquet: {flows_path}")
    print(f"Capture summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
