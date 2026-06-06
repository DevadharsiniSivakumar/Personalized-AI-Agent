from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, TypedDict
from pydantic import BaseModel, Field

class UserSchema(BaseModel):
    """Pydantic schema representing a user in the system."""
    user_id: Optional[int] = None
    username: str
    password_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MemorySchema(BaseModel):
    """Pydantic schema representing a memory item."""
    memory_id: Optional[int] = None
    user_id: int
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    score: Optional[float] = None  # Similarity search relevance score

class SessionSchema(BaseModel):
    """Pydantic schema representing a conversational session."""
    session_id: str
    user_id: int
    title: Optional[str] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AgentState(TypedDict):
    """LangGraph agent state type definition."""
    user_input: str
    current_user_id: int
    intent: str  # Detected intent (e.g., 'knowledge', 'planner', 'decision', 'unknown')
    memory_cmd: Optional[str]  # e.g., 'remember', 'recall', 'search'
    memory_content: Optional[str]  # The content to remember or search/recall query
    response: str  # Final aggregated response text
    agent_outputs: Dict[str, Any]  # Stores outputs from individual agents for analysis/aggregation
    errors: List[str]  # Tracks any errors encountered during processing
