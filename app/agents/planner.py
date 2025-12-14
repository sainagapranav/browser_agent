from app.config import get_llm
from app.state import AgentState

def plan_node(state: AgentState):
    llm = get_llm()
    task = state['task']
    
    prompt = f"""
    You are a QA Automation Lead.
    Task: {task}
    
    Break this task into simple, sequential Playwright steps.
    Return the steps as PLAIN TEXT, ONE STEP PER LINE. 
    Do not use markdown blocks. Do not use bullets. Do not wrap in brackets [].
    
    IMPORTANT GUIDELINES:
    1. For page.goto() steps, ALWAYS use wait_until='domcontentloaded':
       - page.goto('url', wait_until='domcontentloaded')
    
    2. HANDLING NEW TABS (Critical for Amazon/E-commerce):
       - If an action (like clicking a product) opens a new tab, add "browser_manager.switch_to_new_tab()" step immediately after.
    
    3. SEARCHING:
       - Prefer clicking search buttons over pressing Enter.
    
    Example Output: 
    page.goto('https://amazon.in', wait_until='domcontentloaded')
    page.fill('#twotabsearchtextbox', 'blue tshirt')
    page.click('input[type="submit"]')
    browser_manager.switch_to_new_tab()
    """
    
    response = llm.invoke(prompt)
    
    content = response.content.strip()
    
    # Simple line-based parsing
    # Remove markdown code blocks if present
    content = content.replace("```python", "").replace("```text", "").replace("```", "").strip()
    
    # Split by newlines and filter empty lines
    plan = [line.strip() for line in content.split('\n') if line.strip()]
    
    # Remove any leading "- " or "* " or "1. " if LLM ignored instructions
    import re
    cleaned_plan = []
    for step in plan:
        # Remove common list markers
        step = re.sub(r'^[\d]+\.\s*', '', step)
        step = re.sub(r'^[\-\*]\s*', '', step)
        # Remove quotes if the LLM wrapped the whole line in quotes
        if (step.startswith('"') and step.endswith('"')) or (step.startswith("'") and step.endswith("'")):
            step = step[1:-1]
        
        # Verify it looks like code (starts with page. or browser_manager.)
        # This is a loose check to filter out conversational text
        if step.startswith("page.") or step.startswith("browser_manager.") or step.startswith("await"):
            cleaned_plan.append(step)
            
    if not cleaned_plan:
         return {
            "plan": [],
            "current_step_index": 0,
            "retry_count": 0,
            "error": f"Failed to parse plan. No valid steps found in content: {content[:100]}...",
            "logs": [f"❌ Plan parsing failed: No valid steps found."]
        }
            
    return {
        "plan": cleaned_plan, 
        "current_step_index": 0, 
        "retry_count": 0,
        "logs": [f"📅 Plan created with {len(cleaned_plan)} steps."]
    }