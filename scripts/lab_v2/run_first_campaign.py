from __future__ import annotations

import argparse
import datetime as dt
import shutil
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


DEFAULT_HOSTKEY = "ssh-ed25519 255 SHA256:A4qcEVMHXRFWeE0yc7KV1NRakLmMWhFr+gYL1mix0ZI"
DEFAULT_SCENARIOS = ["N01", "N02", "N03", "N06", "N07", "N11", "S01", "S02", "S03", "S05", "S06"]


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def plink_args(plink_path: str, hostkey: str, password: str, target: str) -> list[str]:
    return [
        plink_path,
        "-ssh",
        "-batch",
        "-hostkey",
        hostkey,
        "-pw",
        password,
        target,
    ]


def pscp_args(pscp_path: str, hostkey: str, password: str) -> list[str]:
    return [
        pscp_path,
        "-batch",
        "-scp",
        "-hostkey",
        hostkey,
        "-pw",
        password,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the first lab_v2 capture campaign via Kali.")
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
    parser.add_argument("--hostkey", default=DEFAULT_HOSTKEY)
    parser.add_argument("--campaign-id", default=f"campaign_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}")
    parser.add_argument(
        "--local-output-dir",
        default=str(Path("data") / "lab_v2" / "raw"),
    )
    parser.add_argument("--remote-base-dir", default="/home/kali/lab_v2_runs")
    parser.add_argument(
        "--scenarios",
        nargs="*",
        default=DEFAULT_SCENARIOS,
        help="Scenario IDs to run.",
    )
    parser.add_argument("--repeat-count", type=int, default=1, help="Number of times to replay the scenario list.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    local_output_dir = (repo_root / args.local_output_dir / args.campaign_id).resolve()
    local_output_dir.mkdir(parents=True, exist_ok=True)

    runner_local = Path(__file__).resolve().with_name("kali_lab_v2_runner.sh")
    remote_tools_dir = "/home/kali/lab_v2_tools"
    remote_runner = f"{remote_tools_dir}/kali_lab_v2_runner.sh"
    remote_output_dir = f"{args.remote_base_dir}/{args.campaign_id}"
    kali_target = f"{args.kali_user}@{args.kali_host}"

    upload_dir_cmd = f"mkdir -p {shlex.quote(remote_tools_dir)} {shlex.quote(remote_output_dir)}"
    run(plink_args(args.plink_path, args.hostkey, args.kali_password, kali_target) + [upload_dir_cmd])

    run(
        pscp_args(args.pscp_path, args.hostkey, args.kali_password)
        + [str(runner_local), f"{kali_target}:{remote_runner}"]
    )

    chmod_cmd = f"chmod +x {shlex.quote(remote_runner)}"
    run(plink_args(args.plink_path, args.hostkey, args.kali_password, kali_target) + [chmod_cmd])

    env_assignments = {
        "KALI_SUDO_PASSWORD": args.kali_sudo_password,
        "UBUNTU_USER": args.ubuntu_user,
        "UBUNTU_PASSWORD": args.ubuntu_password,
        "UBUNTU_HOST": args.ubuntu_host,
        "META2_HOST": args.meta2_host,
        "META3_HOST": args.meta3_host,
        "KALI_LAB_HOST": args.kali_lab_host,
    }
    env_str = " ".join(f"{key}={shlex.quote(value)}" for key, value in env_assignments.items())
    scenario_args = " ".join(shlex.quote(item) for item in args.scenarios)
    remote_cmd = (
        f"{env_str} bash {shlex.quote(remote_runner)} "
        f"--campaign-id {shlex.quote(args.campaign_id)} "
        f"--output-dir {shlex.quote(remote_output_dir)} "
        f"--interface {shlex.quote(args.interface)} "
        f"--repeat-count {args.repeat_count} "
        f"{scenario_args}"
    )

    result = run(plink_args(args.plink_path, args.hostkey, args.kali_password, kali_target) + [remote_cmd])
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)

    temp_download_root = Path(tempfile.gettempdir()) / "lab_v2_downloads"
    temp_download_root.mkdir(parents=True, exist_ok=True)
    temp_campaign_dir = temp_download_root / args.campaign_id
    if temp_campaign_dir.exists():
        shutil.rmtree(temp_campaign_dir)

    run(
        pscp_args(args.pscp_path, args.hostkey, args.kali_password)
        + ["-r", f"{kali_target}:{remote_output_dir}", str(temp_download_root)]
    )

    for item in temp_campaign_dir.iterdir():
        target = local_output_dir / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    print(f"Local artifacts downloaded to: {local_output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
