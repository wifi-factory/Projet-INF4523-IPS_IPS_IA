# Semaine 3 - Rapport intermediaire de modelisation IA et detection d'intrusions

- Date de generation : 2026-04-06 08:08:11 Eastern Daylight Time
- Modele exporte : `K:\4. UQO\04. INF4523 - Réseaux d'ordinateurs\Projet-INF4523-IPS_IPS_IA\models\random_forest_lab_v2.joblib`
- Metadonnees du modele : `K:\4. UQO\04. INF4523 - Réseaux d'ordinateurs\Projet-INF4523-IPS_IPS_IA\models\random_forest_lab_v2_metadata.json`
- Rapport d'evaluation source : `K:\4. UQO\04. INF4523 - Réseaux d'ordinateurs\Projet-INF4523-IPS_IPS_IA\reports\model_training\random_forest_lab_v2_eval_20260328_125648.json`

## 1. Objectif
Ce document regroupe les livrables reels de la semaine 3 pour la partie modelisation IA et detection d'intrusions.
Il decrit le modele effectivement entraine, les resultats d'evaluation disponibles dans le depot et l'integration du module de detection dans le pipeline IPS.

## 2. Modele reellement entraine
- Type de modele retenu : RandomForestClassifier
- Variable cible : `label_binary`
- Classe positive : `suspect`
- Nombre de variables en entree avant encodage : 31
- Encodage categoriel visible : `protocol` via One-Hot Encoding
- Parametres retenus : n_estimators=300, max_depth=20, min_samples_leaf=1, max_features=sqrt

## 3. Donnees utilisees
- Vue de donnees : `lab_v2_balanced_v2_20260328_1310`
- Train : 15678 lignes
- Validation : 9227 lignes
- Test : 8373 lignes
- Fichier train : `K:\4. UQO\04. INF4523 - Réseaux d'ordinateurs\Projet-INF4523-IPS_IPS_IA\data\lab_v2\prepared\lab_v2_balanced_v2_20260328_1310\train_balanced.parquet`
- Fichier validation : `K:\4. UQO\04. INF4523 - Réseaux d'ordinateurs\Projet-INF4523-IPS_IPS_IA\data\lab_v2\prepared\lab_v2_balanced_v2_20260328_1310\validation_clean.parquet`
- Fichier test : `K:\4. UQO\04. INF4523 - Réseaux d'ordinateurs\Projet-INF4523-IPS_IPS_IA\data\lab_v2\prepared\lab_v2_balanced_v2_20260328_1310\test_clean.parquet`

## 4. Resultats principaux du modele
- Train : accuracy=0.9999, precision suspect=1.0000, recall suspect=0.9999, F1 suspect=0.9999, ROC-AUC=1.0000
- Validation : accuracy=0.9987, precision suspect=0.9998, recall suspect=0.9979, F1 suspect=0.9988, ROC-AUC=1.0000, FPR=0.0002
- Test : accuracy=0.9995, precision suspect=0.9994, recall suspect=0.9998, F1 suspect=0.9996, ROC-AUC=1.0000, FPR=0.0008

## 5. Comparaison avec la baseline v1
- Baseline v1 validation : accuracy=0.7248, precision suspect=0.6749, recall suspect=0.9745, F1 suspect=0.7974, FPR=0.5876
- Baseline v1 test : accuracy=0.7947, precision suspect=0.7429, recall suspect=0.9738, F1 suspect=0.8429, FPR=0.4383
La comparaison disponible dans le depot montre une amelioration nette du RandomForest lab_v2 par rapport a la baseline v1, en particulier sur le taux de faux positifs.

## 6. Integration du modele dans le pipeline IPS
Le pipeline d'integration visible dans le depot suit la logique suivante : preparation des features -> prediction du modele -> calcul de confiance -> decision d'alerte -> decision de blocage.
- Chargement du modele et verification du contrat : `backend/app/services/model_service.py`
- Preparation des features : `backend/app/services/feature_service.py`
- Orchestration de la detection : `backend/app/services/detection_service.py`
- Exposition API detection : `backend/app/api/routes_detection.py`
- Script d'entrainement : `scripts/lab_v2/train_lab_v2_model.py`

## 7. Livrables disponibles pour la semaine 3
- Modele IA entraine et teste : present
- Rapport intermediaire sur la performance : present
- Code source du module de detection : present

## 8. Limites et remarques honnetes
Le depot materialise clairement un pipeline RandomForest. En revanche, aucun livrable complet equivalent n'est visible pour XGBoost, SVM ou Autoencoder.
Les resultats de performance disponibles sont tres eleves. Ils doivent donc etre interpretes avec prudence et en tenant compte du contexte de laboratoire et du jeu de donnees utilise.

## 9. Conclusion
A ce stade, la semaine 3 est techniquement couverte par un modele RandomForest entraine, evalue et integre au backend IPS. Les livrables produits ici regroupent ces preuves dans un format plus presentable pour une remise universitaire.
