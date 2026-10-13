# Diagnostic du carburant mesuré

Objectif : comprendre trois signaux observés en Silver (plateau à 2 400 kg/h, A20N deux fois plus bas que l'A320, Mach incohérent) avant toute publication.

## H1 : résolution des valeurs de carburant

Part des intervalles dont la valeur est un multiple exact de 10, 50 ou 100 kg.

| Type | Intervalles | Multiple de 10 | Multiple de 50 | Multiple de 100 | Durée médiane (min) |
|---|---:|---:|---:|---:|---:|
| A20N | 69 572 | 10,5 % | 9,6 % | 9,6 % | 5,0 |
| A320 | 45 009 | 58,7 % | 57,1 % | 57,0 % | 5,0 |
| A359 | 33 112 | 18,2 % | 17,2 % | 17,1 % | 9,9 |
| B738 | 9 350 | 16,4 % | 15,6 % | 15,5 % | 5,0 |
| B788 | 8 206 | 88,5 % | 88,5 % | 88,5 % | 10,1 |
| A332 | 7 618 | 53,4 % | 45,5 % | 45,3 % | 5,0 |
| B789 | 4 610 | 11,5 % | 11,4 % | 11,4 % | 4,0 |
| A21N | 4 091 | 35,0 % | 31,2 % | 31,0 % | 5,0 |
| A321 | 2 879 | 14,2 % | 9,9 % | 9,6 % | 5,0 |
| B77W | 2 793 | 66,3 % | 65,9 % | 65,9 % | 15,0 |
| A333 | 2 048 | 90,1 % | 77,3 % | 75,9 % | 5,0 |
| B744 | 1 276 | 93,0 % | 92,8 % | 92,7 % | 10,0 |

Valeurs les plus fréquentes en croisière :

| Type | Valeur (kg) | Intervalles | Part de la croisière du type |
|---|---:|---:|---:|
| A20N | 90,7 | 6 857 | 31,3 % |
| A20N | 45,4 | 2 974 | 13,6 % |
| A20N | 200,0 | 1 417 | 6,5 % |
| A20N | 100,0 | 1 177 | 5,4 % |
| A20N | 73,9 | 592 | 2,7 % |
| A21N | 200,0 | 538 | 27,1 % |
| A21N | 90,7 | 300 | 15,1 % |
| A21N | 163,3 | 191 | 9,6 % |
| A21N | 145,1 | 153 | 7,7 % |
| A21N | 181,4 | 104 | 5,2 % |
| A320 | 200,0 | 9 317 | 53,0 % |
| A320 | 100,0 | 1 662 | 9,5 % |
| A320 | 300,0 | 766 | 4,4 % |
| A320 | 400,0 | 395 | 2,2 % |
| A320 | 600,0 | 286 | 1,6 % |
| B738 | 199,6 | 876 | 16,4 % |
| B738 | 217,7 | 843 | 15,7 % |
| B738 | 181,4 | 655 | 12,2 % |
| B738 | 235,9 | 532 | 9,9 % |
| B738 | 254,0 | 370 | 6,9 % |

## H2 : A20N et A320, débit de croisière calculé par vol

Débit = carburant total de croisière / durée totale de croisière, pour les vols ayant au moins 30 min de croisière mesurée.

| Tranche de débit (kg/h) | Vols A20N | Vols A320 |
|---|---:|---:|
| 0 à 250 | 5 | 2 |
| 250 à 500 | 4 | 1 |
| 500 à 750 | 13 | 5 |
| 750 à 1 000 | 1 043 | 4 |
| 1 000 à 1 250 | 408 | 2 |
| 1 250 à 1 500 | 3 | 3 |
| 1 500 à 1 750 | 66 | 2 |
| 1 750 à 2 000 | 392 | 93 |
| 2 000 à 2 250 | 124 | 494 |
| 2 250 à 2 500 | 12 | 753 |
| 2 500 à 2 750 | 1 | 320 |
| 2 750 à 3 000 | 1 | 106 |
| 3 000 à 3 250 | 0 | 27 |
| 3 250 à 3 500 | 0 | 4 |
| 3 500 à 3 750 | 0 | 1 |
| 4 500 à 4 750 | 0 | 1 |

## H3 : effet de l'agrégation par vol sur la dispersion

| Type | Vols | P10 par vol | Médiane par vol | P90 par vol |
|---|---:|---:|---:|---:|
| A20N | 2 072 | 862 | 995 | 1 964 |
| A320 | 1 818 | 2 058 | 2 358 | 2 691 |
| A359 | 562 | 4 994 | 5 540 | 6 396 |
| B738 | 445 | 2 191 | 2 449 | 2 653 |
| A21N | 184 | 1 141 | 2 236 | 2 526 |
| A332 | 174 | 4 598 | 5 351 | 6 697 |
| A321 | 128 | 1 878 | 2 514 | 2 906 |
| B789 | 83 | 4 661 | 5 569 | 6 369 |
| A333 | 74 | 4 876 | 5 333 | 7 079 |
| B77W | 74 | 7 086 | 7 942 | 9 441 |
| B772 | 72 | 6 064 | 6 667 | 7 989 |
| B744 | 48 | 8 839 | 9 599 | 10 570 |

## H4 : vitesses mesurées en croisière

| Type | Intervalles | Mach médian | Part Mach vide | Vitesse vraie médiane (kt) | Vitesse sol médiane (kt) |
|---|---:|---:|---:|---:|---:|
| A20N | 21 930 | 0,78 | 26,8 % | 454 | 449 |
| A320 | 17 580 | 0,78 | 7,2 % | 459 | 449 |
| B738 | 5 354 | 0,79 | 89,8 % | n.d. | 443 |
| A359 | 5 059 | 0,10 | 69,7 % | 491 | 483 |
| A21N | 1 986 | 0,77 | 44,8 % | n.d. | 450 |
| A332 | 1 953 | 0,81 | 50,3 % | n.d. | 463 |
| A321 | 1 490 | 0,78 | 9,5 % | 449 | 438 |
| B789 | 681 | 0,85 | 86,5 % | n.d. | 482 |
| A333 | 644 | 0,81 | 17,1 % | n.d. | 471 |
| B772 | 444 | 0,83 | 0,0 % | n.d. | 469 |
| B77W | 388 | 0,83 | 56,7 % | n.d. | 482 |
| B744 | 303 | 0,84 | 77,6 % | n.d. | 482 |

## H5 : positions sans coordonnées

| Source | Positions | Sans latitude ou longitude | Sans altitude |
|---|---:|---:|---:|
| adsb | 123 454 329 | 0,0 % | 0,0 % |
| acars | 133 267 | 9,4 % | 3,9 % |

- Minutes de trajectoire avant filtrage (audit) : 1 452 646
- Minutes de trajectoire après filtrage (Silver) : 1 449 967
- Minutes perdues : 0,2 %
