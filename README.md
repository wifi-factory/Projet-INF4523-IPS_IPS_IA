# Projet INF4523 - IPS IPS IA

Prototype backend universitaire d'un systeme IPS base sur l'IA pour l'analyse
de trafic reseau agrege en flux. Cette V1 se concentre sur le backend
FastAPI, le chargement du modele deja entraine, l'application stricte du
contrat de features, la prediction `normal` vs `suspect`, le blocage controle
post-classification, et un mode replay academique.

## Contexte academique

Le projet repond au cadrage du livrable INF4523 autour d'un prototype
demonstrable d'IDS/IPS intelligent.

- Les preuves documentaires lues pour cette implementation sont :
  - `00. Livrables.pdf`
  - `01. rapport_dataset_ips.pdf`
- Le rapport dataset indique un corpus flow-level de 35 498 flux, 45 colonnes,
  avec split par capture sans fuite :
  - train : 24 796 lignes
  - validation : 5 313 lignes
  - test : 5 389 lignes
- Le modele fourni est deja entraine ; cette iteration ne relance donc pas
  l'entrainement.

## Objectif du prototype IDS/IPS IA

- Charger et profiler `train`, `validation`, `test` en parquet.
- Charger le pipeline `joblib` fourni.
- Charger le contrat de features depuis le metadata JSON.
- Exposer une API de prediction flow-level.
- Produire une decision `normal` ou `suspect`.
- Evaluer un blocage controle apres classification.
- Simuler un trafic live via replay sur `validation` ou `test`.
- Journaliser clairement les etapes du backend.

## Artefacts fournis et utilises comme source de verite

- Datasets parquet :
  - `05. train.parquet`
  - `06. validation.parquet`
  - `04. test.parquet`
- Modele :
  - `random_forest_v1.joblib`
- Metadata :
  - `random_forest_v1_metadata.json`
- Documentation :
  - `01. rapport_dataset_ips.pdf`
  - `00. Livrables.pdf`

## Verites techniques confirmees

- Le metadata declare :
  - `model_type = RandomForestClassifier`
  - `target_column = label_binary`
  - `positive_label = suspect`
  - `selected_candidate = {n_estimators: 300, max_depth: 20, min_samples_leaf: 1, max_features: sqrt}`
- Le modele charge est un `sklearn.pipeline.Pipeline` dont l'etape finale est
  bien un `RandomForestClassifier`.
- Les 31 features attendues par le pipeline sont exactement celles du metadata
  avant encodage ; `protocol` est gere en categoriel dans le pipeline et les
  autres colonnes servent de variables numeriques.
- Les colonnes operationnelles exclues du contrat ML incluent notamment
  `src_ip` et `dst_ip`. Elles ne sont jamais injectees dans le vecteur du
  modele.

## Principe flow-level

Le backend ne pretend pas faire de l'inspection packet-level instantanee.
L'inference travaille sur un flux deja agrege et represente par ses features
flow-level.

- Le modele recoit uniquement les 31 features du contrat ML.
- Les metadonnees reseau utiles au logging et au blocage
  (`src_ip`, `dst_ip`, `flow_id`, etc.) restent separees.
- La logique de prevention est `detection puis blocage controle apres
  classification`.

## Architecture backend

Le backend est organise en couches :

- `config` : chemins, mode de blocage, delais de replay.
- `schema_service` : chargement et validation du contrat de features.
- `dataset_service` : lecture parquet, resume et comparaison de schemas.
- `feature_service` : validation stricte, coercition des types, alignement des
  features.
- `model_service` : chargement du pipeline, verification de coherence et
  inference.
- `detection_service` : orchestration prediction + normalisation de sortie.
- `blocking_service` : blocage controle en `dry_run` ou `system_stub`.
- `replay_service` : replay asynchrone sur `validation` ou `test`.
- `api` : endpoints FastAPI.

## Structure du projet

```text
Projet-INF4523-IPS_IPS_IA/
  backend/
    app/
      main.py
      config.py
      api/
        routes_health.py
        routes_dataset.py
        routes_detection.py
        routes_blocking.py
        routes_replay.py
        routes_model.py
      core/
        logging.py
        exceptions.py
      services/
        container.py
        dataset_service.py
        schema_service.py
        model_service.py
        feature_service.py
        detection_service.py
        blocking_service.py
        replay_service.py
      models/
        api_models.py
      utils/
        parquet_utils.py
        dataframe_utils.py
        firewall_utils.py
        time_utils.py
    tests/
  data/
  models/
  docs/
  requirements.txt
  README.md
  .gitignore
```

## Prerequis

- Python 3.11 ou compatible
- Git
- Acces local aux artefacts fournis
- Windows pour le contexte courant ; le preview de blocage cible une integration
  Linux future via `iptables`

## Configuration des chemins

Par defaut, l'application pointe vers les chemins reels observes dans les
artefacts fournis. Les variables d'environnement suivantes permettent de les
surcharger :

- `IPS_MODEL_PATH`
- `IPS_METADATA_PATH`
- `IPS_TRAIN_PATH`
- `IPS_VALIDATION_PATH`
- `IPS_TEST_PATH`
- `IPS_BLOCKING_MODE`
- `IPS_LOG_LEVEL`
- `IPS_REPLAY_DEFAULT_DELAY_SECONDS`

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement local

```powershell
uvicorn backend.app.main:app --reload
```

Documentation interactive :

- Swagger UI : [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc : [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

## Endpoints API

### `GET /health`

Retourne l'etat general du service, le statut du metadata, du modele et la
presence des chemins dataset.

### `GET /model/info`

Retourne :

- type du modele final
- type d'enveloppe pipeline
- target
- positive label
- nombre de features attendues
- colonnes utilisees
- colonnes exclues
- statut du modele

### `GET /datasets/summary`

Retourne un profil de `train`, `validation`, `test` :

- nombre de lignes
- nombre de colonnes
- types
- valeurs manquantes
- distribution de `label_binary`
- comparaison des schemas entre splits

### `POST /detect/flow`

Prend un JSON de flux agrege avec separation stricte entre features ML et
metadonnees operationnelles.

Exemple minimal :

```json
{
  "flow_features": {
    "protocol": "TCP",
    "src_port": 52314,
    "dst_port": 80,
    "duration_ms": 15.2,
    "packet_count_total": 10,
    "packet_count_fwd": 6,
    "packet_count_bwd": 4,
    "byte_count_total": 1400,
    "byte_count_fwd": 900,
    "byte_count_bwd": 500,
    "pkt_len_min": 60,
    "pkt_len_max": 300,
    "pkt_len_mean": 140.0,
    "pkt_len_std": 25.0,
    "iat_min_ms": 0.2,
    "iat_max_ms": 7.0,
    "iat_mean_ms": 1.5,
    "iat_std_ms": 0.8,
    "syn_count": 1,
    "ack_count": 4,
    "rst_count": 0,
    "fin_count": 1,
    "psh_count": 0,
    "icmp_echo_req_count": 0,
    "icmp_echo_reply_count": 0,
    "connections_per_1s": 1,
    "connections_per_5s": 2,
    "distinct_dst_ports_per_5s": 1,
    "distinct_dst_ips_per_5s": 1,
    "icmp_packets_per_1s": 0,
    "failed_connection_ratio": 0.0
  },
  "operational_metadata": {
    "src_ip": "172.30.1.20",
    "dst_ip": "172.30.1.21",
    "flow_id": "demo-flow-001"
  }
}
```

La reponse contient au minimum :

- `predicted_label`
- `is_suspect`
- `confidence`
- `probability`
- `decision_mode = flow_post_classification`
- `model_type`
- `target_column`
- `positive_label`
- `features_used`
- `timestamp_decision`
- `blocking_decision`

### `POST /blocking/evaluate`

Prend une decision deja classee et retourne une evaluation de blocage
controlee, typiquement en `dry_run`.

### `POST /replay/run`

Lance un replay academique sur `validation` ou `test`.

Parametres utiles :

- `split`
- `limit`
- `delay_seconds`
- `pause_between_events`
- `blocking_mode`

### `GET /replay/status`

Retourne l'etat du dernier replay :

- `total_events`
- `processed_events`
- `normal_count`
- `suspect_count`
- `block_decisions_count`
- erreurs eventuelles

## Mode replay academique

Le replay traite ligne par ligne un split `validation` ou `test` comme si les
flux arrivaient en quasi temps reel. Chaque evenement suit :

1. preparation des features
2. inference
3. decision de blocage simulee
4. journalisation

## Tests

Les tests minimaux couvrent :

- chargement parquet
- chargement metadata
- chargement modele
- validation du feature contract
- prediction
- blocage dry-run

Execution :

```powershell
pytest
```

## Limites actuelles

- Cette V1 est academique et demonstrable, pas production-grade.
- Elle s'appuie sur un modele deja entraine.
- La decision est flow-level, pas packet-level.
- Le blocage reel est simule par defaut.
- `system_stub` ne fait qu'exposer un apercu de commande firewall ; aucune
  commande destructive n'est executee.
- La capture live reelle, les regles systeme completes et le dashboard ne sont
  pas encore livres ici.

## Evolutions futures

- capture live depuis interface reseau
- enrichissement des logs et export vers dashboard
- gestion plus fine des politiques de blocage
- instrumentation Linux reelle, securisee et reversible
- reporting et traces d'evaluation

## Note sur le blocage

Le backend applique la logique :

1. classifier le flux
2. si le label predit est `suspect`, produire une decision de blocage
3. executer par defaut en `dry_run`

Ainsi, `src_ip` et `dst_ip` peuvent etre fournis pour les decisions
operationnelles sans jamais entrer dans le vecteur de prediction.

## Note Git

Le projet est prevu pour etre versionne dans le depot local
`Projet-INF4523-IPS_IPS_IA`. Le depot a ete initialise localement. Aucun remote
n'a ete invente ; si un remote GitHub doit etre ajoute plus tard, il devra
provenir d'une URL reelle connue du depot.
