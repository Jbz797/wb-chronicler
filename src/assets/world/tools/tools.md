# 🛠 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 12/06/26 23:42</p>

Invoquer chaque script via `python3 tools/<commande>`. Sortie : objet JSON sur `stdout`. `sections` accepte une liste séparée par des virgules (ex. `stats,ranks`) — `full` (défaut) renvoie toutes les sections.

| Commande                          | Sections                                                                                                                     |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `actor/info.py <id> [sections]`   | `full`, `best_friend`, `creature_traits`, `equipment`, `inventory`, `lover`, `metadata`, `plot`, `ranks_in_species`, `stats` |
| `geography/info.py [sections]`    | `basic`                                                                                                                      |
| `kingdom/info.py <id> [sections]` | `full`, `metadata`, `ranks`, `relations`, `wars`                                                                             |
| `world/info.py [sections]`        | `full`, `cumulative`, `metadata`, `snapshot`                                                                                 |
