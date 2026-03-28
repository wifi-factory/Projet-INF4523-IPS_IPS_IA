from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd


SPLITS = ("train", "validation", "test")


def assign_splits(captures: pd.DataFrame) -> pd.DataFrame:
    records: list[pd.DataFrame] = []
    for label, group in captures.groupby("label_binary", sort=True):
        group = group.sort_values(["campaign_id", "scenario_id", "capture_id"]).reset_index(drop=True)
        total = len(group)
        if total >= 3:
            n_train = max(1, round(total * 0.7))
            n_validation = max(1, round(total * 0.15))
            n_test = max(1, total - n_train - n_validation)
            while n_train + n_validation + n_test > total:
                if n_train >= n_validation and n_train >= n_test and n_train > 1:
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
            n_train, n_validation, n_test = total, 0, 0

        split_labels = (
            ["train"] * n_train
            + ["validation"] * n_validation
            + ["test"] * n_test
        )
        group = group.copy()
        group["split"] = split_labels[:total]
        records.append(group)
    return pd.concat(records, ignore_index=True, sort=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare initial train/validation/test parquet files from lab_v2 processed campaigns.")
    parser.add_argument(
        "--processed-root",
        default=str(Path("data") / "lab_v2" / "processed"),
        help="Root directory containing processed campaign folders.",
    )
    parser.add_argument(
        "--output-root",
        default=str(Path("data") / "lab_v2" / "prepared"),
        help="Root directory for split outputs.",
    )
    parser.add_argument(
        "--split-id",
        default=f"split_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}",
        help="Directory name for this split preparation run.",
    )
    args = parser.parse_args()

    processed_root = Path(args.processed_root).resolve()
    campaigns = sorted(path for path in processed_root.iterdir() if path.is_dir())
    flow_frames: list[pd.DataFrame] = []
    capture_frames: list[pd.DataFrame] = []

    for campaign_dir in campaigns:
        flows_path = campaign_dir / "flows.parquet"
        summary_path = campaign_dir / "capture_summary.csv"
        if flows_path.exists():
            flow_frames.append(pd.read_parquet(flows_path))
        if summary_path.exists():
            capture_frames.append(pd.read_csv(summary_path))

    if not flow_frames or not capture_frames:
        raise FileNotFoundError("No processed campaigns with flows.parquet and capture_summary.csv were found.")

    all_flows = pd.concat(flow_frames, ignore_index=True, sort=False)
    captures = pd.concat(capture_frames, ignore_index=True, sort=False)
    split_plan = assign_splits(captures)

    split_output_dir = Path(args.output_root).resolve() / args.split_id
    split_output_dir.mkdir(parents=True, exist_ok=True)

    all_flows.to_parquet(split_output_dir / "all_flows.parquet", index=False)
    split_plan.to_csv(split_output_dir / "capture_split_plan.csv", index=False)

    for split_name in SPLITS:
        capture_ids = split_plan.loc[split_plan["split"].eq(split_name), "capture_id"].tolist()
        subset = all_flows.loc[all_flows["capture_id"].isin(capture_ids)].reset_index(drop=True)
        if not subset.empty:
            subset.to_parquet(split_output_dir / f"{split_name}.parquet", index=False)

    summary = (
        split_plan.groupby(["split", "label_binary"])
        .size()
        .rename("capture_count")
        .reset_index()
    )
    summary.to_csv(split_output_dir / "split_summary.csv", index=False)

    print(f"Prepared split directory: {split_output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
