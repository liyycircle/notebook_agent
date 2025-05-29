"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""

from datetime import UTC, datetime
import asyncio
from typing import Dict, List, Literal, cast
import uuid

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver

from react_agent.prompts import INTENT_PROMPT, GEN_NOTEBOOK_PROMPT
from react_agent.configuration import Configuration 

from react_agent.state import InputState, MyState
from react_agent.tools import TOOLS, PRETOOLS
from react_agent.utils import load_chat_model

from react_agent.router import route_model_output, human_router, route_gen_output


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
    model = load_chat_model(configuration.model)#.bind_tools(TOOLS)
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

async def gen_notebook(state: MyState) -> Dict[str, List[AIMessage]]:
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
    model = load_chat_model("deepseek/deepseek-coder").bind_tools(PRETOOLS)
    system_message = GEN_NOTEBOOK_PROMPT.format(
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
    print(response)
    return {"messages": [response]}


def ask_human(state: MyState) -> MyState:   
    last_message = state.messages[-1]
    response = interrupt({
        "question": "若同意生成以上内容，请回答「确认」，否则请提供修正描述",
        "llm_output": last_message
    })
    if response.strip() == "确认":
        return {"messages": [AIMessage(content=last_message.content)],
                "exec": True}
    else:
        return {"messages": [AIMessage(content=f"{last_message.content}\n在此基础上修正：{response}")],
                "exec": False}

def approved_node(state: MyState) -> MyState:
    print("✅ Approved path taken.")
    return state

# Define a new graph
builder = StateGraph(MyState, input=InputState, config_schema=Configuration)

# Define the two nodes we will cycle between
builder.add_node(call_model)
builder.add_node("tools", ToolNode(PRETOOLS))
builder.add_node(ask_human)
builder.add_node(human_router)
builder.add_node(gen_notebook)
builder.add_node("gen_tools", ToolNode(TOOLS))

# Set the entrypoint as `call_model`
# This means that this node is the first one called
builder.add_edge("__start__", "call_model")
builder.add_conditional_edges("call_model", route_model_output)
builder.add_edge("tools", "call_model")
builder.add_conditional_edges("ask_human", human_router)
builder.add_edge("gen_tools", "gen_notebook")
builder.add_conditional_edges("gen_notebook", route_gen_output)
builder.add_edge("gen_notebook", "__end__")


# Compile the builder into an executable graph
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer, name="Notebook Agent")
config = {"configurable": {"thread_id": uuid.uuid4()}}

async def get_intent(graph: StateGraph, config: Dict, input_message: str): 
    result = graph.astream({"messages": input_message}, config)
    # result = graph.astream({"messages": input("请输入你的生成需求：")}, config)
    async for i in result:
        print(i)
    
async def main():
    ask_status = True
    await get_intent(graph, config, "你好")
    if ask_status:
        result = await graph.ainvoke(Command(resume=input("请确认提取的意图：")), config=config)
        # result = await graph.ainvoke(Command(resume="确认"), config=config)
        # if result['exec']:
        #     ask_status = False

if __name__ == "__main__":
    asyncio.run(main())

# 生成针对tmall_order_report.csv的数据分析notebook