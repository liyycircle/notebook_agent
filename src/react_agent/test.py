"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""

from datetime import UTC, datetime
from typing import Dict, List, Literal, cast, TypedDict

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt

from react_agent.configuration import Configuration
from react_agent.state import InputState, State
from react_agent.tools import TOOLS
from react_agent.utils import load_chat_model
from langgraph.checkpoint.memory import MemorySaver


# Define the function that calls the model

def call_model(state: State) -> Dict[str, List[AIMessage]]:
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

    # Format the system prompt. Customize this to change the agent's behavior.
    system_message = configuration.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    # Get the model's response
    response = cast(
        AIMessage,
        model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response.tool_calls:
        return {
            "llm_output": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }

    # Return the model's response as a list to be added to existing messages
    return {"llm_output": [response]}

def generate_llm_output(state: State) -> State:
    return {"llm_output": "This is the generated output."}

class State(TypedDict):
    decision: str
    llm_output: List[AIMessage]

def get_valid_age(state: State) -> State:
    prompt = "Please enter your age (must be a non-negative integer)."

    while True:
        user_input = interrupt(prompt)

        # Validate the input
        try:
            age = int(user_input)
            if age < 0:
                raise ValueError("Age must be non-negative.")
            break  # Valid input received
        except (ValueError, TypeError):
            prompt = f"'{user_input}' is not valid. Please enter a non-negative integer for age."

    return {"age": age}

def report_age(state: State) -> State:
    print(f"✅ Human is {state['age']} years old.")
    return state

def ask_human(state: State) -> State:   
    last_message = state["llm_output"][-1]
    decision = interrupt({
        "question": "若同意生成以上内容，请回答「确认生成」，否则请提供修正描述",
        "llm_output": last_message
    })
    print(decision,'------------------------')
    return {"decision": decision}

def approved_node(state: State) -> State:
    print("✅ Approved path taken.")
    return state

def human_router(state: State)-> Literal["approved_node", "call_model"]:
    print(state) 
    if True:
        return "approved_node"
    return "call_model"
    
# Define a new graph

builder = StateGraph(State, input=InputState, config_schema=Configuration)

# Define the two nodes we will cycle between
builder.add_node("call_model", call_model)
# builder.add_node("tools", ToolNode(TOOLS))
builder.add_node("ask_human", ask_human)
builder.add_node("approved_node", approved_node)

# Set the entrypoint as `call_model`
# This means that this node is the first one called
builder.add_edge("__start__", "call_model")
builder.add_edge("call_model", "ask_human")
builder.add_conditional_edges(
    "ask_human",
    human_router,
)
builder.add_edge("approved_node", "__end__")


def route_model_output(state: State) -> Literal["__end__", "tools"]:
    """Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls.

    Args:
        state (State): The current state of the conversation.

    Returns:
        str: The name of the next node to call ("__end__" or "tools").
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )
    # If there is no tool call, then we finish
    if not last_message.tool_calls:
        return "__end__"
    # Otherwise we execute the requested actions
    return "tools"


# Add a conditional edge to determine the next step after `call_model`
# builder.add_conditional_edges(
#     "call_model",
#     # After call_model finishes running, the next node(s) are scheduled
#     # based on the output from route_model_output
#     route_model_output,
# )

# Add a normal edge from `tools` to `call_model`
# This creates a cycle: after using tools, we always return to the model
# builder.add_edge("tools", "call_model")


# Compile the builder into an executable graph
graph = builder.compile(name="ReAct Agent")

result = graph.invoke({})
print(result) 