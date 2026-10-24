# Évaluation

`dataset.jsonl` est le jeu d'évaluation : 80 questions, une par ligne, séparées en un set de **dev** (15 questions, pour régler le système) et un set de **test** (65 questions, réservé aux mesures publiées). Il est figé avant toute expérience de la Phase 3, pour que les comparaisons entre configurations restent honnêtes.

## Format

| Champ | Contenu |
|---|---|
| `id` | `q001`, `q002`… |
| `question` | la question, telle qu'un utilisateur la poserait |
| `reference_answer` | la réponse attendue, rédigée à partir du texte des passages |
| `passage_ids` | identifiants des **passages** justificatifs (jamais des chunks : ils restent valables quelle que soit la stratégie de découpage comparée) ; vide pour une question hors corpus |
| `type` | `factuelle`, `definition`, `multi_articles`, `multi_reglements`, `hors_corpus`, `cas_pratique` |
| `difficulty` | 1 (lecture directe) à 3 (raisonnement sur plusieurs textes) |
| `origin` | `njee` (écrite par l'auteur) ou `proposee_validee` (proposée par l'assistant de développement puis relue et validée) |
| `status` | `draft`, `validated` ou `rejected` ; seules les questions validées sont évaluées |
| `split` | `dev` ou `test` (tirage, voir plus bas) |
| `notes`, `tags` | remarques de relecture ; tags libres (`banque`, `piege-date`, `piege-proche`…) |

## Répartition visée

| Type | Questions | Ce que le type mesure |
|---|---|---|
| factuelle | 20 | retrouver un chiffre, un délai, une date dans un seul passage |
| definition | 10 | restituer une définition de l'art. 3 AI Act ou de l'art. 4 RGPD |
| multi_articles | 12 | combiner plusieurs articles d'un même texte |
| multi_reglements | 12 | combiner l'AI Act, le RGPD et/ou la doctrine CNIL |
| hors_corpus | 10 | refuser quand le corpus ne contient pas la réponse (dont des pièges proches : DSA, NIS 2, article inexistant) |
| cas_pratique | 16 | qualifier une situation concrète (dont des cas bancaires) |

Les questions `piege-date` portent sur les dates de l'AI Act consolidé (2026), qui diffèrent de la version de 2024 que les LLM ont souvent apprise : un système qui répond de mémoire au lieu de lire le corpus se trompe.

## Construction

1. **Brouillons** rédigés à partir du texte des passages du corpus, **jamais à partir des réponses du RAG** : sinon le jeu serait biaisé en faveur du système évalué.
2. **Questions écrites par l'auteur** (au moins 15), plus proches des vraies questions d'un juriste ou d'un chef de projet.
3. **Relecture humaine** de chaque question avec `make review` : la page affiche le texte intégral des passages justificatifs ; on valide, corrige ou rejette. Une question ne peut pas être validée si elle échoue aux contrôles.
4. **Contrôles automatiques** : `uv run rag eval check` vérifie le format, que chaque passage cité existe dans le corpus parsé, qu'une question multi-articles cite au moins deux articles, et qu'une question multi-règlements cite au moins deux sources (AI Act, RGPD, CNIL). Ces contrôles demandent le corpus local (`uv run rag fetch`), absent de la CI.
5. **Split** : `uv run rag eval split` tire les 15 questions de dev par type, au prorata des effectifs, avec une graine fixe (reproductible).
6. **Gel** : `uv run rag eval freeze` refuse s'il reste des brouillons ou si un type n'atteint pas sa cible, puis écrit l'empreinte SHA-256 dans `dataset.sha256`. Le gel est marqué par le tag git `eval-v1`. Un test (`tests/test_evalset.py`) échoue si `dataset.jsonl` change ensuite : toute correction passe par une nouvelle version documentée (`eval-v2`).

## Limites connues

- Les réponses de référence résument le texte ; elles servent de base au juge LLM et à la relecture, pas de vérité juridique.
- Une seule personne relit : pas d'accord inter-annotateurs mesurable.
- Le corpus CNIL est un instantané : une page modifiée par la CNIL peut rendre une question obsolète (les identifiants, eux, sont stables).
