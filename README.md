# Projet INF4523 - Prototype IPS IA

Prototype academique d'IDS/IPS base sur un modele IA flow-level. Le depot
regroupe le backend FastAPI, la dashboard Streamlit, les artefacts de donnees
`lab_v2`, le modele entraine `random_forest_lab_v2` et les rapports produits
pendant les semaines 2 et 3 du projet.

## Contexte

Le projet a ete realise dans le cadre du cours `INF4523 - Reseaux
d'ordinateurs`. L'objectif n'est pas de fournir un produit industriel, mais un
prototype technique coherent et evaluable, capable de :

- charger un modele de classification deja entraine ;
- detecter des flux `normal` ou `suspect` a partir de 31 features ;
- exposer une API backend simple pour la prediction, le replay et le suivi live ;
- piloter une dashboard de supervision ;
- produire des decisions de blocage controlees apres classification.

## Etat reel du prototype

- Backend : FastAPI, structure par services, expose les routes `health`,
  `model`, `datasets`, `detection`, `blocking`, `replay` et `live`.
- Dashboard : Streamlit, pages `Vue ensemble`, `Runtime live`, `Alertes`,
  `Evenements` et `Journal trafic`.
- Modele charge par defaut :
  [random_forest_lab_v2.joblib](models/random_forest_lab_v2.joblib)
- Metadata chargees par defaut :
  [random_forest_lab_v2_metadata.json](models/random_forest_lab_v2_metadata.json)
- Jeux de donnees par defaut :
  [data/lab_v2/prepared/lab_v2_balanced_v2_20260328_1310](data/lab_v2/prepared/lab_v2_balanced_v2_20260328_1310)
- Fonctionnement live : quasi temps reel, mais toujours flow-level. Une alerte
  n'apparait qu'apres finalisation d'un flux ou expiration des conditions de
  flush/timeout.
- Blocage : `dry_run` par defaut. `system_stub` reste un mode de previsualisation
  et `enforce` ne tente l'execution que sur Linux, avec repli propre vers
  `dry_run` si la commande firewall echoue.

## Architecture generale

Le backend assemble les composants suivants :

- `schema_service` : charge le contrat du modele depuis les metadata ;
- `dataset_service` : lit les jeux parquet et calcule les resumes offline ;
- `feature_service` : aligne et convertit les features au format attendu ;
- `model_service` : charge le pipeline `scikit-learn` et produit les predictions ;
- `detection_service` : applique la detection et les seuils live ;
- `blocking_service` : produit la decision de blocage post-classification ;
- `replay_service` : rejoue des flux depuis `validation` ou `test` ;
- `live_capture_service` : capture le trafic via `tshark` ;
- `flow_aggregation_service` : agrege les paquets en flux bidirectionnels ;
- `live_runtime_service` : orchestre `capture -> flux -> prediction -> alerte`.

## Structure du depot

```text
backend/      API FastAPI, logique metier, services et tests backend
dashboard/    application Streamlit, composants UI et tests dashboard
data/         jeux de donnees lab_v2 prepares, campagnes traitees et README
docs/         notes d'ingenierie et documentation technique locale
models/       modele entraine et metadata du contrat ML
reports/      rapports academiques, evaluations modele et supports visuels
scripts/      scripts d'entrainement, de preparation de donnees et d'automatisation
```

## Modele IA utilise

Le depot charge un pipeline `scikit-learn` dont l'etape finale est un
`RandomForestClassifier`.

Elements confirmes par les metadata :

- `target_column = label_binary`
- `positive_label = suspect`
- `selected_candidate = {n_estimators: 300, max_depth: 20, min_samples_leaf: 1, max_features: sqrt}`
- 31 colonnes d'entree avant encodage
- `protocol` traite comme variable categorielle ; les autres features restent
  numeriques

## Jeux de donnees utilises

Le backend pointe par defaut vers la vue preparee
`lab_v2_balanced_v2_20260328_1310`, qui contient :

- `train_balanced.parquet`
- `validation_clean.parquet`
- `test_clean.parquet`
- des CSV et JSON de synthese de split

Le depot conserve aussi d'autres vues preparees plus anciennes dans
`data/lab_v2/prepared/`, mais le modele versionne s'appuie sur
`lab_v2_balanced_v2_20260328_1310`.

Point important :

- `POST /detect/flow` et le runtime live peuvent fonctionner avec le modele et
  les metadata seuls ;
- `GET /datasets/summary` et `POST /replay/run` ont toujours besoin des fichiers
  parquet.

## Execution locale

### 1. Creer l'environnement

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Le depot a ete verifie localement avec Python 3.11.9 dans le venv du projet.

### 2. Lancer le backend

```powershell
.\.venv\Scripts\uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Documentation interactive :

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 3. Lancer la dashboard

```powershell
.\.venv\Scripts\streamlit run dashboard/app.py
```

### Variables d'environnement utiles

- `IPS_MODEL_PATH`
- `IPS_METADATA_PATH`
- `IPS_TRAIN_PATH`
- `IPS_VALIDATION_PATH`
- `IPS_TEST_PATH`
- `IPS_BLOCKING_MODE`
- `IPS_LIVE_INTERFACE`
- `IPS_LIVE_CAPTURE_FILTER`
- `IPS_LIVE_TSHARK_PATH`
- `IPS_LIVE_FLUSH_INTERVAL_SECONDS`
- `IPS_LIVE_TCP_IDLE_TIMEOUT_SECONDS`
- `IPS_LIVE_UDP_IDLE_TIMEOUT_SECONDS`
- `IPS_LIVE_ICMP_IDLE_TIMEOUT_SECONDS`
- `IPS_LIVE_MAX_FLOW_DURATION_SECONDS`
- `IPS_LIVE_ALERT_CONFIDENCE_THRESHOLD`
- `IPS_LIVE_BLOCK_CONFIDENCE_THRESHOLD`
- `IPS_DASHBOARD_BACKEND_URL`
- `IPS_DASHBOARD_REFRESH_SECONDS`
- `IPS_DASHBOARD_ALERT_PULSE_REFRESH_SECONDS`

## Tests

Les tests sont separes entre backend et dashboard :

```powershell
.\.venv\Scripts\python -m pytest backend/tests dashboard/tests -q
```

Commande verifiee localement pendant cet audit : la suite passee dans le venv
du depot.

## Rapports et livrables

Le dossier [reports](reports/)
contient les principaux livrables internes du projet :

- `model_training/` : evaluation du modele `random_forest_lab_v2`
- `week2_preprocessing/` : rapports et figures de pretraitement
- `week3_modelisation/` : rapports, tableaux et assets de la semaine 3
- `dashboard_mockups/` : maquettes de dashboard
- `live_tests/` : snapshots de validation live et, localement, logs de debug non versionnes

## Limites connues

- Prototype academique, pas produit de securite de production.
- Detection flow-level uniquement ; pas d'inspection packet-level instantanee.
- Le live est quasi temps reel, mais l'alerte depend de la finalisation des flux.
- La capture live depend de `tshark` sur la machine qui observe l'interface.
- Le blocage est simule par defaut (`dry_run`).
- `system_stub` n'applique aucune regle ; il sert seulement a exposer une
  commande firewall previsible.
- `enforce` tente une commande `iptables` uniquement sur Linux et se replie en
  `dry_run` si l'execution n'est pas possible.
- Le replay et le resume datasets restent dependants des fichiers parquet.

## Nature du depot

Le depot documente l'etat reel du prototype tel qu'il est versionne. Il ne
faut pas interpreter la documentation comme la promesse d'un blocage reseau
durable ou d'une supervision temps reel stricte type production. La valeur du
projet est avant tout academique : coherence de l'architecture, tracabilite des
artefacts et demonstrabilite du pipeline IA.
