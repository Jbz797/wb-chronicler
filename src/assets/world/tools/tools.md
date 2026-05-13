# 🛠 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 13/05/26 14:30</p>

| Script | Usage | Sortie |
|--------|-------|--------|
| `creature-traits/lookup.py <id> [<id>...]` | Résout un ou plusieurs traits de créature. | Une ligne par trait : `id \| rareté \| description \| flavor \| stats` |
| `equipment/lookup.py <id> [<id>...]` | Résout un ou plusieurs items d'équipement. | Une ligne par item : `id \| rareté \| asset_id \| durabilité \| by \| from \| kills \| âge \| stats` |
| `overview/rank.py <id>` | Classe un acteur sur chacune de ses stats parmi ceux de son espèce. | `id \| ranks` |
| `overview/stats.py <id>` | Calcule les stats agrégées d'un acteur. | `id \| stats` |
| `subspecies-traits/stats.py <id> [<id>...]` | Résout un ou plusieurs traits de sous-espèce. | Une ligne par trait : `id \| stats` |
