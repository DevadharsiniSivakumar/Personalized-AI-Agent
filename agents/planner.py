from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel
from models.schemas import AgentState
from memory.faiss_store import FAISSStore
from utils.logger import logger

class PlannerAgent:
    """Agent responsible for generating structured roadmaps, plans, and milestones."""

    def __init__(self, faiss_store: FAISSStore, llm: BaseChatModel):
        self.faiss_store = faiss_store
        self.llm = llm

    def process(self, state: AgentState) -> Dict[str, Any]:
        """Processes planning queries, retrieving memory context for personalized plans."""
        user_input = state.get("user_input", "")
        user_id = state.get("current_user_id", 1)

        logger.info(f"PlannerAgent invoked with prompt: '{user_input}'")

        try:
            # 1. Query memories to fetch background context
            memories = self.faiss_store.search_memories(user_id=user_id, query=user_input, k=3)
            
            if memories:
                context_lines = []
                for m in memories:
                    # Only use highly relevant memories
                    if m.score is None or m.score >= 0.4:
                        context_lines.append(f"- {m.content}")
                user_context = "\n".join(context_lines) if context_lines else "No specific background memories found."
            else:
                user_context = "No specific background memories found."

            logger.debug(f"Retrieved user context for planner: {user_context}")

            # 2. Formulate LLM call
            prompt = ChatPromptTemplate.from_template("""
You are the Planner Agent of the Personal AI OS, a second brain for the user.
Your role is to generate learning plans, project roadmaps, and break down goals into structured milestones.

User Goal/Request:
{user_input}

User Background Context (retrieved from memories):
{user_context}

Please create a detailed, highly actionable, and structured roadmap/plan.
Guidelines:
1. Divide the journey/project into clear chronological Phases or Milestones.
2. For each Phase, specify key objectives, list exact action items, and estimate a realistic timeline.
3. Suggest specific local tools, frameworks, or resources.
4. Personalize the roadmap using any relevant information from the User Background Context. For example, if the context shows they already have experience with a tool, adapt the plan accordingly.
5. Present the response in beautifully formatted Markdown.
""")

            chain = prompt | self.llm
            response = chain.invoke({
                "user_input": user_input,
                "user_context": user_context
            })

            return {
                "response": response.content,
                "agent_outputs": {
                    "agent": "planner",
                    "plan": response.content,
                    "personalized_with_context": user_context != "No specific background memories found.",
                    "retrieved_memories": [m.model_dump() for m in memories] if memories else []
                }
            }

        except Exception as e:
            error_msg = f"Failed to generate plan: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"response": f"Error: {error_msg}", "errors": [error_msg]}
