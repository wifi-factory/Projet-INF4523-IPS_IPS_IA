from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


FEATURE_DETAILS: dict[str, dict[str, str]] = {
    "protocol": {
        "category": "network_identity",
        "week2_requirement": "protocoles",
        "source": "flow header",
        "normalization_strategy": "categorical cast + OneHotEncoder",
        "notes": "Unique feature categorical retained in the final model contract.",
    },
    "src_port": {
        "category": "network_identity",
        "week2_requirement": "ports",
        "source": "flow header",
        "normalization_strategy": "integer coercion",
        "notes": "Port source extracted at flow level.",
    },
    "dst_port": {
        "category": "network_identity",
        "week2_requirement": "ports",
        "source": "flow header",
        "normalization_strategy": "integer coercion",
        "notes": "Port destination extracted at flow level.",
    },
    "duration_ms": {
        "category": "temporal",
        "week2_requirement": "duree des sessions",
        "source": "flow aggregation",
        "normalization_strategy": "float coercion",
        "notes": "Session duration in milliseconds.",
    },
    "packet_count_total": {
        "category": "volume",
        "week2_requirement": "nombre de paquets",
        "source": "flow aggregation",
        "normalization_strategy": "integer coercion",
        "notes": "Total packets observed in the flow.",
    },
    "packet_count_fwd": {
        "category": "volume",
        "week2_requirement": "nombre de paquets",
        "source": "flow aggregation",
        "normalization_strategy": "integer coercion",
        "notes": "Forward-direction packet count.",
    },
    "packet_count_bwd": {
        "category": "volume",
        "week2_requirement": "nombre de paquets",
        "source": "flow aggregation",
        "normalization_strategy": "integer coercion",
        "notes": "Backward-direction packet count.",
    },
    "byte_count_total": {
        "category": "volume",
        "week2_requirement": "taille",
        "source": "flow aggregation",
        "normalization_strategy": "integer coercion",
        "notes": "Total bytes exchanged in the flow.",
    },
    "byte_count_fwd": {
        "category": "volume",
        "week2_requirement": "taille",
        "source": "flow aggregation",
        "normalization_strategy": "integer coercion",
        "notes": "Forward-direction byte count.",
    },
    "byte_count_bwd": {
        "category": "volume",
        "week2_requirement": "taille",
        "source": "flow aggregation",
        "normalization_strategy": "integer coercion",
        "notes": "Backward-direction byte count.",
    },
    "pkt_len_min": {
        "category": "packet_shape",
        "week2_requirement": "taille",
        "source": "flow aggregation",
        "normalization_strategy": "float coercion",
        "notes": "Minimum observed packet length.",
    },
    "pkt_len_max": {
        "category": "packet_shape",
        "week2_requirement": "taille",
        "source": "flow aggregation",
        "normalization_strategy": "float coercion",
        "notes": "Maximum observed packet length.",
    },
    "pkt_len_mean": {
        "category": "packet_shape",
        "week2_requirement": "taille",
        "source": "flow aggregation",
        "normalization_strategy": "float coercion",
        "notes": "Mean packet length.",
    },
    "pkt_len_std": {
        "category": "packet_shape",
        "week2_requirement": "taille",
        "source": "flow aggregation",
        "normalization_strategy": "float coercion",
        "notes": "Packet length dispersion.",
    },
    "iat_min_ms": {
        "category": "temporal",
        "week2_requirement": "duree des sessions",
        "source": "flow aggregation",
        "normalization_strategy": "float coercion",
        "notes": "Minimum inter-arrival time.",
    },
    "iat_max_ms": {
        "category": "temporal",
        "week2_requirement": "duree des sessions",
        "source": "flow aggregation",
        "normalization_strategy": "float coercion",
        "notes": "Maximum inter-arrival time.",
    },
    "iat_mean_ms": {
        "category": "temporal",
        "week2_requirement": "duree des sessions",
        "source": "flow aggregation",
        "normalization_strategy": "float coercion",
        "notes": "Mean inter-arrival time.",
    },
    "iat_std_ms": {
        "category": "temporal",
        "week2_requirement": "duree des sessions",
        "source": "flow aggregation",
        "normalization_strategy": "float coercion",
        "notes": "Inter-arrival time dispersion.",
    },
    "syn_count": {
        "category": "tcp_flags",
        "week2_requirement": "flags TCP",
        "source": "flow aggregation",
        "normalization_strategy": "integer coercion",
        "notes": "Count of TCP SYN flags.",
    },
    "ack_count": {
        "category": "tcp_flags",
        "week2_requirement": "flags TCP",
        "source": "flow aggregation",
        "normalization_strategy": "integer coercion",
        "notes": "Count of TCP ACK flags.",
    },
    "rst_count": {
        "category": "tcp_flags",
        "week2_requirement": "flags TCP",
        "source": "flow aggregation",
        "normalization_strategy": "integer coercion",
        "notes": "Count of TCP RST flags.",
    },
    "fin_count": {
        "category": "tcp_flags",
        "week2_requirement": "flags TCP",
        "source": "flow aggregation",
        "normalization_strategy": "integer coercion",
        "notes": "Count of TCP FIN flags.",
    },
    "psh_count": {
        "category": "tcp_flags",
        "week2_requirement": "flags TCP",
        "source": "flow aggregation",
        "normalization_strategy": "integer coercion",
        "notes": "Count of TCP PSH flags.",
    },
    "icmp_echo_req_count": {
        "category": "icmp",
        "week2_requirement": "protocoles",
        "source": "flow aggregation",
        "normalization_strategy": "integer coercion",
        "notes": "ICMP echo request count.",
    },
    "icmp_echo_reply_count": {
        "category": "icmp",
        "week2_requirement": "protocoles",
        "source": "flow aggregation",
        "normalization_strategy": "integer coercion",
        "notes": "ICMP echo reply count.",
    },
    "connections_per_1s": {
        "category": "behavioral_window",
        "week2_requirement": "feature engineering comportemental",
        "source": "sliding window",
        "normalization_strategy": "float coercion",
        "notes": "Short-window connection burst indicator.",
    },
    "connections_per_5s": {
        "category": "behavioral_window",
        "week2_requirement": "feature engineering comportemental",
        "source": "sliding window",
        "normalization_strategy": "float coercion",
        "notes": "Longer-window connection burst indicator.",
    },
    "distinct_dst_ports_per_5s": {
        "category": "behavioral_window",
        "week2_requirement": "ports",
        "source": "sliding window",
        "normalization_strategy": "float coercion",
        "notes": "Useful for scan-like multiport behavior.",
    },
    "distinct_dst_ips_per_5s": {
        "category": "behavioral_window",
        "week2_requirement": "feature engineering comportemental",
        "source": "sliding window",
        "normalization_strategy": "float coercion",
        "notes": "Useful for multicible behavior.",
    },
    "icmp_packets_per_1s": {
        "category": "behavioral_window",
        "week2_requirement": "protocoles",
        "source": "sliding window",
        "normalization_strategy": "float coercion",
        "notes": "ICMP burst feature.",
    },
    "failed_connection_ratio": {
        "category": "behavioral_window",
        "week2_requirement": "feature engineering comportemental",
        "source": "sliding window",
        "normalization_strategy": "float coercion",
        "notes": "Tracks failed connection behavior.",
    },
}


ENTROPY_CANDIDATE = {
    "feature_name": "payload_entropy",
    "category": "payload_candidate",
    "dtype_train": "not_computed",
    "included_in_model": False,
    "week2_requirement": "entropie du payload",
    "source": "payload bytes",
    "normalization_strategy": "not implemented in final contract",
    "notes": (
        "Mentioned in the week-2 objectives, but not retained in the final "
        "31-feature flow-level contract. The deployed prototype relies on "
        "behavioral and transport-level indicators instead."
    ),
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_numeric_feature(frame: pd.Series) -> dict[str, Any]:
    numeric = pd.to_numeric(frame, errors="coerce")
    return {
        "non_null_count": int(numeric.notna().sum()),
        "null_count": int(numeric.isna().sum()),
        "null_rate": round(float(numeric.isna().mean()), 6),
        "min": None if numeric.dropna().empty else round(float(numeric.min()), 6),
        "max": None if numeric.dropna().empty else round(float(numeric.max()), 6),
        "mean": None if numeric.dropna().empty else round(float(numeric.mean()), 6),
        "std": None if numeric.dropna().empty else round(float(numeric.std(ddof=0)), 6),
    }


def summarize_categorical_feature(frame: pd.Series) -> dict[str, Any]:
    values = frame.astype(str)
    top_values = values.value_counts(dropna=False).head(5).to_dict()
    return {
        "non_null_count": int(frame.notna().sum()),
        "null_count": int(frame.isna().sum()),
        "null_rate": round(float(frame.isna().mean()), 6),
        "top_values": json.dumps(top_values, ensure_ascii=False),
    }


def build_feature_catalog(metadata: dict[str, Any], train_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for feature_name in metadata["input_columns_before_encoding"]:
        details = FEATURE_DETAILS.get(
            feature_name,
            {
                "category": "other",
                "week2_requirement": "autre",
                "source": "flow aggregation",
                "normalization_strategy": "type coercion",
                "notes": "",
            },
        )
        rows.append(
            {
                "feature_name": feature_name,
                "category": details["category"],
                "dtype_train": str(train_df[feature_name].dtype),
                "included_in_model": True,
                "week2_requirement": details["week2_requirement"],
                "source": details["source"],
                "normalization_strategy": details["normalization_strategy"],
                "notes": details["notes"],
            }
        )
    rows.append(ENTROPY_CANDIDATE)
    return pd.DataFrame(rows)


def build_feature_statistics(metadata: dict[str, Any], train_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for feature_name in metadata["input_columns_before_encoding"]:
        base = {"feature_name": feature_name}
        if feature_name == "protocol":
            rows.append(base | summarize_categorical_feature(train_df[feature_name]))
        else:
            rows.append(base | summarize_numeric_feature(train_df[feature_name]))
    return pd.DataFrame(rows)


def build_preprocessing_summary(metadata: dict[str, Any], splits: dict[str, pd.DataFrame]) -> dict[str, Any]:
    feature_columns = list(metadata["input_columns_before_encoding"])
    split_summary: dict[str, Any] = {}
    for split_name, frame in splits.items():
        split_summary[split_name] = {
            "rows": int(len(frame)),
            "columns": int(len(frame.columns)),
            "label_counts": frame["label_binary"].astype(str).value_counts().to_dict()
            if "label_binary" in frame.columns
            else {},
        }

    return {
        "objective": "Semaine 2 - Pretraitement et feature engineering",
        "model_contract_feature_count": len(feature_columns),
        "categorical_features": ["protocol"],
        "numeric_features": [column for column in feature_columns if column != "protocol"],
        "cleaning_rules": [
            "Verification de la presence de toutes les features requises avant inference.",
            "Coercition stricte des variables numeriques vers int/float.",
            "Conversion des protocoles en texte puis encodage One-Hot dans le pipeline scikit-learn.",
            "Colonnes de contexte exclues du modele: src_ip, dst_ip, timestamps, scenario_id, capture_id, severity.",
            "Aucune standardisation globale appliquee car le modele final est un RandomForest, peu sensible a l'echelle.",
        ],
        "week2_alignment": {
            "ports_protocols_duration": True,
            "packet_counts_sizes_tcp_flags": True,
            "payload_entropy": False,
            "data_cleaning_and_normalization": True,
        },
        "splits": split_summary,
    }


def build_markdown_report(
    *,
    metadata_path: Path,
    output_dir: Path,
    catalog: pd.DataFrame,
    statistics: pd.DataFrame,
    summary: dict[str, Any],
) -> str:
    implemented = catalog[catalog["included_in_model"] == True]["feature_name"].tolist()
    missing_week2 = catalog[catalog["included_in_model"] == False]["feature_name"].tolist()
    protocol_values = "N/A"
    protocol_row = statistics.loc[statistics["feature_name"] == "protocol"]
    if not protocol_row.empty and "top_values" in protocol_row.columns:
        protocol_values = str(protocol_row.iloc[0]["top_values"])

    lines = [
        "# Semaine 2 - Pretraitement et Feature Engineering",
        "",
        "## Objectif",
        "",
        "Formaliser les livrables de la semaine 2 a partir du pipeline reel du projet :",
        "- extraction des features reseau pertinentes ;",
        "- nettoyage et preparation des donnees ;",
        "- justification des choix de normalisation pour le modele final.",
        "",
        "## Source technique retenue",
        "",
        f"- Metadata modele : `{metadata_path}`",
        f"- Dossier de sortie : `{output_dir}`",
        "",
        "## Features effectivement retenues dans le contrat final",
        "",
        f"- Nombre total : **{summary['model_contract_feature_count']}**",
        f"- Features categorielle : **{', '.join(summary['categorical_features'])}**",
        f"- Features numeriques : **{len(summary['numeric_features'])}**",
        "",
        "### Correspondance avec les attentes de la semaine 2",
        "",
        "- Ports, protocoles, duree des sessions : **implantes**",
        "- Nombre de paquets, tailles, flags TCP : **implantes**",
        "- Nettoyage et normalisation : **implantes**",
        "- Entropie du payload : **non retenue dans le contrat final deploye**",
        "",
        "## Nettoyage et normalisation reellement appliques",
        "",
    ]
    for rule in summary["cleaning_rules"]:
        lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "## Observation importante",
            "",
            "Le modele final ne repose pas sur une normalisation de type StandardScaler/MinMaxScaler.",
            "Ce choix est coherent avec l'utilisation d'un RandomForest, qui supporte bien les echelles heterogenes.",
            "La vraie logique de normalisation ici est donc :",
            "- nettoyage des types ;",
            "- controle du schema ;",
            "- encodage du protocole ;",
            "- exclusion des colonnes contextuelles non generalisables.",
            "",
            "## Exemple de distribution",
            "",
            f"- Valeurs dominantes pour `protocol` dans le train : `{protocol_values}`",
            "",
            "## Features candidates non retenues",
            "",
            f"- {', '.join(missing_week2) if missing_week2 else 'aucune'}",
            "",
            "## Artefacts generes",
            "",
            "- `feature_catalog.csv` : catalogue des features et lien avec les objectifs Semaine 2",
            "- `train_feature_statistics.csv` : statistiques descriptives du split train",
            "- `preprocessing_summary.json` : resume machine-readable du nettoyage et des splits",
            "",
            "## Conclusion",
            "",
            "Le livrable Semaine 2 est donc bien materialise dans le projet actuel,",
            "mais avec une nuance importante : l'entropie du payload etait une piste de feature engineering,",
            "alors que la version finale deploye principalement des features flow-level et comportementales.",
            "",
            "Les artefacts ci-dessus peuvent etre repris tels quels dans le rapport ou les slides.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate week-2 preprocessing and feature engineering deliverables."
    )
    parser.add_argument(
        "--metadata-path",
        default=str(Path("models") / "random_forest_lab_v2_metadata.json"),
        help="Model metadata JSON describing the deployed feature contract.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("reports") / "week2_preprocessing"),
        help="Directory where the week-2 deliverables will be written.",
    )
    args = parser.parse_args()

    metadata_path = Path(args.metadata_path).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = load_json(metadata_path)
    split_paths = {
        "train": Path(metadata["train_path"]),
        "validation": Path(metadata["validation_path"]),
        "test": Path(metadata["test_path"]),
    }
    splits = {name: pd.read_parquet(path) for name, path in split_paths.items()}
    train_df = splits["train"]

    catalog = build_feature_catalog(metadata, train_df)
    statistics = build_feature_statistics(metadata, train_df)
    summary = build_preprocessing_summary(metadata, splits)
    markdown_report = build_markdown_report(
        metadata_path=metadata_path,
        output_dir=output_dir,
        catalog=catalog,
        statistics=statistics,
        summary=summary,
    )

    catalog_path = output_dir / "feature_catalog.csv"
    statistics_path = output_dir / "train_feature_statistics.csv"
    summary_path = output_dir / "preprocessing_summary.json"
    report_path = output_dir / "semaine2_pretraitement_feature_engineering.md"

    catalog.to_csv(catalog_path, index=False)
    statistics.to_csv(statistics_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(markdown_report, encoding="utf-8")

    print(f"Generated: {catalog_path}")
    print(f"Generated: {statistics_path}")
    print(f"Generated: {summary_path}")
    print(f"Generated: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
