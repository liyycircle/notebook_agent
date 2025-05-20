from langchain_core.messages import AIMessage
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt

from typing import Literal
from react_agent.state import InputState, MyState


def route_model_output(state: MyState) -> Literal["__end__", "tools"]:
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

def human_router(state: MyState)-> Literal["approved_node", "call_model"]:
    if state.decision == "确认":
        return "approved_node"
    return "call_model"