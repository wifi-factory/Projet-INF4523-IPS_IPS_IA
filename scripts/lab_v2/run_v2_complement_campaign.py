from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


V2_COMPLEMENT_PLAN: list[tuple[str, int]] = [
    ("N31", 4),
    ("N35", 3),
    ("N36", 3),
    ("S23", 4),
    ("S30", 3),
    ("S31", 3),
]


def build_expanded_scenarios() -> list[str]:
    scenarios: list[str] = []
    for scenario_id, count in V2_COMPLEMENT_PLAN:
        scenarios.extend([scenario_id] * count)
    return scenarios


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the short complementary lab_v2 campaign for a cleaner v2 corpus.")
    parser.add_argument("--campaign-id", default=f"v2_complement_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}")
    parser.add_argument("--kali-host", default="192.168.0.217")
    parser.add_argument("--kali-user", default="kali")
    parser.add_argument("--kali-password", default="kali")
    parser.add_argument("--kali-sudo-password", default="kali")
    parser.add_argument("--ubuntu-user", default="manata")
    parser.add_argument("--ubuntu-password", default="Sslyby302!")
    parser.add_argument("--ubuntu-host", default="172.30.1.23")
    parser.add_argument("--meta2-host", default="172.30.1.21")
    parser.add_argument("--meta3-host", default="172.30.1.24")
    parser.add_argument("--kali-lab-host", default="172.30.1.20")
    parser.add_argument("--interface", default="eth1")
    parser.add_argument("--plink-path", default=r"C:\Program Files\PuTTY\plink.exe")
    parser.add_argument("--pscp-path", default=r"C:\Program Files\PuTTY\pscp.exe")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    runner_script = Path(__file__).resolve().with_name("run_first_campaign.py")
    scenarios = build_expanded_scenarios()

    cmd = [
        sys.executable,
        str(runner_script),
        "--campaign-id",
        args.campaign_id,
        "--kali-host",
        args.kali_host,
        "--kali-user",
        args.kali_user,
        "--kali-password",
        args.kali_password,
        "--kali-sudo-password",
        args.kali_sudo_password,
        "--ubuntu-user",
        args.ubuntu_user,
        "--ubuntu-password",
        args.ubuntu_password,
        "--ubuntu-host",
        args.ubuntu_host,
        "--meta2-host",
        args.meta2_host,
        "--meta3-host",
        args.meta3_host,
        "--kali-lab-host",
        args.kali_lab_host,
        "--interface",
        args.interface,
        "--plink-path",
        args.plink_path,
        "--pscp-path",
        args.pscp_path,
        "--repeat-count",
        "1",
        "--scenarios",
        *scenarios,
    ]

    subprocess.run(cmd, check=True, cwd=repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
