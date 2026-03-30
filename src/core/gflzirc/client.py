import json
import time
import requests
from .crypto import gf_authcode

class GFLClient:
    def __init__(self, uid: str, sign_key: str, base_url: str):
        self.uid = uid
        self.sign_key = sign_key
        self.base_url = base_url.rstrip('/')
        self.req_idx = 1
        self.session = requests.Session()
        
        # Force requests to bypass any residual proxy settings
        self.session.proxies = {
            "http": None,
            "https": None
        }
        
        self.session.headers.update({
            "User-Agent": "UnityPlayer/2018.4.36f1 (UnityWebRequest/1.0, libcurl/7.52.0-DEV)",
            "X-Unity-Version": "2018.4.36f1",
            "Content-Type": "application/x-www-form-urlencoded"
        })

    def _get_req_id(self):
        timestamp = int(time.time())
        req_id = f"{timestamp}{self.req_idx:05d}"
        self.req_idx += 1
        return req_id

    def send_request(self, endpoint: str, payload: dict, max_retries: int = 3, timeout: int = 15):
        """
        Sends an encrypted request to the GFL server.
        """
        endpoint = "/" + endpoint.lstrip('/')
        json_str = json.dumps(payload, separators=(',', ':'))
        encrypted = gf_authcode(json_str, 'ENCODE', self.sign_key)
        
        data = {
            "uid": self.uid,
            "req_id": self._get_req_id(),
            "outdatacode": encrypted
        }

        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(max_retries):
            try:
                response = self.session.post(url, data=data, timeout=timeout)
                text = response.text.strip()
                
                if text.startswith("#"):
                    decrypted_str = gf_authcode(text[1:], 'DECODE', self.sign_key)
                    if decrypted_str:
                        try:
                            return json.loads(decrypted_str)
                        except json.JSONDecodeError:
                            return {"error_local": "JSON parse error", "raw": decrypted_str}
                    else:
                        return {"error_local": "Decryption failed.", "raw": text}
                elif text.startswith("{") or text.startswith("["):
                    try:
                        return json.loads(text)
                    except:
                        pass
                elif text.startswith("1"):
                    return {"success": True, "raw": text}
                    
                return {"error_local": "Unexpected plaintext response", "raw": text}
                
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    return {"error_local": f"Network Exception after {max_retries} retries: {str(e)}"}
                time.sleep(2)