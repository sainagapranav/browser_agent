from playwright.async_api import async_playwright
import base64
import asyncio
import threading
import sys

class SyncPlaywrightWrapper:
    """Wrapper that makes async Playwright objects and methods appear synchronous"""
    def __init__(self, obj, run_async_func):
        self._obj = obj
        self._run_async = run_async_func

    def __getattr__(self, name):
        """Dynamically wrap attributes and methods"""
        attr = getattr(self._obj, name)
        
        if callable(attr):
            def wrapper(*args, **kwargs):
                # Unwrap arguments that might be wrappers
                args_real = [self._unwrap_arg(arg) for arg in args]
                kwargs_real = {k: self._unwrap_arg(v) for k, v in kwargs.items()}
                
                if asyncio.iscoroutinefunction(attr):
                    result = self._run_async(attr(*args_real, **kwargs_real))
                else:
                    result = attr(*args_real, **kwargs_real)
                return self._wrap(result)
            return wrapper
            
        return self._wrap(attr)

    def _unwrap_arg(self, arg):
        """Unwrap an argument if it's a SyncPlaywrightWrapper"""
        if isinstance(arg, SyncPlaywrightWrapper):
            # Recursively unwrap if it's nested (just in case)
            return arg._obj
        if isinstance(arg, list):
            return [self._unwrap_arg(item) for item in arg]
        if isinstance(arg, dict):
            return {k: self._unwrap_arg(v) for k, v in arg.items()}
        return arg

    def _wrap(self, result):
        """Recursively wrap results if they are Playwright objects"""
        if isinstance(result, (str, int, float, bool, type(None))):
            return result
        if isinstance(result, list):
            return [self._wrap(item) for item in result]
        if isinstance(result, dict):
            return {k: self._wrap(v) for k, v in result.items()}
            
        # Check if it's a Playwright object that needs wrapping
        # We check by name to avoid importing everything
        type_name = type(result).__name__
        target_types = [
            'Page', 'Locator', 'Frame', 'BrowserContext', 
            'ElementHandle', 'JSHandle', 'Response', 'Route', 
            'Request', 'FrameLocator', 'ConsoleMessage', 'Dialog'
        ]
        
        if type_name in target_types:
            return SyncPlaywrightWrapper(result, self._run_async)
            
        return result

class BrowserManager:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._async_page = None
        self.page = None
        self._loop = None
        self._loop_thread = None

    def _get_or_create_loop(self):
        """Get or create an event loop in a separate thread for async Playwright"""
        if self._loop is None or self._loop.is_closed():
            loop_ready = threading.Event()
            loop_ref = [None]
            
            def _run_loop():
                """Run event loop in thread with correct policy for Windows"""
                # On Windows, we need ProactorEventLoop to support subprocess creation
                # This is required for Playwright to work on Windows with Python 3.13+
                if sys.platform == 'win32':
                    policy = asyncio.WindowsProactorEventLoopPolicy()
                    asyncio.set_event_loop_policy(policy)
                    loop = policy.new_event_loop()
                else:
                    loop = asyncio.new_event_loop()
                
                asyncio.set_event_loop(loop)
                loop_ref[0] = loop
                loop_ready.set()  # Signal that loop is ready
                loop.run_forever()
            
            self._loop_thread = threading.Thread(target=_run_loop, daemon=True)
            self._loop_thread.start()
            loop_ready.wait()  # Wait for loop to be created and set
            self._loop = loop_ref[0]
        return self._loop

    def _run_async(self, coro):
        """Run an async coroutine in the dedicated event loop"""
        loop = self._get_or_create_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    def start(self, headless=False):
        """Start the browser if not already running"""
        if self.page:
            return

        if self._playwright is None:
            self._playwright = self._run_async(async_playwright().start())
            
        if self._browser is None:
            self._browser = self._run_async(self._playwright.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--start-maximized' # Added from snippet
                ]
            ))
            
        # Create context if it doesn't exist
        if self._context is None:
            context_options = {}
            
            # Set viewport for consistency
            context_options['viewport'] = {'width': 1920, 'height': 1080}

            self._context = self._run_async(self._browser.new_context(**context_options))
            
            # Wrap context
            self._context = SyncPlaywrightWrapper(self._context, self._run_async)
            
        if self.page is None:
            self._async_page = self._run_async(self._context._obj.new_page()) # Use the unwrapped context
            
            # Optimize timeouts for speed - shorter timeouts enable faster failure/retry
            # set_default_timeout is synchronous in Playwright python (even async API)
            self._async_page.set_default_timeout(30000)
            # Use domcontentloaded for faster navigation
            self._async_page.set_default_navigation_timeout(30000)
            
            # Create sync wrapper for the page
            self.page = SyncPlaywrightWrapper(self._async_page, self._run_async)
            
            return self._playwright, self._browser, self._async_page, self._context

    def get_page(self):
        """Return the current page object"""
        return self.page

    def set_active_page(self, page_wrapper):
        """Set the currently active page for the browser manager"""
        self.page = page_wrapper
        self._async_page = page_wrapper._obj

    def switch_to_new_tab(self):
        """Switch to the last opened tab/page"""
        if not self._context:
            return {"status": "error", "error": "No browser context found"}
        
        async def _switch():
            pages = self._context.pages
            if len(pages) > 0:
                new_page = pages[-1]
                await new_page.bring_to_front()
                return new_page
            return None
            
        new_async_page = self._run_async(_switch())
        if new_async_page:
            self.set_active_page(SyncPlaywrightWrapper(new_async_page, self._run_async))
            return {"status": "success", "output": f"Switched to new tab. Total tabs: {len(self._context.pages)}"}
        else:
            return {"status": "error", "error": "No pages found to switch to"}

    def execute_script(self, script_code: str):
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        # Clean script code - remove any leading/trailing whitespace
        script_code = script_code.strip()
        
        # Check if script uses 'await' - if so, wrap in async function
        uses_await = 'await' in script_code
        
        try:
            if uses_await:
                # Execute script with await support in async context
                async def _execute_async():
                    """Execute script in async context with async page"""
                    # Capture page in closure for explicit access
                    page_obj = self._async_page
                    
                    # Find minimum indentation (if any) to normalize
                    lines = script_code.split('\n')
                    non_empty_lines = [line for line in lines if line.strip()]
                    if non_empty_lines:
                        min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines)
                    else:
                        min_indent = 0
                    
                    # Wrap the script in an async function so 'await' works
                    # Inject page as a parameter to ensure it's accessible
                    wrapped_code = f"async def _user_script():\n    page = _page_inject\n"
                    # Add proper indentation to each line (preserve relative indentation)
                    for line in lines:
                        if line.strip():  # Non-empty line
                            # Remove minimum indentation, then add function-level indentation
                            current_indent = len(line) - len(line.lstrip())
                            adjusted_indent = current_indent - min_indent
                            wrapped_code += "    " + (" " * adjusted_indent) + line.lstrip() + "\n"
                        else:
                            wrapped_code += "\n"
                    
                    # Create globals dict with page injected
                    globals_dict = {'_page_inject': page_obj, 'browser_manager': self}
                    locals_dict = {}
                    # Execute the wrapped async code to define the function
                    exec(wrapped_code, globals_dict, locals_dict)
                    # Now call the async function
                    await locals_dict['_user_script']()
                    return {"status": "success", "output": "Step completed"}
                
                result = self._run_async(_execute_async())
            else:
                # Execute script with sync wrapper (no await needed)
                # Execute directly with page in globals
                globals_dict = {'page': self.page, 'browser_manager': self}
                exec(script_code, globals_dict, {})
                result = {"status": "success", "output": "Step completed"}
            
            return result
        except Exception as e:
            # Capture screenshot on failure
            async def _screenshot():
                screenshot_bytes = await self._async_page.screenshot()
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                return {
                    "status": "error", 
                    "error": str(e), 
                    "screenshot": screenshot_b64
                }
            
            return self._run_async(_screenshot())

    def close(self):
        if self._browser:
            async def _close():
                if self._context:
                    # Context wrapper might not have close method if it's unwrapped? 
                    # Actually sync wrapper handles it. But let's be safe and use _obj if possible or just call close
                    # Since it is wrapped, we check if we can call it.
                    # Safest is to use the unwrapped object if we kept it?
                    # We only kept self._context as wrapper.
                    # But async Playwright context has close().
                    # Let's trust the wrapper or use _obj attribute if we exposed it (we did in SyncPlaywrightWrapper)
                    
                    # Wait, self._context is SyncPlaywrightWrapper.
                    # We are in async _close(). We should call close() on the underlying async object.
                    await self._context._obj.close()
                    self._context = None
                
                await self._browser.close()
                await self._playwright.stop()
                
                self._browser = None
                self._playwright = None
                self._async_page = None
                self.page = None
            
            if self._loop and not self._loop.is_closed():
                try:
                    self._run_async(_close())
                except:
                    pass
                self._loop.call_soon_threadsafe(self._loop.stop)
                if self._loop_thread:
                    self._loop_thread.join(timeout=2)
                if not self._loop.is_closed():
                    self._loop.close()
                self._loop = None

# Global instance
browser_instance = BrowserManager()