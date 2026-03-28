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
- `live_capture_service` : capture live via `tshark` sur une interface reelle.
- `flow_aggregation_service` : agregration 5-tuple bidirectionnelle et calcul
  des 31 features flow-level.
- `live_runtime_service` : orchestration `capture -> flux -> detection ->
  blocage -> statut`.
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
        routes_live.py
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
        live_capture_service.py
        flow_aggregation_service.py
        live_runtime_service.py
      models/
        api_models.py
      utils/
        parquet_utils.py
        dataframe_utils.py
        firewall_utils.py
        time_utils.py
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
- `tshark` disponible sur la machine qui effectue la capture live

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
- `IPS_LIVE_STATUS_ERROR_LIMIT`

Calibration live recommandee :

- `IPS_LIVE_ALERT_CONFIDENCE_THRESHOLD=0.95`
- `IPS_LIVE_BLOCK_CONFIDENCE_THRESHOLD=0.99`

Interpretation :

- si la probabilite `suspect` est sous le seuil d'alerte, le flux est requalifie
  `normal` pour le runtime live ;
- si elle depasse le seuil d'alerte mais pas le seuil de blocage, le flux est
  `suspect` et compte comme alerte, mais aucun blocage n'est declenche ;
- si elle depasse aussi le seuil de blocage, le flux est `suspect` avec
  blocage controle (`dry_run` ou autre mode selon la config).

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

Exemple avec interface live preconfiguree :

```powershell
$env:IPS_LIVE_INTERFACE="Wi-Fi"
$env:IPS_LIVE_TSHARK_PATH="tshark"
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
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

### `POST /live/start`

Demarre une session de monitoring live native.

Exemple :

```json
{
  "interface_name": "Wi-Fi",
  "capture_filter": "ip",
  "flush_interval_seconds": 1.0,
  "blocking_mode": "dry_run"
}
```

### `GET /live/interfaces`

Retourne les interfaces detectees automatiquement par `tshark` sur la machine
qui execute le backend.

Exemple de reponse :

```json
{
  "interfaces": [
    {"index": "1", "label": "1. Wi-Fi"},
    {"index": "2", "label": "2. Ethernet"}
  ]
}
```

### `GET /live/status`

Retourne l'etat runtime du pipeline live :

- `status`
- `running`
- `session_id`
- `interface_name`
- `capture_filter`
- `blocking_mode`
- `alert_confidence_threshold`
- `block_confidence_threshold`
- `started_at`
- `uptime_seconds`
- `packets_captured`
- `packets_ignored`
- `packet_parse_errors`
- `active_flows`
- `finalized_flows`
- `predictions`
- `alerts`
- `block_decisions`
- `last_predicted_label`
- `last_confidence`
- `last_errors`

Exemple de reponse :

```json
{
  "status": "running",
  "running": true,
  "session_id": "LIVE-AB12CD34",
  "interface_name": "Wi-Fi",
  "capture_filter": "ip",
  "blocking_mode": "dry_run",
  "alert_confidence_threshold": 0.95,
  "block_confidence_threshold": 0.99,
  "started_at": "2026-03-27T19:00:00+00:00",
  "stopped_at": null,
  "last_event_at": "2026-03-27T19:00:03+00:00",
  "uptime_seconds": 3.0,
  "packets_captured": 42,
  "packets_ignored": 0,
  "packet_parse_errors": 0,
  "active_flows": 2,
  "finalized_flows": 5,
  "predictions": 5,
  "alerts": 2,
  "block_decisions": 2,
  "last_predicted_label": "suspect",
  "last_confidence": 0.97,
  "last_errors": []
}
```

### `POST /live/stop`

Arrete proprement la session live, force le flush des flux restants, puis
retourne l'etat final.

## Mode replay academique

Le replay traite ligne par ligne un split `validation` ou `test` comme si les
flux arrivaient en quasi temps reel. Chaque evenement suit :

1. preparation des features
2. inference
3. decision de blocage simulee
4. journalisation

## Pipeline live end-to-end natif

Le backend supporte maintenant une chaine live native :

1. capture via `tshark`
2. parsing minimal paquet
3. agregration bidirectionnelle par 5-tuple
4. finalisation de flux sur timeout d'inactivite, FIN/RST TCP ou duree max
5. calcul des 31 features du contrat du modele
6. appel de `detection_service`
7. appel de `blocking_service`
8. exposition d'un statut runtime exploitable par un dashboard

Points de parite offline/live :

- le modele reste strictement flow-level ;
- la capture live ne predit jamais paquet par paquet ;
- l'ordre des features est toujours derive du metadata ;
- `src_ip` et `dst_ip` restent des metadonnees operationnelles et n'entrent pas
  dans le vecteur ML.
- la calibration live peut appliquer deux seuils distincts :
  `alert_confidence_threshold` et `block_confidence_threshold`.

## Tests

Les tests couvrent :

- parsing live `tshark -> PacketEvent`
- agregration en flux bidirectionnels
- calcul de features flow-level
- start / status / stop runtime
- endpoints `/live/start`, `/live/status`, `/live/stop`
- scenario end-to-end minimal avec emission de prediction et blocage simule

Execution :

```powershell
.\.venv\Scripts\python -m pytest backend/tests
```

Sous-ensembles utiles :

```powershell
.\.venv\Scripts\python -m pytest backend/tests/test_flow_aggregation_service.py
.\.venv\Scripts\python -m pytest backend/tests/test_live_runtime_service.py
.\.venv\Scripts\python -m pytest backend/tests/test_api_live.py
.\.venv\Scripts\python -m pytest backend/tests/test_live_e2e.py
```

## Limites actuelles

- Cette V1 est academique et demonstrable, pas production-grade.
- Elle s'appuie sur un modele deja entraine.
- La decision est flow-level, pas packet-level.
- Le blocage reel est simule par defaut.
- `system_stub` ne fait qu'exposer un apercu de commande firewall ; aucune
  commande destructive n'est executee.
- La capture live depend de `tshark` sur la machine qui observe l'interface.
- Le blocage `enforce` reste volontairement prudent et degrade proprement vers
  `dry_run` si la commande n'est pas applicable.
- Le pipeline live garde les flux actifs en memoire ; il faudra une persistence
  ou un bus d'evenements pour monter en charge.
- Le dashboard n'est pas encore livre ici.

## Evolutions futures

- capture live depuis interface reseau
- enrichissement des logs et export vers dashboard
- gestion plus fine des politiques de blocage
- instrumentation Linux reelle, securisee et reversible
- reporting et traces d'evaluation
- diffusion temps reel des evenements live vers WebSocket ou file de messages

## Note sur le blocage

Le backend applique la logique :

1. classifier le flux
2. si le label predit est `suspect` et depasse le seuil d'alerte live,
   produire une alerte
3. si le meme flux depasse aussi le seuil de blocage live, produire une
   decision de blocage
4. executer par defaut en `dry_run`

Ainsi, `src_ip` et `dst_ip` peuvent etre fournis pour les decisions
operationnelles sans jamais entrer dans le vecteur de prediction.

## Note Git

Le projet est prevu pour etre versionne dans le depot local
`Projet-INF4523-IPS_IPS_IA`. Le depot a ete initialise localement. Aucun remote
n'a ete invente ; si un remote GitHub doit etre ajoute plus tard, il devra
provenir d'une URL reelle connue du depot.
