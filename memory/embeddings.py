import numpy as np
from typing import List
from sentence_transformers import SentenceTransformer
from utils.logger import logger

class EmbeddingsManager:
    """Manages text embeddings using sentence-transformers all-MiniLM-L6-v2."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self) -> SentenceTransformer:
        """Loads and returns the SentenceTransformer model lazily."""
        if self._model is None:
            logger.info(f"Loading SentenceTransformer model '{self.model_name}' (this may take a few seconds on first run)...")
            try:
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"SentenceTransformer model '{self.model_name}' loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise
        return self._model

    def embed_query(self, text: str) -> List[float]:
        """Generates an embedding vector for a single query string."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generates embedding vectors for a list of document strings."""
        if not texts:
            return []
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def get_dimension(self) -> int:
        """Returns the dimensionality of the generated embeddings.

        all-MiniLM-L6-v2 outputs 384-dimensional vectors.
        """
        # For all-MiniLM-L6-v2, it's 384
        return 384
