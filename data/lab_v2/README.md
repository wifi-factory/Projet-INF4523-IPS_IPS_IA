# Lab V2

Le sous-dossier `data/lab_v2/` rassemble les artefacts utilises pour la
generation et la preparation du dataset `lab_v2`.

## Structure reelle

- `prepared/` : vues parquet pretes a l'usage par le backend et les scripts
  d'entrainement
- `processed/` : campagnes converties en flux et consolidees
- `raw/` : captures et manifests de collecte locaux
- `run_logs/` : journaux d'execution locaux

## Vue preparee utilisee par defaut

Le modele versionne `random_forest_lab_v2` s'appuie sur :

- `prepared/lab_v2_balanced_v2_20260328_1310/train_balanced.parquet`
- `prepared/lab_v2_balanced_v2_20260328_1310/validation_clean.parquet`
- `prepared/lab_v2_balanced_v2_20260328_1310/test_clean.parquet`

Les autres sous-dossiers de `prepared/` et `processed/` correspondent a des
iterations precedentes conservees comme traces de travail.

## Scripts associes

- `scripts/lab_v2/run_first_campaign.py`
- `scripts/lab_v2/pcap_to_flows.py`
- `scripts/lab_v2/prepare_split_plan.py`
- `scripts/lab_v2/train_lab_v2_model.py`

## Note importante

Le depot suit les artefacts prepares et les manifests utiles, mais pas toutes
les captures brutes. Les `.pcap` et certains journaux restent locaux et sont
ignores par Git.
