from app.config import get_llm
from app.state import AgentState
from app.tools.browser import browser_instance

def execution_node(state: AgentState):
    llm = get_llm()
    step_idx = state["current_step_index"]
    current_step_desc = state["plan"][step_idx]
    
    logs = []
    
    # Determine script to run (either cached or new)
    if state.get("current_script") and not state.get("error"):
        script = state["current_script"]
    else:
        prompt = f"""
        Write Python Playwright code for this step: "{current_step_desc}".
        Assume 'page' variable exists and browser is already running.
        Assume 'browser_manager' variable exists in scope (use for switching tabs).
        You can use 'await' with page methods (e.g., await page.goto(url)) or call them directly (e.g., page.goto(url)).
        
        Important guidelines:
        1. For page.goto(): ALWAYS use wait_until='domcontentloaded' or 'commit' for SPEED:
           - FASTEST: page.goto(url, wait_until='commit', timeout=30000) - just wait for navigation commit
           - FAST: page.goto(url, wait_until='domcontentloaded', timeout=30000) - wait for DOM ready
           - NEVER use wait_until='load' or 'networkidle' - these are too slow
           - After commit/domcontentloaded, wait for specific elements if needed
           - This makes navigation 3-5x faster on most websites
        2. After page.goto(), wait for page load: page.wait_for_load_state('domcontentloaded') first, then wait for elements
        2a. For form inputs (universal across all sites), prefer name attribute: page.locator('[name="fieldname"]') - this is most reliable across ALL websites
        2b. For search boxes (universal): Try page.locator('[name*="search"], [name*="q"]') or page.locator('input[type="search"], textarea[name*="q"]') - works on Google, Amazon, eBay, etc.
        3. Before filling or clicking, wait for element: page.wait_for_selector('selector', state='visible', timeout=30000)
        4. For search forms (universal): Use page.locator('[name*="search"], [name*="q"], [type="search"]') - works on most sites
        5. Handle dialogs carefully: Use .first for multiple matches: page.locator('button:has-text("Accept")').first.click() with try/except if dialog exists
        6. After pressing Enter or submitting forms, wait for navigation: 
           - Use page.wait_for_load_state('domcontentloaded') for speed (faster than networkidle)
           - Or wait for specific elements: page.wait_for_selector('expected-element', timeout=30000)
           - Avoid 'networkidle' - it's slow and often unnecessary
        7. For page.evaluate() JavaScript code: ALWAYS use null safety:
           - Use optional chaining: element?.property
           - Use nullish coalescing: value ?? defaultValue
           - Filter out nulls: .filter(item => item !== null)
           - Example: item.querySelector('h2 a')?.href ?? null
        8. For attribute selectors that timeout:
           - Try numeric attributes without quotes: [data-rating=4] instead of [data-rating="4"]
           - Check if element exists first: if page.locator('selector').count() > 0
           - Use alternative selectors or text-based locators as fallback
           - Consider that attributes might not exist - handle gracefully
        8a. CRITICAL: Always filter out advertisements/sponsored content:
           - For Amazon/e-commerce: NEVER click sponsored items or ads
           - Filter out sponsored: page.locator('.s-result-item').filter(has_not=page.locator('text=Sponsored')).first
           - Or use: page.locator('[data-asin]:not([data-component-type*="sp-"])').first (excludes sponsored)
           - Check for ad indicators: text=Sponsored, Ad, Advertisement, or data-component-type contains "sp-"
           - Always filter before clicking product items to avoid clicking ads
           - Example for first non-sponsored product: page.locator('.s-result-item').filter(has_not=page.locator('text=Sponsored')).first.click()
        8b. CRITICAL: For e-commerce product pages (universal - works on ALL shopping sites):
           - After clicking a product, wait for product page (FAST): page.wait_for_load_state('domcontentloaded')
           - Wait for product details (universal): page.wait_for_selector('h1, [class*="product"], [class*="title"], [class*="name"]', timeout=30000)
           - SELECT PRODUCT VARIATIONS FIRST if available (universal patterns):
             * Size: page.locator('[name*="size"], [name*="Size"], [data-attribute*="size"], [class*="size"]').first.click(timeout=5000) if exists
             * Color: page.locator('[name*="color"], [name*="Color"], [data-attribute*="color"], [class*="color"]').first.click(timeout=5000) if exists
             * Style/Variant: page.locator('[name*="variant"], [name*="style"], [data-attribute*="variant"]').first.click(timeout=5000) if exists
             * Use try/except for each variation - they may not exist on all sites
           - Then find add-to-cart button using UNIVERSAL generic selectors (works on Amazon, eBay, Walmart, Target, Etsy, etc.):
             * By ID: page.locator('#add-to-cart, #addToCart, #add-to-cart-button, #addToCartButton')
             * By name: page.locator('[name*="add"], [name*="cart"], [name*="add-to-cart"]')
             * By text: page.locator('button:has-text("Add to Cart"), button:has-text("Add to Bag"), button:has-text("Add"), button:has-text("Buy Now")')
             * By class: page.locator('[class*="add-to-cart"], [class*="addToCart"], [class*="add-cart"], [class*="cart-button"]')
             * Try multiple selectors in order until one works - this works on ALL e-commerce sites
        9. CRITICAL: Handle new tabs/windows (common on Amazon/e-commerce):
           - If an action (like clicking a product) opens a new tab, you MUST switch to it:
           - Use: browser_manager.switch_to_new_tab() immediately after the click
           - Example: 
             page.click('.product-link')
             browser_manager.switch_to_new_tab()
        10. Do NOT add imports. Do NOT add page.goto unless specified in the step.
        11. For strict mode violations (multiple elements): Use .first, .last, or .nth(0) to select specific element
        12. CRITICAL: For Image-Based Links (Books, Product Covers, Icons):
            - Text selectors (`text=...`) FAIL if the text is inside an image (like book covers on Vedabase).
            - Use `alt` text: `page.locator('img[alt*="Bhagavad"]').first.click()`
            - Use `aria-label`: `page.locator('[aria-label*="Bhagavad"]').first.click()`
            - CRITICAL: Attributes are CASE-SENSITIVE! "blue" != "Blue".
            - To match text case-insensitively, use Regex:
              `page.locator('img').filter(has_text=re.compile(r'blue tshirt', re.IGNORECASE)).first.click()`
              OR use simple CSS with widely wildcard: `page.locator('img[alt*="lue"]').first.click()`
            - Or use Playwright's text locator which is easier:
              `page.get_by_alt_text(re.compile(r"blue tshirt", re.IGNORECASE)).first.click()`
            - If the text looks stylized or like a logo, it's likely an image. Do not rely on `text=` selector.
        13. For CSS pseudo-selectors: Playwright does NOT support CSS pseudo-selectors like :first-of-type, :nth-child()
           - Instead use: page.locator('.class').first (for first element)
           - Or: page.locator('.class').nth(0) (for nth element)
           - NEVER use: .class:first-of-type or .class:nth-child(1) in Playwright
        14. If element not found, try alternative strategies before giving up
        15. When using quotes in strings: Use double quotes for outer string, single quotes inside, or escape properly
           - Example: page.fill('#id', "text with 'quotes'") or page.fill('#id', 'text with \\'quotes\\'')
        
        Return ONLY the code, no explanations. 
        IMPORTANT: If you use 're' (regex), you MUST import it at the top of your snippet: "import re"
        """
        response = llm.invoke(prompt)
        script = response.content.replace("```python", "").replace("```", "").strip()
    
    logs.append(f"⚙️ Executing Step {step_idx + 1}: {current_step_desc}")

    # Run Browser
    try:
        browser_instance.start(headless=False) # Visible browser for demo
        result = browser_instance.execute_script(script)
        
        if result["status"] == "success":
            new_step_index = step_idx + 1
            logs.append("✅ Success")
            
            return {
                "current_script": None,
                "error": None,
                "current_step_index": new_step_index,
                "retry_count": 0,
                "logs": logs
            }
        else:
            logs.append(f"❌ Error: {result['error']}")
            return {
                "current_script": script,
                "error": result["error"],
                "screenshot": result.get("screenshot"),
                "retry_count": state.get("retry_count", 0) + 1,
                "logs": logs
            }
    except Exception as e:
        logs.append(f"❌ Execution Exception: {str(e)}")
        return {
            "current_script": script,
            "error": str(e),
            "retry_count": state.get("retry_count", 0) + 1,
            "logs": logs
        }