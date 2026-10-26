# Spécification Technique — Stockage Séries Temporelles : InfluxDB vs TimescaleDB

## 1. Contexte & Définitions Techniques

La simulation et le monitoring de moteurs génèrent des volumétries denses de données séquentielles indexées par horodatage (séquences d'injection, cycles thermiques, oscillations de couple). Celles-ci doivent être directement associées aux nomenclatures mécaniques des composants.

* **Base de données Séries Temporelles (Time-Series DB) :** Système de gestion de base de données optimisé pour le stockage, la compression et l'analyse de séquences de valeurs associées à un horodatage précis (*timestamp*).
* **InfluxDB :** SGBD NoSQL orienté séries temporelles, organisant les données selon un schéma de *Tags* (métadonnées indexées), *Fields* (métriques scalaires non indexées) et *Measurements*. Conçu pour des débits d'écriture bruts élevés mais dépourvu de capacités relationnelles natives.
* **TimescaleDB :** Extension d'ingénierie open-source pour le moteur PostgreSQL, implémentant des tables partitionnées automatiquement dans le temps et l'espace appelées **Hypertables**. Permet de combiner le standard SQL complet avec les performances d'une base temporelle spécialisée.
* **Impact de la Forte Cardinalité :** Problématique survenant lorsque le nombre de combinaisons d'identifiants uniques (IDs moteurs x numéros de cylindres x types de capteurs) atteint plusieurs millions. Les bases NoSQL maintenant leurs index de tags intégralement en mémoire vive risquent l'épuisement mémoire (*Out-Of-Memory*), là où les structures relationnelles s'appuient sur des index sur disque éprouvés (B-Tree, BRIN).

---

## 2. Tableau Comparatif Multicritères

| Propriété architecturale | TimescaleDB (Moteur PostgreSQL) | InfluxDB (Moteur NoSQL Time-Series) |
| :--- | :--- | :--- |
| **Paradigme de stockage** | Relationnel unifié étendu aux Hypertables (partitionnement transparent). | NoSQL spécialisé (schéma Tags / Fields / Measurements). |
| **Jointures relationnelles** | Natives et optimisées : clauses `JOIN` standard avec les tables de pièces. | Absentes : impose une corrélation externe au niveau applicatif. |
| **Langage d'interrogation** | SQL ANSI standard (intégration directe ORM TypeORM/Prisma, BI Grafana). | Flux / InfluxQL (langages propriétaires avec dépendances spécifiques). |
| **Résistance à la cardinalité** | Très élevée : s'appuie sur la gestion d'indexation modulaire de PostgreSQL. | Vulnérable : explosion de la consommation RAM lors de la multiplication d'IDs uniques. |
| **Compression & Politiques de données** | Compression en colonnes native (90 à 95 %), agrégations continues automatisées. | Moteur de compression TSM natif performant sur séries stables. |

---

## 3. Analyse Détaillée des Avantages & Inconvénients

### Limites d'InfluxDB pour le Système V-Twins
* **Scission de l'architecture :** InfluxDB étant incapable d'héberger les structures relationnelles complexes (garanties constructeurs, catalogues d'ateliers, pièces de rechange), le système nécessiterait deux bases de données distinctes à synchroniser en continu.
* **Inefficacité des requêtes analytiques :** L'interrogation croisée entre une alerte d'usure et une référence d'équipementier imposerait des requêtes séquentielles lourdes en couche applicative.

### Bénéfices Déterminants de TimescaleDB
* **Architecture consolidée :** PostgreSQL centralise l'intégrité transactionnelle ACID pour les comptes, les nomenclatures moteurs et des milliards d'enregistrements télémétriques.
* **Vues matérialisées continues :** Génération transparente de synthèses d'usure par paliers kilométriques (ex. moyenne glissante tous les 1 000 km) sans pénaliser les performances d'ingestion.

---

## 4. Arbitrage Technique Retenu pour V-Twins

Le projet adopte formellement **TimescaleDB** comme solution de stockage de référence.  
Chaque anomalie physique détectée (ex. température de palier anormale) devant être reliée de manière déterministe à la référence constructeur d'un composant et à son carnet d'entretien, TimescaleDB autorise ces jointures en une requête SQL unique, tout en garantissant une réduction drastique de l'empreinte disque grâce à ses algorithmes de compression par bloc.
