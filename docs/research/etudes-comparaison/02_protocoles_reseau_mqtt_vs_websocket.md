# Spécification Technique — Pipeline Réseau : MQTT vs WebSocket vs REST vs SSE

## 1. Contexte & Définitions Techniques

La plateforme **V-Twins** gère simultanément deux flux d'échanges distincts : l'ingestion massive de télémétrie moteur continue à haute fréquence et la restitution interactive fluide (60 FPS) de l'état du jumeau numérique sur tableau de bord web.

* **MQTT (Message Queuing Telemetry Transport) :** Protocole réseau léger de type Publication/Abonnement (*Pub/Sub*) transitant via un courtier centralisé (*Broker* type EMQX). Conçu spécifiquement pour les terminaux contraints et les connexions réseau instables, il propose un en-tête minimal de 2 octets, l'encapsulation de données binaires compactes (Protocol Buffers) ainsi que des garanties de distribution (QoS 0, 1, 2) et un mécanisme de notification de déconnexion inopinée (*Last Will and Testament*).
* **WebSocket :** Standard de communication bidirectionnelle permanente (*Full-Duplex*) opérant sur un socket TCP unique après une poignée de main initiale sur port HTTP standard. Assure un échange sans surcharge d'en-tête pour le temps réel interactif navigateur-serveur.
* **REST (Representational State Transfer via HTTP) :** Architecture synchrone requête/réponse sans état (*stateless*). Chaque communication transporte l'intégralité des en-têtes textuels HTTP (cookies, tokens JWT, informations d'agent utilisateur).
* **SSE (Server-Sent Events) :** Mécanisme de flux persistant unidirectionnel descendant (serveur vers client) nativement supporté par l'API navigateur *EventSource*.

---

## 2. Tableau Comparatif Multicritères

| Protocole | Modèle de communication | Surcharge d'en-tête (*Overhead*) | Résilience & Déconnexion | Rôle architectural dans V-Twins |
| :--- | :--- | :--- | :--- | :--- |
| **MQTT (v5)** | Pub/Sub asynchrone via Broker. | Ultra-léger (en-tête 2 octets, payload binaire Protobuf). | Élevée : QoS 1 & 2 avec buffer de rétention en cas de coupure 4G/Edge. | **Ingestion télémétrie moteur** : bancs d'essais et simulateurs. |
| **WebSocket** | Full-Duplex bidirectionnel permanent. | Faible (2 à 10 octets après handshake initial). | Détection de rupture TCP au niveau applicatif. | **Streaming Dashboard 3D** : rafraîchissement temps réel des jauges web. |
| **REST (HTTP/2)** | Requête / Réponse synchrone stateless. | Élevé (en-têtes textuels de 500 à 1 000 octets par appel). | Sans état : gestion de reprise entièrement déléguée au client. | **Services administratifs CRUD** : authentification, gestion de parc, PDF. |
| **SSE** | Unidirectionnel (Serveur vers Client). | Moyen (flux continu encodé en texte UTF-8). | Reconnexion automatique native gérée par le navigateur. | **Canal d'alerting critique** : push immédiat lors d'un seuil critique franchi. |

---

## 3. Analyse Détaillée des Avantages & Inconvénients

### Évaluation du REST pour le streaming télémétrique
* **Incompatibilité structurelle :** L'émission de 100 mesures par seconde via des requêtes REST saturerait le réseau d'en-têtes redondants (multiplication du trafic par 50).
* **Charge d'infrastructure :** L'ouverture répétée de contextes HTTP engendrerait un goulot d'étranglement massif sur les passerelles d'API sous charge concurrente.

### Complémentarité Opérationnelle MQTT & WebSocket
* **MQTT pour le flux machine :** Découplage strict des producteurs et consommateurs de données télémétriques avec résilience matérielle aux coupures de liaison.
* **WebSocket pour l'interface utilisateur :** Permet une interaction bidirectionnelle instantanée (modification de la charge du moteur simulé, variation du régime) avec affichage fluide à 60 FPS sans latence perceptible.

---

## 4. Arbitrage Technique Retenu pour V-Twins

Le système sépare fonctionnellement ses flux réseau en trois couches dédiées :
1. **Pipeline d'Ingestion Moteur :** Transport des flux télémétriques via **MQTT v5** avec sérialisation **Protobuf** pour minimiser la bande passante et garantir l'intégrité des paquets.
2. **Pipeline de Rendu Jumeau Numérique :** Passerelle de diffusion **WebSocket** répercutant l'état mécanique du moteur vers le client web 3D.
3. **Couche Métier et Gestion :** Points de terminaison **REST** réservés aux fonctionnalités transactionnelles (profils moteurs, historiques, facturation).
