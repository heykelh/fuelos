# Contrôle d'échelle du carburant mesuré (règle R9, version 2)

Recherche, type par type, de deux populations de vols dont les débits diffèrent d'un facteur constant. OpenAP (TU Delft) sert d'arbitre entre deux échelles, puis chaque vol est comparé au centre de son échelle retenue.

## Référence physique OpenAP en croisière (kg/h)

Conditions : altitude et vitesse sol médianes de la croisière mesurée du type.

| Type | Vols | Altitude (ft) | Vitesse sol (kt) | OpenAP 70 % MTOW | OpenAP 80 % MTOW | OpenAP 90 % MTOW | Mesuré (médiane) | Mesuré / référence 80 % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A20N | 2 518 | 37 002 | 449 | 1 340 | 1 476 | 1 631 | 994 | 0,67 |
| A320 | 2 422 | 36 003 | 448 | 2 373 | 2 581 | 2 813 | 2 374 | 0,92 |
| A359 | 762 | 38 991 | 486 | 6 783 | 7 345 | 7 974 | 5 588 | 0,76 |
| B738 | 479 | 37 446 | 443 | 2 217 | 2 468 | 2 753 | 2 448 | 0,99 |
| A21N | 322 | 35 002 | 447 | n.d. | n.d. | n.d. | 2 265 | n.d. |
| A332 | 234 | 38 000 | 463 | 4 836 | 5 357 | 5 963 | 5 379 | 1,00 |
| A321 | 191 | 35 000 | 437 | 2 757 | 3 044 | 3 365 | 2 547 | 0,84 |
| B789 | 118 | 36 995 | 484 | 6 325 | 6 820 | 7 374 | 5 689 | 0,83 |
| B77W | 96 | 34 000 | 500 | 11 142 | 11 957 | 12 872 | 8 000 | 0,67 |
| A333 | 93 | 37 000 | 464 | 4 976 | 5 492 | 6 089 | 5 333 | 0,97 |
| B772 | 78 | 38 000 | 468 | 9 674 | 10 619 | 11 674 | 6 705 | 0,63 |
| B744 | 59 | 35 992 | 478 | 12 104 | 13 332 | 14 701 | 9 673 | 0,73 |
| B739 | 28 | 37 000 | 451 | 2 322 | 2 573 | 2 858 | 2 600 | 1,01 |
| B737 | 21 | 38 000 | 437 | 2 022 | 2 247 | 2 508 | 2 211 | 0,98 |

Types où mesure et référence concordent (rapport entre 0,9 et 1,1) : A320, B738, A332, A333, B739, B737. Ailleurs, OpenAP sert seulement à arbitrer entre deux échelles, pas à juger un vol isolé.

## Recherche de deux échelles par type

| Type | Vols | Centre bas (kg/h) | Centre haut (kg/h) | Rapport des centres | Part du petit groupe | Référence OpenAP | Échelle retenue | Méthode |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| A20N | 2 518 | 933 | 1 907 | 2,04 | 29,7 % | 1 476 | 1 907 | Deux échelles, arbitrage OpenAP |
| A320 | 2 422 | 2 085 | 2 522 | 1,21 | 40,8 % | 2 581 | 2 374 | Une échelle |
| A359 | 762 | 5 334 | 6 801 | 1,27 | 29,1 % | 7 345 | 5 588 | Une échelle |
| B738 | 479 | 631 | 2 433 | 3,86 | 1,5 % | 2 468 | 2 448 | Une échelle |
| A21N | 322 | 1 065 | 2 331 | 2,19 | 22,4 % | n.d. | n.d. | Deux échelles, pas d'arbitre |
| A332 | 234 | 4 521 | 6 599 | 1,46 | 46,2 % | 5 357 | 5 379 | Une échelle |
| A321 | 191 | 793 | 2 608 | 3,29 | 5,8 % | 3 044 | 2 547 | Une échelle |
| B789 | 118 | 4 981 | 6 417 | 1,29 | 46,6 % | 6 820 | 5 689 | Une échelle |
| B77W | 96 | 7 436 | 9 715 | 1,31 | 34,4 % | 11 957 | 8 000 | Une échelle |
| A333 | 93 | 2 444 | 5 647 | 2,31 | 8,6 % | 5 492 | 5 333 | Une échelle |
| B772 | 78 | 6 307 | 7 797 | 1,24 | 32,1 % | 10 619 | 6 705 | Une échelle |
| B744 | 59 | 9 163 | 10 461 | 1,14 | 47,5 % | 13 332 | 9 673 | Une échelle |
| B739 | 28 | 2 430 | 2 726 | 1,12 | 42,9 % | 2 573 | 2 600 | Une échelle |
| B737 | 21 | 2 162 | 3 056 | 1,41 | 9,5 % | 2 247 | 2 211 | Une échelle |

## Statut des vols d'entraînement

| Type | Cohérent | Échelle suspecte | Non tranché | Non vérifiable | Total |
|---|---:|---:|---:|---:|---:|
| A20N | 747 | 1 771 | 0 | 702 | 3 220 |
| A320 | 2 398 | 24 | 0 | 601 | 3 023 |
| A359 | 746 | 16 | 0 | 809 | 1 571 |
| B788 | 0 | 0 | 0 | 583 | 583 |
| B738 | 470 | 9 | 0 | 72 | 551 |
| A332 | 220 | 14 | 0 | 298 | 532 |
| A21N | 0 | 0 | 322 | 71 | 393 |
| A321 | 179 | 12 | 0 | 94 | 285 |
| B789 | 114 | 4 | 0 | 106 | 224 |
| B77W | 91 | 5 | 0 | 87 | 183 |
| A333 | 90 | 3 | 0 | 63 | 156 |
| B772 | 77 | 1 | 0 | 25 | 103 |

## Débit médian par vol et par phase, vols cohérents uniquement (kg/h)

Format : médiane (nombre de vols). Cellules de moins de 20 vols non affichées. Ce sont les seuls chiffres absolus publiables à ce stade.

| Type | Montée | Croisière | Descente |
|---|---:|---:|---:|
| A320 | 4 361 (920) | 2 388 (2 390) | 1 562 (946) |
| A20N | 3 145 (63) | 1 869 (572) | 1 349 (428) |
| A359 | 10 147 (56) | 5 580 (743) | 2 842 (118) |
| B738 | 5 499 (118) | 2 451 (464) | 1 349 (191) |
| A332 | 8 966 (55) | 5 336 (220) | 2 899 (36) |
| A321 | 5 046 (39) | 2 567 (179) | 1 734 (56) |
| B789 | n.d. | 5 666 (114) | 2 634 (22) |
| B77W | n.d. | 7 973 (91) | 3 599 (27) |
| A333 | n.d. | 5 365 (90) | n.d. |
| B772 | n.d. | 6 709 (77) | 3 127 (44) |
| B744 | n.d. | 9 718 (58) | n.d. |
| B739 | n.d. | 2 600 (27) | n.d. |

Sur les vols cohérents, la croisière médiane de l'A20N est inférieure de 21,7 % à celle de l'A320.
