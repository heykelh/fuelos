# Journal qualité : couche Bronze PRC 2025

Exécution du 12/10/2026 à 15:42. Source : PRC Data Challenge 2025 (Eurocontrol, OpenSky Network), DOI 10.5281/zenodo.19184661.

## Contrôles

| Code | Contrôle | Anomalies | Périmètre | Taux | Gravité | Traitement en Silver |
|---|---|---:|---:|---:|---|---|
| Q01 | Identifiant de vol en double | 0 | 15 761 | 0,00 % | Bloquante | Dédoublonnage |
| Q02 | Horaires de vol incohérents (ordre inversé, moins de 10 min, plus de 20 h) | 0 | 15 761 | 0,00 % | Majeure | Vol exclu des analyses par vol |
| Q03 | Aéroport de départ ou d'arrivée absent du référentiel | 0 | 15 761 | 0,00 % | Mineure | Enrichissement par une source ouverte |
| Q04 | Intervalle carburant en double | 0 | 193 275 | 0,00 % | Bloquante | Dédoublonnage |
| Q05 | Intervalle de durée nulle ou négative | 0 | 193 275 | 0,00 % | Bloquante | Intervalle exclu |
| Q06 | Carburant nul, négatif ou manquant | 0 | 193 275 | 0,00 % | Bloquante | Intervalle exclu |
| Q07 | Intervalles qui se chevauchent dans un même vol | 0 | 193 275 | 0,00 % | Majeure | Signalé, exclu des cumuls par vol |
| Q08 | Intervalle à plus de 2 h avant le décollage ou après l'atterrissage | 54 | 193 275 | 0,03 % | Majeure | Intervalle exclu |
| Q09 | Débit carburant atypique pour le type avion (écart robuste supérieur à 5.0) | 5 902 | 193 275 | 3,05 % | Majeure | Revue manuelle avant exclusion |
| Q10 | Gabarit final différent de l'union des jeux rank et final | 0 | 61 745 | 0,00 % | Majeure | Jeu de test invalide si non nul |
| Q11 | Vol d'entraînement sans trajectoire | 0 | 11 037 | 0,00 % | Majeure | Vol exclu des modèles à base de trajectoire |
| Q12 | Type avion différent entre liste de vols et trajectoire | 0 | 11 037 | 0,00 % | Mineure | Liste de vols retenue comme référence |
| Q13 | Positions aberrantes (altitude, vitesse sol, coordonnées) | 3 589 | 123 587 596 | 0,00 % | Mineure | Positions filtrées |
| Q14 | Vol avec un trou de trajectoire de plus de 10 min | 6 776 | 11 037 | 61,39 % | Majeure | Aucune interpolation sur ces trous |
| Q15 | Intervalle carburant couvert à moins de 50% par la trajectoire | 43 798 | 131 530 | 33,30 % | Majeure | Exclu de l'entraînement des modèles à base de trajectoire |

Seuils : altitude hors de [-1 500 ; 50 000] ft, vitesse sol supérieure à 750 kt, écart robuste calculé sur le logarithme du débit avec la médiane et l'écart absolu médian de chaque type avion (au moins 30 intervalles par type).

Limite connue : le contrôle Q09 compare des intervalles de phases différentes (roulage, montée, croisière). Il ne repère que les erreurs grossières. Un contrôle par phase sera ajouté en Silver.

## Profil des trajectoires

- Part des positions issues d'ACARS : 0,11 %
- Nombre médian de positions par vol : 9 871
- Couverture médiane d'un intervalle carburant : 100,00 %

## Débit carburant observé par type avion

Médiane du débit sur les intervalles mesurés, toutes phases de vol confondues. Ce n'est pas une consommation de croisière : la décomposition par phase vient dans la couche Silver.

| Type | Intervalles | Débit médian (kg/h) |
|---|---:|---:|
| A20N | 69 572 | 1 087 |
| A320 | 45 015 | 2 399 |
| A359 | 33 112 | 5 765 |
| B738 | 9 361 | 2 396 |
| B788 | 8 206 | 4 763 |
| A332 | 7 642 | 5 512 |
| B789 | 4 610 | 5 980 |
| A21N | 4 092 | 2 202 |
| A321 | 2 879 | 2 401 |
| B77W | 2 793 | 7 992 |
| A333 | 2 048 | 5 440 |
| B744 | 1 285 | 9 598 |
