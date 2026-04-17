# Donnees

Le dossier `data/` regroupe les artefacts de donnees utiles au prototype.

## Ce qui est versionne

- les vues preparees `lab_v2` en parquet ;
- les CSV et JSON de synthese associes aux splits ;
- les manifests utiles a la preparation et a l'analyse des campagnes.

## Ce qui reste generalement local

- les captures reseau brutes `.pcap` ;
- les logs de collecte ou de conversion volumineux ;
- les sorties purement temporaires de debug.

Ces fichiers bruts sont normalement ignores par Git pour eviter de versionner
des volumes inutiles.

## Chemins utilises par defaut

Le backend pointe par defaut vers :

- `data/lab_v2/prepared/lab_v2_balanced_v2_20260328_1310/train_balanced.parquet`
- `data/lab_v2/prepared/lab_v2_balanced_v2_20260328_1310/validation_clean.parquet`
- `data/lab_v2/prepared/lab_v2_balanced_v2_20260328_1310/test_clean.parquet`

Ces chemins peuvent etre surcharges avec :

- `IPS_TRAIN_PATH`
- `IPS_VALIDATION_PATH`
- `IPS_TEST_PATH`

## Portabilite

Le runtime d'inference live n'a plus besoin de charger les parquets pour
demarrer si le modele et ses metadata sont presents. En revanche :

- `GET /datasets/summary` lit toujours les parquets ;
- `POST /replay/run` lit toujours les parquets.

Voir aussi [data/lab_v2/README.md](lab_v2/README.md).
