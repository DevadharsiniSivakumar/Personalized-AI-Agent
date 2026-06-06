from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel
from models.schemas import AgentState
from memory.faiss_store import FAISSStore
from utils.logger import logger

class DecisionAgent:
    """Agent responsible for comparing alternatives, analyzing pros/cons, and making recommendations."""

    def __init__(self, faiss_store: FAISSStore, llm: BaseChatModel):
        self.faiss_store = faiss_store
        self.llm = llm

    def process(self, state: AgentState) -> Dict[str, Any]:
        """Processes decision/comparison queries, incorporating user memory context."""
        user_input = state.get("user_input", "")
        user_id = state.get("current_user_id", 1)

        logger.info(f"DecisionAgent invoked with prompt: '{user_input}'")

        try:
            # 1. Query memories for context relevant to the decision topic
            memories = self.faiss_store.search_memories(user_id=user_id, query=user_input, k=3)
            
            if memories:
                context_lines = []
                for m in memories:
                    # Filter out low-relevance results
                    if m.score is None or m.score >= 0.4:
                        context_lines.append(f"- {m.content}")
                user_context = "\n".join(context_lines) if context_lines else "No specific background memories found."
            else:
                user_context = "No specific background memories found."

            logger.debug(f"Retrieved user context for decision: {user_context}")

            # 2. Formulate LLM call
            prompt = ChatPromptTemplate.from_template("""
You are the Decision Agent of the Personal AI OS, a second brain for the user.
Your role is to compare alternatives, generate pros and cons, recommend actions, and explain the reasoning behind the recommendation.

User Inquiry/Decision Query:
{user_input}

User Background Context (retrieved from memories):
{user_context}

Please provide a comprehensive decision analysis report.
Guidelines:
1. **Overview**: Define the options being compared and the context.
2. **Comparison Table/Matrix**: Provide a markdown comparison of key characteristics (e.g., learning curve, industry demand, local storage/hardware requirements, alignment with user context).
3. **Pros and Cons**: Detail the strengths and weaknesses of each option.
4. **Recommendation**: Give a definitive recommendation based on the trade-offs.
5. **Reasoning & Explanation**: Elaborate on the reasoning, explicitly citing items from the User Background Context if they support the decision.
6. Present the output in clean, readable Markdown.
""")

            chain = prompt | self.llm
            response = chain.invoke({
                "user_input": user_input,
                "user_context": user_context
            })

            return {
                "response": response.content,
                "agent_outputs": {
                    "agent": "decision",
                    "comparison": response.content,
                    "personalized_with_context": user_context != "No specific background memories found."
                }
            }

        except Exception as e:
            error_msg = f"Failed to perform decision analysis: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"response": f"Error: {error_msg}", "errors": [error_msg]}
