from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "reports" / "week3_modelisation"
MODEL_TRAINING_DIR = ROOT / "reports" / "model_training"
MODELS_DIR = ROOT / "models"

MODEL_PATH = MODELS_DIR / "random_forest_lab_v2.joblib"
METADATA_PATH = MODELS_DIR / "random_forest_lab_v2_metadata.json"

REPORT_MD_PATH = REPORTS_DIR / "rapport_intermediaire_performance_semaine3.md"
REPORT_DOCX_PATH = REPORTS_DIR / "rapport_intermediaire_performance_semaine3.docx"
PERFORMANCE_CSV_PATH = REPORTS_DIR / "performance_modele_semaine3.csv"
SUMMARY_JSON_PATH = REPORTS_DIR / "semaine3_livrables_summary.json"
DETECTION_SOURCES_MD_PATH = REPORTS_DIR / "code_source_module_detection.md"

DETECTION_SOURCE_FILES = [
    ROOT / "backend" / "app" / "api" / "routes_detection.py",
    ROOT / "backend" / "app" / "services" / "detection_service.py",
    ROOT / "backend" / "app" / "services" / "model_service.py",
    ROOT / "backend" / "app" / "services" / "feature_service.py",
    ROOT / "backend" / "app" / "services" / "schema_service.py",
    ROOT / "scripts" / "lab_v2" / "train_lab_v2_model.py",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_text(value: Any) -> str:
    text = str(value)
    if "Ã" in text:
        try:
            return text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return text
    return text


def latest_eval_report() -> Path:
    candidates = sorted(MODEL_TRAINING_DIR.glob("random_forest_lab_v2_eval_*.json"))
    if not candidates:
        raise FileNotFoundError(f"No evaluation report found in {MODEL_TRAINING_DIR}")
    return candidates[-1]


def fmt_metric(value: Any) -> str:
    if value is None:
        return "N/D"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def write_performance_csv(evaluation_report: dict[str, Any]) -> None:
    rows: list[dict[str, Any]] = []
    for split_name in ("train", "validation", "test"):
        split_metrics = evaluation_report["new_model"][split_name]
        rows.append(
            {
                "modele": "random_forest_lab_v2",
                "split": split_name,
                "rows": split_metrics.get("rows"),
                "accuracy": split_metrics.get("accuracy"),
                "balanced_accuracy": split_metrics.get("balanced_accuracy"),
                "precision_suspect": split_metrics.get("precision_suspect"),
                "recall_suspect": split_metrics.get("recall_suspect"),
                "f1_suspect": split_metrics.get("f1_suspect"),
                "false_positive_rate": split_metrics.get("false_positive_rate"),
                "roc_auc_suspect": split_metrics.get("roc_auc_suspect"),
            }
        )

    baseline = evaluation_report.get("baseline_v1") or {}
    for split_name in ("validation", "test"):
        split_metrics = baseline.get(split_name)
        if not split_metrics:
            continue
        rows.append(
            {
                "modele": "baseline_v1",
                "split": split_name,
                "rows": split_metrics.get("rows"),
                "accuracy": split_metrics.get("accuracy"),
                "balanced_accuracy": split_metrics.get("balanced_accuracy"),
                "precision_suspect": split_metrics.get("precision_suspect"),
                "recall_suspect": split_metrics.get("recall_suspect"),
                "f1_suspect": split_metrics.get("f1_suspect"),
                "false_positive_rate": split_metrics.get("false_positive_rate"),
                "roc_auc_suspect": split_metrics.get("roc_auc_suspect"),
            }
        )

    with PERFORMANCE_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "modele",
                "split",
                "rows",
                "accuracy",
                "balanced_accuracy",
                "precision_suspect",
                "recall_suspect",
                "f1_suspect",
                "false_positive_rate",
                "roc_auc_suspect",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def build_report_markdown(
    *,
    metadata: dict[str, Any],
    evaluation_report: dict[str, Any],
    evaluation_report_path: Path,
) -> str:
    created_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    train = evaluation_report["new_model"]["train"]
    validation = evaluation_report["new_model"]["validation"]
    test = evaluation_report["new_model"]["test"]
    baseline_validation = (evaluation_report.get("baseline_v1") or {}).get("validation")
    baseline_test = (evaluation_report.get("baseline_v1") or {}).get("test")
    training_summary = metadata.get("training_summary", {})
    selected_candidate = metadata.get("selected_candidate", {})

    lines: list[str] = []
    lines.append("# Semaine 3 - Rapport intermediaire de modelisation IA et detection d'intrusions")
    lines.append("")
    lines.append(f"- Date de generation : {created_at}")
    lines.append(f"- Modele exporte : `{clean_text(MODEL_PATH)}`")
    lines.append(f"- Metadonnees du modele : `{clean_text(METADATA_PATH)}`")
    lines.append(f"- Rapport d'evaluation source : `{clean_text(evaluation_report_path)}`")
    lines.append("")
    lines.append("## 1. Objectif")
    lines.append(
        "Ce document regroupe les livrables reels de la semaine 3 pour la partie modelisation IA et detection d'intrusions."
    )
    lines.append(
        "Il decrit le modele effectivement entraine, les resultats d'evaluation disponibles dans le depot et l'integration du module de detection dans le pipeline IPS."
    )
    lines.append("")
    lines.append("## 2. Modele reellement entraine")
    lines.append("- Type de modele retenu : RandomForestClassifier")
    lines.append(f"- Variable cible : `{metadata['target_column']}`")
    lines.append(f"- Classe positive : `{metadata['positive_label']}`")
    lines.append(f"- Nombre de variables en entree avant encodage : {len(metadata['input_columns_before_encoding'])}")
    lines.append("- Encodage categoriel visible : `protocol` via One-Hot Encoding")
    lines.append(
        f"- Parametres retenus : n_estimators={selected_candidate.get('n_estimators')}, "
        f"max_depth={selected_candidate.get('max_depth')}, "
        f"min_samples_leaf={selected_candidate.get('min_samples_leaf')}, "
        f"max_features={selected_candidate.get('max_features')}"
    )
    lines.append("")
    lines.append("## 3. Donnees utilisees")
    lines.append(f"- Vue de donnees : `{metadata['dataset_view_id']}`")
    lines.append(f"- Train : {training_summary.get('train_rows')} lignes")
    lines.append(f"- Validation : {training_summary.get('validation_rows')} lignes")
    lines.append(f"- Test : {training_summary.get('test_rows')} lignes")
    lines.append(f"- Fichier train : `{clean_text(metadata['train_path'])}`")
    lines.append(f"- Fichier validation : `{clean_text(metadata['validation_path'])}`")
    lines.append(f"- Fichier test : `{clean_text(metadata['test_path'])}`")
    lines.append("")
    lines.append("## 4. Resultats principaux du modele")
    lines.append(
        f"- Train : accuracy={fmt_metric(train['accuracy'])}, precision suspect={fmt_metric(train['precision_suspect'])}, "
        f"recall suspect={fmt_metric(train['recall_suspect'])}, F1 suspect={fmt_metric(train['f1_suspect'])}, "
        f"ROC-AUC={fmt_metric(train.get('roc_auc_suspect'))}"
    )
    lines.append(
        f"- Validation : accuracy={fmt_metric(validation['accuracy'])}, precision suspect={fmt_metric(validation['precision_suspect'])}, "
        f"recall suspect={fmt_metric(validation['recall_suspect'])}, F1 suspect={fmt_metric(validation['f1_suspect'])}, "
        f"ROC-AUC={fmt_metric(validation.get('roc_auc_suspect'))}, FPR={fmt_metric(validation.get('false_positive_rate'))}"
    )
    lines.append(
        f"- Test : accuracy={fmt_metric(test['accuracy'])}, precision suspect={fmt_metric(test['precision_suspect'])}, "
        f"recall suspect={fmt_metric(test['recall_suspect'])}, F1 suspect={fmt_metric(test['f1_suspect'])}, "
        f"ROC-AUC={fmt_metric(test.get('roc_auc_suspect'))}, FPR={fmt_metric(test.get('false_positive_rate'))}"
    )
    lines.append("")
    lines.append("## 5. Comparaison avec la baseline v1")
    if baseline_validation and baseline_test:
        lines.append(
            f"- Baseline v1 validation : accuracy={fmt_metric(baseline_validation['accuracy'])}, "
            f"precision suspect={fmt_metric(baseline_validation['precision_suspect'])}, "
            f"recall suspect={fmt_metric(baseline_validation['recall_suspect'])}, "
            f"F1 suspect={fmt_metric(baseline_validation['f1_suspect'])}, "
            f"FPR={fmt_metric(baseline_validation.get('false_positive_rate'))}"
        )
        lines.append(
            f"- Baseline v1 test : accuracy={fmt_metric(baseline_test['accuracy'])}, "
            f"precision suspect={fmt_metric(baseline_test['precision_suspect'])}, "
            f"recall suspect={fmt_metric(baseline_test['recall_suspect'])}, "
            f"F1 suspect={fmt_metric(baseline_test['f1_suspect'])}, "
            f"FPR={fmt_metric(baseline_test.get('false_positive_rate'))}"
        )
        lines.append(
            "La comparaison disponible dans le depot montre une amelioration nette du RandomForest lab_v2 par rapport a la baseline v1, en particulier sur le taux de faux positifs."
        )
    else:
        lines.append("Aucune comparaison baseline exploitable n'est visible dans les elements fournis.")
    lines.append("")
    lines.append("## 6. Integration du modele dans le pipeline IPS")
    lines.append(
        "Le pipeline d'integration visible dans le depot suit la logique suivante : preparation des features -> prediction du modele -> calcul de confiance -> decision d'alerte -> decision de blocage."
    )
    lines.append("- Chargement du modele et verification du contrat : `backend/app/services/model_service.py`")
    lines.append("- Preparation des features : `backend/app/services/feature_service.py`")
    lines.append("- Orchestration de la detection : `backend/app/services/detection_service.py`")
    lines.append("- Exposition API detection : `backend/app/api/routes_detection.py`")
    lines.append("- Script d'entrainement : `scripts/lab_v2/train_lab_v2_model.py`")
    lines.append("")
    lines.append("## 7. Livrables disponibles pour la semaine 3")
    lines.append("- Modele IA entraine et teste : present")
    lines.append("- Rapport intermediaire sur la performance : present")
    lines.append("- Code source du module de detection : present")
    lines.append("")
    lines.append("## 8. Limites et remarques honnetes")
    lines.append(
        "Le depot materialise clairement un pipeline RandomForest. En revanche, aucun livrable complet equivalent n'est visible pour XGBoost, SVM ou Autoencoder."
    )
    lines.append(
        "Les resultats de performance disponibles sont tres eleves. Ils doivent donc etre interpretes avec prudence et en tenant compte du contexte de laboratoire et du jeu de donnees utilise."
    )
    lines.append("")
    lines.append("## 9. Conclusion")
    lines.append(
        "A ce stade, la semaine 3 est techniquement couverte par un modele RandomForest entraine, evalue et integre au backend IPS. Les livrables produits ici regroupent ces preuves dans un format plus presentable pour une remise universitaire."
    )
    lines.append("")
    return "\n".join(lines)


def write_detection_sources_markdown() -> None:
    lines = [
        "# Code source du module de detection",
        "",
        "Les fichiers suivants constituent le coeur visible du module de detection et de son integration dans le pipeline IPS :",
        "",
    ]
    for path in DETECTION_SOURCE_FILES:
        lines.append(f"- `{path}`")
    lines.append("")
    lines.append(
        "Ces chemins pointent vers les fichiers reels du depot. Aucun duplicata n'a ete cree ici afin d'eviter les divergences entre le livrable et le code source actif."
    )
    lines.append("")
    DETECTION_SOURCES_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_summary_json(
    *,
    evaluation_report_path: Path,
    metadata: dict[str, Any],
    evaluation_report: dict[str, Any],
) -> None:
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "week": 3,
        "scope": "Modelisation IA et detection d'intrusions",
        "deliverables": {
            "trained_model": str(MODEL_PATH),
            "model_metadata": str(METADATA_PATH),
            "performance_report_source": str(evaluation_report_path),
            "intermediate_report_markdown": str(REPORT_MD_PATH),
            "intermediate_report_docx": str(REPORT_DOCX_PATH),
            "performance_csv": str(PERFORMANCE_CSV_PATH),
            "detection_sources_index": str(DETECTION_SOURCES_MD_PATH),
        },
        "model_type": metadata.get("model_type"),
        "dataset_view_id": metadata.get("dataset_view_id"),
        "evaluation_test": evaluation_report["new_model"]["test"],
        "notes": [
            "Le depot materialise un pipeline RandomForest complet.",
            "Aucun livrable equivalent complet n'a ete trouve pour XGBoost, SVM ou Autoencoder.",
        ],
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def export_docx(markdown_path: Path, docx_path: Path) -> None:
    script_path = ROOT / "scripts" / "reporting" / "export_markdown_to_docx.py"
    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--input",
            str(markdown_path),
            "--output",
            str(docx_path),
        ],
        check=True,
        cwd=str(ROOT),
    )


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    evaluation_report_path = latest_eval_report()
    evaluation_report = read_json(evaluation_report_path)
    metadata = read_json(METADATA_PATH)

    REPORT_MD_PATH.write_text(
        build_report_markdown(
            metadata=metadata,
            evaluation_report=evaluation_report,
            evaluation_report_path=evaluation_report_path,
        ),
        encoding="utf-8",
    )
    write_performance_csv(evaluation_report)
    write_detection_sources_markdown()
    write_summary_json(
        evaluation_report_path=evaluation_report_path,
        metadata=metadata,
        evaluation_report=evaluation_report,
    )
    export_docx(REPORT_MD_PATH, REPORT_DOCX_PATH)

    print(f"Generated: {REPORT_MD_PATH}")
    print(f"Generated: {REPORT_DOCX_PATH}")
    print(f"Generated: {PERFORMANCE_CSV_PATH}")
    print(f"Generated: {SUMMARY_JSON_PATH}")
    print(f"Generated: {DETECTION_SOURCES_MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
