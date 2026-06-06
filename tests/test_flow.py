import os
import sys
import unittest
from unittest.mock import MagicMock
from tempfile import TemporaryDirectory
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from models.schemas import MemorySchema
from memory.sqlite_store import SQLiteStore
from memory.faiss_store import FAISSStore
from memory.embeddings import EmbeddingsManager


class TestPersonalAIOSMemorySystem(unittest.TestCase):
    """Unit tests for the memory stores and operations of Personal AI OS."""

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_brain.db")
        self.faiss_path = os.path.join(self.temp_dir.name, "test_faiss")
        
        # 1. Setup SQLite Store
        self.sqlite_store = SQLiteStore(self.db_path)
        
        # 2. Mock Embeddings Manager to avoid loading sentence-transformers model during tests
        self.mock_embeddings = MagicMock(spec=EmbeddingsManager)
        # Mock dimension to return 384
        self.mock_embeddings.get_dimension.return_value = 384
        # Mock embed_query to return a dummy list of 384 floats
        self.mock_embeddings.embed_query.side_effect = lambda text: [0.1] * 384
        
        # 3. Setup FAISS Store with mocked embeddings
        self.faiss_store = FAISSStore(self.faiss_path, self.sqlite_store, self.mock_embeddings)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_user_creation(self):
        """Verifies creating a user and retrieving it behaves correctly."""
        user = self.sqlite_store.get_or_create_user("test_coder")
        self.assertEqual(user.username, "test_coder")
        self.assertIsNotNone(user.user_id)
        
        # Fetching again should return the same user ID
        user_repeat = self.sqlite_store.get_or_create_user("test_coder")
        self.assertEqual(user.user_id, user_repeat.user_id)

    def test_save_and_retrieve_memory(self):
        """Tests saving memories to SQLite metadata and retrieving them."""
        user = self.sqlite_store.get_or_create_user("john_doe")
        
        mem1 = self.sqlite_store.save_memory(user.user_id, "I love coding in Python")
        mem2 = self.sqlite_store.save_memory(user.user_id, "I am building a multi-agent system")
        
        self.assertEqual(mem1.content, "I love coding in Python")
        self.assertEqual(mem1.user_id, user.user_id)
        self.assertIsNotNone(mem1.memory_id)

        # Retrieve singular
        fetched = self.sqlite_store.get_memory(mem1.memory_id)
        self.assertEqual(fetched.content, "I love coding in Python")

        # Retrieve multiple ordered IDs
        memories = self.sqlite_store.get_memories_by_ids([mem2.memory_id, mem1.memory_id])
        self.assertEqual(len(memories), 2)
        self.assertEqual(memories[0].content, "I am building a multi-agent system")
        self.assertEqual(memories[1].content, "I love coding in Python")

    def test_faiss_semantic_indexing(self):
        """Tests that saving memories updates both SQLite and FAISS, and allows search."""
        user = self.sqlite_store.get_or_create_user("alex")
        
        # Save memory via FAISSStore wrapper
        mem = self.faiss_store.save_memory(user.user_id, "I work on computer vision projects")
        self.assertIsNotNone(mem.memory_id)
        
        # Check FAISS index tracks item
        self.assertEqual(self.faiss_store.index.ntotal, 1)
        
        # Perform similarity search
        results = self.faiss_store.search_memories(user.user_id, "vision", k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "I work on computer vision projects")
        self.assertIsNotNone(results[0].score)
        
    def test_session_history(self):
        """Tests saving and retrieving session history blocks."""
        user = self.sqlite_store.get_or_create_user("session_tester")
        history = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hello, how can I help you today?"}
        ]
        
        self.sqlite_store.save_session_history("session_123", user.user_id, history)
        
        session = self.sqlite_store.get_session_history("session_123")
        self.assertIsNotNone(session)
        self.assertEqual(session.user_id, user.user_id)
        self.assertEqual(len(session.history), 2)
        self.assertEqual(session.history[0]["content"], "Hello!")

    def test_user_password_hashing(self):
        """Tests user creation with a password, hash storage, and verification."""
        from utils.security import verify_password
        
        # Create user with password
        user = self.sqlite_store.create_user("secured_user", "my_secure_p@ss1")
        self.assertEqual(user.username, "secured_user")
        self.assertIsNotNone(user.password_hash)
        self.assertTrue(user.password_hash.startswith("pbkdf2_sha256$"))
        
        # Retrieve user
        fetched = self.sqlite_store.get_user("secured_user")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.password_hash, user.password_hash)
        
        # Verify password checks
        self.assertTrue(verify_password("my_secure_p@ss1", fetched.password_hash))
        self.assertFalse(verify_password("wrong_password", fetched.password_hash))
        self.assertFalse(verify_password("", fetched.password_hash))


if __name__ == "__main__":
    unittest.main()
