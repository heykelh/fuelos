# Anomalies de données remontées au fournisseur

Jeu concerné : PRC Data Challenge 2025 (Eurocontrol, OpenSky Network), DOI 10.5281/zenodo.19184661.
Périmètre analysé : 11 037 vols d'entraînement, 131 530 intervalles carburant.
Rédaction au format d'un ticket adressé à une équipe Data Factory.

## DATA-001 : carburant A20N divisé par environ deux sur 70 % des vols

- **Priorité** : haute
- **Constat** : la croisière par vol de l'A20N se répartit en deux groupes, centrés sur
  933 kg/h (70 % des vols) et 1 907 kg/h (30 %). Rapport entre les deux : 2,04.
- **Preuves** :
  - avant traitement, l'A20N consommait environ 45 % de l'A320 sur toutes les phases
    (montée 0,44, croisière 0,41, descente 0,48), soit un facteur constant ;
  - quasiment aucun vol entre les deux groupes ;
  - la référence physique OpenAP désigne le groupe haut comme plausible.
- **Impact** : sans traitement, tout chiffre absolu A20N est sous-estimé de moitié. L'écart
  A20N / A320 en croisière passe de -57 % (brut) à -21,7 % (après traitement).
- **Hypothèse la plus compatible** : valeur transmise pour un seul moteur sur une partie des
  vols (facteur attendu 2,00). Une confusion kg / livre donnerait 2,20 : moins compatible.
- **Traitement dans FUELOS** : règle R9. Vols du groupe bas marqués « échelle suspecte » et
  exclus des chiffres absolus. Valeur brute conservée. Aucun facteur de correction appliqué.
- **Demande** : confirmer la grandeur transmise (total ou par moteur) et fournir une
  métadonnée de source par vol (anonymisée si besoin) permettant de distinguer les flux.

## DATA-002 : même défaut probable sur l'A21N

- **Priorité** : moyenne
- **Constat** : deux groupes centrés sur 1 065 kg/h et 2 331 kg/h (rapport 2,19), le petit
  groupe représentant 22,4 % des vols.
- **Limite** : aucune référence OpenAP pour ce type, donc aucun arbitrage possible.
- **Traitement dans FUELOS** : 322 vols « non tranchés », exclus des chiffres absolus.
- **Demande** : même demande que DATA-001.

## DATA-003 : résolution du carburant par paliers

- **Priorité** : moyenne
- **Constat** : selon le type, 9 % à 93 % des valeurs sont des multiples exacts de 100 kg,
  et une partie des valeurs correspond à des multiples exacts de 20 lb convertis en kg
  (90,7 kg = 200 lb, 181,4 kg = 400 lb).
- **Impact** : sur un intervalle médian de 5 minutes, le pas de mesure domine. Exemple :
  53 % des intervalles de croisière A320 valent exactement 200 kg, soit un faux plateau à
  2 400 kg/h (dispersion apparente de 0,6 %).
- **Traitement dans FUELOS** : règle R6. Débits calculés par vol et par phase, sur au moins
  15 minutes, jamais par intervalle isolé.
- **Demande** : documenter la résolution d'origine et l'unité source de chaque valeur.

## DATA-004 : champ Mach défectueux ou incomplet

- **Priorité** : basse
- **Constat** : Mach médian de 0,10 pour l'A359 en croisière à 38 000 ft, alors que sa
  vitesse vraie médiane est de 491 kt. Mach vide sur 27 % à 90 % des intervalles selon le type.
- **Traitement dans FUELOS** : règle R8. Mach non utilisé ; vitesse sol ADS-B utilisée.
- **Demande** : vérifier le décodage du Mach ACARS pour l'A359.

## DATA-005 : couverture de trajectoire (limite, pas défaut)

- **Priorité** : information
- **Constat** : 96,9 % des vols long-courriers ont au moins un trou de plus de 10 minutes
  (récepteurs ADS-B au sol, absents au-dessus des océans). Plus de 92 % des intervalles au
  sol sont mal couverts.
- **Traitement dans FUELOS** : règle R4. Aucune interpolation. Phase « indéterminée » si
  l'intervalle est couvert à moins de 50 %. Analyses au sol menées avec d'autres sources
  (Eurocontrol, ICAO Engine Emissions Databank).
