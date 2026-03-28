from __future__ import annotations

import platform
import shlex
import subprocess


def build_firewall_command_preview(
    *,
    source_ip: str | None,
    destination_ip: str | None,
    protocol: str | None,
    source_port: int | None,
    destination_port: int | None,
) -> str | None:
    proto = protocol.lower() if protocol else None

    if source_ip:
        return f"iptables -I INPUT 1 -s {source_ip} -j DROP"
    if destination_ip and proto and destination_port is not None:
        return (
            f"iptables -I OUTPUT 1 -d {destination_ip} "
            f"-p {proto} --dport {destination_port} -j DROP"
        )
    if proto and destination_port is not None:
        return f"iptables -I INPUT 1 -p {proto} --dport {destination_port} -j DROP"
    if proto and source_port is not None:
        return f"iptables -I INPUT 1 -p {proto} --sport {source_port} -j DROP"
    return None


def apply_firewall_command(command: str) -> tuple[bool, str]:
    if not command:
        return False, "No firewall command available to execute."

    if platform.system().lower() != "linux":
        return False, "Firewall enforcement is only supported on Linux."

    try:
        subprocess.run(
            shlex.split(command),
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        return False, f"Firewall enforcement failed: {exc}"

    return True, "Firewall command executed successfully."
