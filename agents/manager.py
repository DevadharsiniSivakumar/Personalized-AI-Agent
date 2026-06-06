import json
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel
from models.schemas import AgentState
from utils.logger import logger

class IntentClassification(BaseModel):
    """Pydantic model representing structured intent routing results."""
    intent: str = Field(description="Target agent: 'knowledge', 'planner', 'decision', or 'unknown'")
    memory_cmd: Optional[str] = Field(None, description="Memory command: 'remember', 'recall', 'search', or null")
    memory_content: Optional[str] = Field(None, description="The content to remember or search/recall query, or null")

class ManagerAgent:
    """Agent responsible for routing user requests to specific agents based on intent."""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def process(self, state: AgentState) -> Dict[str, Any]:
        """Analyzes user input, detects intent, and sets routing values in state."""
        user_input = state.get("user_input", "")
        logger.info(f"ManagerAgent analyzing user input: '{user_input}'")

        # 1. Try quick heuristic rules first for clear matches (faster and avoids LLM hallucinations)
        classification = self._classify_heuristically(user_input)
        if classification.intent != "unknown":
            logger.info(f"Intent classified heuristically: {classification}")
            return {
                "intent": classification.intent,
                "memory_cmd": classification.memory_cmd,
                "memory_content": classification.memory_content
            }

        # 2. Fallback to LLM classification for semantic/complex queries
        try:
            classification = self._classify_with_llm(user_input)
        except Exception as e:
            logger.warning(f"Structured LLM classification failed ({e}). Falling back to heuristic classification.")
            classification = self._classify_heuristically(user_input)

        logger.info(f"Intent classified by LLM: {classification}")

        return {
            "intent": classification.intent,
            "memory_cmd": classification.memory_cmd,
            "memory_content": classification.memory_content
        }

    def _classify_with_llm(self, user_input: str) -> IntentClassification:
        """Invokes the LLM to classify user intent structurally."""
        # Use structured LLM capabilities if supported
        try:
            structured_llm = self.llm.with_structured_output(IntentClassification)
            prompt = ChatPromptTemplate.from_template("""
You are the Manager Agent of the Personal AI OS, a second brain for the user.
Analyze the user's message and categorize it into the correct intent and memory parameters.

Available Intents:
1. 'knowledge': User wants to remember, search, or recall personal facts or memories.
   - Command 'remember': User explicitly wants to save or store a fact. (e.g., "Remember that I love coding in Rust", "Store my work project details")
   - Command 'search': User wants a raw listing or search of their memories. (e.g., "Search memories for Rust", "Find YOLO in my brain")
   - Command 'recall': User asks a question about their past, projects, preferences, or details they previously told you. (e.g., "What projects did I work on?", "What's my programming language choice?")
2. 'planner': User wants a learning roadmap, study guide, milestone breakdown, or project plan. (e.g., "Create a plan to learn LangGraph", "Roadmap for AI Engineer")
3. 'decision': User wants to compare options, analyze pros/cons, needs a recommendation or decision analysis. (e.g., "ROS vs Full Stack, which to choose?", "Should I buy an Intel or Apple Silicon Mac?")
4. 'unknown': General chit-chat or anything else that doesn't fit above.

User Message:
"{user_input}"
""")
            chain = prompt | structured_llm
            result = chain.invoke({"user_input": user_input})
            
            # Ensure return is a valid IntentClassification
            if isinstance(result, dict):
                return IntentClassification(**result)
            return result
        except Exception as e:
            # If with_structured_output is not supported, fallback to manual JSON prompting
            logger.debug(f"Pydantic structured output not supported or failed: {e}. Trying standard JSON parsing.")
            return self._classify_with_json_prompt(user_input)

    def _classify_with_json_prompt(self, user_input: str) -> IntentClassification:
        """Prompt the LLM to return plain JSON and parse it manually."""
        prompt = ChatPromptTemplate.from_template("""
You are the Manager Agent of the Personal AI OS.
Classify the user's input and determine which agent should handle it.

Available Intents & Memory Commands:
1. 'knowledge':
   - 'remember': User wants to save/store a fact.
   - 'search': User wants a raw listing of memories matching a query.
   - 'recall': User is asking a question about their own history/memories.
2. 'planner': User wants a learning path, roadmap, study plan, or project milestones.
3. 'decision': User wants to compare options, get pros/cons, needs a recommendation.
4. 'unknown': Other inputs.

User Input:
"{user_input}"

Respond ONLY with a valid JSON block containing "intent", "memory_cmd", and "memory_content" keys. Do not include markdown formatting or explanations.
Example output:
{{"intent": "knowledge", "memory_cmd": "remember", "memory_content": "Working on a YOLO project"}}
""")
        chain = prompt | self.llm
        response = chain.invoke({"user_input": user_input})
        
        # Clean JSON markdown if model wrapped it
        clean_content = response.content.strip()
        if clean_content.startswith("```json"):
            clean_content = clean_content[7:]
        if clean_content.endswith("```"):
            clean_content = clean_content[:-3]
        clean_content = clean_content.strip()

        data = json.loads(clean_content)
        return IntentClassification(
            intent=data.get("intent", "unknown"),
            memory_cmd=data.get("memory_cmd"),
            memory_content=data.get("memory_content")
        )

    def _classify_heuristically(self, user_input: str) -> IntentClassification:
        """Rule-based intent routing as a bulletproof fallback."""
        text = user_input.lower().strip()
        
        # Knowledge: remember
        if text.startswith("remember") or text.startswith("save memory") or text.startswith("store that") or "remember that" in text or "remember to" in text:
            content = user_input
            # Strip common prefixes
            for prefix in ["remember that", "remember to", "remember", "save memory", "store that"]:
                if text.startswith(prefix):
                    content = user_input[len(prefix):].strip()
                    break
            return IntentClassification(intent="knowledge", memory_cmd="remember", memory_content=content)
            
        # Knowledge: search
        if text.startswith("search") or text.startswith("find ") or any(w in text for w in ["search memories", "search for", "find memory", "find in my brain"]):
            content = user_input
            for prefix in ["search memories for", "search memories", "search for", "find memory for", "find memory", "find in my brain", "find"]:
                if text.startswith(prefix):
                    content = user_input[len(prefix):].strip()
                    break
            return IntentClassification(intent="knowledge", memory_cmd="search", memory_content=content)

        # Knowledge: recall (questions about self/history)
        if any(w in text for w in ["what project", "what am i", "my name", "what is my", "do i know", "am i working"]):
            return IntentClassification(intent="knowledge", memory_cmd="recall", memory_content=user_input)

        # Planner
        if any(w in text for w in ["roadmap", "milestone", "plan to", "how to learn", "learning path", "study guide"]):
            return IntentClassification(intent="planner")

        # Decision
        if any(w in text for w in ["should i", "vs", "versus", "compare", "or should", "which is better", "pros and cons"]):
            return IntentClassification(intent="decision")

        return IntentClassification(intent="unknown")

    def aggregate_response(self, state: AgentState) -> Dict[str, Any]:
        """Node function to consolidate outputs and structure the final system output."""
        intent = state.get("intent", "unknown")
        agent_outputs = state.get("agent_outputs", {})
        response = state.get("response", "")
        errors = state.get("errors", [])

        logger.info(f"Aggregating response for intent '{intent}'.")

        # Format standard response wrapper if errors exist
        if errors:
            final_resp = f"An error occurred during processing:\n" + "\n".join(f"- {e}" for e in errors)
            return {"response": final_resp}

        # If we have a direct response text from an agent, return it as the final response
        if response:
            return {"response": response}

        # Catch-all fallback if no agent updated the response field
        fallback_resp = "I processed your request, but was unable to generate a specific agent response. Please try rephrasing."
        return {"response": fallback_resp}
