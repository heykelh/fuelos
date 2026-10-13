# Phases de vol et débits carburant (couche Silver)

Phase déduite de la trajectoire de chaque intervalle carburant : vitesse sol moyenne inférieure à 40 kt : sol ; variation d'altitude supérieure à 300 ft/min : montée ou descente ; sinon altitude moyenne d'au moins 20000 ft : croisière, en dessous : palier bas. Intervalle couvert à moins de 50% par la trajectoire : indéterminé.

Les débits sont calculés par vol et par phase, car le carburant est relevé par paliers (souvent 100 kg ou 20 lb) : sur un intervalle de 5 minutes, ce pas domine la mesure.

## Répartition des intervalles par phase (vols avec trajectoire)

| Catégorie | Phase | Intervalles | Part |
|---|---|---:|---:|
| Court et moyen-courrier | Croisière | 48 966 | 56,6 % |
| Court et moyen-courrier | Descente | 14 412 | 16,6 % |
| Court et moyen-courrier | Indéterminée | 11 071 | 12,8 % |
| Court et moyen-courrier | Montée | 10 342 | 11,9 % |
| Court et moyen-courrier | Palier bas | 1 788 | 2,1 % |
| Long-courrier | Indéterminée | 32 681 | 72,8 % |
| Long-courrier | Croisière | 9 642 | 21,5 % |
| Long-courrier | Descente | 1 488 | 3,3 % |
| Long-courrier | Montée | 939 | 2,1 % |
| Long-courrier | Palier bas | 152 | 0,3 % |
| Long-courrier | Sol | 3 | 0,0 % |

Intervalles sans trajectoire téléchargée :

- final : 37 454
- rank : 24 283

## Test d'unité kg / livre (règle R7)

Vols « motif livre » : au moins la moitié des valeurs sont des multiples exacts de 20 lb. Débit de croisière calculé par vol. Rapport attendu en cas de confusion d'unité : 0,4536.

| Type | Vols motif livre | Autres vols | Croisière motif livre (kg/h) | Croisière autres (kg/h) | Rapport | Verdict |
|---|---:|---:|---:|---:|---:|---|
| A20N | 1 152 | 922 | 934 | 1 138 | 0,82 | À examiner |
| A320 | 321 | 1 497 | 2 426 | 2 339 | 1,04 | Pas d'écart |
| A359 | 179 | 383 | 5 560 | 5 532 | 1,00 | Pas d'écart |
| B738 | 311 | 134 | 2 466 | 2 400 | 1,03 | Pas d'écart |
| A21N | 87 | 97 | 1 714 | 2 295 | 0,75 | À examiner |
| A332 | 34 | 140 | 5 150 | 5 461 | 0,94 | Pas d'écart |
| A321 | 22 | 106 | 2 608 | 2 492 | 1,05 | Pas d'écart |
| B789 | 0 | 84 | n.d. | 5 614 | n.d. | Échantillon insuffisant |
| B77W | 0 | 75 | n.d. | 7 911 | n.d. | Échantillon insuffisant |
| A333 | 5 | 69 | 3 464 | 5 400 | 0,64 | Échantillon insuffisant |
| B772 | 1 | 71 | 5 638 | 6 699 | 0,84 | Échantillon insuffisant |
| B744 | 0 | 48 | n.d. | 9 599 | n.d. | Échantillon insuffisant |

Vols corrigés (valeur brute conservée dans fuel_kg, valeur corrigée dans fuel_kg_corr) :

| Type | Vols corrigés | Vols du type | Part |
|---|---:|---:|---:|

## Effet de la correction sur la croisière

| Type | Vols | Médiane brute (kg/h) | Médiane corrigée (kg/h) |
|---|---:|---:|---:|
| A20N | 2 518 | 994 | 994 |
| A21N | 322 | 2 265 | 2 265 |
| A320 | 2 422 | 2 374 | 2 374 |
| A321 | 191 | 2 547 | 2 547 |

Après correction, la croisière médiane de l'A20N est inférieure de 58,1 % à celle de l'A320.

## Débit médian par vol et par phase (kg/h, après correction)

Format : médiane (nombre de vols). Phases d'au moins 15 min par vol. Cellules de moins de 20 vols non affichées. Valeurs atypiques exclues.

| Type | Montée | Croisière | Descente |
|---|---:|---:|---:|
| A320 | 4 392 (1 055) | 2 388 (2 390) | 1 599 (1 259) |
| A20N | 1 952 (927) | 978 (2 332) | 773 (1 320) |
| A359 | 10 488 (62) | 5 580 (743) | 2 988 (153) |
| B738 | 5 490 (123) | 2 451 (464) | 1 359 (219) |
| A21N | 2 313 (72) | 2 359 (250) | 1 385 (109) |
| A332 | 9 119 (70) | 5 338 (221) | 2 998 (85) |
| A321 | 4 975 (67) | 2 567 (179) | 1 741 (119) |
| B789 | n.d. | 5 666 (114) | 2 592 (38) |
| A333 | n.d. | 5 396 (91) | 3 536 (34) |
| B77W | n.d. | 7 973 (91) | 3 600 (34) |
| B772 | n.d. | 6 709 (77) | 3 127 (44) |
| B744 | n.d. | 9 718 (58) | n.d. |
