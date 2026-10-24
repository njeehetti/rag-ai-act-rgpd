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
- Parsing en passages citables : AI Act et RGPD (articles, paragraphes, points, considérants, annexes), fiches CNIL (sections h2/h3/h4). 1 780 passages au total.
- Deux stratégies de découpage, taille fixe (1 325 chunks) et structurelle (2 255 chunks), toutes deux encodées avec Qwen3-Embedding-0.6B dans pgvector.
- Génération sourcée avec qwen3:8b (Ollama) : refus sans appel au LLM quand aucun passage n'est trouvé, et contrôle de chaque citation.
- Accès via `rag ask`, `POST /ask` et une UI Streamlit (`make ui`) : chat, exemples (dont des cas bancaires), citations cliquables vers le texte officiel, extraits récupérés avec leurs scores.

**Problèmes rencontrés**
- Indexation interrompue : grâce au cache d'embeddings (modèle, SHA-256 du texte), la reprise n'a recalculé que les textes manquants.
- Qwen3-Embedding passé en float16 sur GPU pour partager les 8 Go de VRAM avec le LLM.
- Avec un contexte de 16k, qwen3:8b tournait à 20 % sur CPU (11 à 20 s par réponse). En passant à 8k (`llm_num_ctx`), il tient entièrement sur le GPU : environ 5 s par réponse. Le 1er appel « à froid » prenait 140 s, d'où le préchargement du modèle dans l'UI.
- Console Windows en cp1252 : la CLI force désormais l'UTF-8.

**Relecture indépendante (sous-agent, 24/10)**
- Corrigé :
  - prompt non borné (une section CNIL de 27 000 caractères dépassait la fenêtre du LLM) : budget de contexte et découpage CNIL aux titres h4 (D9) ;
  - connexion psycopg unique en `autocommit=False` (transaction laissée ouverte, connexion bloquée après une erreur, aucune reconnexion) : pool `psycopg_pool`, autocommit, transactions explicites ;
  - réindexation non atomique : remplacement des passages et chunks dans une seule transaction, et verrou consultatif sur les migrations ;
  - identifiants CNIL dépendants de l'ordre et libellés en double (D8) ;
  - « n° » devenu « n », « 1er » devenu « 1 », « ( ) » laissé par les renvois de notes ;
  - citations au niveau d'un point (« art. 5 §1 a ») rejetées à tort : rattachées au paragraphe qui les contient ;
  - refus détecté même au milieu d'une réponse utile, réponse tronquée non signalée, réponse sans source non signalée (`grounded`, `truncated`) ;
  - erreurs de base ou d'Ollama en 500 brut : 503 avec message.
- Reporté :
  - seuil de similarité pour refuser avant l'appel au LLM : à calibrer sur les questions pièges de la Phase 2 ;
  - citations groupées (« §1 et §2 ») ;
  - `version_date` des textes EUR-Lex ;
  - clé du cache d'embeddings sans dtype ni révision du modèle.

**Démo de 5 questions (critère de fin de Phase 1, 24/10)**

| Question | Citations | Invalides | Résultat |
|---|---|---|---|
| Transparence d'un chatbot | AI Act, art. 50 §1 et §5 | 0 | correct |
| Donnée à caractère personnel | RGPD, art. 4, point 1 | 0 | correct |
| Pratiques d'IA interdites | AI Act, art. 5 §1 | 0 | correct |
| Quand faire une AIPD | 2 sections CNIL + RGPD, art. 35 §1 | 0 | correct |
| Recette de la tarte Tatin | aucune | 0 | refus correct |

**Constat qualité (à mesurer en Phase 2)**
- Sur le scoring de crédit, la réponse cite le considérant 58 mais pas l'annexe III 5(b), qui fonde la qualification de haut risque.

**Reste à faire**
- Phase 2 : jeu d'évaluation (format, outil de revue Streamlit, validation par Njee).

## 24/10/2026 — Phase 2 (en cours) : jeu d'évaluation

- Outillage : `rag eval check | split | freeze` (`evalset.py`), page de relecture `make review`, test de gel par SHA-256.
- 66 brouillons rédigés à partir des passages (16 factuelles, 8 définitions, 11 multi-articles, 10 multi-règlements, 8 hors corpus, 13 cas pratiques, dont 12 tagués `banque`). `rag eval check` : aucun problème après correction de deux questions « multi-articles » qui ne citaient qu'un article.
- En lisant le corpus pour rédiger, deux défauts de parsing trouvés et corrigés : l'exposant de « 10^25 » (art. 51 §2) était supprimé comme un renvoi de note ; le texte d'interface CNIL (« Imprimer l'article », navigation entre fiches) était indexé. Le corpus passe à 1 779 passages ; **réindexation à faire** avant la Phase 3.
- Constat utile pour l'évaluation : l'AI Act consolidé (2026) a déplacé des dates (haut risque annexe III au 2 décembre 2027) et ajouté des articles (4 bis, 5 §1 b bis/b ter). Des questions `piege-date` testent qu'on lit le corpus plutôt que la mémoire du LLM.
- Reste : questions de l'auteur (au moins 15), relecture de toutes les questions, split, gel, tag `eval-v1`.
