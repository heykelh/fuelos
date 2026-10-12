# Inventaire de la couche Bronze : PRC Data Challenge 2025

## Tables

| Fichier | Lignes | Colonnes |
|---|---:|---|
| airports.parquet | 8 787 | icao (VARCHAR) ; longitude (DOUBLE) ; latitude (DOUBLE) ; elevation (BIGINT) |
| flightlist_final.parquet | 2 836 | flight_date (DATE) ; aircraft_type (VARCHAR) ; takeoff (TIMESTAMP) ; landed (TIMESTAMP) ; origin_icao (VARCHAR) ; origin_name (VARCHAR) ; destination_icao (VARCHAR) ; destination_name (VARCHAR) ; flight_id (VARCHAR) |
| flightlist_rank.parquet | 1 888 | flight_date (DATE) ; aircraft_type (VARCHAR) ; takeoff (TIMESTAMP) ; landed (TIMESTAMP) ; origin_icao (VARCHAR) ; origin_name (VARCHAR) ; destination_icao (VARCHAR) ; destination_name (VARCHAR) ; flight_id (VARCHAR) |
| flightlist_train.parquet | 11 037 | flight_date (DATE) ; aircraft_type (VARCHAR) ; takeoff (TIMESTAMP) ; landed (TIMESTAMP) ; origin_icao (VARCHAR) ; origin_name (VARCHAR) ; destination_icao (VARCHAR) ; destination_name (VARCHAR) ; flight_id (VARCHAR) |
| fuel_final.parquet | 37 456 | idx (BIGINT) ; flight_id (VARCHAR) ; start (TIMESTAMP_NS) ; end (TIMESTAMP_NS) ; fuel_kg (DOUBLE) |
| fuel_final_submit.parquet | 61 745 | idx (BIGINT) ; flight_id (VARCHAR) ; start (TIMESTAMP_NS) ; end (TIMESTAMP_NS) ; fuel_kg (INTEGER) |
| fuel_rank.parquet | 24 289 | idx (BIGINT) ; flight_id (VARCHAR) ; start (TIMESTAMP_NS) ; end (TIMESTAMP_NS) ; fuel_kg (DOUBLE) |
| fuel_rank_submit.parquet | 24 289 | idx (BIGINT) ; flight_id (VARCHAR) ; start (TIMESTAMP_NS) ; end (TIMESTAMP_NS) ; fuel_kg (INTEGER) |
| fuel_train.parquet | 131 530 | idx (BIGINT) ; flight_id (VARCHAR) ; start (TIMESTAMP_NS) ; end (TIMESTAMP_NS) ; fuel_kg (DOUBLE) |

## Trajectoires

| Dossier | Fichiers | Taille |
|---|---:|---:|
| flights_train | 11 037 | 3 146.0 Mo |

Schéma d'une trajectoire (prc770822360.parquet, 25 461 positions) :

- timestamp (TIMESTAMP_NS)
- flight_id (VARCHAR)
- typecode (VARCHAR)
- latitude (DOUBLE)
- longitude (DOUBLE)
- altitude (DOUBLE)
- groundspeed (DOUBLE)
- track (DOUBLE)
- vertical_rate (DOUBLE)
- mach (DOUBLE)
- TAS (DOUBLE)
- CAS (DOUBLE)
- source (VARCHAR)

## Premiers chiffres

- Vols distincts (toutes listes) : 15 761
- Intervalles carburant (entraînement) : 131 530
- Vols couverts par ces intervalles : 11 037
- Carburant total mesuré : 73 355.0 t
- Durée médiane d'un intervalle : 5.0 min
- Vols du fichier carburant absents des listes de vols : 0
- Vols au départ ou à l'arrivée de CDG ou ORY : 142

Types avion les plus représentés :

| Type | Vols |
|---|---:|
| A20N | 5 221 |
| A320 | 4 074 |
| A359 | 2 196 |
| B738 | 753 |
| A332 | 714 |
| B788 | 655 |
| A21N | 507 |
| A321 | 325 |
| B789 | 320 |
| B77W | 295 |
| A333 | 212 |
| B744 | 175 |
| B772 | 133 |
| A319 | 45 |
| B737 | 36 |
