import hashlib
import base64
import time
import json
import requests
import gzip

# ==========================================
# GFL Crypto Core
# ==========================================

def md5(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def gf_authcode(string: str, operation: str = 'ENCODE', key: str = '', expiry: int = 3600) -> str:
    key_hash = md5(key)
    keya = md5(key_hash[0:16])
    keyb = md5(key_hash[16:32])
    
    cryptkey = keyb + md5(keyb)
    key_length = len(cryptkey)
    
    if operation == 'DECODE':
        try:
            b64_str = string.strip()
            b64_str = b64_str + "=" * ((4 - len(b64_str) % 4) % 4)
            string_bytes = base64.b64decode(b64_str)
        except Exception:
            return ""
    else:
        expiry_time = (expiry + int(time.time())) if expiry > 0 else 0
        header = f"{expiry_time:010d}"
        checksum = md5(string + keya)[0:16]
        payload = header + checksum + string
        string_bytes = payload.encode('utf-8')

    string_length = len(string_bytes)
    result = bytearray()
    box = list(range(256))
    rndkey = [ord(cryptkey[i % key_length]) for i in range(256)]
    
    j = 0
    for i in range(256):
        j = (j + box[i] + rndkey[i]) % 256
        box[i], box[j] = box[j], box[i]
        
    a = j = 0
    for i in range(string_length):
        a = (a + 1) % 256
        j = (j + box[a]) % 256
        box[a], box[j] = box[j], box[a]
        result.append(string_bytes[i] ^ box[(box[a] + box[j]) % 256])
        
    if operation == 'DECODE':
        res_str = bytes(result)
        try:
            ext_bytes = res_str[26:]
            if ext_bytes.startswith(b'\x1f\x8b'):
                try:
                    ext_bytes = gzip.decompress(ext_bytes)
                except Exception:
                    pass
            ext_text = ext_bytes.decode('utf-8', errors='ignore').strip('\0')
            return ext_text
        except Exception:
            return ""
    else:
        return base64.b64encode(bytes(result)).decode('utf-8')


# ==========================================
# GFL API Client
# ==========================================

class GFLClient:
    def __init__(self, uid: str, sign_key: str):
        self.uid = uid
        self.sign_key = sign_key
        self.req_idx = 1
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "UnityPlayer/2018.4.36f1 (UnityWebRequest/1.0, libcurl/7.52.0-DEV)",
            "X-Unity-Version": "2018.4.36f1",
            "Content-Type": "application/x-www-form-urlencoded"
        })
        self.base_url = "http://gfcn-game.gw.merge.sunborngame.com/index.php/1000"

    def _get_req_id(self):
        timestamp = int(time.time())
        req_id = f"{timestamp}{self.req_idx:05d}"
        self.req_idx += 1
        return req_id

    def send_request(self, endpoint: str, payload_dict: dict):
        # 统一强制使用 outdatacode，绕过 signcode 复杂的拦截机制
        json_str = json.dumps(payload_dict, separators=(',', ':'))
        encrypted = gf_authcode(json_str, 'ENCODE', self.sign_key)
        
        data = {
            "uid": self.uid,
            "req_id": self._get_req_id(),
            "outdatacode": encrypted
        }

        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.post(url, data=data, timeout=10)
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
            
        except Exception as e:
            return {"error_local": f"Network Exception: {str(e)}"}


# ==========================================
# Auto Farm Logic
# ==========================================

def check_step_error(resp: dict, step_name: str) -> bool:
    if "error_local" in resp:
        print(f"[-] {step_name} Local Error: {resp['error_local']}")
        print(f"    Raw output: {resp.get('raw', 'None')}")
        return True
    if "error" in resp:
        print(f"[-] {step_name} Server Error: {resp['error']}")
        return True
    return False

def farm_mission_11880(client: GFLClient, squad_id: int):
    mission_id = 11880
    GUIDE_COURSE = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,1,1,1,0,1,0,0,0,0,0,0,1,1,1,1,1,1,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,1,0,0,0,0,0,0,1,1,1,0,0,1,0,1,1,1,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1,1,1,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,1,1,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]

    print(f"[*] Deploying and starting mission {mission_id}...")
    
    # 1. combinationInfo
    resp = client.send_request("/Mission/combinationInfo", {"mission_id": mission_id})
    if check_step_error(resp, "combinationInfo"): return
    
    # 2. startMission
    start_payload = {
        "mission_id": mission_id,
        "spots": [],
        "squad_spots": [
            {"spot_id": 901926, "squad_with_user_id": squad_id, "battleskill_switch": 1}
        ],
        "sangvis_spots": [], "vehicle_spots": [], "ally_spots": [], "mission_ally_spots": [],
        "ally_id": int(time.time())
    }
    resp = client.send_request("/Mission/startMission", start_payload)
    if check_step_error(resp, "startMission"): return
    
    # 3. Guide
    guide_inner_json = json.dumps({"course": GUIDE_COURSE}, separators=(',', ':'))
    resp = client.send_request("/Index/guide", {"guide": guide_inner_json})
    if check_step_error(resp, "Index/guide"): return
    
    # 4. Turns
    print("[*] Simulating turns to clear the mission...")
    time.sleep(0.1)
    
    # 统一使用 outdatacode 发送空载荷
    resp = client.send_request("/Mission/endTurn", {})
    if check_step_error(resp, "endTurn"): return
    
    time.sleep(0.1)
    resp = client.send_request("/Mission/startEnemyTurn", {})
    if check_step_error(resp, "startEnemyTurn"): return
    
    time.sleep(0.1)
    resp = client.send_request("/Mission/endEnemyTurn", {})
    if check_step_error(resp, "endEnemyTurn"): return
    
    time.sleep(0.1)
    # 最后一次回合请求，通常会带回结算奖励
    final_resp = client.send_request("/Mission/startTurn", {})
    if check_step_error(final_resp, "startTurn"): return
    
    # 5. Result
    check_drop_result(final_resp)

def check_drop_result(response_data: dict):
    win_result = response_data.get("mission_win_result", {})
    if not win_result:
        print("[!] Flow finished, but no 'mission_win_result' found.")
        return
        
    reward_guns = win_result.get("reward_gun", [])
    if reward_guns:
        for gun in reward_guns:
            print(f"[+] MISSION CLEARED! Got T-Doll Drop! Gun ID: {gun.get('gun_id')}")
    else:
        print("[+] Mission cleared successfully. (No T-Doll drop this time)")


if __name__ == '__main__':
    USER_UID = "4370354"
    SIGN_KEY = "7a750d1c4a17f24a39e80b832d26abbf"
    SQUAD_ID = 106360
    LOOP_COUNT = 200

    client = GFLClient(USER_UID, SIGN_KEY)

    print("=========================================")
    print("   GFL Protocol Auto-Farming Initiated   ")
    print("=========================================")

    for i in range(1, LOOP_COUNT + 1):
        print(f"\n--- Run {i} / {LOOP_COUNT} ---")
        farm_mission_11880(client, SQUAD_ID)
        
        if i < LOOP_COUNT:
            print("[*] Sleeping for 4 seconds before next run...")
            time.sleep(0.1)
            
    print("\n[*] All farming runs completed.")