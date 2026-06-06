import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.config import DATABASE_PATH, FAISS_INDEX_PATH, get_llm
from utils.logger import logger
from models.schemas import AgentState, UserSchema
from memory.sqlite_store import SQLiteStore
from memory.embeddings import EmbeddingsManager
from memory.faiss_store import FAISSStore
from workflows.graph import create_workflow

app = FastAPI(title="Personal AI OS Web API", version="1.0.0")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global stores
sqlite_store = None
faiss_store = None
workflow = None

class UserAuthRequest(BaseModel):
    username: str
    password: str

class ChatMessageRequest(BaseModel):
    user_id: int
    session_id: str
    message: str

class MemoryCreateRequest(BaseModel):
    user_id: int
    content: str

class UpdateTitleRequest(BaseModel):
    user_id: int
    title: str

@app.on_event("startup")
def startup_event():
    global sqlite_store, faiss_store, workflow
    if os.getenv("TESTING") == "true":
        logger.info("Skipping real backend initialization for unit tests.")
        return
    try:
        logger.info("Booting backend services for Web UI...")
        sqlite_store = SQLiteStore(DATABASE_PATH)
        embeddings_manager = EmbeddingsManager()
        faiss_store = FAISSStore(FAISS_INDEX_PATH, sqlite_store, embeddings_manager)
        llm = get_llm()
        workflow = create_workflow(faiss_store, llm)
        logger.info("Web UI backend services booted successfully.")
    except Exception as e:
        logger.error(f"Failed to boot backend services: {e}", exc_info=True)
        raise e

# --- Authentication APIs ---

@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(req: UserAuthRequest):
    username = req.username.strip()
    password = req.password
    
    if not username:
        raise HTTPException(status_code=400, detail="Username cannot be empty.")
    if not password:
        raise HTTPException(status_code=400, detail="Password cannot be empty.")
        
    try:
        existing_user = sqlite_store.get_user(username)
        if existing_user:
            raise HTTPException(status_code=400, detail=f"User '{username}' already exists.")
            
        user = sqlite_store.create_user(username, password)
        return {"status": "success", "user_id": user.user_id, "username": user.username}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/login")
def login_user(req: UserAuthRequest):
    username = req.username.strip()
    password = req.password
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required.")
        
    try:
        user = sqlite_store.get_user(username)
        if not user:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found. Please register first.")
            
        if not user.password_hash:
            # Legacy user, return special flag or handle update
            return {"status": "update_required", "user_id": user.user_id, "username": user.username}
            
        from utils.security import verify_password
        if verify_password(password, user.password_hash):
            return {"status": "success", "user_id": user.user_id, "username": user.username}
        else:
            raise HTTPException(status_code=401, detail="Incorrect password.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging in: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/update_password")
def update_legacy_password(req: UserAuthRequest):
    username = req.username.strip()
    password = req.password
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required.")
        
    try:
        user = sqlite_store.get_user(username)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
            
        if user.password_hash:
            raise HTTPException(status_code=400, detail="Password is already set.")
            
        from utils.security import hash_password
        pw_hash = hash_password(password)
        with sqlite_store._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (pw_hash, user.user_id))
            conn.commit()
            
        return {"status": "success", "user_id": user.user_id, "username": user.username}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting password: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- Chat & Agent APIs ---

@app.post("/api/chat")
def process_chat_message(req: ChatMessageRequest):
    try:
        user_id = req.user_id
        session_id = req.session_id.strip()
        user_message = req.message.strip()
        
        if not user_message:
            raise HTTPException(status_code=400, detail="Message cannot be empty.")
            
        # 1. Fetch current session history if any
        session_record = sqlite_store.get_session_history(session_id)
        history = []
        should_generate_title = False
        
        if session_record:
            history = session_record.history
            if not session_record.title or session_record.title == "New Conversation":
                if len(history) == 0:
                    should_generate_title = True
        else:
            should_generate_title = True
            
        # 2. Append user message to history
        history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # 3. Compile context / history for LangGraph state if needed
        initial_state: AgentState = {
            "user_input": user_message,
            "current_user_id": user_id,
            "intent": "unknown",
            "memory_cmd": None,
            "memory_content": None,
            "response": "",
            "agent_outputs": {},
            "errors": []
        }
        
        # 4. Invoke multi-agent workflow
        final_state = workflow.invoke(initial_state)
        
        response_text = final_state.get("response", "No response generated.")
        intent = final_state.get("intent", "unknown").upper()
        errors = final_state.get("errors", [])
        
        # 5. Append assistant response to history
        history.append({
            "role": "assistant",
            "content": response_text,
            "intent": intent,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # 6. Save history back to SQLite, generating a title if needed
        generated_title = None
        if should_generate_title:
            try:
                logger.info(f"Generating conversation title for session {session_id}...")
                from langchain_core.prompts import ChatPromptTemplate
                title_prompt = ChatPromptTemplate.from_template(
                    "Generate a short, descriptive, and punchy title (maximum 4 words) summarizing this user query. "
                    "Do not put quotes, punctuation, or any introductory text in the response. "
                    "User Query: '{message}'"
                )
                title_chain = title_prompt | get_llm()
                title_res = title_chain.invoke({"message": user_message})
                generated_title = title_res.content.strip().replace('"', '').replace("'", "")
                logger.info(f"Generated title: '{generated_title}'")
            except Exception as e:
                logger.error(f"Failed to generate conversation title: {e}")
                generated_title = "New Conversation"
                
        sqlite_store.save_session_history(session_id, user_id, history, title=generated_title)
        
        return {
            "status": "success",
            "response": response_text,
            "intent": intent,
            "errors": errors,
            "agent_outputs": final_state.get("agent_outputs", {})
        }
    except Exception as e:
        logger.error(f"Error in chat processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/history/{session_id}")
def get_chat_history(session_id: str, user_id: int):
    try:
        session_record = sqlite_store.get_session_history(session_id)
        if session_record:
            if session_record.user_id != user_id:
                raise HTTPException(status_code=403, detail="Forbidden session access.")
            return {"status": "success", "history": session_record.history}
        return {"status": "success", "history": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/chat/history/{session_id}")
def clear_chat_history(session_id: str, user_id: int):
    try:
        # Clear chat history in SQLite by saving an empty list
        sqlite_store.save_session_history(session_id, user_id, [])
        return {"status": "success", "detail": "Session history cleared."}
    except Exception as e:
        logger.error(f"Error clearing history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- Session Management APIs ---

@app.get("/api/sessions")
def get_sessions(user_id: int):
    try:
        sessions = sqlite_store.get_user_sessions(user_id)
        return {
            "status": "success",
            "sessions": [
                {
                    "session_id": s.session_id,
                    "user_id": s.user_id,
                    "title": s.title or "New Conversation",
                    "updated_at": s.updated_at.isoformat()
                }
                for s in sessions
            ]
        }
    except Exception as e:
        logger.error(f"Error retrieving sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sessions")
def create_session(user_id: int):
    try:
        import uuid
        session_id = f"session_{uuid.uuid4().hex[:12]}_{int(datetime.now(timezone.utc).timestamp())}"
        title = "New Conversation"
        sqlite_store.save_session_history(session_id, user_id, [], title=title)
        return {
            "status": "success",
            "session_id": session_id,
            "title": title
        }
    except Exception as e:
        logger.error(f"Error creating session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/sessions/{session_id}/title")
def rename_session(session_id: str, req: UpdateTitleRequest):
    try:
        success = sqlite_store.update_session_title(session_id, req.user_id, req.title.strip())
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=404, detail="Session not found.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renaming session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str, user_id: int):
    try:
        success = sqlite_store.delete_session(session_id, user_id)
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=404, detail="Session not found.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- Memory Management APIs ---

@app.get("/api/memories")
def get_user_memories(user_id: int):
    try:
        # Fetch directly from SQLite database memories table
        with sqlite_store._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT memory_id, content, created_at FROM memories WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
            rows = cursor.fetchall()
            
        memories = []
        for r in rows:
            memories.append({
                "memory_id": r["memory_id"],
                "content": r["content"],
                "created_at": r["created_at"]
            })
        return {"status": "success", "memories": memories}
    except Exception as e:
        logger.error(f"Error fetching memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/memories")
def create_user_memory(req: MemoryCreateRequest):
    try:
        content = req.content.strip()
        if not content:
            raise HTTPException(status_code=400, detail="Memory content cannot be empty.")
            
        # Save through FAISSStore wrapper so it updates both SQLite and FAISS
        memory = faiss_store.save_memory(user_id=req.user_id, content=content)
        return {"status": "success", "memory": memory.model_dump()}
    except Exception as e:
        logger.error(f"Error creating memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/memories/{memory_id}")
def delete_user_memory(memory_id: int, user_id: int):
    try:
        # Delete from SQLite and FAISS via FAISSStore wrapper
        success = faiss_store.delete_memory(user_id=user_id, memory_id=memory_id)
        if success:
            return {"status": "success", "detail": f"Memory ID {memory_id} deleted."}
        else:
            raise HTTPException(status_code=404, detail="Memory not found or unauthorized.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- Serve Static Frontend Files ---

# Create static directory if it does not exist (we will fill it next)
os.makedirs("static", exist_ok=True)

# Mount the static files at root
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Allow port selection from env var, defaulting to 8000
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting server on port {port}...")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
