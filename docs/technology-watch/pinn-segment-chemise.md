# Note de veille — PINN pour le contact segment–chemise

**Ticket :** [#54](https://github.com/V-Twin-EIP/V-Twin/issues/54). **Auteur :** Slakkos, relecture des hypothèses physiques par AdamTamboura. **Date :** 12 novembre 2026.
**Suite de :** [étude #33](../research/etudes-comparaison/04_prediction_usure_moteur_pinn_vs_ml.md). **Liens :** [journal #29](README.md), [validation #4](https://github.com/V-Twin-EIP/V-Twin/issues/4), [ADR 0004](../architecture/adr/0004-study-review-and-v1-boundary.md).

**Question du mentor (26/10) :** faut-il étudier un PINN pour le modèle d'usure, et avec quelles données ?
**Réponse courte :** on garde un PINN comme piste à tester, sur un seul observable et contre une référence physique. Il ne remplace pas le modèle physique en V1. Ce que l'étude #33 présentait comme « adopté » (inférence < 20 ms, respect « garanti » des lois physiques) n'a pas de source et n'est pas mesuré pour V-Twin.

## 1. Observable retenu

**Épaisseur minimale du film d'huile sous le segment de feu, `h_min`, en fonction de l'angle vilebrequin.**

- C'est une sortie directe de l'équation de Reynolds. Elle sépare frottement hydrodynamique et contact entre aspérités, en amont de l'usure.
- Elle répond à la comparaison prévue des deux huiles (CONF-A / CONF-B du [catalogue de scénarios](../validation/scenarios/scenario-catalog.md)).
- Elle se mesure sur moteur allumé. Mills, Vail et Dwyer-Joyce (2015) mesurent `h_min` par ultrasons, depuis l'extérieur de la chemise, sur un monocylindre essence (Honda CRF450R, 96 × 62,1 mm). Ils trouvent 2 à 3 µm à 3 200 tr/min, et un film quasi nul pendant la combustion, avec contact probable entre aspérités. Ce moteur n'est pas le Hydra : ces valeurs servent d'ordre de grandeur, pas de référence de validation.

## 2. Rôle des contraintes physiques dans l'apprentissage

Un PINN approxime la solution, ici la pression `p(x)` dans le film, par un réseau de neurones. Sa fonction de perte additionne :
- le résidu de l'équation de Reynolds aux points de collocation ;
- les conditions aux limites ;
- les éventuelles mesures.

Il peut aussi apprendre un paramètre inconnu, comme `h_min`, en problème inverse (Raissi et al., 2019).

Ce que disent les sources :
- **La physique est une pénalité, pas une garantie.** Le résidu est seulement minimisé. Un PINN mal entraîné peut violer l'équation sans que rien ne le signale. Il faut donc le comparer à un solveur de référence.
- **Pas besoin de gros volumes de données pour résoudre Reynolds**, puisque les points de collocation suffisent. Mais Almqvist (2021) écrit lui-même que le but n'est pas de battre les différences finies en précision ni en efficacité.
- **Le profil du segment pose problème.** Les PINN exigent une solution dérivable. Les discontinuités d'épaisseur de film demandent des variantes dédiées : lissage par tanh ou formulation d'interface (Guan et al., 2025). La cavitation en sortie de segment complique aussi l'entraînement.
- **Aucune étude PINN propre au segment–chemise n'a été trouvée** (recherche du 12/11/2026). Les travaux existants portent sur des paliers, des patins ou des pompes hydrauliques.

## 3. Comparaison sur le même observable

| | Référence physique | ML pur (régression) | PINN |
| :--- | :--- | :--- | :--- |
| Entrées | Profil du segment, charge radiale, vitesse piston, μ(T) | Les mêmes, plus des exemples `h_min` étiquetés | Les mêmes ; `h_min` peut être appris (problème inverse) |
| Données de calibration | Paramètres matériau et huile | Beaucoup de couples entrée → `h_min` (simulés ou mesurés) | Peu, voire aucune pour le problème direct |
| Données d'évaluation | Mesures indépendantes de `h_min` (ultrasons, LIF) | Les mêmes, hors jeu d'entraînement | Les mêmes, plus l'écart à la référence physique |
| Contraintes physiques | Exactes au maillage près | Aucune | Pénalité dans la perte |
| Métrique d'erreur | Convergence en maillage | Erreur relative sur `h_min`, hors domaine compris | Erreur relative sur `h_min` et `p(x)` contre la référence |
| Coût à mesurer | Temps de résolution par angle | Entraînement + inférence | Entraînement (par cas, sauf PINN paramétré) + inférence |

## 4. Essai minimal reproductible proposé

1. **Référence :** équation de Reynolds 1D stationnaire, sans cavitation, sous un segment de profil parabolique, à un angle de mi-course. Résolution par différences finies. On cherche `h_min` tel que la portance égale la charge radiale imposée.
2. **PINN :** même problème, `p(x)` par réseau et `h_min` comme paramètre appris.
3. **Deux viscosités** (équivalents de CONF-A et CONF-B), même charge et même vitesse. La vitesse piston vient du modèle cinématique déjà implémenté (`vtwin run`).
4. **Mesures :**
   - erreur relative du PINN sur `h_min` et sur la portance ;
   - même sens et même amplitude de variation entre les deux huiles ;
   - temps d'entraînement et d'inférence comparés au solveur par différences finies, sur la même machine.

Cet essai est une **vérification** (solveur contre solveur), sur des données synthétiques déclarées. Ce n'est pas une validation physique.

**Données manquantes :**
- le profil, la largeur et la tension du segment du Hydra ;
- les deux lois μ(T) ;
- la pression des gaz derrière le segment ;
- une mesure indépendante de `h_min` sur un moteur comparable.

**Conséquence :** l'essai se lance avec des valeurs marquées « hypothèse de démo ». Aucune conclusion physique n'en sortira tant que #3/#4 n'auront pas fixé les paramètres et la référence de mesure.

## 5. Décision pour la V1

- **Conservée :** la référence physique en Python/NumPy/SciPy (ADR 0004). Le PINN reste un **candidat différé**. Aucune dépendance d'apprentissage n'entre dans le produit.
- **Prochaine preuve :** l'essai minimal ci-dessus, avec la même métrique pour les deux méthodes. Si le PINN atteint la précision de la référence et réduit un coût mesuré, on rouvre l'ADR 0004.
- **Question pour l'expert tribologie ([experts](../experts/README.md)) :** quelle mesure de `h_min` fait foi pour valider le modèle segment–chemise, et dans quelles conditions ?

## Slide de synthèse

> **PINN pour le segment–chemise : piste testée, pas adoptée**
> - Observable : épaisseur minimale du film `h_min` (mesurable par ultrasons : 2–3 µm sur un monocylindre essence, Mills 2015).
> - Un PINN impose la physique par pénalité : ce n'est pas une garantie, il faut une référence pour le vérifier.
> - Aucune étude PINN segment–chemise trouvée. Points durs : profil du segment, cavitation.
> - Essai proposé : Reynolds 1D, deux huiles, PINN contre différences finies (précision et coût).
> - Décision V1 : modèle physique de référence ; PINN rouvert seulement si l'essai le justifie.

## Sources

- Raissi M., Perdikaris P., Karniadakis G.E. (2019). Physics-informed neural networks: A deep learning framework for solving forward and inverse problems involving nonlinear partial differential equations. *Journal of Computational Physics*, 378, 686–707. [doi:10.1016/j.jcp.2018.10.045](https://doi.org/10.1016/j.jcp.2018.10.045)
- Almqvist A. (2021). Fundamentals of Physics-Informed Neural Networks Applied to Solve the Reynolds Boundary Value Problem. *Lubricants*, 9(8), 82. [doi:10.3390/lubricants9080082](https://doi.org/10.3390/lubricants9080082)
- Guan B., He Q., Hu Y., Zheng Z., Huang W. (2025). Physics-informed neural network for hydrodynamic lubrication with film thickness discontinuity. *Friction*, 13(9), 9441035. [doi:10.26599/FRICT.2025.9441035](https://doi.org/10.26599/FRICT.2025.9441035)
- Mills R., Vail J.R., Dwyer-Joyce R. (2015). Ultrasound for the non-invasive measurement of internal combustion engine piston ring oil films. *Proc. IMechE Part J: J. Engineering Tribology*, 229(2), 207–215. [doi:10.1177/1350650114552538](https://doi.org/10.1177/1350650114552538), [version acceptée](https://eprints.whiterose.ac.uk/86931/)

Limites de cette note : les articles de Raissi, Almqvist et Guan ont été lus par leur résumé et leurs métadonnées, pas en texte intégral. Mills 2015 a été lu en version acceptée.
