import os
import sys
os.environ["TESTING"] = "true"
import unittest
from unittest.mock import MagicMock
from tempfile import TemporaryDirectory
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
import server
from memory.sqlite_store import SQLiteStore
from memory.faiss_store import FAISSStore
from memory.embeddings import EmbeddingsManager

class TestPersonalAIOSWebApi(unittest.TestCase):
    """Unit tests for the FastAPI backend endpoints."""

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_api_brain.db")
        self.faiss_path = os.path.join(self.temp_dir.name, "test_api_faiss")
        
        # 1. Setup Mocked Stores
        self.sqlite_store = SQLiteStore(self.db_path)
        
        self.mock_embeddings = MagicMock(spec=EmbeddingsManager)
        self.mock_embeddings.get_dimension.return_value = 384
        self.mock_embeddings.embed_query.side_effect = lambda text: [0.1] * 384
        
        self.faiss_store = FAISSStore(self.faiss_path, self.sqlite_store, self.mock_embeddings)
        
        # 2. Setup Mocked Workflow (LangGraph)
        self.mock_workflow = MagicMock()
        self.mock_workflow.invoke.return_value = {
            "response": "This is a mock agent response.",
            "intent": "general_chat",
            "errors": []
        }
        
        # 3. Assign Mocked Services directly to the server module globals
        server.sqlite_store = self.sqlite_store
        server.faiss_store = self.faiss_store
        server.workflow = self.mock_workflow
        
        # 4. Create FastAPI Test Client
        self.client = TestClient(server.app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_auth_register_and_login(self):
        """Tests user registration, login, and password validation flow."""
        # Register user
        register_payload = {"username": "api_user", "password": "secure_password"}
        res = self.client.post("/api/auth/register", json=register_payload)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["status"], "success")
        user_id = res.json()["user_id"]
        
        # Login with correct password
        login_payload = {"username": "api_user", "password": "secure_password"}
        res = self.client.post("/api/auth/login", json=login_payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")
        self.assertEqual(res.json()["user_id"], user_id)
        
        # Login with wrong password
        login_payload = {"username": "api_user", "password": "wrong_password"}
        res = self.client.post("/api/auth/login", json=login_payload)
        self.assertEqual(res.status_code, 401)
        
        # Login non-existent user
        login_payload = {"username": "no_user", "password": "password"}
        res = self.client.post("/api/auth/login", json=login_payload)
        self.assertEqual(res.status_code, 404)

    def test_legacy_user_password_update(self):
        """Tests that legacy users without passwords can set their password."""
        # Create a legacy user in the DB directly without password hash
        user = self.sqlite_store.create_user("legacy_coder", password=None)
        self.assertIsNone(user.password_hash)
        
        # Logging in should request password setup
        res = self.client.post("/api/auth/login", json={"username": "legacy_coder", "password": "any"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "update_required")
        
        # Update legacy password
        res = self.client.post("/api/auth/update_password", json={"username": "legacy_coder", "password": "new_password"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")
        
        # Verify login now succeeds with the updated password
        res = self.client.post("/api/auth/login", json={"username": "legacy_coder", "password": "new_password"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")

    def test_chat_interaction_flow(self):
        """Tests sending a chat message, checking response, and validating history persistence."""
        user = self.sqlite_store.create_user("chatter", "pass")
        
        chat_payload = {
            "user_id": user.user_id,
            "session_id": "test_session_99",
            "message": "Hello second brain!"
        }
        res = self.client.post("/api/chat", json=chat_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["response"], "This is a mock agent response.")
        
        # Check chat history endpoint
        res = self.client.get(f"/api/chat/history/test_session_99?user_id={user.user_id}")
        self.assertEqual(res.status_code, 200)
        history = res.json()["history"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["content"], "Hello second brain!")
        self.assertEqual(history[1]["content"], "This is a mock agent response.")
        
        # Clear chat history
        res = self.client.delete(f"/api/chat/history/test_session_99?user_id={user.user_id}")
        self.assertEqual(res.status_code, 200)
        
        # Check history is cleared
        res = self.client.get(f"/api/chat/history/test_session_99?user_id={user.user_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["history"], [])

    def test_memory_management_endpoints(self):
        """Tests memory creation, retrieval, filtering, and deletion via APIs."""
        user = self.sqlite_store.create_user("memorizer", "pass")
        
        # Create memory
        res = self.client.post("/api/memories", json={"user_id": user.user_id, "content": "I like building web interfaces."})
        self.assertEqual(res.status_code, 200)
        memory_id = res.json()["memory"]["memory_id"]
        
        # List memories
        res = self.client.get(f"/api/memories?user_id={user.user_id}")
        self.assertEqual(res.status_code, 200)
        memories = res.json()["memories"]
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["content"], "I like building web interfaces.")
        
        # Delete memory
        res = self.client.delete(f"/api/memories/{memory_id}?user_id={user.user_id}")
        self.assertEqual(res.status_code, 200)
        
        # List memories again (should be empty)
        res = self.client.get(f"/api/memories?user_id={user.user_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["memories"], [])

    def test_session_management_flow(self):
        """Tests session creation, listing, renaming, and deletion via APIs."""
        user = self.sqlite_store.create_user("sessionizer", "pass")
        
        # 1. Create a session
        res = self.client.post(f"/api/sessions?user_id={user.user_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        session_id = data["session_id"]
        self.assertEqual(data["title"], "New Conversation")
        
        # 2. Get sessions list
        res = self.client.get(f"/api/sessions?user_id={user.user_id}")
        self.assertEqual(res.status_code, 200)
        sessions = res.json()["sessions"]
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], session_id)
        self.assertEqual(sessions[0]["title"], "New Conversation")
        
        # 3. Rename session
        rename_payload = {"user_id": user.user_id, "title": "Updated Session Title"}
        res = self.client.put(f"/api/sessions/{session_id}/title", json=rename_payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")
        
        # Verify title is updated
        res = self.client.get(f"/api/sessions?user_id={user.user_id}")
        self.assertEqual(res.status_code, 200)
        sessions = res.json()["sessions"]
        self.assertEqual(sessions[0]["title"], "Updated Session Title")
        
        # 4. Delete session
        res = self.client.delete(f"/api/sessions/{session_id}?user_id={user.user_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")
        
        # Verify session is deleted
        res = self.client.get(f"/api/sessions?user_id={user.user_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["sessions"], [])

if __name__ == "__main__":
    unittest.main()
