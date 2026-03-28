# Lab V2 Data

This directory stores raw and derived artifacts captured on the `PentestNet`
segment for the `lab_v2` dataset effort.

Suggested structure:

- `raw/<campaign_id>/` for first-pass `.pcap` campaign files and manifests
- `processed/` for flow-level exports derived from those captures
- `metadata/` for scenario manifests and split information
- `prepared/` for initial `train/validation/test` parquet outputs

Automation entrypoints:

- `scripts/lab_v2/run_first_campaign.py`
- `scripts/lab_v2/pcap_to_flows.py`
- `scripts/lab_v2/prepare_split_plan.py`

It uploads a runner to Kali, triggers a small set of normal and suspect
scenarios across `Kali`, `Metasploitable2`, `Metasploitable3`, and
`ubuntu-client-normal`, then downloads the resulting `.pcap` files and the
campaign manifest into `data/lab_v2/raw/<campaign_id>/`.

The conversion and preparation flow is:

1. collect raw campaign pcaps on `PentestNet`
2. convert each campaign with `pcap_to_flows.py`
3. merge processed campaigns and create a first split with `prepare_split_plan.py`
