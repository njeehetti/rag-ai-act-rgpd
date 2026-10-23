"""Liste versionnée des sources du corpus (voir data/SOURCES.md pour les licences)."""

from dataclasses import dataclass
from typing import Literal

CELLAR_URL = "http://publications.europa.eu/resource/celex/{celex}"
CNIL_URL = "https://www.cnil.fr/fr/{slug}"


@dataclass(frozen=True)
class Source:
    id: str
    kind: Literal["eurlex", "cnil"]
    url: str

    @property
    def filename(self) -> str:
        return f"{self.kind}/{self.id}.html"

    @property
    def headers(self) -> dict[str, str]:
        if self.kind == "eurlex":
            # Cellar sert le XHTML sur négociation de contenu ; EUR-Lex bloque les robots.
            return {"Accept": "application/xhtml+xml", "Accept-Language": "fra"}
        return {}


def _eurlex(celex: str) -> Source:
    return Source(id=celex, kind="eurlex", url=CELLAR_URL.format(celex=celex))


EURLEX_SOURCES = [
    _eurlex("02024R1689-20260727"),  # AI Act consolidé (articles, annexes)
    _eurlex("32024R1689"),  # AI Act, JO original (considérants)
    _eurlex("32016R0679"),  # RGPD
]

CNIL_SLUGS = [
    # Recommandations IA (https://www.cnil.fr/fr/les-fiches-pratiques-ia)
    "developpement-des-systemes-dia-les-recommandations-de-la-cnil-pour-respecter-le-rgpd",
    "quel-est-le-perimetre-des-fiches-pratiques-sur-lia",
    "determiner-le-regime-juridique-applicable",
    "definir-une-finalite-0",
    "determiner-la-qualification-juridique-des-fournisseurs-de-systemes-dia",
    "assurer-que-le-traitement-est-licite",
    "assurer-que-le-traitement-est-licite-reutilisation-des-donnees",
    "realiser-une-analyse-dimpact-si-necessaire",
    "tenir-compte-de-la-protection-des-donnees-dans-la-conception-du-systeme",
    "tenir-compte-de-la-protection-des-donnees-dans-la-collecte-et-la-gestion-des-donnees",
    "base-legale-interet-legitime-developpement-systeme",
    "focus-interet-legitime-collecte-par-moissonnage",
    "ia-informer-les-personnes-concernees",
    "ia-respecter-lexercice-des-droits-des-personnes",
    "ia-annoter-les-donnees",
    "ia-garantir-la-securite-du-developpement",
    "ia-analyser-le-statut-dun-modele-dia-au-regard-du-rgpd",
    # Bases légales (https://www.cnil.fr/fr/les-bases-legales)
    "les-bases-legales/liceite-essentiel-sur-les-bases-legales",
    "les-bases-legales/consentement",
    "les-bases-legales/contrat",
    "les-bases-legales/obligation-legale",
    "les-bases-legales/mission-interet-public",
    "les-bases-legales/interet-legitime",
    "les-bases-legales/choisir-base-legale",
    # Analyse d'impact (le hub /fr/RGPD-analyse-impact-... ne contient que des liens)
    "ce-quil-faut-savoir-sur-lanalyse-dimpact-relative-la-protection-des-donnees-aipd",
    "listes-des-traitements-pour-lesquels-une-aipd-est-requise-ou-non",
]

CNIL_SOURCES = [
    Source(id=slug.replace("/", "--"), kind="cnil", url=CNIL_URL.format(slug=slug))
    for slug in CNIL_SLUGS
]

ALL_SOURCES = EURLEX_SOURCES + CNIL_SOURCES
