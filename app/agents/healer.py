from app.config import get_llm
from app.state import AgentState

from langchain_core.messages import HumanMessage

def repair_node(state: AgentState):
    llm = get_llm()
    
    # Prepare the prompt text
    prompt_text = f"""
    Fix this Playwright script. The script failed with an error.
    
    Error: {state['error']}
    
    Broken Script:
    {state['current_script']}
    
    IMPORTANT: If the error mentions "page.evaluate" or JavaScript errors:
    - The error is in JavaScript code inside page.evaluate()
    - Add null checks: Use optional chaining (?.) and nullish coalescing (??)
    - Filter out null values before accessing properties
    - Example: item.querySelector('h2 a')?.href ?? null
    - Filter results: .map(...).filter(link => link !== null)
    
    For other errors, try these fixes in order:
    
    1. For strict mode violations (multiple elements found):
       - Use .first or .last to select specific element: page.locator('selector').first
       - Or use more specific selectors to narrow down: page.locator('div[role="dialog"]').get_by_text('Accept')
       - Or use nth=0 for first element: page.locator('selector').nth(0)
       - For dialogs, try: page.locator('button:has-text("Accept")').first.click() or page.locator('button:has-text("I agree")').first.click()
    
    2. For JavaScript evaluation errors in page.evaluate():
       - Add null safety: Use optional chaining (?.) and nullish coalescing (??)
       - Check if element exists before accessing properties
       - Example fix: item.querySelector('h2 a')?.href ?? null
       - Filter out nulls: .map(...).filter(link => link !== null)
       - Add try-catch in JavaScript if needed
       - Verify selectors exist: if (item.querySelector('selector')) before accessing
    
    3. For Google search box (if placeholder not found):
       - Google search: Use page.locator('textarea[name="q"]')  (most reliable)
       - Or: page.locator('input[name="q"]') as fallback
       - Or: page.locator('[name="q"]')  (works for both input and textarea)
       - DO NOT use get_by_placeholder if it's timing out - use name attribute instead
       - Always wait for it: page.wait_for_selector('textarea[name="q"]', state='visible')
    
    4. Handle dialogs/modals properly:
       - Wait for page load first: page.wait_for_load_state('domcontentloaded')
       - Then try to dismiss dialogs using specific text: page.locator('button:has-text("Accept all")').first.click(timeout=5000) with try/except
       - Or skip dialog handling if not critical - just wait for main content
    
    5. Wait for page to fully load after navigation:
       - After page.goto(), add: page.wait_for_load_state('domcontentloaded')
       - Wait for specific elements: page.wait_for_selector('textarea[name="q"]', state='visible', timeout=30000)
    
    5a. For navigation timeout errors (page.goto() timing out) - OPTIMIZE FOR SPEED:
       - FASTEST: Use wait_until='commit' - just waits for navigation to start: page.goto(url, wait_until='commit', timeout=30000)
       - FAST: Use wait_until='domcontentloaded' - waits for DOM ready: page.goto(url, wait_until='domcontentloaded', timeout=30000)
       - NEVER use wait_until='load' or 'networkidle' - these wait for all resources and are 3-5x slower
       - After commit/domcontentloaded, wait for specific elements: page.wait_for_selector('main-selector', timeout=30000)
       - This approach works for ALL websites (not just specific types) and is much faster
       - If timeout still occurs, check network connectivity or use timeout=60000
    
    6. Use more robust locators:
       - For forms: use name attribute: page.locator('[name="fieldname"]')
       - For buttons: use text content: page.locator('button:has-text("Submit")')
       - Avoid generic role selectors when multiple exist - be more specific
    
    7. If selector with attribute doesn't work (especially for Amazon/e-commerce):
       - Check if attribute value is numeric vs string: data-review-rating="4" vs data-review-rating=4
       - Try without quotes for numeric values: [data-review-rating=4] instead of [data-review-rating="4"]
       - Try partial matching: [data-review-rating*="4"]
       - For Amazon ratings, the attribute might be on a different element - try parent containers
       - Alternative: Find product containers first, then filter by rating text: page.locator('[data-asin]').filter(has=page.locator('.a-icon-alt:has-text("4")'))
       - Try clicking the product link/container instead of the rating span
       - Use text-based search: page.locator('span:has-text("4")').first
       - Check if element exists before clicking: use try/except or check count first
       - Consider the rating might be displayed as stars - use different selector like '.a-icon-star' or similar
       - Use page.locator('[data-asin]').first.click() to click first product if rating selector fails
    
    7a. CRITICAL: Avoid clicking advertisements/sponsored content (for all e-commerce sites):
       - NEVER click on elements with "Sponsored", "Ad", "Advertisement" text
       - Filter out sponsored items: page.locator('.product-item').filter(has_not=page.locator('text=/Sponsored|Ad|Advertisement/i'))
       - Common patterns:
         * Filter by text: .filter(has_not=page.locator('text=Sponsored'))
         * Filter by attributes: .filter(has_not=page.locator('[class*="sponsored"]'))
         * Filter by data attributes: .filter(has_not=page.locator('[data-type*="sponsor"]'))
       - Skip ad containers: Filter elements that don't have sponsored/ads classes or attributes
       - ALWAYS filter out sponsored/ad elements before clicking product items
       - Example: page.locator('.product').filter(has_not=page.locator('text=Sponsored')).first.click()
    
    8. For CSS pseudo-selector errors (like :first-of-type, :nth-child):
       - Playwright does NOT support CSS pseudo-selectors in selectors
       - Instead of: '.class:first-of-type' use: page.locator('.class').first
       - Instead of: '.class:nth-child(1)' use: page.locator('.class').nth(0)
       - Use Playwright's locator methods: .first, .last, .nth(index) instead of CSS pseudo-selectors
    
    9. For "unterminated string literal" errors:
       - Check quote usage: If outer string uses single quotes, escape inner single quotes: 'text with \\'quotes\\''
       - Or use double quotes for outer string: "text with 'quotes'"
       - For strings with quotes, prefer: page.fill('#id', "text") or page.fill('#id', 'text')
       - Avoid mixing quote types incorrectly
    
    10. After pressing Enter or submitting forms, wait for navigation (FAST):
       - FAST: page.wait_for_load_state('domcontentloaded') - waits for DOM ready (much faster)
       - Or wait for specific element: page.wait_for_selector('expected-element', timeout=30000)
       - Avoid 'networkidle' - it's too slow and often unnecessary
       - This works for all websites and is faster
    
    11. CRITICAL: For clicking products on search results (BEFORE going to product page):
       - NEVER use CSS pseudo-selectors like :first-of-type, :nth-child() - Playwright doesn't support them
       - ALWAYS filter out sponsored/ads before clicking: page.locator('.s-result-item').filter(has_not=page.locator('text=Sponsored')).first.click()
       - Or: page.locator('[data-asin]:not([data-component-type*="sp-"])').first.click() (excludes sponsored)
       - Use .first or .nth(0) instead of CSS pseudo-selectors
       - After clicking product, wait for navigation: page.wait_for_load_state('domcontentloaded')
    
    12. CRITICAL: For e-commerce product pages (universal - works on ALL shopping sites):
       - After clicking a product from search results, wait for product page to load (FAST): page.wait_for_load_state('domcontentloaded')
       - Wait for product details to appear (universal): page.wait_for_selector('h1, [class*="product"], [class*="title"], [id*="productTitle"]', timeout=30000)
       - Product variations MUST be selected first if available (Size, Color, Style, etc.) - UNIVERSAL PATTERNS:
         * Try selecting size: try: page.locator('select[name*="size"], select[name*="Size"], [data-action*="size"]').first.select_option(index=1, timeout=5000) except: pass
         * Try clicking size button: try: page.locator('[name*="size"], [data-action*="size"], [class*="size"] button').first.click(timeout=5000) except: pass
         * Try selecting color: try: page.locator('[name*="color"], [data-action*="color"], [class*="color"] button, [aria-label*="Color"]').first.click(timeout=5000) except: pass
         * Wait a moment after selecting variations: page.wait_for_timeout(1000) or page.wait_for_load_state('domcontentloaded')
       - Then find add-to-cart button using UNIVERSAL generic selectors (works on Amazon, eBay, Walmart, Target, Etsy, etc.):
         * Try multiple selectors in order until one works:
           - page.locator('#add-to-cart-button, #addToCart, #add-to-cart, [name*="add-to-cart"]').first.wait_for(timeout=30000)
           - Or: page.locator('[name*="submit"], [id*="addToCart"]').first.wait_for(timeout=30000)
           - Or: page.locator('button:has-text("Add to Cart"), button:has-text("Add to Bag"), input[value*="Add"]').first.wait_for(timeout=30000)
           - Or: page.locator('[class*="add-to-cart"], [class*="addToCart"]').first.wait_for(timeout=30000)
       - Use try/except to try each selector until one works
       - This approach works for ALL e-commerce sites, not just specific ones
    
    IMPORTANT FIXES FOR COMMON ERRORS:
    - If JavaScript error in page.evaluate(): Add null checks with ?. and filter nulls
    - If strict mode violation with dialogs: Use .first or more specific selectors
    - If placeholder timeout: Use name attribute instead: page.locator('textarea[name="q"]')
    - If selector timeout (element not found): Try alternative selectors, check attribute format, use text-based locators
    - If page.goto() timeout: Use wait_until='domcontentloaded' or 'commit' instead of default 'load'
    - Always wait for elements before interacting: page.wait_for_selector('textarea[name="q"]', state='visible')
    - If element timeout after clicking a link/button: The action might have opened a NEW TAB
      -> ADD: browser_manager.switch_to_new_tab() after the click
      -> This switches context to the new tab where the element actually exists
    - If "Text not found" but you see it in screenshot: IT IS LIKELY AN IMAGE/LOGO
      -> Do NOT use `text=...` selector.
      -> Use `img[alt*="Text"]` or `[aria-label*="Text"]`.
      -> Example: page.locator('img[alt*="Bhagavad"]').first.click()
    
    - CRITICAL: For XPath image selectors that timeout (like //img[contains(@alt, "text")]):
      -> XPath selectors in Playwright: Use page.locator('xpath=//img[@alt]') or just convert to CSS
      -> BETTER: Use CSS attribute selector: page.locator('img[alt*="text"]') instead of XPath
      -> For case-insensitive matching, use partial match with lowercase: page.locator('img[alt*="blue"]')
      -> OR use Playwright's get_by_alt_text: page.get_by_alt_text("text", exact=False).first
      -> CRITICAL: On Amazon/e-commerce, DON'T click images directly - click the product link/container
      -> Instead: page.locator('.s-result-item').filter(has=page.locator('img[alt*="blue"]')).first.click()
      -> ALWAYS filter out sponsored: .filter(has_not=page.locator('text=Sponsored')) before clicking
      -> For product images, click the parent container/a tag, not the img: page.locator('a[href*="/dp/"]').first.click()
    
    For the specific error about "Cannot read properties of null":
    - Change: item.querySelector('h2 a').href
    - To: item.querySelector('h2 a')?.href ?? null
    - Then filter: .map(...).filter(link => link !== null)
    
    For attribute selector timeouts (like data-review-rating):
    - Try numeric without quotes: [data-review-rating=4] instead of [data-review-rating="4"]
    - Try finding parent container first, then filtering children
    - Use text-based search as fallback
    - Check if element exists before interacting
    - Consider that the attribute might not be present - use optional selectors or try/except
    
    For "unterminated string literal" syntax errors:
    - Fix quote escaping in string literals
    - Use double quotes for outer string if inner has single quotes: "text with 'quotes'"
    - Or escape properly: 'text with \\'quotes\\''
    
    For CSS pseudo-selector errors (:first-of-type, :nth-child):
    - Replace with Playwright methods: page.locator('.class').first
    - Never use CSS pseudo-selectors in Playwright locators
    
    For page.goto() timeout errors - SPEED OPTIMIZATION:
    - Change: page.goto(url) or page.goto(url, wait_until='load')
    - To: page.goto(url, wait_until='commit', timeout=30000) - FASTEST (just navigation commit)
    - Or: page.goto(url, wait_until='domcontentloaded', timeout=30000) - FAST (DOM ready)
    - Then wait for specific elements: page.wait_for_selector('main-selector', timeout=30000)
    - NEVER use 'load' or 'networkidle' - they wait for all resources and are 3-5x slower
    - 'commit' and 'domcontentloaded' work for ALL websites, not just specific types
    - This makes navigation much faster while still being reliable
    
    CRITICAL: For clicking product items (especially Amazon):
    - ALWAYS filter out sponsored/ads before clicking
    - Use: page.locator('.s-result-item').filter(has_not=page.locator('text=Sponsored')).first
    - Or: page.locator('[data-asin]:not([data-component-type*="sp-"])').first
    - Never click items with "Sponsored" text or sponsored data attributes
    - This ensures you click actual products, not advertisements
    
    CRITICAL: For e-commerce product pages (add-to-cart button not found):
    - FIRST: Wait for product page to load (FAST): page.wait_for_load_state('domcontentloaded') after clicking product
    - Wait for product title/details: page.wait_for_selector('h1, [id*="productTitle"], [class*="product-title"]', timeout=30000)
    - SELECT PRODUCT VARIATIONS FIRST (Size, Color, Style) if options are available - this is REQUIRED on many sites:
      * Try size select: try: page.locator('select[name*="size"]').first.select_option(index=1, timeout=3000) except: pass
      * Try size button: try: page.locator('[data-action*="size"], [class*="size"] button, [aria-label*="Size"]').first.click(timeout=3000) except: pass
      * Try color button: try: page.locator('[data-action*="color"], [aria-label*="Color"]').first.click(timeout=3000) except: pass
      * Wait after variations: page.wait_for_timeout(1000) or page.wait_for_load_state('domcontentloaded')
    - Then find add-to-cart button: Try multiple selector strategies in order until one works:
      * Try: page.locator('#add-to-cart-button, #addToCart, [name*="add-to-cart"]').first.wait_for(timeout=30000)
      * Or: page.locator('[name*="submit"], [id*="addToCart"]').first.wait_for(timeout=30000)
      * Or: page.locator('button:has-text("Add to Cart"), button:has-text("Add to Bag"), input[value*="Add"]').first.wait_for(timeout=30000)
      * Or: page.locator('[class*="add-to-cart"], [class*="addToCart"]').first.wait_for(timeout=30000)
    - Use try/except to try each selector if previous fails
    - If still not found, the product might require size/color selection that wasn't detected - check page for variation options
    
    Return ONLY the fixed python code. Do not include imports or explanations. Do NOT wrap the code in ```python or ```.
    """
    
    # Construct message contents
    message_content = []
    
    # Add text prompt
    message_content.append({"type": "text", "text": prompt_text})
    
    # Add screenshot if available
    if state.get('screenshot'):
        import base64
        import io
        from PIL import Image
        
        try:
            # Decode base64
            img_data = base64.b64decode(state['screenshot'])
            img = Image.open(io.BytesIO(img_data))
            
            # Resize max dimension to 1024 to save tokens
            max_dim = 1024
            if img.width > max_dim or img.height > max_dim:
                img.thumbnail((max_dim, max_dim))
                
            # Convert to RGB (if RGBA) and save as JPEG to reduce size
            if img.mode == 'RGBA':
                img = img.convert('RGB')
                
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=70) # Compress
            img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            message_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_str}"
                }
            })
            log_msg = f"🩹 Applying fix attempt #{state['retry_count']} (with vision)..."
        except Exception as e:
            # Fallback if image processing fails
            log_msg = f"🩹 Applying fix attempt #{state['retry_count']} (Vision failed: {str(e)})..."
            message_content.append({"type": "text", "text": "Screenshot unavailable."})
    else:
        log_msg = f"🩹 Applying fix attempt #{state['retry_count']}..."
    
    # Create the message
    messages = [HumanMessage(content=message_content)]
    
    response = llm.invoke(messages)
    fixed_script = response.content.replace("```python", "").replace("```", "").strip()
    
    return {
        "current_script": fixed_script,
        "logs": [log_msg]
    }