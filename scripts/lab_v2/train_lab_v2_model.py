from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


BASELINE_MODEL_PATH = Path(
    r"K:\4. UQO\04. INF4523 - Réseaux d'ordinateurs\7. IPS - IA - INF4523 met a jour\models\random_forest_v1.joblib"
)
BASELINE_METADATA_PATH = Path(
    r"K:\4. UQO\04. INF4523 - Réseaux d'ordinateurs\7. IPS - IA - INF4523 met a jour\models\random_forest_v1_metadata.json"
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_dataset(df: pd.DataFrame, feature_columns: list[str], target_column: str) -> pd.DataFrame:
    context_columns = [column for column in ("capture_id", "scenario_id", "scenario_family") if column in df.columns]
    required = feature_columns + [target_column]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise KeyError(f"Dataset missing required columns: {missing}")
    prepared = df[required + context_columns].copy()
    prepared["protocol"] = prepared["protocol"].astype(str)
    for column in feature_columns:
        if column == "protocol":
            continue
        prepared[column] = pd.to_numeric(prepared[column], errors="raise")
    prepared[target_column] = prepared[target_column].astype(str)
    return prepared


def build_pipeline(
    feature_columns: list[str],
    categorical_columns: list[str],
    model_params: dict[str, Any],
) -> Pipeline:
    numeric_columns = [column for column in feature_columns if column not in categorical_columns]
    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical_columns),
            ("numeric", "passthrough", numeric_columns),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    classifier = RandomForestClassifier(
        n_estimators=int(model_params["n_estimators"]),
        max_depth=int(model_params["max_depth"]) if model_params["max_depth"] is not None else None,
        min_samples_leaf=int(model_params["min_samples_leaf"]),
        max_features=model_params["max_features"],
        random_state=42,
        n_jobs=-1,
    )
    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", classifier),
        ]
    )


def evaluate_model(
    model: Any,
    frame: pd.DataFrame,
    *,
    feature_columns: list[str],
    target_column: str,
    positive_label: str,
) -> dict[str, Any]:
    x = frame[feature_columns]
    y_true = frame[target_column].astype(str)
    y_pred = pd.Series(model.predict(x), index=frame.index, dtype="object").astype(str)
    label_order = sorted(pd.unique(pd.concat([y_true, y_pred], ignore_index=True)))

    metrics: dict[str, Any] = {
        "rows": int(len(frame)),
        "label_counts": y_true.value_counts().to_dict(),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 6),
        "precision_suspect": round(float(precision_score(y_true, y_pred, pos_label=positive_label, zero_division=0)), 6),
        "recall_suspect": round(float(recall_score(y_true, y_pred, pos_label=positive_label, zero_division=0)), 6),
        "f1_suspect": round(float(f1_score(y_true, y_pred, pos_label=positive_label, zero_division=0)), 6),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=label_order).tolist(),
        "confusion_labels": label_order,
        "classification_report": classification_report(y_true, y_pred, labels=label_order, output_dict=True, zero_division=0),
    }

    # false positive rate for the suspect class
    if set(["normal", positive_label]).issubset(label_order):
        cm = confusion_matrix(y_true, y_pred, labels=["normal", positive_label])
        tn, fp, fn, tp = cm.ravel()
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        metrics["false_positive_rate"] = round(float(fpr), 6)

    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(x)
        classes = [str(value) for value in model.classes_]
        if positive_label in classes:
            positive_index = classes.index(positive_label)
            positive_scores = probabilities[:, positive_index]
            try:
                metrics["roc_auc_suspect"] = round(float(roc_auc_score((y_true == positive_label).astype(int), positive_scores)), 6)
            except ValueError:
                metrics["roc_auc_suspect"] = None
            metrics["mean_probability_suspect"] = round(float(positive_scores.mean()), 6)

    per_scenario = (
        pd.DataFrame(
            {
                "scenario_id": frame["scenario_id"].astype(str).values if "scenario_id" in frame.columns else "unknown",
                "scenario_family": frame["scenario_family"].astype(str).values if "scenario_family" in frame.columns else "unknown",
                "y_true": y_true.values,
                "y_pred": y_pred.values,
            }
        )
        .groupby(["scenario_id", "scenario_family"])
        .apply(
            lambda group: pd.Series(
                {
                    "rows": len(group),
                    "accuracy": accuracy_score(group["y_true"], group["y_pred"]),
                    "predicted_suspect_rate": (group["y_pred"] == positive_label).mean(),
                    "true_suspect_rate": (group["y_true"] == positive_label).mean(),
                }
            ),
            include_groups=False,
        )
        .reset_index()
        .sort_values(["rows", "scenario_id"], ascending=[False, True])
    )
    metrics["scenario_breakdown"] = per_scenario.to_dict("records")
    return metrics


def markdown_report(
    *,
    output_model_path: Path,
    output_metadata_path: Path,
    train_metrics: dict[str, Any],
    validation_metrics: dict[str, Any],
    test_metrics: dict[str, Any],
    baseline_validation: dict[str, Any] | None,
    baseline_test: dict[str, Any] | None,
) -> str:
    lines: list[str] = []
    lines.append("# RandomForest lab_v2 Training Report")
    lines.append("")
    lines.append(f"- Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Exported model: `{output_model_path}`")
    lines.append(f"- Exported metadata: `{output_metadata_path}`")
    lines.append("")
    lines.append("## New Model Metrics")
    lines.append("")
    lines.append("| Split | Rows | Accuracy | Balanced Acc. | Precision suspect | Recall suspect | F1 suspect | FPR | ROC AUC |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name, metrics in [("train", train_metrics), ("validation", validation_metrics), ("test", test_metrics)]:
        lines.append(
            f"| {name} | {metrics['rows']} | {metrics['accuracy']:.4f} | {metrics['balanced_accuracy']:.4f} | "
            f"{metrics['precision_suspect']:.4f} | {metrics['recall_suspect']:.4f} | {metrics['f1_suspect']:.4f} | "
            f"{metrics.get('false_positive_rate', 0.0):.4f} | {metrics.get('roc_auc_suspect', 0.0) or 0.0:.4f} |"
        )
    lines.append("")
    if baseline_validation and baseline_test:
        lines.append("## Baseline Comparison (v1 on lab_v2)")
        lines.append("")
        lines.append("| Model | Split | Accuracy | Balanced Acc. | Precision suspect | Recall suspect | F1 suspect | FPR | ROC AUC |")
        lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
        for split_name, metrics in [("validation", baseline_validation), ("test", baseline_test)]:
            lines.append(
                f"| baseline_v1 | {split_name} | {metrics['accuracy']:.4f} | {metrics['balanced_accuracy']:.4f} | "
                f"{metrics['precision_suspect']:.4f} | {metrics['recall_suspect']:.4f} | {metrics['f1_suspect']:.4f} | "
                f"{metrics.get('false_positive_rate', 0.0):.4f} | {metrics.get('roc_auc_suspect', 0.0) or 0.0:.4f} |"
            )
        for split_name, metrics in [("validation", validation_metrics), ("test", test_metrics)]:
            lines.append(
                f"| random_forest_lab_v2 | {split_name} | {metrics['accuracy']:.4f} | {metrics['balanced_accuracy']:.4f} | "
                f"{metrics['precision_suspect']:.4f} | {metrics['recall_suspect']:.4f} | {metrics['f1_suspect']:.4f} | "
                f"{metrics.get('false_positive_rate', 0.0):.4f} | {metrics.get('roc_auc_suspect', 0.0) or 0.0:.4f} |"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Train and evaluate a RandomForest model on lab_v2_balanced_v2.")
    parser.add_argument(
        "--prepared-dir",
        default=str(Path("data") / "lab_v2" / "prepared" / "lab_v2_balanced_v2_20260328_1310"),
        help="Prepared dataset directory containing train_balanced/validation_clean/test_clean parquet files.",
    )
    parser.add_argument(
        "--baseline-model-path",
        default=str(BASELINE_MODEL_PATH),
        help="Optional baseline model path to compare against.",
    )
    parser.add_argument(
        "--baseline-metadata-path",
        default=str(BASELINE_METADATA_PATH),
        help="Optional baseline metadata path to compare against and to reuse the feature contract.",
    )
    parser.add_argument(
        "--output-model-path",
        default=str(Path("models") / "random_forest_lab_v2.joblib"),
        help="Output path for the trained model.",
    )
    parser.add_argument(
        "--output-metadata-path",
        default=str(Path("models") / "random_forest_lab_v2_metadata.json"),
        help="Output path for the exported metadata JSON.",
    )
    parser.add_argument(
        "--report-dir",
        default=str(Path("reports") / "model_training"),
        help="Directory where evaluation reports will be written.",
    )
    args = parser.parse_args()

    prepared_dir = Path(args.prepared_dir).resolve()
    output_model_path = Path(args.output_model_path).resolve()
    output_metadata_path = Path(args.output_metadata_path).resolve()
    report_dir = Path(args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    output_model_path.parent.mkdir(parents=True, exist_ok=True)
    output_metadata_path.parent.mkdir(parents=True, exist_ok=True)

    baseline_metadata = load_json(Path(args.baseline_metadata_path))
    feature_columns = list(baseline_metadata["input_columns_before_encoding"])
    target_column = str(baseline_metadata["target_column"])
    positive_label = str(baseline_metadata["positive_label"])
    categorical_columns = [column for column in feature_columns if column == "protocol"]

    train_df = ensure_dataset(pd.read_parquet(prepared_dir / "train_balanced.parquet"), feature_columns, target_column)
    validation_df = ensure_dataset(pd.read_parquet(prepared_dir / "validation_clean.parquet"), feature_columns, target_column)
    test_df = ensure_dataset(pd.read_parquet(prepared_dir / "test_clean.parquet"), feature_columns, target_column)

    model_params = dict(baseline_metadata["selected_candidate"])
    pipeline = build_pipeline(feature_columns, categorical_columns, model_params)
    pipeline.fit(train_df[feature_columns], train_df[target_column])

    train_metrics = evaluate_model(
        pipeline, train_df, feature_columns=feature_columns, target_column=target_column, positive_label=positive_label
    )
    validation_metrics = evaluate_model(
        pipeline, validation_df, feature_columns=feature_columns, target_column=target_column, positive_label=positive_label
    )
    test_metrics = evaluate_model(
        pipeline, test_df, feature_columns=feature_columns, target_column=target_column, positive_label=positive_label
    )

    baseline_validation: dict[str, Any] | None = None
    baseline_test: dict[str, Any] | None = None
    baseline_model_path = Path(args.baseline_model_path)
    if baseline_model_path.exists():
        baseline_model = joblib.load(baseline_model_path)
        baseline_validation = evaluate_model(
            baseline_model,
            validation_df,
            feature_columns=feature_columns,
            target_column=target_column,
            positive_label=positive_label,
        )
        baseline_test = evaluate_model(
            baseline_model,
            test_df,
            feature_columns=feature_columns,
            target_column=target_column,
            positive_label=positive_label,
        )

    joblib.dump(pipeline, output_model_path)

    exported_metadata = {
        "model_type": "RandomForestClassifier",
        "target_column": target_column,
        "positive_label": positive_label,
        "selected_candidate": model_params,
        "excluded_columns": baseline_metadata["excluded_columns"],
        "input_columns_before_encoding": feature_columns,
        "train_path": str(prepared_dir / "train_balanced.parquet"),
        "validation_path": str(prepared_dir / "validation_clean.parquet"),
        "test_path": str(prepared_dir / "test_clean.parquet"),
        "dataset_view_id": prepared_dir.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "training_summary": {
            "train_rows": len(train_df),
            "validation_rows": len(validation_df),
            "test_rows": len(test_df),
            "train_label_counts": train_df[target_column].value_counts().to_dict(),
            "validation_label_counts": validation_df[target_column].value_counts().to_dict(),
            "test_label_counts": test_df[target_column].value_counts().to_dict(),
        },
        "evaluation": {
            "train": {
                "accuracy": train_metrics["accuracy"],
                "balanced_accuracy": train_metrics["balanced_accuracy"],
                "precision_suspect": train_metrics["precision_suspect"],
                "recall_suspect": train_metrics["recall_suspect"],
                "f1_suspect": train_metrics["f1_suspect"],
                "false_positive_rate": train_metrics.get("false_positive_rate"),
                "roc_auc_suspect": train_metrics.get("roc_auc_suspect"),
            },
            "validation": {
                "accuracy": validation_metrics["accuracy"],
                "balanced_accuracy": validation_metrics["balanced_accuracy"],
                "precision_suspect": validation_metrics["precision_suspect"],
                "recall_suspect": validation_metrics["recall_suspect"],
                "f1_suspect": validation_metrics["f1_suspect"],
                "false_positive_rate": validation_metrics.get("false_positive_rate"),
                "roc_auc_suspect": validation_metrics.get("roc_auc_suspect"),
            },
            "test": {
                "accuracy": test_metrics["accuracy"],
                "balanced_accuracy": test_metrics["balanced_accuracy"],
                "precision_suspect": test_metrics["precision_suspect"],
                "recall_suspect": test_metrics["recall_suspect"],
                "f1_suspect": test_metrics["f1_suspect"],
                "false_positive_rate": test_metrics.get("false_positive_rate"),
                "roc_auc_suspect": test_metrics.get("roc_auc_suspect"),
            },
        },
    }
    output_metadata_path.write_text(json.dumps(exported_metadata, indent=2), encoding="utf-8")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_report_path = report_dir / f"random_forest_lab_v2_eval_{timestamp}.json"
    md_report_path = report_dir / f"random_forest_lab_v2_eval_{timestamp}.md"
    json_report = {
        "model_path": str(output_model_path),
        "metadata_path": str(output_metadata_path),
        "prepared_dir": str(prepared_dir),
        "new_model": {
            "train": train_metrics,
            "validation": validation_metrics,
            "test": test_metrics,
        },
        "baseline_v1": {
            "validation": baseline_validation,
            "test": baseline_test,
        },
    }
    json_report_path.write_text(json.dumps(json_report, indent=2), encoding="utf-8")
    md_report_path.write_text(
        markdown_report(
            output_model_path=output_model_path,
            output_metadata_path=output_metadata_path,
            train_metrics=train_metrics,
            validation_metrics=validation_metrics,
            test_metrics=test_metrics,
            baseline_validation=baseline_validation,
            baseline_test=baseline_test,
        ),
        encoding="utf-8",
    )

    print(f"Exported model: {output_model_path}")
    print(f"Exported metadata: {output_metadata_path}")
    print(f"JSON report: {json_report_path}")
    print(f"Markdown report: {md_report_path}")
    print("Validation metrics:", json.dumps(validation_metrics, indent=2)[:2500])
    print("Test metrics:", json.dumps(test_metrics, indent=2)[:2500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
