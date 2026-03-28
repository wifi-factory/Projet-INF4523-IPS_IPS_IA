# RandomForest lab_v2 Training Report

- Generated at: 2026-03-28T16:56:48.653157+00:00
- Exported model: `K:\4. UQO\04. INF4523 - Réseaux d'ordinateurs\Projet-INF4523-IPS_IPS_IA\models\random_forest_lab_v2.joblib`
- Exported metadata: `K:\4. UQO\04. INF4523 - Réseaux d'ordinateurs\Projet-INF4523-IPS_IPS_IA\models\random_forest_lab_v2_metadata.json`

## New Model Metrics

| Split | Rows | Accuracy | Balanced Acc. | Precision suspect | Recall suspect | F1 suspect | FPR | ROC AUC |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| train | 15678 | 0.9999 | 0.9999 | 1.0000 | 0.9999 | 0.9999 | 0.0000 | 1.0000 |
| validation | 9227 | 0.9987 | 0.9988 | 0.9998 | 0.9979 | 0.9988 | 0.0002 | 1.0000 |
| test | 8373 | 0.9995 | 0.9995 | 0.9994 | 0.9998 | 0.9996 | 0.0008 | 1.0000 |

## Baseline Comparison (v1 on lab_v2)

| Model | Split | Accuracy | Balanced Acc. | Precision suspect | Recall suspect | F1 suspect | FPR | ROC AUC |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| baseline_v1 | validation | 0.7248 | 0.6934 | 0.6749 | 0.9745 | 0.7974 | 0.5876 | 0.9817 |
| baseline_v1 | test | 0.7947 | 0.7678 | 0.7429 | 0.9738 | 0.8429 | 0.4383 | 0.9801 |
| random_forest_lab_v2 | validation | 0.9987 | 0.9988 | 0.9998 | 0.9979 | 0.9988 | 0.0002 | 1.0000 |
| random_forest_lab_v2 | test | 0.9995 | 0.9995 | 0.9994 | 0.9998 | 0.9996 | 0.0008 | 1.0000 |
