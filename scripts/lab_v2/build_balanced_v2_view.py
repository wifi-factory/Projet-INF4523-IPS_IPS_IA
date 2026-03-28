from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import pandas as pd


EXCLUDED_STATUSES = {"scenario_error"}
IGNORED_CAMPAIGN_PREFIXES = ("smoke_",)

TRAIN_CAPS_V2: dict[str, int] = {
    "N20": 120,
    "N21": 120,
    "N22": 180,
    "N23": 120,
    "N24": 100,
    "N30": 140,
    "N31": 80,
    "N35": 20,
    "N36": 50,
    "S20": 350,
    "S21": 500,
    "S22": 250,
    "S23": 180,
    "S24": 160,
    "S25": 160,
    "S30": 60,
    "S31": 60,
}


def stable_hash(value: object) -> str:
    return hashlib.md5(str(value).encode("utf-8")).hexdigest()


def load_processed_captures(processed_root: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for summary_path in sorted(processed_root.glob("*/capture_summary.csv")):
        campaign_id = summary_path.parent.name
        if campaign_id.startswith(IGNORED_CAMPAIGN_PREFIXES):
            continue
        frame = pd.read_csv(summary_path)
        frames.append(frame)
    if not frames:
        raise FileNotFoundError("No processed capture summaries found.")
    combined = pd.concat(frames, ignore_index=True, sort=False)
    return combined.loc[~combined["status"].isin(EXCLUDED_STATUSES)].reset_index(drop=True)


def load_processed_flows(processed_root: Path, allowed_campaigns: set[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for flows_path in sorted(processed_root.glob("*/flows.parquet")):
        campaign_id = flows_path.parent.name
        if campaign_id not in allowed_campaigns:
            continue
        frames.append(pd.read_parquet(flows_path))
    if not frames:
        raise FileNotFoundError("No processed flow parquet files found for the selected campaigns.")
    return pd.concat(frames, ignore_index=True, sort=False)


def assign_splits_by_scenario(captures: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for scenario_id, group in captures.groupby("scenario_id", sort=True):
        group = group.sort_values(["campaign_id", "capture_id"]).reset_index(drop=True)
        total = len(group)
        if total >= 3:
            n_train = max(1, round(total * 0.7))
            n_validation = max(1, round(total * 0.15))
            n_test = max(1, total - n_train - n_validation)
            while n_train + n_validation + n_test > total:
                if n_train > max(n_validation, n_test) and n_train > 1:
                    n_train -= 1
                elif n_validation >= n_test and n_validation > 1:
                    n_validation -= 1
                elif n_test > 1:
                    n_test -= 1
                else:
                    break
            while n_train + n_validation + n_test < total:
                n_train += 1
        elif total == 2:
            n_train, n_validation, n_test = 1, 0, 1
        else:
            n_train, n_validation, n_test = 1, 0, 0

        split_labels = ["train"] * n_train + ["validation"] * n_validation + ["test"] * n_test
        scenario_frame = group.copy()
        scenario_frame["split"] = split_labels[:total]
        parts.append(scenario_frame)
    return pd.concat(parts, ignore_index=True, sort=False)


def sort_flow_frame(frame: pd.DataFrame) -> pd.DataFrame:
    sort_columns = [column for column in ("start_ts", "end_ts", "flow_id") if column in frame.columns]
    if not sort_columns:
        return frame.reset_index(drop=True)
    return frame.sort_values(sort_columns).reset_index(drop=True)


def cap_train_capture(group: pd.DataFrame) -> pd.DataFrame:
    scenario_id = str(group["scenario_id"].iloc[0])
    cap = TRAIN_CAPS_V2.get(scenario_id)
    ordered = sort_flow_frame(group)
    if cap is None or len(ordered) <= cap:
        return ordered
    return ordered.head(cap).reset_index(drop=True)


def balance_labels(frame: pd.DataFrame) -> pd.DataFrame:
    counts = frame["label_binary"].value_counts()
    if counts.empty:
        return frame
    target = int(counts.min())
    parts: list[pd.DataFrame] = []
    for label, group in frame.groupby("label_binary", sort=True):
        if len(group) > target:
            sampled = (
                group.assign(_stable_key=group["flow_id"].map(stable_hash))
                .sort_values("_stable_key")
                .head(target)
                .drop(columns="_stable_key")
            )
            parts.append(sort_flow_frame(sampled))
        else:
            parts.append(sort_flow_frame(group))
    return pd.concat(parts, ignore_index=True, sort=False)


def scenario_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=["label_binary", "scenario_id", "scenario_family", "flow_count", "pct_within_label"]
        )
    result = (
        frame.groupby(["label_binary", "scenario_id", "scenario_family"])
        .size()
        .rename("flow_count")
        .reset_index()
    )
    result["pct_within_label"] = (
        result["flow_count"]
        / result.groupby("label_binary")["flow_count"].transform("sum")
        * 100
    ).round(2)
    return result.sort_values(["label_binary", "flow_count"], ascending=[True, False]).reset_index(drop=True)


def family_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["label_binary", "scenario_family", "flow_count", "pct_within_label"])
    result = (
        frame.groupby(["label_binary", "scenario_family"])
        .size()
        .rename("flow_count")
        .reset_index()
    )
    result["pct_within_label"] = (
        result["flow_count"]
        / result.groupby("label_binary")["flow_count"].transform("sum")
        * 100
    ).round(2)
    return result.sort_values(["label_binary", "flow_count"], ascending=[True, False]).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a family-aware balanced v2 view from processed lab_v2 campaigns.")
    parser.add_argument(
        "--processed-root",
        default=str(Path("data") / "lab_v2" / "processed"),
        help="Root directory containing processed campaigns.",
    )
    parser.add_argument(
        "--output-root",
        default=str(Path("data") / "lab_v2" / "prepared"),
        help="Root directory for the v2 prepared view.",
    )
    parser.add_argument(
        "--view-id",
        default=f"lab_v2_balanced_v2_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}",
        help="Output directory name.",
    )
    args = parser.parse_args()

    processed_root = Path(args.processed_root).resolve()
    output_dir = Path(args.output_root).resolve() / args.view_id
    output_dir.mkdir(parents=True, exist_ok=True)

    captures = load_processed_captures(processed_root)
    all_flows = load_processed_flows(processed_root, allowed_campaigns=set(captures["campaign_id"].unique()))

    split_plan = assign_splits_by_scenario(captures)
    split_plan.to_csv(output_dir / "capture_split_plan_v2.csv", index=False)

    train_capture_ids = split_plan.loc[split_plan["split"].eq("train"), "capture_id"].tolist()
    validation_capture_ids = split_plan.loc[split_plan["split"].eq("validation"), "capture_id"].tolist()
    test_capture_ids = split_plan.loc[split_plan["split"].eq("test"), "capture_id"].tolist()

    train_source = all_flows.loc[all_flows["capture_id"].isin(train_capture_ids)].copy()
    validation_clean = all_flows.loc[all_flows["capture_id"].isin(validation_capture_ids)].copy()
    test_clean = all_flows.loc[all_flows["capture_id"].isin(test_capture_ids)].copy()

    capped_parts: list[pd.DataFrame] = []
    cap_rows: list[dict[str, object]] = []
    for capture_id, group in train_source.groupby("capture_id", sort=True):
        kept = cap_train_capture(group)
        scenario_id = str(group["scenario_id"].iloc[0])
        cap_rows.append(
            {
                "capture_id": capture_id,
                "scenario_id": scenario_id,
                "scenario_family": str(group["scenario_family"].iloc[0]),
                "label_binary": str(group["label_binary"].iloc[0]),
                "original_flow_count": int(len(group)),
                "capped_flow_count": int(len(kept)),
                "cap_applied": TRAIN_CAPS_V2.get(scenario_id),
            }
        )
        capped_parts.append(kept)

    train_capped = pd.concat(capped_parts, ignore_index=True, sort=False) if capped_parts else pd.DataFrame()
    train_balanced = balance_labels(train_capped)

    train_balanced.to_parquet(output_dir / "train_balanced.parquet", index=False)
    validation_clean.to_parquet(output_dir / "validation_clean.parquet", index=False)
    test_clean.to_parquet(output_dir / "test_clean.parquet", index=False)
    all_flows.to_parquet(output_dir / "all_flows_clean.parquet", index=False)

    pd.DataFrame(cap_rows).to_csv(output_dir / "train_capture_caps_v2.csv", index=False)
    scenario_distribution(train_source).to_csv(output_dir / "train_source_distribution.csv", index=False)
    scenario_distribution(train_capped).to_csv(output_dir / "train_capped_distribution.csv", index=False)
    scenario_distribution(train_balanced).to_csv(output_dir / "train_balanced_distribution.csv", index=False)
    family_distribution(train_balanced).to_csv(output_dir / "train_balanced_family_distribution.csv", index=False)
    family_distribution(validation_clean).to_csv(output_dir / "validation_family_distribution.csv", index=False)
    family_distribution(test_clean).to_csv(output_dir / "test_family_distribution.csv", index=False)

    split_family_presence = (
        split_plan.groupby(["split", "scenario_family"])
        .size()
        .rename("capture_count")
        .reset_index()
        .sort_values(["split", "scenario_family"])
    )
    split_family_presence.to_csv(output_dir / "split_family_presence.csv", index=False)

    summary = {
        "excluded_statuses": sorted(EXCLUDED_STATUSES),
        "ignored_campaign_prefixes": list(IGNORED_CAMPAIGN_PREFIXES),
        "train_caps_v2": TRAIN_CAPS_V2,
        "campaign_count": int(captures["campaign_id"].nunique()),
        "capture_count": int(captures["capture_id"].nunique()),
        "all_flow_rows": int(len(all_flows)),
        "all_label_counts": all_flows["label_binary"].value_counts().to_dict(),
        "train_source_rows": int(len(train_source)),
        "train_source_label_counts": train_source["label_binary"].value_counts().to_dict(),
        "train_capped_rows": int(len(train_capped)),
        "train_capped_label_counts": train_capped["label_binary"].value_counts().to_dict(),
        "train_balanced_rows": int(len(train_balanced)),
        "train_balanced_label_counts": train_balanced["label_binary"].value_counts().to_dict(),
        "validation_clean_rows": int(len(validation_clean)),
        "validation_clean_label_counts": validation_clean["label_binary"].value_counts().to_dict(),
        "test_clean_rows": int(len(test_clean)),
        "test_clean_label_counts": test_clean["label_binary"].value_counts().to_dict(),
        "split_capture_counts": split_plan["split"].value_counts().to_dict(),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Built v2 balanced view: {output_dir}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
