from langgraph.graph import StateGraph, END
from app.state import AgentState
from app.agents.planner import plan_node
from app.agents.coder import execution_node
from app.agents.healer import repair_node
from app.agents.discovery import discovery_node
from app.agents.monitor import monitor_node

def should_continue(state: AgentState):
    # Check if we have a plan
    plan = state.get("plan", [])
    if not plan or len(plan) == 0:
        return "end"
    
    # Check for errors first
    error = state.get("error")
    if error:
        retry_count = state.get("retry_count", 0)
        if retry_count > 3:
            return "failed"
        return "repair"
    
    # Check if all steps are complete
    current_step_index = state.get("current_step_index", 0)
    if current_step_index >= len(plan):
        return "end"
        
    # Continue to next step
    return "continue"

workflow = StateGraph(AgentState)

workflow.add_node("planner", plan_node)
workflow.add_node("executor", execution_node)
workflow.add_node("repair", repair_node)
workflow.add_node("discovery", discovery_node)
workflow.add_node("monitor", monitor_node)

# Check if plan is valid before execution
def check_plan(state: AgentState):
    plan = state.get("plan", [])
    error = state.get("error")
    
    # If error during planning or empty plan, stop
    if error or not plan:
        return "end"
        
    return "continue"

workflow.set_entry_point("planner")

# Conditional edge from planner
workflow.add_conditional_edges(
    "planner",
    check_plan,
    {
        "continue": "executor",
        "end": END
    }
)

# Route executor -> monitor -> should_continue
workflow.add_edge("executor", "monitor")

workflow.add_conditional_edges(
    "monitor",
    should_continue,
    {
        "continue": "executor",
        "repair": "repair",
        "failed": END,
        "end": END
    }
)

workflow.add_edge("repair", "executor")

app = workflow.compile()