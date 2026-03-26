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
# GFL API Client (Added Retry Mechanism)
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

    def send_request(self, endpoint: str, payload: dict, max_retries: int = 3):
        """发送请求，支持 JSON 字典或数组，支持断网重试"""
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
                # 增加了 timeout 容忍网络波动
                response = self.session.post(url, data=data, timeout=15)
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
                print(f"[!] Network error on {endpoint}, retrying ({attempt + 1}/{max_retries})...")
                time.sleep(2)


# ==========================================
# Auto Farm Logic
# ==========================================

def abort_stuck_mission(client: GFLClient, mission_id: int):
    """强制终止战役清空状态，解决 error:2 和 error:300 的死锁问题"""
    print(f"[!] Attempting to Force Abort Mission {mission_id} to clear state...")
    # 大多数情况下 /Mission/abortMission 或 /Mission/withdraw 可以重置状态
    resp = client.send_request("/Mission/abortMission", {"mission_id": mission_id})
    if resp.get("success") or "mission_win_result" in str(resp):
        print("[+] Mission aborted successfully. State cleared.")
    else:
        print("[-] Abort returned:", resp)
    time.sleep(2)

def check_step_error(resp: dict, step_name: str) -> bool:
    if "error_local" in resp:
        print(f"[-] {step_name} Local Error: {resp['error_local']}")
        return True
    if "error" in resp:
        print(f"[-] {step_name} Server Error: {resp['error']}")
        return True
    return False

def check_drop_result(response_data: dict) -> list:
    """提取结算数据，返回收集到的人形 UID 列表"""
    collected_guns = []
    win_result = response_data.get("mission_win_result", {})
    if not win_result:
        print("[!] Flow finished, but no 'mission_win_result' found.")
        return collected_guns
        
    reward_guns = win_result.get("reward_gun", [])
    if reward_guns:
        for gun in reward_guns:
            gun_id = gun.get('gun_id')
            gun_uid = int(gun.get('gun_with_user_id'))
            print(f"[+] MISSION CLEARED! Got T-Doll! Gun ID: {gun_id} | UID: {gun_uid} ")
            
            # --- 新增的时间打印逻辑 ---
            current_time = time.strftime("%H:%M:%S")
            # \033[36m 是青色(Cyan)的 ANSI 颜色码，\033[0m 用来重置颜色
            print(f"\033[36m[T] {current_time}\033[0m")
            # --------------------------
            
            collected_guns.append(gun_uid)
    else:
        print("[+] Mission cleared successfully. (No T-Doll drop this time)")
        
    return collected_guns

def farm_mission_11880(client: GFLClient, squad_id: int):
    """执行一次完整的 11880 战役，如果发生严重错误返回 None，否则返回获得的人形列表"""
    mission_id = 11880
    GUIDE_COURSE = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,1,1,1,0,1,0,0,0,0,0,0,1,1,1,1,1,1,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,1,0,0,0,0,0,0,1,1,1,0,0,1,0,1,1,1,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1,1,1,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,1,1,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]

    # 1. combinationInfo
    resp = client.send_request("/Mission/combinationInfo", {"mission_id": mission_id})
    if check_step_error(resp, "combinationInfo"): return None
    
    # 2. startMission
    start_payload = {
        "mission_id": mission_id, "spots": [],
        "squad_spots": [{"spot_id": 901926, "squad_with_user_id": squad_id, "battleskill_switch": 1}],
        "sangvis_spots": [], "vehicle_spots": [], "ally_spots": [], "mission_ally_spots": [],
        "ally_id": int(time.time())
    }
    resp = client.send_request("/Mission/startMission", start_payload)
    if check_step_error(resp, "startMission"): return None
    
    # 3. Guide
    guide_inner_json = json.dumps({"course": GUIDE_COURSE}, separators=(',', ':'))
    resp = client.send_request("/Index/guide", {"guide": guide_inner_json})
    if check_step_error(resp, "Index/guide"): return None
    
    # 4. Turns (加入适当延迟)
    time.sleep(0.5)
    resp = client.send_request("/Mission/endTurn", {})
    if check_step_error(resp, "endTurn"): return None
    
    time.sleep(0.2)
    resp = client.send_request("/Mission/startEnemyTurn", {})
    if check_step_error(resp, "startEnemyTurn"): return None
    
    time.sleep(0.2)
    resp = client.send_request("/Mission/endEnemyTurn", {})
    if check_step_error(resp, "endEnemyTurn"): return None
    
    time.sleep(0.2)
    final_resp = client.send_request("/Mission/startTurn", {})
    if check_step_error(final_resp, "startTurn"): return None
    
    # 5. 返回掉落的 gun_uids 数组
    return check_drop_result(final_resp)

def retire_guns(client: GFLClient, gun_uids: list):
    """调用接口自动拆解收集到的人形"""
    if not gun_uids:
        print("[*] No T-Dolls to retire in this batch.")
        return
    
    print(f"[*] Submitting {len(gun_uids)} T-Dolls for Auto-Retire...")
    # Payload 直接就是一个 JSON Array [11111, 22222]
    resp = client.send_request("/Gun/retireGun", gun_uids)
    
    if resp.get("success"):
        print("[+] Auto-Retire Successful! Workspace Cleared. ")
    else:
        print(f"[-] Retire Failed: {resp}")


if __name__ == '__main__':
    USER_UID = "4370354"
    SIGN_KEY = "6aee2d0fe0b2afe11e4b7d59b30ff1f2"
    SQUAD_ID = 106360
    
    MACRO_LOOPS = 200         # 大循环次数 (拆解次数)
    MISSIONS_PER_RETIRE = 50 # 每次大循环刷多少次图再进行拆解

    client = GFLClient(USER_UID, SIGN_KEY)

    print("=========================================")
    print("   GFL Protocol Auto-Farming Initiated   ")
    print("   Includes Error-Recovery & Auto-Retire ")
    print("=========================================")

    for macro in range(1, MACRO_LOOPS + 1):
        print(f"\n=========================================")
        print(f"  >>> MACRO BATCH {macro} / {MACRO_LOOPS} STARTING <<<")
        print(f"=========================================")
        
        batch_collected_guns = []
        
        for micro in range(1, MISSIONS_PER_RETIRE + 1):
            print(f"\n--- Mission Run {micro} / {MISSIONS_PER_RETIRE} (Batch {macro}) ---")
            
            # 执行战役并获取掉落的人形 UID 列表
            dropped_guns = farm_mission_11880(client, SQUAD_ID)
            
            # 如果 dropped_guns 为 None，说明遇到了严重错误（如 error:2, error:300）
            if dropped_guns is None:
                abort_stuck_mission(client, 11880)
                print("[!] Skipping to next run to recover state...")
                time.sleep(3)
                continue
                
            # 将本次掉落追加到批次列表中
            batch_collected_guns.extend(dropped_guns)
            
            if micro < MISSIONS_PER_RETIRE:
                time.sleep(1) # 单局之间的保护性停顿
                
        # 当一个批次（比如 20 次）刷完后，统一拆解
        print(f"\n[+] Batch {macro} completed. Preparing to retire...")
        retire_guns(client, batch_collected_guns)
        time.sleep(2)
            
    print("\n[*] All farming and retire runs completed gracefully.")