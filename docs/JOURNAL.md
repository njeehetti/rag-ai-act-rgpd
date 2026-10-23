# Journal de bord

## Planning (validé le 23/10/2026)

| Période | Contenu |
|---|---|
| 23 oct.–2 nov. | Phase 0 (squelette) + Phase 1 (ingestion, RAG de base, démo `/ask`) |
| 3–16 nov. | Phase 2 : jeu d'évaluation (brouillons, validation par Njee, gel) |
| 17–23 nov. | Phase 3 : expériences A/B/C |
| 24–30 nov. | Phase 4 : agent |
| 1–7 déc. | Phase 5 : MCP, déploiement, README final |
| 8 déc.–10 janv. | Marge, post LinkedIn, préparation des entretiens |

## 23/10/2026 — Phase 0

**Fait**
- Inventaire des outils, vérification des sources et licences (`data/SOURCES.md`), des versions de bibliothèques et des modèles (`DECISIONS.md`).
- Modèles validés (D4).
- Squelette : uv + Python 3.12, ruff, mypy strict, pytest, FastAPI `/health`, Docker Compose (Postgres 18.6 + pgvector 0.8.7), CI GitHub Actions.

**Problèmes rencontrés**
- EUR-Lex bloque les clients scriptés, d'où le passage par Cellar (D1).
- Identifiants ghcr.io périmés en local, d'où l'installation d'uv par pip dans l'image (D6).
- Starlette déprécie `httpx` pour `TestClient`, remplacé par `httpx2`.

**Reste à faire**
- CI verte sur GitHub, issues de roadmap.
- Phase 1 : plan d'ingestion et de parsing à valider.
