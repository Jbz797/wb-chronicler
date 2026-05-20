# 🛠 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 20/05/26 09:44</p>

Invoquer chaque script via `python3 tools/<commande>`. Sortie : objet JSON sur `stdout`. `sections` accepte une liste séparée par des virgules (ex. `stats,ranks`) — `full` (défaut) renvoie toutes les sections.

| Commande | Sections |
|----------|----------|
| `actor/overview.py <id> [sections]` | `full`, `creature_traits`, `cumulative`, `equipment`, `metadata`, `ranks`, `snapshot` |
| `world/overview.py [sections]` | `full`, `cumulative`, `metadata`, `snapshot` |
