from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import pandas as pd


SCENARIO_CAPS: dict[str, int] = {
    "N20": 150,
    "N21": 150,
    "N22": 250,
    "N23": 120,
    "N24": 100,
    "N30": 160,
    "S20": 400,
    "S21": 600,
    "S22": 300,
    "S24": 180,
    "S25": 180,
}

EXCLUDED_STATUSES = {"scenario_error"}


def stable_hash(value: object) -> str:
    return hashlib.md5(str(value).encode("utf-8")).hexdigest()


def sort_flow_frame(frame: pd.DataFrame) -> pd.DataFrame:
    sort_columns = [column for column in ("start_ts", "end_ts", "flow_id") if column in frame.columns]
    if not sort_columns:
        return frame.reset_index(drop=True)
    return frame.sort_values(sort_columns).reset_index(drop=True)


def cap_capture(group: pd.DataFrame) -> pd.DataFrame:
    scenario_id = str(group["scenario_id"].iloc[0])
    cap = SCENARIO_CAPS.get(scenario_id)
    ordered = sort_flow_frame(group)
    if cap is None or len(ordered) <= cap:
        return ordered
    return ordered.head(cap).reset_index(drop=True)


def balance_labels(frame: pd.DataFrame) -> pd.DataFrame:
    label_counts = frame["label_binary"].value_counts()
    if label_counts.empty:
        return frame
    target = int(label_counts.min())
    balanced_parts: list[pd.DataFrame] = []
    for label, group in frame.groupby("label_binary", sort=True):
        if len(group) > target:
            sampled = (
                group.assign(_stable_key=group["flow_id"].map(stable_hash))
                .sort_values("_stable_key")
                .head(target)
                .drop(columns="_stable_key")
            )
            balanced_parts.append(sort_flow_frame(sampled))
        else:
            balanced_parts.append(sort_flow_frame(group))
    return pd.concat(balanced_parts, ignore_index=True, sort=False)


def scenario_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=["label_binary", "scenario_id", "scenario_family", "flow_count", "pct_within_label"]
        )
    distribution = (
        frame.groupby(["label_binary", "scenario_id", "scenario_family"])
        .size()
        .rename("flow_count")
        .reset_index()
    )
    distribution["pct_within_label"] = (
        distribution["flow_count"]
        / distribution.groupby("label_binary")["flow_count"].transform("sum")
        * 100
    ).round(2)
    return distribution.sort_values(["label_binary", "flow_count"], ascending=[True, False]).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a balanced train view from a prepared lab_v2 split.")
    parser.add_argument(
        "--source-split-dir",
        default=str(Path("data") / "lab_v2" / "prepared" / "post_v1_20260328_1105"),
        help="Prepared split directory containing all_flows.parquet and capture_split_plan.csv.",
    )
    parser.add_argument(
        "--output-root",
        default=str(Path("data") / "lab_v2" / "prepared"),
        help="Root directory where the balanced view will be created.",
    )
    parser.add_argument(
        "--view-id",
        default=f"train_balanced_v1_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}",
        help="Output directory name for the balanced view.",
    )
    args = parser.parse_args()

    source_split_dir = Path(args.source_split_dir).resolve()
    output_dir = Path(args.output_root).resolve() / args.view_id
    output_dir.mkdir(parents=True, exist_ok=True)

    all_flows = pd.read_parquet(source_split_dir / "all_flows.parquet")
    capture_plan = pd.read_csv(source_split_dir / "capture_split_plan.csv")

    clean_capture_plan = capture_plan.loc[~capture_plan["status"].isin(EXCLUDED_STATUSES)].copy()

    train_captures = clean_capture_plan.loc[clean_capture_plan["split"].eq("train"), "capture_id"].tolist()
    validation_captures = clean_capture_plan.loc[clean_capture_plan["split"].eq("validation"), "capture_id"].tolist()
    test_captures = clean_capture_plan.loc[clean_capture_plan["split"].eq("test"), "capture_id"].tolist()

    train_source = all_flows.loc[all_flows["capture_id"].isin(train_captures)].copy()
    validation_clean = all_flows.loc[all_flows["capture_id"].isin(validation_captures)].copy()
    test_clean = all_flows.loc[all_flows["capture_id"].isin(test_captures)].copy()

    capped_parts: list[pd.DataFrame] = []
    capture_cap_rows: list[dict[str, object]] = []
    for capture_id, group in train_source.groupby("capture_id", sort=True):
        scenario_id = str(group["scenario_id"].iloc[0])
        label_binary = str(group["label_binary"].iloc[0])
        kept = cap_capture(group)
        capture_cap_rows.append(
            {
                "capture_id": capture_id,
                "scenario_id": scenario_id,
                "scenario_family": str(group["scenario_family"].iloc[0]),
                "label_binary": label_binary,
                "original_flow_count": int(len(group)),
                "capped_flow_count": int(len(kept)),
                "cap_applied": SCENARIO_CAPS.get(scenario_id),
            }
        )
        capped_parts.append(kept)

    train_capped = pd.concat(capped_parts, ignore_index=True, sort=False) if capped_parts else pd.DataFrame()
    train_balanced = balance_labels(train_capped)

    train_balanced.to_parquet(output_dir / "train_balanced.parquet", index=False)
    validation_clean.to_parquet(output_dir / "validation_clean.parquet", index=False)
    test_clean.to_parquet(output_dir / "test_clean.parquet", index=False)

    pd.DataFrame(capture_cap_rows).to_csv(output_dir / "train_capture_caps.csv", index=False)
    scenario_distribution(train_capped).to_csv(output_dir / "train_capped_distribution.csv", index=False)
    scenario_distribution(train_balanced).to_csv(output_dir / "train_balanced_distribution.csv", index=False)

    clean_capture_plan.to_csv(output_dir / "capture_split_plan_clean.csv", index=False)

    summary = {
        "source_split_dir": str(source_split_dir),
        "excluded_statuses": sorted(EXCLUDED_STATUSES),
        "cap_plan": SCENARIO_CAPS,
        "train_source_rows": int(len(train_source)),
        "train_capped_rows": int(len(train_capped)),
        "train_balanced_rows": int(len(train_balanced)),
        "train_source_label_counts": train_source["label_binary"].value_counts().to_dict(),
        "train_capped_label_counts": train_capped["label_binary"].value_counts().to_dict(),
        "train_balanced_label_counts": train_balanced["label_binary"].value_counts().to_dict(),
        "validation_clean_rows": int(len(validation_clean)),
        "validation_clean_label_counts": validation_clean["label_binary"].value_counts().to_dict(),
        "test_clean_rows": int(len(test_clean)),
        "test_clean_label_counts": test_clean["label_binary"].value_counts().to_dict(),
        "excluded_capture_count": int((capture_plan["status"].isin(EXCLUDED_STATUSES)).sum()),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Balanced view created: {output_dir}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
