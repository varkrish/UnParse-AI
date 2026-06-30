"""
agent.py — LangGraph AST Agent entrypoint.

Uses the adapted frappe-ai-agent scaffold to orchestrate a tool-calling LLM 
that populates the Kùzu AST graph directly via Python tool functions.
"""

from __future__ import annotations

import kuzu
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

from src.ast_agent.config import Settings
from src.ast_agent.integrations.llm import create_llm
from src.ast_agent.agent.graph import create_agent_graph, build_checkpointer
from src.ast_agent.agent.prompts import build_system_prompt
from src.ast_agent.tools import ast_tools

def run_agent(
    conn: kuzu.Connection,
    user_prompt: str,
    module_id: str = "mod_main",
) -> str:
    """
    Run the LangGraph agent to process a user prompt and populate the DB.
    Returns the module_id.
    """
    # Provide the database connection to our tools
    ast_tools.set_connection(conn)
    
    # Initialize from scaffold config
    settings = Settings()
    llm = create_llm(settings)
    
    # Wrap our python functions into LangChain tools
    lc_tools = [tool(f) for f in ast_tools.get_tool_functions()]
    
    checkpointer = build_checkpointer()
    system_prompt = build_system_prompt()
    
    graph = create_agent_graph(
        llm=llm,
        tools=lc_tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer
    )
    
    config = {"configurable": {"thread_id": module_id}}
    prompt_with_context = f"=== TASK ===\nModule id to use as root: '{module_id}'\n\n{user_prompt}"
    
    print(f"🤖 Calling LangGraph Agent (Model: {settings.llm_model})...")
    
    for event in graph.stream({"messages": [HumanMessage(content=prompt_with_context)]}, config):
        for node_name, node_data in event.items():
            if node_name == "agent":
                msg = node_data["messages"][-1]
                print(f"  💬 Agent response:\n{msg.content}")
            elif node_name == "tools":
                for msg in node_data["messages"]:
                    print(f"  ✅ Tool execution result: {msg.content}")
            
    print(f"\n✅ Finished processing module: {module_id}")
    return module_id
