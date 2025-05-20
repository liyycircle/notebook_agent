"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""

from datetime import UTC, datetime
import asyncio
from typing import Dict, List, Literal, cast
import uuid

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver

from react_agent.prompts import INTENT_PROMPT
from react_agent.configuration import Configuration 

from react_agent.state import InputState, MyState
from react_agent.tools import TOOLS
from react_agent.utils import load_chat_model

from react_agent.router import route_model_output, human_router


# Define the function that calls the model

async def call_model(state: MyState) -> Dict[str, List[AIMessage]]:
    """Call the LLM powering our "agent".

    This function prepares the prompt, initializes the model, and processes the response.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_context()

    # Initialize the model with tool binding. Change the model or add more tools here.
    model = load_chat_model(configuration.model).bind_tools(TOOLS)
    system_message = INTENT_PROMPT.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )


    # Get the model's response
    response = cast(
        AIMessage,
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }

    # Return the model's response as a list to be added to existing messages
    return {"messages": [response]}

def ask_human(state: MyState) -> MyState:   
    last_message = state.messages[-1]
    decision = interrupt({
        "question": "若同意生成以上内容，请回答「确认」，否则请提供修正描述",
        "llm_output": last_message
    })
    return {"decision": decision}

def approved_node(state: MyState) -> MyState:
    print("✅ Approved path taken.")
    return state

# Define a new graph
builder = StateGraph(MyState, input=InputState, config_schema=Configuration)

# Define the two nodes we will cycle between
builder.add_node(call_model)
builder.add_node(ask_human)
builder.add_node(approved_node)
builder.add_node(human_router)
# builder.add_node("tools", ToolNode(TOOLS))

# Set the entrypoint as `call_model`
# This means that this node is the first one called
builder.add_edge("__start__", "call_model")
builder.add_edge("call_model", "ask_human")
builder.add_conditional_edges("ask_human",human_router,)
builder.add_edge("approved_node", "__end__")


# Add a conditional edge to determine the next step after `call_model`
# builder.add_conditional_edges("call_model", route_model_output,)

# Add a normal edge from `tools` to `call_model`
# This creates a cycle: after using tools, we always return to the model
# builder.add_edge("tools", "call_model")


# Compile the builder into an executable graph
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer, name="Notebook Agent")
config = {"configurable": {"thread_id": uuid.uuid4()}}

async def get_intent(graph: StateGraph, config: Dict): 
    result = graph.astream({"messages": "请生成一个包含随机数绘制的散点图notebook"}, config)
    # result = graph.astream({"messages": input("请输入你的生成需求：")}, config)
    async for i in result:
        print(i)
    
if __name__ == "__main__":
    while MyState.decision != "确认":
        asyncio.run(get_intent(graph, config))
        result = asyncio.run(graph.ainvoke(Command(resume=input("请确认提取的意图：")), config=config))
        print(result)

# 生成针对tmall_order_report.csv的数据分析notebook