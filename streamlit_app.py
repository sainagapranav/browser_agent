import streamlit as st
import base64
from app.graph import app as agent_app
from app.tools.browser import browser_instance
import os

st.set_page_config(page_title="AI Browser Agent", page_icon="🤖", layout="wide")

# Configure Logging
import logging
logging.basicConfig(
    filename='agent.log',
    filemode='a',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

st.title("🤖 Autonomous Browser Agent")
st.markdown("Powered by **LangGraph**, **Playwright**, and **OpenRouter**")

# Sidebar for Configuration
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("OpenRouter API Key", type="password")
    headless = st.checkbox("Run Headless", value=False)
    
    if api_key:
        import os
        os.environ["OPENROUTER_API_KEY"] = api_key

# Main Interface
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display Chat History
# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if "logs" in message and message["logs"]:
            with st.status("Execution Log", expanded=False, state="complete"):
                for log in message["logs"]:
                    st.write(log)
        st.markdown(message["content"])
        if "image" in message:
            st.image(base64.b64decode(message["image"]))

# State Management
if "is_running" not in st.session_state:
    st.session_state.is_running = False

# Input - Disabled when agent is running
task = st.chat_input("What should I do on the web?", disabled=st.session_state.is_running)

if task:
    if not os.getenv("OPENROUTER_API_KEY"):
        st.error("Please provide an OpenRouter API Key in the sidebar.")
        st.stop()

    # Add user message
    st.session_state.messages.append({"role": "user", "content": task})
    st.session_state.is_running = True
    st.rerun()

# Agent Execution
if st.session_state.is_running:
    # Get the latest task (last user message)
    # We need to find the last user message to use as the task
    # In this simple flow, it's usually the last message
    current_task = st.session_state.messages[-1]["content"]
    
    with st.chat_message("assistant"):
        status_container = st.status("Agent is working...", expanded=True)
        
        initial_state = {
            "task": current_task,
            "plan": [],
            "current_step_index": 0,
            "retry_count": 0,
            "error": None,
            "logs": []
        }

        collected_logs = []

        try:
            # Run the Graph
            final_state = None
            for event in agent_app.stream(initial_state):
                # Inspect the event to find the current node's output
                current_node = next(iter(event)) # e.g., 'planner', 'executor'
                node_data = event[current_node]
                
                # Update UI with logs immediately
                if "logs" in node_data:
                    for log in node_data["logs"]:
                        status_container.write(log)
                        collected_logs.append(log)
                
                # Check for screenshots (Errors)
                if "screenshot" in node_data and node_data["screenshot"]:
                    status_container.error("Encountered an error. Analyzing visual state...")
                    st.image(base64.b64decode(node_data["screenshot"]), caption="Error State")
                
                # Update final state for next iteration
                final_state = node_data

            # Check final state
            if final_state:
                plan_length = len(final_state.get("plan", []))
                current_step = final_state.get("current_step_index", 0)
                
                if current_step >= plan_length:
                    status_container.update(label="Task Complete!", state="complete", expanded=False)
                    st.success("Workflow Finished.")
                elif final_state.get("error") and final_state.get("retry_count", 0) > 3:
                    status_container.update(label="Task Failed", state="error", expanded=False)
                    st.error("Workflow failed after multiple retries.")
                else:
                    # Still in progress - show current status
                    status_container.update(label=f"Step {current_step} of {plan_length}", state="running")
            
            # Save final message with collected logs
            st.session_state.messages.append({
                "role": "assistant", 
                "content": "Task completed successfully.",
                "logs": collected_logs
            })
            
            # Keep browser open - user can close it manually
            col1, col2 = st.columns([3, 1])
            with col1:
                st.info("🌐 Browser window remains open so you can view the results.")
            with col2:
                if st.button("Close Browser", type="secondary"):
                    browser_instance.close()
                    st.success("Browser closed.")

        except Exception as e:
            st.error(f"System Error: {e}")
            # Persist error to chat history so it's visible after rerun
            st.session_state.messages.append({
                "role": "assistant", 
                "content": f"❌ Task failed: {str(e)}",
                "logs": collected_logs
            })
        
        finally:
            st.session_state.is_running = False
            st.rerun()