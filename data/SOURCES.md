# Sources du corpus

Vérifiées le 23/10/2026. Les textes bruts sont téléchargés par les scripts d'ingestion dans `data/raw/` (non versionné).

## AI Act — Règlement (UE) 2024/1689

| | |
|---|---|
| Version utilisée | Consolidée du 27/07/2026, CELEX `02024R1689-20260727` (intègre le règlement modificatif (UE) 2026/1744 et le rectificatif FR du 9/10/2025) |
| Accès machine | `http://publications.europa.eu/resource/celex/02024R1689-20260727`, `Accept: application/xhtml+xml`, `Accept-Language: fra` |
| Page lisible | https://eur-lex.europa.eu/legal-content/FR/TXT/HTML/?uri=CELEX:02024R1689-20260727 |
| Formats | XHTML, PDF, Formex 4 (XML) |
| Licence | Décision 2011/833/UE : réutilisation libre, y compris commerciale, avec mention de la source et sans dénaturer le texte. Avis juridique Europa : CC BY 4.0. |

## RGPD — Règlement (UE) 2016/679

| | |
|---|---|
| Version utilisée | CELEX `32016R0679` (consolidée `02016R0679-20160504` : rectificatifs seulement, aucun amendement) |
| Accès machine | `http://publications.europa.eu/resource/celex/32016R0679` |
| Licence | Identique à l'AI Act |
| À surveiller | La modification du RGPD par l'Omnibus numérique (COM(2025) 837) n'était pas adoptée à la mi-septembre 2026 |

**Attribution :** « © Union européenne, https://eur-lex.europa.eu/ ». Seule l'édition électronique du Journal officiel fait foi.

## CNIL — Recommandations et guides

| Ensemble | URL | Format |
|---|---|---|
| Fiches pratiques IA (1 à 13, 8 bis) | https://www.cnil.fr/fr/les-fiches-pratiques-ia | HTML |
| Liste de vérification IA | https://www.cnil.fr/sites/default/files/2025-07/ia_liste_de_verification.pdf | PDF |
| AIPD / PIA | https://www.cnil.fr/fr/RGPD-analyse-impact-protection-des-donnees-aipd | HTML + PDF |
| Bases légales | https://www.cnil.fr/fr/les-bases-legales | HTML |

**Licence : CC BY-ND 4.0** (https://www.cnil.fr/fr/mentions-legales). Il faut une attribution, un lien vers la licence et la date d'extraction, et **aucune modification** n'est permise. Les chunks restent donc des extraits verbatim et sont cités tels quels.

## CNIL — Délibérations et sanctions (pour l'agent)

| Source | URL | Licence | Fraîcheur |
|---|---|---|---|
| Délibérations CNIL (XML DILA, sanctions comprises) | https://echanges.dila.gouv.fr/OPENDATA/CNIL/ | Licence Ouverte | Incréments quasi quotidiens |
| « Sanctions prononcées par la CNIL » (CSV) | https://www.data.gouv.fr/datasets/sanctions-prononcees-par-la-cnil | Licence Ouverte | **Arrêté à septembre 2024** |

Choix envisagé pour l'outil `query_sanctions` : l'export XML de la DILA. La décision sera prise en Phase 4.

## Non vérifié

- Le texte exact de l'avis juridique propre à EUR-Lex (page inaccessible aux robots ; on s'appuie sur la Décision 2011/833/UE).
- Si le rectificatif du RGPD du 23/05/2018 concerne la version française.
