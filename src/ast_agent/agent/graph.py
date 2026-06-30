from typing import TypedDict, Annotated, Sequence
import json
import re
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, render_text_description
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Checkpointer

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

def build_checkpointer() -> InMemorySaver:
    return InMemorySaver()

def create_agent_graph(
    llm: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str,
    checkpointer: Checkpointer | None = None,
):
    tools_by_name = {t.name: t for t in tools}
    tool_descriptions = render_text_description(tools)
    
    full_system_prompt = system_prompt + f"\n\nAvailable Tools:\n{tool_descriptions}"

    def call_model(state: AgentState):
        messages = [{"role": "system", "content": full_system_prompt}] + state["messages"]
        response = llm.invoke(messages)
        return {"messages": [response]}

    def execute_tools(state: AgentState):
        last_message = state["messages"][-1]
        content = last_message.content
        
        # Parse custom tool format: 
        # ```tool
        # tool_name
        # {"arg1": "val1"}
        # ```
        tool_results = []
        matches = re.finditer(r"```tool\s*\n(.*?)\n(.*?)```", content, re.DOTALL)
        
        called_any = False
        for match in matches:
            called_any = True
            tool_name = match.group(1).strip()
            tool_args_str = match.group(2).strip()
            try:
                args = json.loads(tool_args_str)
                tool = tools_by_name.get(tool_name)
                if tool:
                    result = tool.invoke(args)
                    tool_results.append(HumanMessage(content=f"Tool {tool_name} returned:\n{result}"))
                else:
                    tool_results.append(HumanMessage(content=f"Error: Tool {tool_name} not found."))
            except Exception as e:
                tool_results.append(HumanMessage(content=f"Error parsing args or executing {tool_name}: {e}"))
                
        if not called_any:
            # Maybe the model just output raw JSON without codeblocks
            pass
            
        return {"messages": tool_results}

    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if "```tool" in last_message.content:
            return "tools"
        return "end"

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", execute_tools)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    workflow.add_edge("tools", "agent")
    
    return workflow.compile(checkpointer=checkpointer)
