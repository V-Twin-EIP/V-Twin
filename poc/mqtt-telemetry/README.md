# POC — télémétrie MQTT

**Ticket :** [#35 — TW.7](https://github.com/V-Twin-EIP/V-Twin/issues/35). **Auteur :** Slakkos. **Date :** 12 novembre 2026.
**Suite de :** [étude #31](../../docs/research/etudes-comparaison/02_protocoles_reseau_mqtt_vs_websocket.md) et la décision d'équipe du 12/11 (MQTT pour la télémétrie des particuliers, [journal de veille](../../docs/technology-watch/README.md)). **Prépare :** le benchmark de transport [#42](https://github.com/V-Twin-EIP/V-Twin/issues/42).

**Question :** un flux producteur → broker → consommateur MQTT v5 transporte-t-il des échantillons V-Twin sans perte ni doublon non détecté, sous charge et quand un maillon tombe ?

**Réponse :** oui, dans les situations testées, avec un réglage indispensable. Si le broker crashe sans sauvegarde périodique, des messages sont perdus. Avec `autosave_interval 1`, la perte tombe à zéro et les rares doublons sont écartés par le consommateur.

Ce POC utilise des **données synthétiques déclarées** et tourne sur une seule machine. Il ne prouve ni une acquisition sur véhicule ([#34](https://github.com/V-Twin-EIP/V-Twin/issues/34)), ni une latence réseau réelle, ni la supériorité de MQTT sur WebSocket, REST ou SSE (#42). Rien n'est intégré au produit : la sandbox V1 garde son API HTTP ([ADR 0004](../../docs/architecture/adr/0004-study-review-and-v1-boundary.md)).

## Montage

| Élément | Choix | Pourquoi |
| :--- | :--- | :--- |
| Broker | Mosquitto 2.1.2, local, `127.0.0.1:18830`, [mosquitto.conf](mosquitto.conf) | Broker de référence open source, multiplateforme |
| Client | paho-mqtt 2.1.0 (Python), MQTT v5 | Client Python officiel Eclipse ; même langage que le noyau |
| Garantie de livraison | QoS 1 (au moins une fois) | Pas de perte silencieuse ; les doublons sont gérés côté consommateur |
| Sessions | `clean_start=False`, expiration 3 600 s | Le broker garde les messages d'un consommateur déconnecté |
| Reconnexion | Automatique, délai de 0,1 à 1 s | Le producteur met en file d'attente pendant la coupure |
| Topic | `vtwin/v1/telemetry/{source_id}/obd` | Version et source dans le chemin |
| Format | JSON, contrat `vtwin.telemetry-sample` 0.1.0 | Lisible pour un POC ; Protobuf à mesurer dans #42 |

### Contrat de message

Chaque échantillon porte :
- `schema`, `schema_version`, `source_id` et `synthetic: true` ;
- un numéro de séquence `seq`, qui sert à détecter pertes, doublons et désordre ;
- `source_ts_ns`, avec son horloge déclarée (`source_clock: unix_wall_ns`) ;
- les signaux, chacun avec son PID OBD-II : régime `0C`, charge `04`, température d'eau `05`, et température d'huile `5C`, déclarée absente.

Le consommateur rejette les messages non conformes : schéma inconnu, en-tête invalide, valeur non finie ou absence non déclarée.

Producteur et consommateur partagent la même horloge, puisqu'ils tournent sur la même machine. La latence mesurée couvre donc publication → broker → réception, sans réseau ni synchronisation d'horloges.

## Scénarios

| Scénario | Débit | Durée | Ce qui est testé |
| :--- | ---: | ---: | :--- |
| `nominal_obd_10hz` | 10 Hz | 20 s | Fréquence typique d'un dongle OBD-II (ordre de grandeur de l'étude #30) |
| `load_can_500hz` | 500 Hz | 10 s | Haut de la plage CAN citée dans l'étude #30 |
| `stress_2000hz` | 2 000 Hz | 10 s | Marge au-delà de la charge attendue |
| `invalid_inputs` | 50 Hz | 10 s | 1 message sur 25 a une valeur invalide et doit être rejeté |
| `consumer_outage` | 50 Hz | 20 s | Le consommateur se déconnecte 4 s, puis reprend sa session |
| `broker_restart` | 50 Hz | 20 s | Arrêt propre (SIGTERM) du broker pendant 3 s |
| `broker_crash` | 50 Hz | 20 s | Arrêt brutal (SIGKILL) du broker pendant 3 s, réglage par défaut |
| `broker_crash_autosave_1s` | 50 Hz | 20 s | Même crash, avec sauvegarde de l'état du broker chaque seconde |

Chaque scénario repart d'un broker vide et est répété 3 fois.

## Résultats

| Scénario | Publiés (par essai) | Perdus (3 essais) | Doublons écartés | Désordre | Rejetés | Latence p50 (ms) | Latence p95 (ms) | Latence max (ms) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `nominal_obd_10hz` | 200 | 0 / 0 / 0 | 0 | 0 | 0 | 0.42–0.44 | 0.69–4.24 | 17.16 |
| `load_can_500hz` | 5000 | 0 / 0 / 0 | 0 | 0 | 0 | 0.28–0.62 | 5.75–12.97 | 81.83 |
| `stress_2000hz` | 20000 | 0 / 0 / 0 | 0 | 0 | 0 | 0.32–0.33 | 3.02–4.29 | 102.16 |
| `invalid_inputs` | 480 | 0 / 0 / 0 | 0 | 0 | 60 | 0.55–0.60 | 7.95–9.40 | 19.58 |
| `consumer_outage` | 1000 | 0 / 0 / 0 | 1 | 0 | 0 | 0.38–0.59 | 2981.96–3037.52 | 4029.70 |
| `broker_restart` | 1000 | 0 / 0 / 0 | 0 | 0 | 0 | 0.29–0.34 | 2507.26–2526.03 | 3519.86 |
| `broker_crash` | 1000 | 0 / 0 / 44 | 0 | 0 | 0 | 0.37–0.83 | 1692.79–2533.34 | 3527.49 |
| `broker_crash_autosave_1s` | 1000 | 0 / 0 / 0 | 3 | 0 | 0 | 0.50–0.57 | 2525.69–2538.84 | 3535.64 |

Plages = minimum–maximum sur les 3 essais ; latence mesurée sur la même machine (pas de réseau).

Machine : MacBook Pro M4 (arm64, 10 cœurs), macOS 26.6, Python 3.13.16, paho-mqtt 2.1.0, Mosquitto 2.1.2. Les scénarios de charge et de messages invalides ont été relancés sur la machine au repos : la première campagne tournait en même temps qu'une suite de tests, ce qui gonflait les pics de latence sans changer les pertes. La latence des scénarios de coupure inclut volontairement la durée de la coupure, puisque les messages attendent la reconnexion.

Données brutes : [results/mqtt-poc-2026-11-12.json](results/mqtt-poc-2026-11-12.json) (versions, machine, réglages et chaque répétition).

### Lecture

- **Charge :** aucune perte, aucun doublon, aucun désordre jusqu'à 2 000 messages/s (20 000 messages par essai), environ 434 octets par message en JSON. La latence locale médiane est inférieure à 1 ms. Le p95 reste sous 13 ms, avec des pointes isolées jusqu'à environ 100 ms.
- **Coupure du consommateur et redémarrage propre du broker :** aucune perte. Les messages sont gardés puis livrés à la reconnexion. Leur latence est donc la durée de la coupure : c'est voulu, pas un défaut.
- **Crash du broker, réglage par défaut :** la session du consommateur est perdue à chaque crash (0 reprise sur 3). Par défaut, Mosquitto n'écrit son état sur disque qu'à l'arrêt propre et toutes les 30 minutes (`autosave_interval 1800`). Après un crash en cours de scénario, il redémarre donc sans la session ni l'abonnement. Les messages publiés avant le réabonnement n'ont plus de destinataire. La perte dépend de qui se reconnecte en premier : 44 messages dans 1 essai sur 3, et 130 à 177 messages sur 1 000 dans les essais exploratoires.
- **Crash avec `autosave_interval 1` :** session reprise 3 fois sur 3, aucune perte. Le broker renvoie un message déjà livré par essai (QoS 1, au moins une fois). Le consommateur le reconnaît à son `seq` et l'écarte.
- **Messages invalides :** tous rejetés et comptés par motif, sans bloquer le flux.

## Conclusion

1. MQTT v5 avec QoS 1 et sessions persistantes répond au besoin de **transport fiable** du futur jumeau, à condition de :
   - faire sauvegarder périodiquement l'état du broker ;
   - dédoublonner côté consommateur avec un numéro de séquence par source.
2. Le contrat de message, avec source, horloge, unités par PID et absences déclarées, est réutilisable pour l'adaptateur d'acquisition (#17).
3. **Ce n'est pas encore une adoption.** Il reste :
   - le benchmark #42 face à WebSocket, REST et SSE, sur la même charge, avec mesure des ressources ;
   - un test sur réseau réel ;
   - une source réelle (#34).

**Limites :**
- une seule machine (Mac M4, macOS) ;
- pas de TLS ni d'authentification (broker en local, connexions anonymes) ;
- pas de mesure CPU/RAM du broker ;
- payload JSON non optimisé ;
- QoS 2 et rétention longue non testés.

## Reproduire

Prérequis : Mosquitto installé (`brew install mosquitto` sur macOS, `apt install mosquitto` sur Debian/Ubuntu, installeur officiel sous Windows) et `uv`. Depuis la racine du dépôt :

```sh
uv run --no-project --with paho-mqtt==2.1.0 python poc/mqtt-telemetry/poc_mqtt.py --repeat 3 --output poc/mqtt-telemetry/results/mqtt-poc-2026-11-12.json
```

Option `--only <scénario…>` pour en lancer certains. Le script lance et arrête lui-même le broker, avec un dossier de persistance temporaire. Le port 18830 doit être libre.
