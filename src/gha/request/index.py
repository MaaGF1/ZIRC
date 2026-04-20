# src/gha/request/index.py

import time
from .base import BaseRequest

class IndexRequest(BaseRequest):
    def __init__(self, agent):
        super().__init__(agent)
        self.api_endpoint = "Index/index"

    def fetch(self) -> dict:
        print(f"\n[>] Fetching Commander Index Data from server...")
        payload = {
            "time": int(time.time()),
            "furniture_data": False
        }
        
        resp = self.agent.safe_request(self.api_endpoint, payload, "fetchIndex")
        
        if self.agent.check_step_error(resp, "fetchIndex"):
            return None
            
        if isinstance(resp, dict) and "user_info" in resp:
            print(f"[+] Index Data fetched successfully.")
            return resp
            
        print("[-] FATAL: Index request returned unexpected format.")
        return None