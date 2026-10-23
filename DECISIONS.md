# Décisions techniques

Chaque décision : le choix, le pourquoi, l'alternative écartée, et la source vérifiée. Vérifications faites le 23/10/2026.

## D1 — Récupérer les textes européens via Cellar, pas via EUR-Lex

- **Choix :** télécharger l'AI Act et le RGPD depuis le service Cellar de l'Office des publications (`http://publications.europa.eu/resource/celex/{CELEX}`, en-tête `Accept: application/xhtml+xml`, `Accept-Language: fra`).
- **Pourquoi :** EUR-Lex renvoie une réponse vide (HTTP 202, 0 octet) aux clients scriptés. Cellar sert le même document et sans blocage, ce qui rend l'ingestion reproductible.
- **Écarté :** le scraping d'EUR-Lex (bloqué, fragile) et le PDF (perd la structure).

## D2 — Utiliser la version consolidée de l'AI Act du 27/07/2026

- **Choix :** CELEX `02024R1689-20260727`.
- **Pourquoi :** le règlement (UE) 2026/1744 (« Omnibus numérique ») a décalé les dates d'application des systèmes à haut risque, au 2/12/2027 (Annexe III) et au 2/08/2028 (Annexe I). Avec le texte de 2024, on donnerait des dates fausses.
- **Conséquence :** dans la version consolidée, les paragraphes ont des identifiants HTML aléatoires. Les identifiants citables sont donc construits à partir de la numérotation juridique (`aiact:art50:p1`), pas à partir du HTML.

## D3 — Une seule base : PostgreSQL 18 + pgvector 0.8.7

- **Choix :** image `pgvector/pgvector:0.8.7-pg18`.
- **Pourquoi :** une seule base pour les vecteurs, la recherche plein texte (`french`), les métadonnées et les tables de l'agent. Cela fait moins de pièces mobiles, et SQL permet des jointures entre recherche et métadonnées.
- **Écarté :** Qdrant en base principale. Il est plus spécialisé, mais imposerait une deuxième base pour le lexical et les données structurées.

## D4 — Modèles (validés le 23/10/2026)

| Rôle | Choix | Pourquoi | Écarté |
|---|---|---|---|
| Embedding local | `Qwen/Qwen3-Embedding-0.6B` (Apache-2.0) | Meilleur score MMTEB de sa taille (64,3) | `BAAI/bge-m3` (59,6), gardé en secours si c'est trop lent sur CPU |
| Embedding API | OpenAI `text-embedding-3-small` | 0,02 $ par million de tokens : le corpus entier coûte quelques centimes | `mistral-embed` (modèle de 2023) |
| Reranker | `BAAI/bge-reranker-v2-m3` (Apache-2.0) | Vrai cross-encoder multilingue, rapide | Qwen3-Reranker (de type LLM, lent sur CPU) ; Jina (licence non commerciale CC BY-NC) |
| Génération | `claude-haiku-5-5` ; Mistral Small 4 en second fournisseur | Peu cher (0,10 $ / 0,50 $ par million de tokens) ; le second fournisseur prouve que l'interface est interchangeable | — |
| Juge | `claude-sonnet-5-5` | Modèle différent du générateur, ce qui limite le biais d'auto-évaluation | Ragas (0.4.3, pas de version depuis 9 mois). Un juge maison est calibré sur 20 notes humaines. |

Sources : fiches Hugging Face des modèles, scores MMTEB publiés sur les fiches de Qwen3-Embedding et d'EmbeddingGemma-2, pages de tarifs d'Anthropic, d'OpenAI et de Mistral.

## D5 — Outillage : uv, ruff, mypy strict, pytest

- **Pourquoi :** uv donne un lockfile reproductible et des installations rapides. mypy en mode strict signale le typage dès le départ, ce qui est moins coûteux que de l'ajouter après coup.
- **Écarté :** Poetry (plus lent, et uv est devenu le standard).

## D6 — Installer uv dans l'image Docker avec pip

- **Choix :** `pip install uv==0.13.5` plutôt que `COPY --from=ghcr.io/astral-sh/uv`.
- **Pourquoi :** les identifiants ghcr.io périmés sur la machine de dev faisaient échouer le build. pip ne dépend d'aucun registre externe autre que PyPI, et la version reste figée.

## D7 — UI : Streamlit

- **Pourquoi :** la même techno sert à l'UI de démo et à l'outil de revue du jeu d'évaluation (Phase 2).
- **Écarté :** Gradio. Il n'apporte rien de plus ici, et ses Spaces gratuits sur CPU sont désormais payants.
