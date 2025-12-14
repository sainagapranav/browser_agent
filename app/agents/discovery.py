from app.config import get_llm
from app.state import AgentState
from app.tools.browser import browser_instance
from langchain_core.messages import HumanMessage

def discovery_node(state: AgentState):
    """
    Discovery Agent: Crawls a URL and identifies potential user flows.
    """
    llm = get_llm()
    task = state.get('task')
    
    # Extract URL from task if present (simple heuristic)
    import re
    url_match = re.search(r'https?://[^\s]+', task)
    if not url_match:
        return {
            "logs": ["⚠️ No URL found in task for discovery. Skipping."]
        }
    
    url = url_match.group(0)
    
    # 1. Navigate to the page
    browser_instance.start(headless=False)
    page = browser_instance.get_page()
    
    try:
        page.goto(url, wait_until='domcontentloaded')
        page.wait_for_timeout(2000) # Wait for UI to settle
        
        # 2. Capture Screenshot for Vision Analysis
        import base64
        screenshot_bytes = page.screenshot(type='png')
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        
        # 3. Get page text/content (simplified)
        page_title = page.title()
        
        # 4. Ask LLM to identify flows
        prompt_text = f"""
        You are a Test Architect. You are looking at the website: {url} (Title: {page_title}).
        
        Based on the screenshot of the page, identify 3-5 critical user flows that should be tested.
        Examples of flows: "Login with valid credentials", "Search for a product", "Add item to cart", "Navigate to About Us".
        
        Return ONLY a Python list of strings describing these flows.
        """
        
        message_content = [
            {"type": "text", "text": prompt_text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}
            }
        ]
        
        response = llm.invoke([HumanMessage(content=message_content)])
        
        # Parse flows
        try:
            suggested_flows = eval(response.content.replace("```python", "").replace("```", "").strip())
        except:
            suggested_flows = ["Could not parse flows"]

        return {
            "logs": [f"🔍 Discovery complete. Found flows: {suggested_flows}"],
            # In a real app, we might store these in state or present to user
            # For now, we just log them.
        }
        
    except Exception as e:
        return {
            "logs": [f"❌ Discovery failed: {str(e)}"]
        }
