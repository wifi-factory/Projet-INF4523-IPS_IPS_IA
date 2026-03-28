#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  kali_lab_v2_runner.sh --campaign-id <id> --output-dir <dir> [--interface eth1] [--repeat-count 1] [scenario...]

Environment:
  KALI_SUDO_PASSWORD   required for tcpdump, nmap -sS, and hping3
  UBUNTU_USER          default: manata
  UBUNTU_PASSWORD      required for benign scenarios sourced from Ubuntu client
  UBUNTU_HOST          default: 172.30.1.23
  META2_HOST           default: 172.30.1.21
  META3_HOST           default: 172.30.1.24
  KALI_LAB_HOST        default: 172.30.1.20
EOF
}

CAMPAIGN_ID=""
OUTPUT_DIR=""
INTERFACE="eth1"
REPEAT_COUNT="1"
declare -a SCENARIOS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --campaign-id)
      CAMPAIGN_ID="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --interface)
      INTERFACE="$2"
      shift 2
      ;;
    --repeat-count)
      REPEAT_COUNT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      SCENARIOS+=("$1")
      shift
      ;;
  esac
done

if [[ -z "$CAMPAIGN_ID" || -z "$OUTPUT_DIR" ]]; then
  usage >&2
  exit 1
fi

if [[ -z "${KALI_SUDO_PASSWORD:-}" ]]; then
  echo "KALI_SUDO_PASSWORD is required." >&2
  exit 1
fi

UBUNTU_USER="${UBUNTU_USER:-manata}"
UBUNTU_PASSWORD="${UBUNTU_PASSWORD:-}"
UBUNTU_HOST="${UBUNTU_HOST:-172.30.1.23}"
META2_HOST="${META2_HOST:-172.30.1.21}"
META3_HOST="${META3_HOST:-172.30.1.24}"
META3_USER="${META3_USER:-vagrant}"
META3_PASSWORD="${META3_PASSWORD:-vagrant}"
KALI_LAB_HOST="${KALI_LAB_HOST:-172.30.1.20}"

if ! [[ "$REPEAT_COUNT" =~ ^[1-9][0-9]*$ ]]; then
  echo "--repeat-count must be a positive integer." >&2
  exit 1
fi

if [[ ${#SCENARIOS[@]} -eq 0 ]]; then
  SCENARIOS=("N01" "N02" "N03" "N06" "N07" "N11" "S01" "S02" "S03" "S05" "S06")
fi

mkdir -p "$OUTPUT_DIR"
MANIFEST_PATH="$OUTPUT_DIR/manifest.csv"
if [[ ! -f "$MANIFEST_PATH" ]]; then
  echo "campaign_id,run_index,scenario_id,scenario_family,label_binary,source_host,target_host,pcap_name,started_at_utc,packet_count,status,notes" > "$MANIFEST_PATH"
fi

remote_ubuntu() {
  if [[ -z "$UBUNTU_PASSWORD" ]]; then
    echo "UBUNTU_PASSWORD is required for Ubuntu-driven scenarios." >&2
    return 1
  fi
  sshpass -p "$UBUNTU_PASSWORD" ssh \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    "${UBUNTU_USER}@${UBUNTU_HOST}" \
    "$@"
}

ensure_kali_package() {
  local binary="$1"
  local package_name="$2"
  if command -v "$binary" >/dev/null 2>&1; then
    return 0
  fi
  echo "$KALI_SUDO_PASSWORD" | sudo -S apt-get update >/dev/null
  echo "$KALI_SUDO_PASSWORD" | sudo -S env DEBIAN_FRONTEND=noninteractive apt-get install -y "$package_name" >/dev/null
}

ensure_ubuntu_package() {
  local binary="$1"
  local package_name="$2"
  remote_ubuntu "command -v $binary >/dev/null 2>&1 || (echo '$UBUNTU_PASSWORD' | sudo -S apt-get update >/dev/null && echo '$UBUNTU_PASSWORD' | sudo -S env DEBIAN_FRONTEND=noninteractive apt-get install -y $package_name >/dev/null)"
}

start_dnsmasq() {
  local dns_conf dns_log
  dns_conf="$(mktemp /tmp/labv2_dnsmasq.XXXX.conf)"
  dns_log="${dns_conf%.conf}.log"
  cat >"$dns_conf" <<EOF
port=53
listen-address=${KALI_LAB_HOST}
bind-interfaces
no-resolv
domain-needed
bogus-priv
address=/labv2.test/${META3_HOST}
EOF
  echo "$KALI_SUDO_PASSWORD" | sudo -S dnsmasq --conf-file="$dns_conf" --keep-in-foreground >"$dns_log" 2>&1 &
  DNSMASQ_PID=$!
  DNSMASQ_CONF="$dns_conf"
  DNSMASQ_LOG="$dns_log"
  sleep 2
}

stop_dnsmasq() {
  if [[ -n "${DNSMASQ_PID:-}" ]] && kill -0 "$DNSMASQ_PID" 2>/dev/null; then
    echo "$KALI_SUDO_PASSWORD" | sudo -S kill "$DNSMASQ_PID" >/dev/null 2>&1 || true
    wait "$DNSMASQ_PID" || true
  fi
  [[ -n "${DNSMASQ_CONF:-}" ]] && rm -f "$DNSMASQ_CONF"
  [[ -n "${DNSMASQ_LOG:-}" ]] && rm -f "$DNSMASQ_LOG"
}

start_iperf3_server() {
  ensure_kali_package iperf3 iperf3
  iperf3 -s -1 -B "$KALI_LAB_HOST" >/tmp/labv2_iperf3_server.log 2>&1 &
  IPERF3_PID=$!
  sleep 2
}

wait_iperf3_server() {
  if [[ -n "${IPERF3_PID:-}" ]]; then
    wait "$IPERF3_PID" || true
  fi
}

prepare_dependencies() {
  local need_iperf3=0
  local need_dns=0
  local need_ubuntu_curl=0
  local need_ubuntu_wget=0
  local need_ubuntu_dnsutils=0
  local need_ubuntu_ssh=0
  local need_kali_nmap=0
  local need_kali_hping3=0
  local need_kali_nc=0
  local need_kali_sshpass=0
  local need_kali_curl=0
  for scenario in "${SCENARIOS[@]}"; do
    case "$scenario" in
      N06) need_dns=1 ;;
      N07) need_iperf3=1 ;;
      N20|N21|N30) need_ubuntu_curl=1 ;;
      N31) need_ubuntu_wget=1 ;;
      N22) need_dns=1; need_ubuntu_dnsutils=1 ;;
      N23|N35|N36) need_ubuntu_ssh=1 ;;
      N24|N11) need_ubuntu_wget=1 ;;
      N25) need_iperf3=1 ;;
      S01|S20|S21|S22|S25) need_kali_nmap=1 ;;
      S05|S06|S23) need_kali_hping3=1 ;;
      S24) need_kali_nc=1 ;;
      S30) need_kali_sshpass=1 ;;
      S31) need_kali_curl=1 ;;
    esac
  done

  if [[ "$need_dns" -eq 1 ]]; then
    ensure_kali_package dnsmasq dnsmasq
  fi
  if [[ "$need_iperf3" -eq 1 ]]; then
    ensure_kali_package iperf3 iperf3
    ensure_ubuntu_package iperf3 iperf3
  fi
  if [[ "$need_ubuntu_curl" -eq 1 ]]; then
    ensure_ubuntu_package curl curl
  fi
  if [[ "$need_ubuntu_wget" -eq 1 ]]; then
    ensure_ubuntu_package wget wget
  fi
  if [[ "$need_ubuntu_dnsutils" -eq 1 ]]; then
    ensure_ubuntu_package dig dnsutils
  fi
  if [[ "$need_ubuntu_ssh" -eq 1 ]]; then
    ensure_ubuntu_package ssh sshpass
    ensure_ubuntu_package sshpass sshpass
  fi
  if [[ "$need_kali_nmap" -eq 1 ]]; then
    ensure_kali_package nmap nmap
  fi
  if [[ "$need_kali_hping3" -eq 1 ]]; then
    ensure_kali_package hping3 hping3
  fi
  if [[ "$need_kali_nc" -eq 1 ]]; then
    ensure_kali_package nc netcat-openbsd
  fi
  if [[ "$need_kali_sshpass" -eq 1 ]]; then
    ensure_kali_package sshpass sshpass
  fi
  if [[ "$need_kali_curl" -eq 1 ]]; then
    ensure_kali_package curl curl
  fi
}

run_scenario() {
  local scenario="$1"
  case "$scenario" in
    N01)
      remote_ubuntu "ping -c 5 ${META2_HOST} >/dev/null"
      ;;
    N02)
      remote_ubuntu "curl -fsS http://${META2_HOST}/ >/dev/null"
      ;;
    N03)
      remote_ubuntu "curl -fsS http://${META3_HOST}/ >/dev/null"
      ;;
    N06)
      start_dnsmasq
      remote_ubuntu "dig +short @${KALI_LAB_HOST} labv2.test >/dev/null"
      stop_dnsmasq
      ;;
    N07)
      start_iperf3_server
      remote_ubuntu "iperf3 -c ${KALI_LAB_HOST} -B ${UBUNTU_HOST} -t 5 >/dev/null"
      wait_iperf3_server
      ;;
    N11)
      remote_ubuntu "wget -q -O /dev/null http://${META3_HOST}/"
      ;;
    N20)
      remote_ubuntu "for i in \$(seq 1 300); do curl -s --http1.1 --no-keepalive --max-time 3 http://${META2_HOST}/ >/dev/null; done"
      ;;
    N21)
      remote_ubuntu "for i in \$(seq 1 300); do curl -s --http1.1 --no-keepalive --max-time 3 http://${META3_HOST}/ >/dev/null; done"
      ;;
    N22)
      start_dnsmasq
      remote_ubuntu "for i in \$(seq 1 500); do dig +short +time=1 +tries=1 @${KALI_LAB_HOST} labv2.test >/dev/null; done"
      stop_dnsmasq
      ;;
    N23)
      remote_ubuntu "for i in \$(seq 1 150); do sshpass -p '${META3_PASSWORD}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=3 ${META3_USER}@${META3_HOST} true >/dev/null 2>&1; done"
      ;;
    N24)
      remote_ubuntu "for i in \$(seq 1 120); do wget -q -O /dev/null \"http://${META3_HOST}/?r=\${i}\"; done"
      ;;
    N25)
      start_iperf3_server
      remote_ubuntu "iperf3 -c ${KALI_LAB_HOST} -B ${UBUNTU_HOST} -t 15 >/dev/null"
      wait_iperf3_server
      ;;
    N30)
      remote_ubuntu "for i in \$(seq 1 300); do curl -sk --http1.1 --no-keepalive --max-time 4 https://${META3_HOST}/ >/dev/null; done"
      ;;
    N31)
      remote_ubuntu "for i in \$(seq 1 80); do wget --no-check-certificate -q -O /dev/null \"https://${META3_HOST}/labv2.bin?download=\${i}\"; done"
      ;;
    N35)
      remote_ubuntu "dd if=/dev/urandom of=/tmp/labv2_scp_1m.bin bs=1M count=1 status=none && for i in \$(seq 1 20); do sshpass -p '${META3_PASSWORD}' scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null /tmp/labv2_scp_1m.bin ${META3_USER}@${META3_HOST}:/tmp/labv2_scp_\${i}.bin >/dev/null 2>&1; done"
      ;;
    N36)
      remote_ubuntu "dd if=/dev/urandom of=/tmp/labv2_admin_256k.bin bs=256K count=1 status=none && for i in \$(seq 1 40); do sshpass -p '${META3_PASSWORD}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=3 ${META3_USER}@${META3_HOST} id >/dev/null 2>&1; done && for i in \$(seq 1 10); do sshpass -p '${META3_PASSWORD}' scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null /tmp/labv2_admin_256k.bin ${META3_USER}@${META3_HOST}:/tmp/labv2_admin_\${i}.bin >/dev/null 2>&1; done"
      ;;
    S01)
      echo "$KALI_SUDO_PASSWORD" | sudo -S nmap -Pn -sS -p 1-128 "${META2_HOST}" >/dev/null
      ;;
    S20)
      echo "$KALI_SUDO_PASSWORD" | sudo -S nmap -Pn -sS -p 1-1000 "${META2_HOST}" >/dev/null
      ;;
    S21)
      nmap -Pn -sT -p 1-1000 "${META3_HOST}" >/dev/null
      ;;
    S22)
      nmap -Pn -sU -p 1-300 "${META3_HOST}" >/dev/null
      ;;
    S23)
      for p in $(seq 1 200); do
        echo "$KALI_SUDO_PASSWORD" | sudo -S hping3 -S -p "$p" -c 1 -q "${META3_HOST}" >/dev/null 2>&1 || true
      done
      ;;
    S24)
      for i in $(seq 1 200); do
        nc -zvw1 "${META2_HOST}" 65000 >/dev/null 2>&1 || true
      done
      ;;
    S30)
      for i in $(seq 1 60); do
        sshpass -p 'WrongLabV2!' ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=3 "${META3_USER}@${META3_HOST}" true >/dev/null 2>&1 || true
      done
      ;;
    S31)
      for i in $(seq 1 60); do
        curl -sk --http1.1 --no-keepalive --max-time 3 "https://${META3_HOST}/probe-${i}?check=${i}" >/dev/null || true
      done
      ;;
    S25)
      echo "$KALI_SUDO_PASSWORD" | sudo -S nmap -Pn -sS --scan-delay 500ms -p 1-200 "${META2_HOST}" >/dev/null
      ;;
    S02)
      nmap -Pn -sT -p 1-128 "${META3_HOST}" >/dev/null
      ;;
    S03)
      nmap -Pn -sU -p 53,67,68,69,123,161,500,514 "${META3_HOST}" >/dev/null
      ;;
    S05)
      echo "$KALI_SUDO_PASSWORD" | sudo -S hping3 -S -p 80 -c 20 "${META3_HOST}" >/dev/null 2>&1
      ;;
    S06)
      echo "$KALI_SUDO_PASSWORD" | sudo -S hping3 --icmp -c 40 --fast "${META2_HOST}" >/dev/null 2>&1
      ;;
    *)
      echo "Unknown scenario: $scenario" >&2
      return 1
      ;;
  esac
}

scenario_family() {
  case "$1" in
    N01) echo "normal_icmp" ;;
    N02|N03) echo "normal_http" ;;
    N06) echo "normal_dns" ;;
    N07) echo "normal_bulk_tcp" ;;
    N11) echo "normal_wget" ;;
    N20|N21) echo "normal_http_short" ;;
    N22) echo "normal_dns_burst" ;;
    N23) echo "normal_ssh_short" ;;
    N24) echo "normal_wget_burst" ;;
    N25) echo "normal_bulk_tcp" ;;
    N30) echo "normal_https_short" ;;
    N31) echo "normal_https_download" ;;
    N35) echo "normal_scp" ;;
    N36) echo "normal_admin_mixed" ;;
    S01) echo "scan_syn" ;;
    S20) echo "scan_syn_large" ;;
    S21) echo "scan_connect_large" ;;
    S22) echo "scan_udp_large" ;;
    S23) echo "syn_burst_multiport" ;;
    S24) echo "failed_connection_burst" ;;
    S30) echo "ssh_bruteforce_light" ;;
    S31) echo "web_probe_https" ;;
    S25) echo "scan_syn_slow" ;;
    S02) echo "scan_connect" ;;
    S03) echo "scan_udp" ;;
    S05) echo "syn_burst" ;;
    S06) echo "icmp_burst" ;;
    *) echo "unknown" ;;
  esac
}

scenario_label() {
  case "$1" in
    N*) echo "normal" ;;
    S*) echo "suspect" ;;
    *) echo "unknown" ;;
  esac
}

scenario_source_host() {
  case "$1" in
    N*) echo "$UBUNTU_HOST" ;;
    S*) echo "$KALI_LAB_HOST" ;;
    *) echo "" ;;
  esac
}

scenario_target_host() {
  case "$1" in
    N01|S01) echo "$META2_HOST" ;;
    N02) echo "$META2_HOST" ;;
    N20|S20|S25) echo "$META2_HOST" ;;
    N03|N11|S02|S03|S05) echo "$META3_HOST" ;;
    N21|N23|N24|N30|N31|N35|N36|S21|S22|S23|S30|S31) echo "$META3_HOST" ;;
    S24) echo "$META2_HOST" ;;
    N06|N07) echo "$KALI_LAB_HOST" ;;
    N22|N25) echo "$KALI_LAB_HOST" ;;
    S06) echo "$META2_HOST" ;;
    *) echo "" ;;
  esac
}

scenario_note() {
  case "$1" in
    N01) echo "ubuntu ping meta2" ;;
    N02) echo "ubuntu curl meta2 http" ;;
    N03) echo "ubuntu curl meta3 http" ;;
    N06) echo "ubuntu dig query to kali dnsmasq" ;;
    N07) echo "ubuntu iperf3 tcp to kali" ;;
    N11) echo "ubuntu wget meta3 http" ;;
    N20) echo "ubuntu short http burst to meta2" ;;
    N21) echo "ubuntu short http burst to meta3" ;;
    N22) echo "ubuntu dns burst to kali dnsmasq" ;;
    N23) echo "ubuntu repeated ssh one-shot to meta3" ;;
    N24) echo "ubuntu wget burst to meta3 http" ;;
    N25) echo "ubuntu iperf3 15s tcp to kali" ;;
    N30) echo "ubuntu short https burst to meta3" ;;
    N31) echo "ubuntu repeated https downloads from meta3" ;;
    N35) echo "ubuntu repeated scp to meta3" ;;
    N36) echo "ubuntu mixed ssh and scp admin activity to meta3" ;;
    S01) echo "kali syn scan meta2 ports 1-128" ;;
    S20) echo "kali syn scan meta2 ports 1-1000" ;;
    S21) echo "kali connect scan meta3 ports 1-1000" ;;
    S22) echo "kali udp scan meta3 ports 1-300" ;;
    S23) echo "kali syn multiport burst meta3 ports 1-200" ;;
    S24) echo "kali repeated failed tcp connect meta2 port 65000" ;;
    S30) echo "kali repeated ssh auth failures to meta3" ;;
    S31) echo "kali repeated https web probing to meta3" ;;
    S25) echo "kali slow syn scan meta2 ports 1-200" ;;
    S02) echo "kali connect scan meta3 ports 1-128" ;;
    S03) echo "kali udp scan meta3 selected ports" ;;
    S05) echo "kali syn burst meta3 port 80" ;;
    S06) echo "kali icmp burst meta2" ;;
    *) echo "" ;;
  esac
}

prepare_dependencies

declare -A SCENARIO_RUN_COUNTS=()

for run_index in $(seq 1 "$REPEAT_COUNT"); do
  for scenario in "${SCENARIOS[@]}"; do
    started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    SCENARIO_RUN_COUNTS["$scenario"]=$(( ${SCENARIO_RUN_COUNTS["$scenario"]:-0} + 1 ))
    scenario_run_index="${SCENARIO_RUN_COUNTS["$scenario"]}"
    run_suffix="$(printf 'run%02d' "$scenario_run_index")"
    pcap_name="${CAMPAIGN_ID}_${scenario}_${run_suffix}.pcap"
    pcap_path="${OUTPUT_DIR}/${pcap_name}"
    log_path="${OUTPUT_DIR}/${pcap_name%.pcap}.log"
    capture_filter="host ${KALI_LAB_HOST} or host ${UBUNTU_HOST} or host ${META2_HOST} or host ${META3_HOST}"

    echo "$KALI_SUDO_PASSWORD" | sudo -S rm -f "$pcap_path"
    echo "$KALI_SUDO_PASSWORD" | sudo -S tcpdump -i "$INTERFACE" -nn -U -w "$pcap_path" "$capture_filter" >"$log_path" 2>&1 &
    capture_pid=$!

    sleep 2
    status="ok"
    if ! run_scenario "$scenario"; then
      status="scenario_error"
    fi
    sleep 2

    if kill -0 "$capture_pid" 2>/dev/null; then
      echo "$KALI_SUDO_PASSWORD" | sudo -S kill -INT "$capture_pid" >/dev/null 2>&1 || true
    fi
    wait "$capture_pid" || true

    echo "$KALI_SUDO_PASSWORD" | sudo -S chown "$(id -un):$(id -gn)" "$pcap_path" "$log_path" >/dev/null 2>&1 || true
    packet_count="$(tcpdump -nr "$pcap_path" 2>/dev/null | wc -l | tr -d ' ')"
    echo "${CAMPAIGN_ID},${scenario_run_index},${scenario},$(scenario_family "$scenario"),$(scenario_label "$scenario"),$(scenario_source_host "$scenario"),$(scenario_target_host "$scenario"),${pcap_name},${started_at},${packet_count},${status},$(scenario_note "$scenario")" >> "$MANIFEST_PATH"
  done
done

echo "Campaign completed: $CAMPAIGN_ID"
echo "Artifacts: $OUTPUT_DIR"
