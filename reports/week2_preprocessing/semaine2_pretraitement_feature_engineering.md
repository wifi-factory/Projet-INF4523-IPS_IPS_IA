# Semaine 2 - Pretraitement et Feature Engineering

## Objectif

Formaliser les livrables de la semaine 2 a partir du pipeline reel du projet :
- extraction des features reseau pertinentes ;
- nettoyage et preparation des donnees ;
- justification des choix de normalisation pour le modele final.

## Source technique retenue

- Metadata modele : `K:\4. UQO\04. INF4523 - Réseaux d'ordinateurs\Projet-INF4523-IPS_IPS_IA\models\random_forest_lab_v2_metadata.json`
- Dossier de sortie : `K:\4. UQO\04. INF4523 - Réseaux d'ordinateurs\Projet-INF4523-IPS_IPS_IA\reports\week2_preprocessing`

## Features effectivement retenues dans le contrat final

- Nombre total : **31**
- Features categorielle : **protocol**
- Features numeriques : **30**

### Correspondance avec les attentes de la semaine 2

- Ports, protocoles, duree des sessions : **implantes**
- Nombre de paquets, tailles, flags TCP : **implantes**
- Nettoyage et normalisation : **implantes**
- Entropie du payload : **non retenue dans le contrat final deploye**

## Nettoyage et normalisation reellement appliques

- Verification de la presence de toutes les features requises avant inference.
- Coercition stricte des variables numeriques vers int/float.
- Conversion des protocoles en texte puis encodage One-Hot dans le pipeline scikit-learn.
- Colonnes de contexte exclues du modele: src_ip, dst_ip, timestamps, scenario_id, capture_id, severity.
- Aucune standardisation globale appliquee car le modele final est un RandomForest, peu sensible a l'echelle.

## Observation importante

Le modele final ne repose pas sur une normalisation de type StandardScaler/MinMaxScaler.
Ce choix est coherent avec l'utilisation d'un RandomForest, qui supporte bien les echelles heterogenes.
La vraie logique de normalisation ici est donc :
- nettoyage des types ;
- controle du schema ;
- encodage du protocole ;
- exclusion des colonnes contextuelles non generalisables.

## Exemple de distribution

- Valeurs dominantes pour `protocol` dans le train : `{"TCP": 12935, "UDP": 2736, "ICMP": 7}`

## Features candidates non retenues

- payload_entropy

## Artefacts generes

- `feature_catalog.csv` : catalogue des features et lien avec les objectifs Semaine 2
- `train_feature_statistics.csv` : statistiques descriptives du split train
- `preprocessing_summary.json` : resume machine-readable du nettoyage et des splits

## Conclusion

Le livrable Semaine 2 est donc bien materialise dans le projet actuel,
mais avec une nuance importante : l'entropie du payload etait une piste de feature engineering,
alors que la version finale deploye principalement des features flow-level et comportementales.

Les artefacts ci-dessus peuvent etre repris tels quels dans le rapport ou les slides.
