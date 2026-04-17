# Modeles

Le dossier `models/` contient les artefacts ML charges par defaut au demarrage
du backend.

## Fichiers principaux

- `random_forest_lab_v2.joblib` : pipeline `scikit-learn` versionne
- `random_forest_lab_v2_metadata.json` : contrat du modele et informations de
  calibration

## Ce que contiennent les metadata

- type du modele final ;
- cible `label_binary` et label positif `suspect` ;
- 31 colonnes d'entree avant encodage ;
- hyperparametres retenus du `RandomForestClassifier` ;
- types runtime des features pour la coercition live ;
- chemins relatifs vers les parquets de `train`, `validation` et `test`.

## Point important

Le backend peut charger le modele et ses metadata sans avoir acces aux parquets.
Cette portabilite couvre la prediction live et `POST /detect/flow`.

Les parquets restent necessaires pour :

- `GET /datasets/summary`
- `POST /replay/run`
