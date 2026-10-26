# Spécification Technique — Télémétrie Moteur : OBD-II vs Bus CAN Natif

## 1. Contexte & Définitions Techniques

Dans le cadre de la plateforme **V-Twins**, la modélisation haute fidélité du groupe motopropulseur repose sur l'acquisition rigoureuse des grandeurs physiques dynamiques (régime de rotation, pression d'huile, avance à l'allumage, cliquetis, températures d'échappement).

* **OBD-II (On-Board Diagnostics version 2) :** Interface de diagnostic normalisée (ISO 15765 / SAE J1979) obligatoire sur l'ensemble du parc automobile européen post-2001 (essence) et post-2004 (diesel). Accessible via le connecteur physique 16 broches sous l'habitacle. Fonctionne sur un modèle synchrone de type maître-esclave (*polling*) : l'outil client émet une requête ciblant un identifiant de paramètre (PID) standardisé, et le calculateur moteur répond de manière séquentielle.
* **Bus CAN Natif (Controller Area Network) :** Réseau de communication série multiplexé physique différentiel reliant l'ensemble des Calculateurs Électroniques (ECU) du moteur. Fonctionne en diffusion asynchrone continue (*broadcast*) de trames brutes horodatées, sans sollicitation préalable, avec des débits nominaux atteignant 1 Mbps (CAN 2.0B) et 5 Mbps (CAN-FD).
* **Problématique d'échantillonnage des vibrations moteur :** Tout jeu anormal ou dysfonctionnement mécanique (usure progressive d'un coussinet de bielle, grippage de segment, encrassement d'injecteur) génère des chocs cycliques à chaque tour de vilebrequin. À 3 000 tr/min (50 rotations par seconde), les harmoniques vibratoires caractéristiques de dégradation se situent entre 100 Hz et 500 Hz. L'échantillonnage de ces phénomènes impose une fréquence d'acquisition nettement supérieure au seuil de Shannon-Nyquist.

---

## 2. Tableau Comparatif Multicritères

| Critère d'évaluation | OBD-II (SAE J1979 / Standard) | Bus CAN Natif (CAN 2.0B / CAN-FD) |
| :--- | :--- | :--- |
| **Paradigme de communication** | Requête / Réponse synchrone (Master-Slave Polling). | Diffusion asynchrone continue en temps réel (*Broadcast*). |
| **Fréquence d'échantillonnage réelle** | Faible : 2 Hz à 20 Hz (décroît linéairement selon le nombre de PIDs). | Haute fréquence : 100 Hz à 1 000 Hz natifs sur les trames ECU. |
| **Périmètre des données accessibles** | Limité aux ~130 PIDs légaux standardisés (régime moyen, T° eau, MAP). | Trames brutes complètes : avance cylindre par cylindre, knock sensor, couple dynamique. |
| **Déploiement & Accessibilité matérielle** | Immédiat : dongles Bluetooth/Wi-Fi grand public (type ELM327). | Complexe : piquage faisceau/passerelle et décodage via fichier de base .DBC. |

---

## 3. Analyse Détaillée des Avantages & Inconvénients

### OBD-II
* **Points forts :**
  * Zéro friction matérielle pour le conducteur particulier : matériel économique accessible dans le commerce grand public.
  * Standardisation universelle : interopérabilité immédiate quel que soit le constructeur du véhicule.
* **Limites techniques :**
  * Fréquence d'acquisition bridée (~10 Hz) : incapacité structurelle à capter les micro-chocs mécaniques et les variations transitoires de cliquetis.

### Bus CAN Natif
* **Points forts :**
  * Granularité milliseconde indispensable à la simulation physique précise du jumeau numérique moteur.
  * Accès exhaustif aux grandeurs internes non filtrées par la couche logicielle de diagnostic.
* **Limites techniques :**
  * Spécification propriétaire par constructeur : trames protégées nécessitant l'obtention ou l'ingénierie inverse de fichiers .DBC.

---

## 4. Arbitrage Technique Retenu pour V-Twins

Le projet implémente une **architecture d'ingestion duale** :
1. **Périmètre Constructeurs & Simulateur de Moteurs Virtuels :** Utilisation exclusive du format de trames **Bus CAN** (100–500 Hz) pour garantir la fidélité de reproduction de l'effort mécanique sur le vilebrequin.
2. **Périmètre Particuliers sur Véhicule de Série :** Collecte des données courantes via le port **OBD-II**, couplée à un module d'interpolation neuronale (super-résolution temporelle) permettant de déduire les contraintes internes moteur à partir des variables globales disponibles.
