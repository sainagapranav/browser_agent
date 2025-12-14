
import sys
import os
import io
import contextlib

# Add parent dir to path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.graph import app as agent_app

def test_saucedemo_login():
    """
    Test the agent's ability to login to a standard test site.
    """
    print("🧪 Starting Test: Login to SauceDemo...")
    
    task = "Go to https://www.saucedemo.com, login with username 'standard_user' and password 'secret_sauce', and verify I am on the inventory page."
    
    initial_state = {
        "task": task,
        "plan": [],
        "current_step_index": 0,
        "retry_count": 0,
        "error": None,
        "logs": []
    }
    
    # Run the graph
    print("⚙️ Running Agent Graph...")
    final_state = None
    
    # We don't want to spam stdout with browser logs during test
    try:
        for event in agent_app.stream(initial_state):
             # Just iterate to completion
             for node, data in event.items():
                 final_state = data
                 if "logs" in data:
                     for log in data["logs"]:
                         print(f"  [Agent]: {log}")
                         
    except Exception as e:
        print(f"❌ Test Failed with Exception: {e}")
        return False
        
    # Verify results
    if final_state and not final_state.get("error"):
        print("✅ Test Passed: Agent completed task without error.")
        return True
    else:
        print(f"❌ Test Failed: Agent finished with error: {final_state.get('error') if final_state else 'Unknown'}")
        return False


if __name__ == "__main__":
    from app.tools.browser import browser_instance
    try:
        success = test_saucedemo_login()
        print("\n🌐 Browser is still open. Press Enter to close it and exit.")
        input()
    finally:
        print("Closing browser...")
        browser_instance.close()
        
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
