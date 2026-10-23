# rag-ai-act-rgpd

[![CI](https://github.com/njeehetti/rag-ai-act-rgpd/actions/workflows/ci.yml/badge.svg)](https://github.com/njeehetti/rag-ai-act-rgpd/actions/workflows/ci.yml)

Assistant en français qui répond aux questions sur l'**AI Act**, le **RGPD** et la doctrine de la **CNIL**, avec des citations précises (`[AI Act, art. 50 §1]`), et agent qui produit une **pré-analyse de conformité** structurée pour un cas d'usage.

> ⚠️ **Outil pédagogique, pas un conseil juridique.** Les réponses peuvent être incomplètes ou erronées. Seule la version publiée au Journal officiel de l'Union européenne fait foi.

**Statut : en construction (Phase 0, squelette).** La démo, les résultats chiffrés et le schéma d'architecture arriveront au fil des phases. Voir [`docs/JOURNAL.md`](docs/JOURNAL.md).

## Ce que le projet va démontrer

- Un RAG **sans framework** (pas de LangChain / LlamaIndex) sur PostgreSQL + pgvector : recherche hybride lexicale + vectorielle, fusion RRF, reranking cross-encoder.
- Un **jeu d'évaluation de 80 questions validé à la main et gelé**, et des expériences comparées avec intervalles de confiance.
- Un agent à function calling, avec sorties Pydantic et garde-fous (budget, itérations, affirmations sourcées).
- Un serveur MCP exposant la recherche dans le corpus.

## Lancer en local

Prérequis : [uv](https://docs.astral.sh/uv/) et Docker.

```bash
cp .env.example .env
docker compose up -d --build   # Postgres + pgvector et l'API sur http://localhost:8000
uv sync && make check          # lint, typage, tests
```

## Documentation

- [`DECISIONS.md`](DECISIONS.md) : les choix techniques, leurs alternatives et leurs sources
- [`data/SOURCES.md`](data/SOURCES.md) : le corpus et ses licences
- [`docs/JOURNAL.md`](docs/JOURNAL.md) : l'avancement

## Licence

Code sous licence [MIT](LICENSE). Les textes du corpus gardent leurs propres licences (voir [`data/SOURCES.md`](data/SOURCES.md)).
