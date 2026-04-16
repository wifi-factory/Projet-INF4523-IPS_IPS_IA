# Documentation technique des features extraites

## Résumé

Ce rapport documente les variables extraites à partir du trafic réseau dans le cadre du prototype IPS basé sur l’IA. Il s’appuie uniquement sur les artefacts réellement visibles dans le dépôt : metadata du modèle, jeux préparés, catalogue des features et code d’agrégation flow-level.

- Nombre de features retenues dans le contrat final : **31**
- Taille du train : **15678** lignes
- Taille de la validation : **9227** lignes
- Taille du test : **8373** lignes

## Limites visibles

- `payload_entropy` apparaît comme feature candidate mais n’est pas implémentée dans le contrat final.
- Les compteurs TCP (`syn_count`, `ack_count`, `rst_count`, `fin_count`, `psh_count`) et `failed_connection_ratio` sont présents dans le contrat, mais les statistiques visibles sur les splits préparés les montrent entièrement nuls.

## Families

- **Identification réseau** : 3 variable(s)
- **Temporelles** : 5 variable(s)
- **Volume et taille** : 6 variable(s)
- **Statistiques** : 4 variable(s)
- **TCP et protocole** : 5 variable(s)
- **TCP et protocole** : 2 variable(s)
- **Comportementales** : 6 variable(s)
- **Avancées** : 1 variable(s)

