from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel
from models.schemas import AgentState, MemorySchema
from memory.faiss_store import FAISSStore
from utils.logger import logger

class KnowledgeAgent:
    """Agent responsible for saving, recalling, and searching user memories."""

    def __init__(self, faiss_store: FAISSStore, llm: BaseChatModel):
        self.faiss_store = faiss_store
        self.llm = llm

    def process(self, state: AgentState) -> Dict[str, Any]:
        """Processes knowledge/memory operations based on the state directives."""
        cmd = state.get("memory_cmd")
        user_input = state.get("user_input", "")
        
        if not cmd:
            if any(w in user_input.lower() for w in ["remember", "store", "save"]):
                cmd = "remember"
            else:
                cmd = "recall"
                
        # Use cleaned user input directly for remember command to avoid saving LLM artifacts
        if cmd == "remember":
            content = user_input
            text_lower = user_input.lower().strip()
            for prefix in ["remember that", "remember to", "remember", "save memory", "store that"]:
                if text_lower.startswith(prefix):
                    content = user_input[len(prefix):].strip()
                    break
        else:
            content = state.get("memory_content") or user_input
            
        user_id = state.get("current_user_id", 1)

        logger.info(f"KnowledgeAgent invoked: command={cmd}, content_len={len(content)}")

        if cmd == "remember":
            return self._handle_remember(user_id, content)
        elif cmd == "recall":
            return self._handle_recall(user_id, content)
        elif cmd == "search":
            return self._handle_search(user_id, content)
        else:
            error_msg = f"Unknown memory command: {cmd}"
            logger.error(error_msg)
            return {"response": f"Error: {error_msg}", "errors": [error_msg]}

    def _handle_remember(self, user_id: int, content: str) -> Dict[str, Any]:
        """Saves a new memory into the database and vector store."""
        if not content.strip():
            return {"response": "Memory content cannot be empty."}
        try:
            memory = self.faiss_store.save_memory(user_id=user_id, content=content)
            response_text = f"Memory saved successfully (ID: {memory.memory_id})."
            return {
                "response": response_text,
                "agent_outputs": {
                    "action": "remember",
                    "status": "success",
                    "memory": memory.model_dump()
                }
            }
        except Exception as e:
            error_msg = f"Failed to save memory: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"response": f"Error: {error_msg}", "errors": [error_msg]}

    def _handle_recall(self, user_id: int, query: str) -> Dict[str, Any]:
        """Uses vector search and an LLM to synthesize an answer based on user memories."""
        try:
            # Search FAISS index for relevant memories
            memories = self.faiss_store.search_memories(user_id=user_id, query=query, k=5)
            
            if not memories:
                return {
                    "response": "I could not find any relevant memories in my database.",
                    "agent_outputs": {"action": "recall", "found": False, "memories": []}
                }

            # Build memory context for the LLM
            context_items = []
            for i, mem in enumerate(memories):
                timestamp = mem.created_at.strftime("%Y-%m-%d %H:%M:%S")
                context_items.append(f"[{i+1}] (Saved at {timestamp}): {mem.content}")
            
            context_str = "\n".join(context_items)
            
            # Prompts the LLM to write a concise response using the memories
            prompt = ChatPromptTemplate.from_template("""
You are the Knowledge Agent of the Personal AI OS, a second brain for the user.
Your job is to answer the user's question using their saved memories.

Retrieved Memories:
{memories_context}

User's Question:
{user_question}

Provide a natural, friendly, and concise answer based ONLY on the retrieved memories.
If the memories do not contain the answer or are not relevant to the question, politely state that you could not find any relevant memories regarding this query.
Do not assume, hallucinate, or make up facts outside of what is written in the retrieved memories.
""")
            
            chain = prompt | self.llm
            response = chain.invoke({
                "memories_context": context_str,
                "user_question": query
            })
            
            # Return result
            return {
                "response": response.content,
                "agent_outputs": {
                    "action": "recall",
                    "found": True,
                    "memories": [m.model_dump() for m in memories]
                }
            }
        except Exception as e:
            error_msg = f"Failed to recall memory: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"response": f"Error: {error_msg}", "errors": [error_msg]}

    def _handle_search(self, user_id: int, query: str) -> Dict[str, Any]:
        """Lists matching memories directly with similarity scores without synthesis."""
        try:
            memories = self.faiss_store.search_memories(user_id=user_id, query=query, k=5)
            
            if not memories:
                return {
                    "response": f"No memories found matching '{query}'.",
                    "agent_outputs": {"action": "search", "found": False, "memories": []}
                }

            # Format the output list for the user
            lines = [f"Found {len(memories)} matching memory/memories for '{query}':\n"]
            for i, mem in enumerate(memories):
                score_str = f"Score: {mem.score:.2f}" if mem.score is not None else "Text Match"
                timestamp = mem.created_at.strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"  • ID: {mem.memory_id} | {score_str} | {timestamp}")
                lines.append(f"    \"{mem.content}\"\n")

            return {
                "response": "\n".join(lines).strip(),
                "agent_outputs": {
                    "action": "search",
                    "found": True,
                    "memories": [m.model_dump() for m in memories]
                }
            }
        except Exception as e:
            error_msg = f"Failed to search memories: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"response": f"Error: {error_msg}", "errors": [error_msg]}
