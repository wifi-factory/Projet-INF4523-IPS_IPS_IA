from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable

from ..config import Settings
from ..core.exceptions import CaptureError
from ..core.logging import get_logger
from .flow_aggregation_service import PacketEvent, protocol_name


TSHARK_FIELDS = [
    "frame.time_epoch",
    "ip.src",
    "ip.dst",
    "tcp.srcport",
    "udp.srcport",
    "tcp.dstport",
    "udp.dstport",
    "ip.proto",
    "frame.len",
    "tcp.flags.syn",
    "tcp.flags.ack",
    "tcp.flags.reset",
    "tcp.flags.fin",
    "tcp.flags.push",
    "icmp.type",
]
INTERFACE_RE = re.compile(r"^\s*(?P<index>\d+)\.\s+(?P<label>.+?)\s*$")


def to_int(value: object, default: int = 0) -> int:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return int(float(text))
    except Exception:
        return default


def to_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return float(text)
    except Exception:
        return default


class TsharkCaptureSession:
    def __init__(
        self,
        *,
        process: subprocess.Popen[str],
        reader_thread: threading.Thread,
        stderr_thread: threading.Thread,
        stop_event: threading.Event,
    ) -> None:
        self._process = process
        self._reader_thread = reader_thread
        self._stderr_thread = stderr_thread
        self._stop_event = stop_event

    def stop(self) -> None:
        self._stop_event.set()
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=3.0)
        self._reader_thread.join(timeout=3.0)
        self._stderr_thread.join(timeout=3.0)

    def is_alive(self) -> bool:
        return self._reader_thread.is_alive()


class LiveCaptureService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(self.__class__.__name__)

    def list_interfaces(self) -> list[tuple[str, str]]:
        executable = self._resolve_tshark_executable()
        process = subprocess.run(
            [executable, "-D"],
            capture_output=True,
            text=True,
            check=False,
        )
        if process.returncode != 0:
            raise CaptureError(
                process.stderr.strip()
                or "Unable to list tshark interfaces."
            )

        interfaces: list[tuple[str, str]] = []
        for line in process.stdout.splitlines():
            match = INTERFACE_RE.match(line)
            if not match:
                continue
            interfaces.append((match.group("index"), line.strip()))
        return interfaces

    def start_session(
        self,
        *,
        interface_name: str,
        on_packet: Callable[[PacketEvent], None],
        on_error: Callable[[str], None],
        on_parse_error: Callable[[str], None] | None = None,
        capture_filter: str | None = None,
    ) -> TsharkCaptureSession:
        executable = self._resolve_tshark_executable()
        command = self._build_command(
            executable=executable,
            interface_name=interface_name,
            capture_filter=capture_filter or self.settings.live_capture_filter,
        )

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except Exception as exc:  # pragma: no cover - platform subprocess details
            raise CaptureError(f"Unable to start tshark capture: {exc}") from exc

        stop_event = threading.Event()

        def consume_stdout() -> None:
            try:
                assert process.stdout is not None
                for line in process.stdout:
                    if stop_event.is_set():
                        break
                    packet = self.parse_packet_line(line)
                    if packet is None:
                        if on_parse_error is not None:
                            on_parse_error("Unable to parse tshark packet line.")
                        continue
                    on_packet(packet)
            except Exception as exc:
                on_error(f"Live capture reader failed: {exc}")
            finally:
                stop_event.set()

        def consume_stderr() -> None:
            try:
                assert process.stderr is not None
                for line in process.stderr:
                    if stop_event.is_set():
                        break
                    message = line.strip()
                    if message:
                        lowered = message.lower()
                        if any(token in lowered for token in ("error", "failed", "invalid")):
                            on_error(message)
                        else:
                            self.logger.info(
                                "tshark stderr",
                                extra={"context": {"message": message}},
                            )
            finally:
                stop_event.set()

        reader_thread = threading.Thread(target=consume_stdout, daemon=True)
        stderr_thread = threading.Thread(target=consume_stderr, daemon=True)
        reader_thread.start()
        stderr_thread.start()

        self.logger.info(
            "Live capture session started",
            extra={
                "context": {
                    "interface_name": interface_name,
                    "capture_filter": capture_filter or self.settings.live_capture_filter,
                    "command": command,
                }
            },
        )
        return TsharkCaptureSession(
            process=process,
            reader_thread=reader_thread,
            stderr_thread=stderr_thread,
            stop_event=stop_event,
        )

    @staticmethod
    def parse_packet_line(line: str) -> PacketEvent | None:
        reader = csv.reader(io.StringIO(line))
        fields = next(reader, None)
        if not fields or len(fields) < len(TSHARK_FIELDS):
            return None

        timestamp = to_float(fields[0], default=-1.0)
        src_ip = fields[1].strip()
        dst_ip = fields[2].strip()
        if timestamp < 0 or not src_ip or not dst_ip:
            return None

        tcp_src = to_int(fields[3])
        udp_src = to_int(fields[4])
        tcp_dst = to_int(fields[5])
        udp_dst = to_int(fields[6])
        protocol = protocol_name(to_int(fields[7], -1))
        if protocol == "TCP":
            src_port, dst_port = tcp_src, tcp_dst
        elif protocol == "UDP":
            src_port, dst_port = udp_src, udp_dst
        else:
            src_port, dst_port = 0, 0

        return PacketEvent(
            timestamp=timestamp,
            src_ip=src_ip,
            dst_ip=dst_ip,
            src_port=src_port,
            dst_port=dst_port,
            protocol=protocol,
            packet_length=to_int(fields[8]),
            syn=to_int(fields[9]),
            ack=to_int(fields[10]),
            rst=to_int(fields[11]),
            fin=to_int(fields[12]),
            psh=to_int(fields[13]),
            icmp_type=to_int(fields[14], -1),
        )

    def _resolve_tshark_executable(self) -> str:
        configured = self.settings.live_tshark_path
        candidate = Path(configured)
        if candidate.exists():
            return str(candidate)

        resolved = shutil.which(configured)
        if resolved:
            return resolved

        raise CaptureError(
            f"tshark executable not found: {configured}. "
            "Install Wireshark/tshark or set IPS_LIVE_TSHARK_PATH."
        )

    @staticmethod
    def _build_command(
        *,
        executable: str,
        interface_name: str,
        capture_filter: str,
    ) -> list[str]:
        command = [
            executable,
            "-l",
            "-n",
            "-Q",
            "-i",
            interface_name,
        ]
        if capture_filter:
            command.extend(["-f", capture_filter])
        command.extend(["-Y", "ip and not arp and not dhcp and not bootp"])
        command.extend(
            [
                "-T",
                "fields",
                "-E",
                "header=n",
                "-E",
                "separator=,",
                "-E",
                "quote=d",
            ]
        )
        for field in TSHARK_FIELDS:
            command.extend(["-e", field])
        return command
