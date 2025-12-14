import os
import base64
from app.state import AgentState
from app.tools.browser import browser_instance

# Simple baseline storage (in a real app, use a database or artifact store)
BASELINE_DIR = "baselines"

def monitor_node(state: AgentState):
    """
    Regression Monitor: Compares current screenshot with baseline.
    """
    os.makedirs(BASELINE_DIR, exist_ok=True)
    
    # Identify task ID (simple hash of the task description for now)
    import hashlib
    task_hash = hashlib.md5(state['task'].encode()).hexdigest()
    step = state.get('current_step_index', 0)
    baseline_path = os.path.join(BASELINE_DIR, f"{task_hash}_step_{step}.png")
    
    # Capture current screenshot
    try:
        browser_instance.start(headless=False)
        page = browser_instance.get_page()
        screenshot_bytes = page.screenshot(type='png')
        
        # If no baseline, save as baseline
        if not os.path.exists(baseline_path):
            with open(baseline_path, "wb") as f:
                f.write(screenshot_bytes)
            return {
                "logs": ["📸 New task detected. Saved screenshot as BASELINE."]
            }
        
        # If baseline exists, compare
        else:
            # We need an image library for comparison. 
            # If PIL is not installed, we skip (or notify).
            try:
                from PIL import Image, ImageChops
                import io
                
                img_current = Image.open(io.BytesIO(screenshot_bytes)).convert('RGB')
                img_baseline = Image.open(baseline_path).convert('RGB')
                
                # Resize if needed to match (simple approach)
                if img_current.size != img_baseline.size:
                    img_current = img_current.resize(img_baseline.size)
                
                # Calculate diff
                diff = ImageChops.difference(img_current, img_baseline)
                bbox = diff.getbbox()
                
                if bbox:
                    # Calculate percentage difference (rough)
                    import numpy as np
                    diff_arr = np.array(diff)
                    diff_percentage = np.mean(diff_arr) / 255 * 100
                    
                    if diff_percentage > 1.0: # Threshold 1%
                        return {
                            "logs": [f"⚠️ VISUAL REGRESSION DETECTED! Difference: {diff_percentage:.2f}%"]
                        }
                    else:
                         return {
                            "logs": ["✅ Visual Check Passed (Minor noise ignored)."]
                        }
                else:
                    return {
                        "logs": ["✅ Visual Check Passed (Exact match)."]
                    }
                    
            except ImportError:
                 return {
                    "logs": ["⚠️ PIL/numpy not found. Skipping visual regression check."]
                }
                
    except Exception as e:
        return {
            "logs": [f"❌ Monitor failed: {str(e)}"]
        }
