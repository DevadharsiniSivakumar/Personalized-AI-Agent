import os
import faiss
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from models.schemas import MemorySchema
from memory.embeddings import EmbeddingsManager
from memory.sqlite_store import SQLiteStore
from utils.logger import logger

class FAISSStore:
    """Manages the vector similarity store using FAISS, synced with SQLite metadata."""

    def __init__(self, index_path: str, sqlite_store: SQLiteStore, embeddings_manager: EmbeddingsManager):
        self.index_path = index_path
        self.sqlite_store = sqlite_store
        self.embeddings = embeddings_manager
        self.dimension = self.embeddings.get_dimension()
        self.index = self._load_or_create_index()

    def _load_or_create_index(self) -> faiss.Index:
        """Loads a FAISS index from disk, or creates a new IndexIDMap flat index if missing."""
        if os.path.exists(self.index_path):
            logger.info(f"Loading existing FAISS index from: {self.index_path}")
            try:
                index = faiss.read_index(self.index_path)
                logger.info("FAISS index loaded successfully.")
                return index
            except Exception as e:
                logger.error(f"Error loading FAISS index: {e}. Creating a new one.", exc_info=True)
                
        logger.info(f"Creating a new FAISS index (dimension: {self.dimension})")
        # Use IndexFlatL2 for L2 similarity (Euclidean distance) or IndexFlatIP for dot product (Cosine Similarity)
        # Sentence-transformers embeddings are normalized, making L2 distance directly related to Cosine Similarity.
        quantizer = faiss.IndexFlatL2(self.dimension)
        # Use IndexIDMap to link custom SQLite primary key IDs to embeddings
        return faiss.IndexIDMap(quantizer)

    def _save_index(self):
        """Persists the FAISS index to the file system."""
        try:
            # Ensure folder exists
            Path(self.index_path).parent.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self.index, self.index_path)
            logger.debug(f"FAISS index saved successfully to: {self.index_path}")
        except Exception as e:
            logger.error(f"Error saving FAISS index to disk: {e}", exc_info=True)

    def save_memory(self, user_id: int, content: str) -> MemorySchema:
        """Saves memory to SQLite, generates vector embedding, updates FAISS index, and persists."""
        # 1. Save metadata to SQLite to get unique ID
        memory_schema = self.sqlite_store.save_memory(user_id=user_id, content=content)
        memory_id = memory_schema.memory_id
        
        if memory_id is None:
            raise ValueError("SQLite save failed, memory_id is None")

        # 2. Compute embedding
        logger.info(f"Generating embedding for memory ID {memory_id}...")
        vector = self.embeddings.embed_query(content)
        vector_np = np.array([vector], dtype=np.float32)
        ids_np = np.array([memory_id], dtype=np.int64)

        # 3. Insert into FAISS map
        self.index.add_with_ids(vector_np, ids_np)
        
        # 4. Persist FAISS store
        self._save_index()
        logger.info(f"Memory ID {memory_id} successfully indexed in FAISS vector store.")
        
        return memory_schema

    def search_memories(self, user_id: int, query: str, k: int = 5) -> List[MemorySchema]:
        """Performs a semantic vector similarity search in the FAISS index.

        Returns matching SQLite MemorySchema structures sorted by similarity.
        """
        if self.index.ntotal == 0:
            logger.warning("FAISS search called but index is empty. Falling back to SQLite text search.")
            return self.sqlite_store.search_memories_by_text(user_id, query)

        # 1. Compute query vector
        logger.debug(f"Searching memories semantically for query: '{query}'")
        vector = self.embeddings.embed_query(query)
        vector_np = np.array([vector], dtype=np.float32)

        # 2. Perform FAISS search (returns distance squared and index ID)
        k = min(k, self.index.ntotal)
        distances, indices = self.index.search(vector_np, k)

        # 3. Extract matching IDs
        matched_ids = []
        scores_map = {}
        
        for dist, idx in zip(distances[0], indices[0]):
            # FAISS returns -1 for empty search slots
            if idx == -1:
                continue
            matched_id = int(idx)
            matched_ids.append(matched_id)
            # Store score: normalize L2 distance (lower distance = higher similarity)
            # Convert to a simple relevance score where 1.0 is exact match
            score = float(1.0 / (1.0 + dist))
            scores_map[matched_id] = score

        if not matched_ids:
            return []

        # 4. Fetch memory metadata from SQLite
        memories = self.sqlite_store.get_memories_by_ids(matched_ids)
        
        # 5. Filter memories by current user_id and attach scores
        user_memories = []
        for mem in memories:
            if mem.user_id == user_id:
                mem.score = scores_map.get(mem.memory_id, 0.0)
                user_memories.append(mem)

        # Re-sort list based on relevance score descending
        user_memories.sort(key=lambda m: m.score if m.score is not None else 0.0, reverse=True)
        return user_memories

    def delete_memory(self, user_id: int, memory_id: int) -> bool:
        """Deletes a memory from SQLite metadata and removes its vector from FAISS."""
        success = self.sqlite_store.delete_memory(user_id, memory_id)
        if success:
            try:
                if self.index.ntotal > 0:
                    logger.info(f"Removing memory ID {memory_id} from FAISS store...")
                    ids_np = np.array([memory_id], dtype=np.int64)
                    # remove_ids returns number of removed vectors
                    removed_count = self.index.remove_ids(ids_np)
                    logger.info(f"Removed {removed_count} vector(s) from FAISS.")
                    self._save_index()
            except Exception as e:
                logger.error(f"Error removing memory ID {memory_id} from FAISS: {e}", exc_info=True)
        return success
