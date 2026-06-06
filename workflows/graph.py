from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from models.schemas import AgentState
from memory.faiss_store import FAISSStore
from agents.manager import ManagerAgent
from agents.knowledge import KnowledgeAgent
from agents.planner import PlannerAgent
from agents.decision import DecisionAgent
from utils.logger import logger

def create_workflow(faiss_store: FAISSStore, llm: BaseChatModel) -> StateGraph:
    """Builds and compiles the multi-agent LangGraph workflow.

    Defines the nodes, edges, conditional routing, and response aggregation.
    """
    logger.info("Initializing multi-agent workflow graph...")

    # Instantiate the agents
    manager_agent = ManagerAgent(llm=llm)
    knowledge_agent = KnowledgeAgent(faiss_store=faiss_store, llm=llm)
    planner_agent = PlannerAgent(faiss_store=faiss_store, llm=llm)
    decision_agent = DecisionAgent(faiss_store=faiss_store, llm=llm)

    # Define Node functions wrapping agent executions
    def manager_node(state: AgentState) -> Dict[str, Any]:
        try:
            return manager_agent.process(state)
        except Exception as e:
            err_msg = f"Manager Node failed: {e}"
            logger.error(err_msg, exc_info=True)
            return {"errors": state.get("errors", []) + [err_msg]}

    def knowledge_node(state: AgentState) -> Dict[str, Any]:
        try:
            return knowledge_agent.process(state)
        except Exception as e:
            err_msg = f"Knowledge Node failed: {e}"
            logger.error(err_msg, exc_info=True)
            return {"response": f"Knowledge Agent Error: {e}", "errors": state.get("errors", []) + [err_msg]}

    def planner_node(state: AgentState) -> Dict[str, Any]:
        try:
            return planner_agent.process(state)
        except Exception as e:
            err_msg = f"Planner Node failed: {e}"
            logger.error(err_msg, exc_info=True)
            return {"response": f"Planner Agent Error: {e}", "errors": state.get("errors", []) + [err_msg]}

    def decision_node(state: AgentState) -> Dict[str, Any]:
        try:
            return decision_agent.process(state)
        except Exception as e:
            err_msg = f"Decision Node failed: {e}"
            logger.error(err_msg, exc_info=True)
            return {"response": f"Decision Agent Error: {e}", "errors": state.get("errors", []) + [err_msg]}

    def general_chat_node(state: AgentState) -> Dict[str, Any]:
        """Fall-back node that handles general conversation using the central LLM."""
        user_input = state.get("user_input", "")
        logger.info(f"GeneralChatNode invoked for input: '{user_input}'")
        try:
            prompt = ChatPromptTemplate.from_template("""
You are the assistant in a Personal AI OS (a personal second brain).
The Manager agent routed this query to general chat. Provide a direct, helpful, and natural response.

User Input:
{user_input}
""")
            chain = prompt | llm
            res = chain.invoke({"user_input": user_input})
            return {"response": res.content}
        except Exception as e:
            err_msg = f"General Chat Node failed: {e}"
            logger.error(err_msg, exc_info=True)
            return {"response": f"Assistant Error: {e}", "errors": state.get("errors", []) + [err_msg]}

    def aggregator_node(state: AgentState) -> Dict[str, Any]:
        try:
            return manager_agent.aggregate_response(state)
        except Exception as e:
            err_msg = f"Aggregator Node failed: {e}"
            logger.error(err_msg, exc_info=True)
            return {"response": f"Aggregator Error: {e}", "errors": state.get("errors", []) + [err_msg]}

    # Define the StateGraph structure
    workflow = StateGraph(AgentState)

    # Add all processing nodes
    workflow.add_node("manager_agent", manager_node)
    workflow.add_node("knowledge_agent", knowledge_node)
    workflow.add_node("planner_agent", planner_node)
    workflow.add_node("decision_agent", decision_node)
    workflow.add_node("general_chat", general_chat_node)
    workflow.add_node("aggregator", aggregator_node)

    # Establish manager_agent as the main system entry point
    workflow.set_entry_point("manager_agent")

    # Routing logic based on manager classification output
    def route_decision(state: AgentState) -> str:
        intent = state.get("intent", "unknown")
        if intent == "knowledge":
            return "knowledge_agent"
        elif intent == "planner":
            return "planner_agent"
        elif intent == "decision":
            return "decision_agent"
        else:
            return "general_chat"

    # Add the routing conditional edges
    workflow.add_conditional_edges(
        "manager_agent",
        route_decision,
        {
            "knowledge_agent": "knowledge_agent",
            "planner_agent": "planner_agent",
            "decision_agent": "decision_agent",
            "general_chat": "general_chat"
        }
    )

    # Connect all processing nodes to the aggregator
    workflow.add_edge("knowledge_agent", "aggregator")
    workflow.add_edge("planner_agent", "aggregator")
    workflow.add_edge("decision_agent", "aggregator")
    workflow.add_edge("general_chat", "aggregator")

    # End the graph processing after response aggregation
    workflow.add_edge("aggregator", END)

    logger.info("Multi-agent workflow graph compiled successfully.")
    return workflow.compile()
