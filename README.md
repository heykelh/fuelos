# FUELOS : Fuel Operations Study

Analyse de l'efficacité carburant des opérations aériennes à partir de données ouvertes et réelles :
consommation par phase de vol, trajectoires, leviers d'économie, indicateurs de suivi et modèles
de prédiction du carburant.

## Ce que ce projet est, et ce qu'il n'est pas

- Toutes les données sont publiques. Aucune donnée interne de compagnie aérienne n'est utilisée.
- Aucun chiffre n'est inventé : chaque résultat est rattaché à sa source et à sa méthode.
- Les vols du jeu PRC 2025 sont anonymisés et ne portent pas d'identifiant compagnie. Les
  comparaisons se font par type avion et par aéroport.
- Aucun indicateur individuel de pilote n'est produit : les analyses restent agrégées.

## Données

| Source | Contenu |
|---|---|
| PRC Data Challenge 2025 (Eurocontrol PRC, OpenSky Network, TU Delft) | Carburant mesuré par intervalle (ACARS), trajectoires ADS-B et ACARS, liste des vols, avril à octobre 2025. DOI : 10.5281/zenodo.19184661 |
| Eurocontrol Aviation Intelligence Portal | Roulage, attente terminale, efficacité verticale par aéroport |
| ICAO Engine Emissions Databank (EASA) | Débit carburant des moteurs par régime |
| OpenAP (TU Delft) | Modèle ouvert de performance avion |

Les licences de chaque source s'appliquent à leurs données respectives. Les données brutes ne sont
pas versionnées dans ce dépôt.

## Architecture

- Bronze : données brutes telles que publiées
- Silver : unités harmonisées, contrôles qualité, phases de vol détectées
- Gold : modèle commun (vols, phases, segments, types avion, aéroports) et indicateurs exportés
  pour le site

Stack : Python 3.12, DuckDB, Parquet, pandas, OpenAP, scipy, statsmodels, scikit-learn, PyTorch,
pandera, pytest. Site : Next.js, TypeScript, Recharts, MapLibre, déployé sur Vercel.

## Structure

- `pipeline/` : scripts numérotés, du téléchargement à l'export
- `notebooks/` : exploration
- `tests/` : recette automatisée
- `docs/` : méthodologie, journal qualité, charte d'usage des données
- `web/` : site (à venir)

## Démarrage (Windows, PowerShell)

    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements-dev.txt
    python pipeline\01_download.py --list

## Feuille de route

- P0 : ingestion, contrôles qualité, anatomie d'un vol, charte d'usage des données
- P1 : leviers, indicateurs, études ciblées, comparaisons par type avion
- P2 : modèles scikit-learn et PyTorch, recette, restitutions, méthodologie, version anglaise

## Auteur

Heykel Hachiche : github.com/heykelh
