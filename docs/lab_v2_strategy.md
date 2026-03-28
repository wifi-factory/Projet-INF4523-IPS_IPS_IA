# Lab V2 Strategy

## Current Lab State

The shared lab segment for the IPS demonstration is `PentestNet` on
`172.30.1.0/24`.

Confirmed nodes on March 27, 2026:

| Role | VM | Interface | Current IP | Status |
| --- | --- | --- | --- | --- |
| Attacker | `kali-linux-2025.2-virtualbox-amd64` | `eth1` | `172.30.1.20` | Reachable, SSH OK |
| Legacy target | `Metasploitable2` | `eth0` | `172.30.1.21` | Reachable, SSH OK |
| Normal client | `ubuntu-client-normal` | `enp0s3` | `172.30.1.23` | Installed, SSH active |
| Rich target | `metasploitable3-ub1404` | `eth0` | `172.30.1.24` | Reachable, SSH OK |

Important:

- the observed addressing is correct for the lab and the nodes are reachable
- some guests still obtain that address from the lab DHCP behavior
- treat the table below as the frozen target plan for `lab_v2`, even if you
  later hard-pin each guest explicitly

Observed auxiliary addresses:

| IP | Note |
| --- | --- |
| `172.30.1.1` | Present on `PentestNet`; likely provides DHCP/router behavior on the segment |
| `10.0.3.15` | NAT-side address on `ubuntu-client-normal` (`enp0s8`) for package installs |

## Addressing Plan

Use `PentestNet` only for dataset generation, replay, and the live academic
demonstration.

Recommended fixed plan:

| IP | Role | Hostname / VM | Notes |
| --- | --- | --- | --- |
| `172.30.1.10` | Optional controller | future backend monitor VM | Reserved |
| `172.30.1.20` | Attacker | `kali-lab` | Kali attack and tooling node |
| `172.30.1.21` | Legacy target | `meta2-lab` | Metasploitable2 |
| `172.30.1.22` | Optional service | future dashboard / sensor | Reserved |
| `172.30.1.23` | Normal client | `ubuntu-client-normal` | Benign traffic source |
| `172.30.1.24` | Rich target | `meta3-lab` | Metasploitable3 Ubuntu |
| `172.30.1.30-39` | Extra clients | future VMs | Reserved |

Practical rule:

- keep the capture and ML validation on `PentestNet`
- keep Internet egress, updates, and package downloads on secondary NICs only
- avoid using the host Wi-Fi traffic as a demo source for IDS/IPS validation

## What Was Finalized

`ubuntu-client-normal` was completed and is now usable:

- Ubuntu Server 24.04.4 LTS installed on disk
- hostname set to `ubuntu-client-normal`
- SSH service installed and active
- reachable from Kali on `172.30.1.23`
- still observed on the `PentestNet` segment at the expected `.23` slot

## Lab V2 Collection Rules

To avoid offline/live drift, all future `lab_v2` captures must use:

- the same `PentestNet` segment
- the same flow aggregation logic as the backend live runtime
- the same 31 model features
- the same post-flow decision model
- scenario-level labeling with a stable naming convention

Automation entrypoints committed in the repository:

- `scripts/lab_v2/kali_lab_v2_runner.sh`
- `scripts/lab_v2/run_first_campaign.py`
- `data/lab_v2/raw/` for downloaded campaign artifacts

Current automated subset already exercised on the lab:

- `N01` benign ICMP
- `N02` benign HTTP with `curl`
- `N03` benign HTTP to Meta3
- `N06` benign DNS query to temporary Kali `dnsmasq`
- `N07` benign `iperf3` TCP flow to Kali
- `N11` benign HTTP download with `wget`
- `S01` SYN scan
- `S02` connect scan
- `S03` UDP scan
- `S05` SYN burst
- `S06` ICMP burst

Recommended raw naming:

`YYYYMMDD_sessionXX_family_scenario_runYY_label.pcap`

Example:

`20260328_s01_normal_http_run01_normal.pcap`

## Normal Traffic Scenarios

Capture each scenario 5 to 10 times with small controlled variations.

| Scenario ID | Family | Source | Target | Tool / Action | Goal |
| --- | --- | --- | --- | --- | --- |
| `N01` | `normal_icmp` | Ubuntu client | Meta2, Meta3 | `ping -c 5` | Benign ICMP baseline |
| `N02` | `normal_http` | Ubuntu client | Meta3 | `curl http://<target>` | Simple web access |
| `N03` | `normal_https` | Ubuntu client | external or lab web service | `curl https://...` | Short TLS flows |
| `N04` | `normal_ssh` | Ubuntu client | Meta3 | `ssh` login and exit | Interactive admin traffic |
| `N05` | `normal_scp` | Ubuntu client | Meta3 | `scp` small file | Short file transfer |
| `N06` | `normal_dns` | Ubuntu client | resolver | `dig`, `nslookup` | DNS request burst |
| `N07` | `normal_bulk_tcp` | Ubuntu client | Meta3 or iperf server | `iperf3 -c ...` | Stable TCP throughput |
| `N08` | `normal_bulk_udp` | Ubuntu client | Meta3 or iperf server | `iperf3 -u -c ...` | Stable UDP throughput |
| `N09` | `normal_http_burst` | Ubuntu client | Meta3 | repeated `curl` loop | Repeated but legitimate short flows |
| `N10` | `normal_multi_service` | Ubuntu client | Meta2 and Meta3 | mixed `ping`, `curl`, `ssh` | Session realism |

## Suspect Traffic Scenarios

Keep all attack traffic controlled, short, and non-destructive.

| Scenario ID | Family | Source | Target | Tool / Action | Goal |
| --- | --- | --- | --- | --- | --- |
| `S01` | `scan_syn` | Kali | Meta2 | `nmap -sS <target>` | SYN scan baseline |
| `S02` | `scan_connect` | Kali | Meta3 | `nmap -sT <target>` | Full connect scan |
| `S03` | `scan_udp` | Kali | Meta3 | `nmap -sU <target>` | UDP probing |
| `S04` | `scan_multiport` | Kali | Meta2, Meta3 | `nmap -p 1-1024` | Wider recon burst |
| `S05` | `syn_burst` | Kali | Meta3 | `hping3 -S -p 80 -c 20` | Short SYN burst |
| `S06` | `icmp_burst` | Kali | Meta2 | `hping3 --icmp -c 50` | Abnormal ICMP rate |
| `S07` | `udp_burst` | Kali | Meta3 | `hping3 --udp -p 53 -c 30` | Short UDP burst |
| `S08` | `failed_connection_burst` | Kali | Meta3 | repeated closed-port connects | Failed connection ratio stress |
| `S09` | `slow_scan` | Kali | Meta3 | slow `nmap` timing | Lower-rate recon behavior |
| `S10` | `mixed_recon` | Kali | Meta2, Meta3 | combined `ping`, `nmap`, `hping3` | Demonstration attack chain |

## Dataset Split Strategy

Do not split randomly by row.

Split by capture or run:

- `train`: 70%
- `validation`: 15%
- `test`: 15%

Keep all flows from one capture in the same split.

## Presentation Simulation

Recommended short academic demo:

1. Show `GET /health`, `GET /model/info`, and `GET /live/interfaces`.
2. Start live monitoring on the lab-facing interface.
3. Generate one benign scenario from `ubuntu-client-normal`, such as `N02`.
4. Show `GET /live/status`.
5. Generate one suspect scenario from Kali, such as `S01` or `S05`.
6. Show `GET /live/status` again and explain the post-classification
   blocking decision in `dry_run`.
7. Stop monitoring cleanly.

## Immediate Next Steps

1. Freeze Kali and Meta2 addresses if you want fully static addressing.
2. Keep `ubuntu-client-normal` as the official benign client for `lab_v2`.
3. Use `Meta2` and `Meta3` together to diversify the suspicious and benign
   interaction patterns.
4. Build `lab_v2` only from `PentestNet` captures, not host Wi-Fi traffic.

## Current Seed Warning

The first prepared split is valid at the capture level, but it is still very
imbalanced at the flow level because recon captures create far more finalized
flows than benign captures.

That means:

- the current split is suitable as an initial seed
- it is not yet a strong final training corpus
- the next collection wave should prioritize additional benign capture volume
  and more benign session diversity
