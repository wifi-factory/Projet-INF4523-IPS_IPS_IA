from __future__ import annotations

from backend.app.core.exceptions import CaptureError
from backend.app.services.live_capture_service import LiveCaptureService


def test_parse_packet_line_returns_packet_event_for_tcp(settings):
    line = (
        '"1711542000.100000","192.168.0.10","192.168.0.20","52314","","80","","6","60","1","0","0","0","0",""'
    )

    packet = LiveCaptureService(settings).parse_packet_line(line)

    assert packet is not None
    assert packet.protocol == "TCP"
    assert packet.src_ip == "192.168.0.10"
    assert packet.dst_ip == "192.168.0.20"
    assert packet.src_port == 52314
    assert packet.dst_port == 80
    assert packet.syn == 1


def test_parse_packet_line_returns_none_for_invalid_payload(settings):
    packet = LiveCaptureService(settings).parse_packet_line('"broken","csv"')

    assert packet is None


def test_list_interfaces_falls_back_when_tshark_is_missing(settings, monkeypatch):
    service = LiveCaptureService(settings)

    monkeypatch.setattr(
        service,
        "_resolve_tshark_executable",
        lambda: (_ for _ in ()).throw(CaptureError("tshark missing")),
    )
    monkeypatch.setattr(
        service,
        "_fallback_list_interfaces",
        lambda: [("1", "1. Ethernet"), ("2", "2. Wi-Fi")],
    )

    interfaces = service.list_interfaces()

    assert interfaces == [("1", "1. Ethernet"), ("2", "2. Wi-Fi")]


def test_parse_windows_interface_output_supports_powershell_and_netsh(settings):
    service = LiveCaptureService(settings)

    powershell_output = "Ethernet\nWi-Fi\nvEthernet (Default Switch)\n"
    netsh_output = (
        "Admin State    State          Type             Interface Name\n"
        "-------------------------------------------------------------------------\n"
        "Enabled        Connected      Dedicated        Ethernet\n"
        "Enabled        Disconnected   Dedicated        Wi-Fi\n"
    )

    assert service._parse_windows_interface_output(powershell_output) == [
        "Ethernet",
        "Wi-Fi",
        "vEthernet (Default Switch)",
    ]
    assert service._parse_windows_interface_output(netsh_output) == [
        "Ethernet",
        "Wi-Fi",
    ]
