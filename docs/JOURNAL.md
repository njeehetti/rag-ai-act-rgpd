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

- Dépôt public https://github.com/njeehetti/rag-ai-act-rgpd, CI verte, issues de roadmap #1 à #5.
- `setup-uv` ne publie plus de tag majeur flottant : version figée à `v10.3.2`.

**Reste à faire**
- Phase 1 : plan d'ingestion et de parsing à valider.

## 23–24/10/2026 — Phase 1

**Fait**
- Téléchargement du corpus via Cellar et cnil.fr, avec un manifeste SHA-256 (`rag fetch` / `rag verify`).
- Parsing en passages citables : AI Act et RGPD (articles, paragraphes, points, considérants, annexes), fiches CNIL (sections). 1 721 passages au total.
- Deux stratégies de découpage, taille fixe (1 331 chunks) et structurelle (2 232 chunks), toutes deux encodées avec Qwen3-Embedding-0.6B dans pgvector.
- Génération sourcée avec qwen3:8b (Ollama) : refus sans appel au LLM quand aucun passage n'est trouvé, et contrôle de chaque citation.
- Accès via `rag ask`, `POST /ask` et une UI Streamlit (`make ui`) : chat, exemples (dont des cas bancaires), citations cliquables vers le texte officiel, extraits récupérés avec leurs scores.

**Problèmes rencontrés**
- Indexation interrompue : grâce au cache d'embeddings (modèle, SHA-256 du texte), la reprise n'a recalculé que les textes manquants.
- Qwen3-Embedding passé en float16 sur GPU pour partager les 8 Go de VRAM avec le LLM.
- Avec un contexte de 16k, qwen3:8b tournait à 20 % sur CPU (11 à 20 s par réponse). En passant à 8k (`llm_num_ctx`), il tient entièrement sur le GPU : environ 5 s par réponse. Le 1er appel « à froid » prenait 140 s, d'où le préchargement du modèle dans l'UI.
- Console Windows en cp1252 : la CLI force désormais l'UTF-8.

**Constat qualité (à mesurer en Phase 2)**
- Sur le scoring de crédit, la réponse cite le considérant 58 mais pas l'annexe III 5(b), qui fonde la qualification de haut risque.

**Reste à faire**
- Phase 2 : jeu d'évaluation (format, outil de revue Streamlit, validation par Njee).
