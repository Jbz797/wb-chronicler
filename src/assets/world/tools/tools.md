# 🛠 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 27/05/26 09:14</p>

Invoquer chaque script via `python3 tools/<commande>`. Sortie : objet JSON sur `stdout`. `sections` accepte une liste séparée par des virgules (ex. `stats,ranks`) — `full` (défaut) renvoie toutes les sections.

| Commande                            | Sections                                                                                                                     |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `actor/overview.py <id> [sections]` | `full`, `best_friend`, `creature_traits`, `equipment`, `inventory`, `lover`, `metadata`, `plot`, `ranks_in_species`, `stats` |
| `world/overview.py [sections]`      | `full`, `cumulative`, `metadata`, `snapshot`                                                                                 |
