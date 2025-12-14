from typing import List, Optional, TypedDict

class AgentState(TypedDict):
    task: str                       
    plan: List[str]                 
    current_step_index: int         
    
    current_script: Optional[str]   
    execution_result: Optional[str] 
    error: Optional[str]            
    screenshot: Optional[str]       # Now storing base64 string for Streamlit
    
    retry_count: int 
    logs: List[str]                 # New: To display progress in UI