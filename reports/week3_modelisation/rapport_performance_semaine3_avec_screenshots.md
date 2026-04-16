# Rapport de performance Semaine 3 avec captures et graphes

## 1. Introduction
Ce document presente une version enrichie du rapport de performance de la semaine 3. Il regroupe les metriques du modele retenu, des graphes de comparaison et plusieurs captures du pipeline de preparation des donnees.

## 2. Modele retenu
- Type de modele : RandomForestClassifier
- Classe positive : `suspect`
- Vue de donnees : `lab_v2_balanced_v2_20260328_1310`
- Nombre de variables avant encodage : 31

## 3. Tableau de synthese des performances

| Split | Accuracy | Precision suspect | Recall suspect | F1 suspect | FPR | ROC-AUC |
|---|---:|---:|---:|---:|---:|---:|
| train | 0.9999 | 1.0000 | 0.9999 | 0.9999 | 0.0000 | 1.0000 |
| validation | 0.9987 | 0.9998 | 0.9979 | 0.9988 | 0.0002 | 1.0000 |
| test | 0.9995 | 0.9994 | 0.9998 | 0.9996 | 0.0008 | 1.0000 |

## 4. Comparaison avec la baseline
Sur validation, la baseline v1 atteint une accuracy de 0.7248, contre 0.9987 pour le modele retenu. Sur test, le nouveau modele conserve aussi un net avantage, avec un FPR de 0.0008 contre 0.4383 pour la baseline.

## 5. Graphes de performance
- `graph_metrics_par_split.png`
- `graph_baseline_vs_modele.png`
- `graph_false_positive_rate.png`
- `graph_roc_auc.png`

## 6. Screenshots retenus
### Figure 1 - Capture reseau avec tshark sur trafic normal
Cette capture montre une observation directe du trafic reseau brut. Elle rappelle que le pipeline du projet part bien d'une acquisition reelle avant transformation en variables exploitables par le modele.
Fichier : `09. tshark_ping_normal.jpg`

### Figure 2 - Fichiers CSV generes par le pipeline
Cette figure illustre la production des fichiers intermediaires issus de la capture et du pretraitement. Elle permet de visualiser la transition entre trafic brut et donnees tabulaires.
Fichier : `10. csv_files.jpg`

### Figure 3 - Script de construction du dataset
Cette capture apporte une preuve visuelle de l'etape d'assemblage du dataset. Elle est utile pour montrer que la preparation des donnees repose sur un script explicite et reproductible.
Fichier : `13. script_build_datasetjpg.jpg`

### Figure 4 - Extrait du dataset associe au trafic normal
Cette figure montre un apercu de la structure tabulaire des donnees pour des observations normales. Elle aide a comprendre le format des entrees donnees au modele.
Fichier : `14. Dataset_normal_screen.jpg`

### Figure 5 - Extrait du dataset associe a un scenario de scan
Cette figure montre un exemple de lignes liees a un comportement suspect de type scan. Elle permet d'illustrer que le dataset couvre aussi des scenarios offensifs.
Fichier : `15. Dataset_scan.jpg`

## 7. Integration du module de detection
Le resume technique disponible confirme que le modele est integre dans le backend IPS : preparation des features, prediction, calcul de confiance, alerte et blocage.

## 8. Remarques critiques
Les performances observees sont tres elevees. Elles doivent etre interpretees avec prudence dans la mesure ou les resultats proviennent d'un contexte de laboratoire controle.
Les artefacts visibles materialisent un pipeline RandomForest complet, mais pas d'implementation equivalente pour XGBoost, SVM ou Autoencoder.

## 9. Conclusion
Le modele RandomForest retenu est non seulement entraine et evalue, mais aussi integre dans le pipeline de detection du backend. Le rapport enrichi produit ici rend cette semaine 3 plus presentable pour une remise universitaire.

Note technique source : `K:\4. UQO\04. INF4523 - Réseaux d'ordinateurs\Projet-INF4523-IPS_IPS_IA\reports\model_training\random_forest_lab_v2_eval_20260328_125648.json`
