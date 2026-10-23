"""Modèles d'embedding derrière une interface unique, pour pouvoir les comparer (Phase 3)."""

from typing import Protocol

import numpy as np

QWEN3_EMBEDDING = "Qwen/Qwen3-Embedding-0.6B"
BGE_M3 = "BAAI/bge-m3"


class Embedder(Protocol):
    name: str

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """Modèle local (sentence-transformers), sur GPU si disponible.

    Les modèles asymétriques comme Qwen3-Embedding encodent la question avec une
    instruction et les documents sans : ``encode_query`` / ``encode_document`` appliquent
    les prompts déclarés par le modèle. Les vecteurs sont normalisés (cosinus = produit
    scalaire), ce qui correspond à l'opérateur ``<=>`` de pgvector.
    """

    def __init__(self, name: str = QWEN3_EMBEDDING, batch_size: int = 16) -> None:
        import torch  # imports lourds, différés
        from sentence_transformers import SentenceTransformer

        self.name = name
        self._batch_size = batch_size
        # float16 sur GPU : moitié moins de mémoire, sans perte mesurable pour la recherche.
        kwargs = {"dtype": torch.float16} if torch.cuda.is_available() else {}
        self._model = SentenceTransformer(name, model_kwargs=kwargs)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            self._model.encode_document(
                texts,
                batch_size=self._batch_size,
                normalize_embeddings=True,
                show_progress_bar=len(texts) > 100,
            )
        )

    def embed_query(self, text: str) -> np.ndarray:
        return np.asarray(self._model.encode_query(text, normalize_embeddings=True))
