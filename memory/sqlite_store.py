import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Generator
from models.schemas import MemorySchema, UserSchema, SessionSchema
from utils.logger import logger

class SQLiteStore:
    """Manages SQLite storage for users, metadata of memories, and session histories."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager to ensure connections are always closed.

        Crucial for Windows file locks and resource cleanup.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initializes database tables if they do not exist."""
        logger.info(f"Initializing SQLite database at: {self.db_path}")
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                
                # Create Users Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT,
                        created_at TEXT NOT NULL
                    )
                """)
                
                # Table migration: Ensure password_hash column exists
                cursor.execute("PRAGMA table_info(users)")
                columns = [row["name"] for row in cursor.fetchall()]
                if "password_hash" not in columns:
                    logger.info("Migrating database: adding password_hash column to users table")
                    cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
                
                # Create Memories Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                    )
                """)
                
                # Create Sessions Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        title TEXT,
                        history TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                    )
                """)
                
                # Table migration: Ensure title column exists in sessions table
                cursor.execute("PRAGMA table_info(sessions)")
                columns = [row["name"] for row in cursor.fetchall()]
                if "title" not in columns:
                    logger.info("Migrating database: adding title column to sessions table")
                    cursor.execute("ALTER TABLE sessions ADD COLUMN title TEXT")
                
                conn.commit()
            logger.info("SQLite database tables initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing SQLite database: {e}", exc_info=True)
            raise

    # --- User Operations ---

    def get_user(self, username: str) -> Optional[UserSchema]:
        """Gets user by username, returning None if not found."""
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
                row = cursor.fetchone()
                if row:
                    return UserSchema(
                        user_id=row["user_id"],
                        username=row["username"],
                        password_hash=row["password_hash"],
                        created_at=datetime.fromisoformat(row["created_at"])
                    )
            return None
        except Exception as e:
            logger.error(f"Error in get_user: {e}", exc_info=True)
            raise

    def create_user(self, username: str, password: Optional[str] = None) -> UserSchema:
        """Creates a new user with optional password hashing."""
        try:
            from utils.security import hash_password
            password_hash = hash_password(password) if password else None
            now_str = datetime.now(timezone.utc).isoformat()
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                    (username, password_hash, now_str)
                )
                conn.commit()
                new_id = cursor.lastrowid
                
            logger.info(f"Created new user '{username}' with ID {new_id}")
            return UserSchema(
                user_id=new_id,
                username=username,
                password_hash=password_hash,
                created_at=datetime.fromisoformat(now_str)
            )
        except Exception as e:
            logger.error(f"Error in create_user: {e}", exc_info=True)
            raise

    def get_or_create_user(self, username: str) -> UserSchema:
        """Legacy helper for testing and backward compatibility."""
        user = self.get_user(username)
        if user:
            return user
        return self.create_user(username)

    # --- Memory Operations ---

    def save_memory(self, user_id: int, content: str) -> MemorySchema:
        """Saves a new memory to the database and returns the Schema."""
        try:
            now_str = datetime.now(timezone.utc).isoformat()
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO memories (user_id, content, created_at) VALUES (?, ?, ?)",
                    (user_id, content, now_str)
                )
                conn.commit()
                memory_id = cursor.lastrowid
                
            logger.debug(f"Saved memory ID {memory_id} for user {user_id}")
            return MemorySchema(
                memory_id=memory_id,
                user_id=user_id,
                content=content,
                created_at=datetime.fromisoformat(now_str)
            )
        except Exception as e:
            logger.error(f"Error in save_memory: {e}", exc_info=True)
            raise

    def get_memory(self, memory_id: int) -> Optional[MemorySchema]:
        """Retrieves a single memory by its primary key ID."""
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM memories WHERE memory_id = ?", (memory_id,))
                row = cursor.fetchone()
                
                if row:
                    return MemorySchema(
                        memory_id=row["memory_id"],
                        user_id=row["user_id"],
                        content=row["content"],
                        created_at=datetime.fromisoformat(row["created_at"])
                    )
            return None
        except Exception as e:
            logger.error(f"Error retrieving memory ID {memory_id}: {e}", exc_info=True)
            raise

    def get_memories_by_ids(self, memory_ids: List[int]) -> List[MemorySchema]:
        """Fetches metadata for multiple memories matching given IDs, maintaining ordering."""
        if not memory_ids:
            return []
        try:
            placeholders = ",".join("?" for _ in memory_ids)
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT * FROM memories WHERE memory_id IN ({placeholders})",
                    memory_ids
                )
                rows = cursor.fetchall()
                
                # Map records by ID for fast lookup during order alignment
                memory_map = {}
                for r in rows:
                    mem = MemorySchema(
                        memory_id=r["memory_id"],
                        user_id=r["user_id"],
                        content=r["content"],
                        created_at=datetime.fromisoformat(r["created_at"])
                    )
                    memory_map[r["memory_id"]] = mem
                
                # Order the memories matching the requested input IDs sequence
                ordered_memories = []
                for mid in memory_ids:
                    if mid in memory_map:
                        ordered_memories.append(memory_map[mid])
                
                return ordered_memories
        except Exception as e:
            logger.error(f"Error in get_memories_by_ids: {e}", exc_info=True)
            raise

    def search_memories_by_text(self, user_id: int, query: str) -> List[MemorySchema]:
        """Performs simple keyword text-based search (LIKE) in SQLite."""
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM memories WHERE user_id = ? AND content LIKE ? ORDER BY created_at DESC",
                    (user_id, f"%{query}%")
                )
                rows = cursor.fetchall()
                return [
                    MemorySchema(
                        memory_id=r["memory_id"],
                        user_id=r["user_id"],
                        content=r["content"],
                        created_at=datetime.fromisoformat(r["created_at"])
                    )
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Error in search_memories_by_text: {e}", exc_info=True)
            raise

    def delete_memory(self, user_id: int, memory_id: int) -> bool:
        """Deletes a memory by its ID for a specific user."""
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM memories WHERE memory_id = ? AND user_id = ?",
                    (memory_id, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting memory ID {memory_id} for user {user_id}: {e}", exc_info=True)
            raise

    # --- Session Operations ---

    def save_session_history(self, session_id: str, user_id: int, history: List[Dict[str, Any]], title: Optional[str] = None):
        """Saves or updates session chat history, optionally updating the title."""
        try:
            now_str = datetime.now(timezone.utc).isoformat()
            history_json = json.dumps(history)
            with self._connection() as conn:
                cursor = conn.cursor()
                if title is not None:
                    cursor.execute(
                        """
                        INSERT INTO sessions (session_id, user_id, title, history, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(session_id) DO UPDATE SET
                            title = excluded.title,
                            history = excluded.history,
                            updated_at = excluded.updated_at
                        """,
                        (session_id, user_id, title, history_json, now_str)
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO sessions (session_id, user_id, history, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(session_id) DO UPDATE SET
                            history = excluded.history,
                            updated_at = excluded.updated_at
                        """,
                        (session_id, user_id, history_json, now_str)
                    )
                conn.commit()
            logger.debug(f"Saved session '{session_id}' state successfully.")
        except Exception as e:
            logger.error(f"Error saving session history: {e}", exc_info=True)
            raise

    def get_session_history(self, session_id: str) -> Optional[SessionSchema]:
        """Retrieves and parses conversational history for a session."""
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()
                
                if row:
                    return SessionSchema(
                        session_id=row["session_id"],
                        user_id=row["user_id"],
                        title=row["title"] if "title" in row.keys() else None,
                        history=json.loads(row["history"]),
                        updated_at=datetime.fromisoformat(row["updated_at"])
                    )
            return None
        except Exception as e:
            logger.error(f"Error retrieving session '{session_id}': {e}", exc_info=True)
            raise

    def get_user_sessions(self, user_id: int) -> List[SessionSchema]:
        """Retrieves all sessions metadata for a specific user, sorted by update date descending."""
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT session_id, user_id, title, history, updated_at FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
                    (user_id,)
                )
                rows = cursor.fetchall()
                return [
                    SessionSchema(
                        session_id=row["session_id"],
                        user_id=row["user_id"],
                        title=row["title"],
                        history=json.loads(row["history"]),
                        updated_at=datetime.fromisoformat(row["updated_at"])
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Error retrieving user sessions for user {user_id}: {e}", exc_info=True)
            raise

    def delete_session(self, session_id: str, user_id: int) -> bool:
        """Deletes a session for a user."""
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM sessions WHERE session_id = ? AND user_id = ?",
                    (session_id, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting session {session_id} for user {user_id}: {e}", exc_info=True)
            raise

    def update_session_title(self, session_id: str, user_id: int, title: str) -> bool:
        """Renames a session's title."""
        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ? AND user_id = ?",
                    (title, datetime.now(timezone.utc).isoformat(), session_id, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating title for session {session_id}: {e}", exc_info=True)
            raise
