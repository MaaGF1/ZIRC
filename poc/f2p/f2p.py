import hashlib
import base64
import time
import json
import requests
import gzip
import os
import sys
import threading
import shlex
import socket
import select
import re

# For Auto-Proxy Configuration on Windows
import winreg
import ctypes

# ==========================================
# [1] Parameterized Configuration
# ==========================================
CONFIG = {
    "USER_UID": "_InputYourID_",                                                # User ID (Will be auto-filled by Capture)
    "SIGN_KEY": "1234567890abcdefghijklmnopqrstuv",                             # User's sign key (Will be auto-filled by Capture)
    "STATIC_KEY": "yundoudou",                                                  # The global static key used before login
    "MACRO_LOOPS": 200,                                                         # total f2p times = MACRO_LOOPS * MISSIONS_PER_RETIRE
    "MISSIONS_PER_RETIRE": 50,                                                  # Retire the doll after `MISSIONS_PER_RETIRE` times
    "SQUAD_ID": 106360,                                                         # BGM-71's ID
    "BASE_URL": "http://gfcn-game.gw.merge.sunborngame.com/index.php/1000",     # URL of CN's M4A1, replace the URL if you are using a different server
    "PROXY_PORT": 8080
}

# ==========================================
# [2] Threading State Flags
# ==========================================
current_worker_thread = None
worker_mode = None  # 'c' for Capture(Proxy), 'r' for Farm, None for Idle

stop_macro_flag = False
stop_micro_flag = False
stop_capture_flag = False

# ==========================================
# [3] GFL Crypto Core
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
# [4] GFL API Client
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
        self.base_url = CONFIG["BASE_URL"]

    def _get_req_id(self):
        timestamp = int(time.time())
        req_id = f"{timestamp}{self.req_idx:05d}"
        self.req_idx += 1
        return req_id

    def send_request(self, endpoint: str, payload: dict, max_retries: int = 3):
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
# [5] Auto Farm Logic
# ==========================================
def abort_stuck_mission(client: GFLClient, mission_id: int):
    print(f"[!] Attempting to Force Abort Mission {mission_id} to clear state...")
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
            print(f"[+] MISSION CLEARED! Got T-Doll! Gun ID: {gun_id} | UID: {gun_uid}")
            
            current_time = time.strftime("%H:%M:%S")
            print(f"[*] Drop Time: {current_time}")
            
            collected_guns.append(gun_uid)
    else:
        print("[+] Mission cleared successfully. (No T-Doll drop this time)")
        
    return collected_guns

def farm_mission_11880(client: GFLClient, squad_id: int):
    mission_id = 11880
    GUIDE_COURSE = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,1,1,1,0,1,0,0,0,0,0,0,1,1,1,1,1,1,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,1,0,0,0,0,0,0,1,1,1,0,0,1,0,1,1,1,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1,1,1,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,1,1,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]

    resp = client.send_request("/Mission/combinationInfo", {"mission_id": mission_id})
    if check_step_error(resp, "combinationInfo"): return None
    
    start_payload = {
        "mission_id": mission_id, "spots": [],
        "squad_spots": [{"spot_id": 901926, "squad_with_user_id": squad_id, "battleskill_switch": 1}],
        "sangvis_spots": [], "vehicle_spots": [], "ally_spots": [], "mission_ally_spots": [],
        "ally_id": int(time.time())
    }
    resp = client.send_request("/Mission/startMission", start_payload)
    if check_step_error(resp, "startMission"): return None
    
    guide_inner_json = json.dumps({"course": GUIDE_COURSE}, separators=(',', ':'))
    resp = client.send_request("/Index/guide", {"guide": guide_inner_json})
    if check_step_error(resp, "Index/guide"): return None
    
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
    
    return check_drop_result(final_resp)

def retire_guns(client: GFLClient, gun_uids: list):
    if not gun_uids:
        print("[*] No T-Dolls to retire in this batch.")
        return
    
    print(f"[*] Submitting {len(gun_uids)} T-Dolls for Auto-Retire...")
    resp = client.send_request("/Gun/retireGun", gun_uids)
    
    if resp.get("success"):
        print("[+] Auto-Retire Successful! Workspace Cleared.")
    else:
        print(f"[-] Retire Failed: {resp}")

# ==========================================
# [6] System Proxy Configuration (Windows)
# ==========================================
INTERNET_OPTION_REFRESH = 37
INTERNET_OPTION_SETTINGS_CHANGED = 39

def refresh_windows_proxy():
    internet_set_option = ctypes.windll.wininet.InternetSetOptionW
    internet_set_option(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
    internet_set_option(0, INTERNET_OPTION_REFRESH, 0, 0)

def set_windows_proxy(enable: bool, proxy_addr="127.0.0.1:8080"):
    try:
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        hKey = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_WRITE)
        
        if enable:
            winreg.SetValueEx(hKey, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(hKey, "ProxyServer", 0, winreg.REG_SZ, proxy_addr)
            print(f"[*] Windows System Proxy ENABLED -> {proxy_addr}")
        else:
            winreg.SetValueEx(hKey, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            print(f"[*] Windows System Proxy DISABLED -> Restored to Direct")
            
        winreg.CloseKey(hKey)
        refresh_windows_proxy()
    except Exception as e:
        print(f"[!] Failed to modify Windows Proxy: {e}")
        print("[!] Please run this script as Administrator.")

# ==========================================
# [7] Smart Blind MITM Proxy Logic
# ==========================================
def blind_relay(src_sock, dst_sock):
    """ Blindly forwards data between two sockets (used for HTTPS / generic traffic) """
    sockets = [src_sock, dst_sock]
    try:
        while not stop_capture_flag:
            readable, _, _ = select.select(sockets, [], [], 1.0)
            if not readable:
                continue
            for sock in readable:
                data = sock.recv(8192)
                if not data:
                    return # Connection closed
                if sock is src_sock:
                    dst_sock.sendall(data)
                else:
                    src_sock.sendall(data)
    except Exception:
        pass

def handle_proxy_client(client_socket):
    """ Handles a single proxy connection, parses HTTP headers to find target """
    try:
        # Read the initial request
        request_header = b""
        while b"\r\n\r\n" not in request_header:
            chunk = client_socket.recv(4096)
            if not chunk:
                break
            request_header += chunk
            
        if not request_header:
            client_socket.close()
            return
            
        header_str = request_header.split(b"\r\n\r\n")[0].decode('ascii', errors='ignore')
        lines = header_str.split('\r\n')
        first_line = lines[0].split()
        
        if len(first_line) < 3:
            client_socket.close()
            return
            
        method, url, protocol = first_line
        
        # Parse Host header
        host = ""
        port = 80
        for line in lines[1:]:
            if line.lower().startswith("host:"):
                host_val = line.split(":", 1)[1].strip()
                if ":" in host_val:
                    host, p = host_val.split(":", 1)
                    port = int(p)
                else:
                    host = host_val
                    port = 443 if method == "CONNECT" else 80
                break
                
        if not host:
            client_socket.close()
            return

        # Connect to Target Server
        target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target_socket.connect((host, port))
        
        if method == "CONNECT":
            # HTTPS Blind Forwarding (No Certificate Warnings)
            client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            blind_relay(client_socket, target_socket)
        else:
            # HTTP Interception
            is_target_api = "/Index/getUidPC" in url
            target_socket.sendall(request_header)
            
            # Read response and forward
            response_buffer = b""
            while not stop_capture_flag:
                data = target_socket.recv(8192)
                if not data:
                    break
                client_socket.sendall(data)
                if is_target_api:
                    response_buffer += data
                    
            # Capture SIGN_KEY if this was the target API
            if is_target_api and response_buffer:
                # Use regex to find the encrypted payload starting with '#'
                # Payload is base64 characters: A-Z, a-z, 0-9, +, /, =
                match = re.search(b'#([A-Za-z0-9+/=]+)', response_buffer)
                if match:
                    encrypted_b64 = match.group(1).decode('ascii')
                    print("\n[+] Captured getUidPC Response! Decrypting with STATIC_KEY...")
                    
                    decrypted = gf_authcode(encrypted_b64, 'DECODE', CONFIG["STATIC_KEY"])
                    if decrypted:
                        try:
                            json_data = json.loads(decrypted)
                            extracted_uid = json_data.get("uid")
                            extracted_sign = json_data.get("sign")
                            
                            if extracted_uid and extracted_sign:
                                CONFIG["USER_UID"] = str(extracted_uid)
                                CONFIG["SIGN_KEY"] = str(extracted_sign)
                                print(f"\n[+] SUCCESS! Keys Auto-Configured:")
                                print(f"    UID  : {CONFIG['USER_UID']}")
                                print(f"    SIGN : {CONFIG['SIGN_KEY']}")
                                print("[+] Stopping Proxy and restoring system network...")
                                
                                # Auto-stop the capture process
                                global stop_capture_flag
                                stop_capture_flag = True
                        except Exception as e:
                            print(f"[-] JSON parse error after decryption: {e}")
                    else:
                        print("[-] Decryption returned empty string. Wrong STATIC_KEY?")

    except Exception as e:
        pass
    finally:
        try: client_socket.close()
        except: pass
        try: target_socket.close()
        except: pass

def proxy_server_worker():
    global stop_capture_flag, worker_mode, current_worker_thread
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(("127.0.0.1", CONFIG["PROXY_PORT"]))
        server.listen(100)
        print(f"[*] Proxy Server listening on 127.0.0.1:{CONFIG['PROXY_PORT']}...")
        
        # Turn ON Windows Proxy
        set_windows_proxy(True, f"127.0.0.1:{CONFIG['PROXY_PORT']}")
        print("[*] System Proxy is hijacked. Please login to the game now.")
        print("[*] (Type -q to cancel and restore network)")
        
        server.settimeout(1.0)
        while not stop_capture_flag:
            try:
                client_sock, addr = server.accept()
                t = threading.Thread(target=handle_proxy_client, args=(client_sock,))
                t.daemon = True
                t.start()
            except socket.timeout:
                continue
                
    except Exception as e:
        print(f"[!] Proxy Server Error: {e}")
    finally:
        server.close()
        # Turn OFF Windows Proxy securely
        set_windows_proxy(False)
        print("[*] Capture Proxy shut down safely.")
        
        worker_mode = None
        current_worker_thread = None

# ==========================================
# [8] Worker Threads Logic
# ==========================================
def farm_worker():
    global stop_macro_flag, stop_micro_flag, worker_mode, current_worker_thread
    
    if CONFIG["SIGN_KEY"] == "1234567890abcdefghijklmnopqrstuv":
        print("[!] SIGN_KEY is default. Please run Capture (-c) first!")
        worker_mode = None
        current_worker_thread = None
        return

    client = GFLClient(CONFIG["USER_UID"], CONFIG["SIGN_KEY"])

    print("=========================================")
    print("   GFL Protocol Auto-Farming Started     ")
    print("=========================================")

    for macro in range(1, CONFIG["MACRO_LOOPS"] + 1):
        if stop_macro_flag:
            print("[*] Macro loop stop requested. Breaking outer loop.")
            break
            
        print(f"\n=========================================")
        print(f"  >>> MACRO BATCH {macro} / {CONFIG['MACRO_LOOPS']} STARTING <<<")
        print(f"=========================================")
        
        batch_collected_guns = []
        
        for micro in range(1, CONFIG["MISSIONS_PER_RETIRE"] + 1):
            if stop_micro_flag or stop_macro_flag:
                print("[*] Micro loop stop requested. Breaking inner loop.")
                break
                
            print(f"\n--- Mission Run {micro} / {CONFIG['MISSIONS_PER_RETIRE']} (Batch {macro}) ---")
            
            dropped_guns = farm_mission_11880(client, CONFIG["SQUAD_ID"])
            
            if dropped_guns is None:
                abort_stuck_mission(client, 11880)
                print("[!] Skipping to next run to recover state...")
                time.sleep(3)
                continue
                
            batch_collected_guns.extend(dropped_guns)
            
            if micro < CONFIG["MISSIONS_PER_RETIRE"]:
                time.sleep(1) 
                
        print(f"\n[+] Batch {macro} completed or interrupted. Preparing to retire...")
        retire_guns(client, batch_collected_guns)
        time.sleep(2)
        
        if stop_micro_flag:
            break
            
    print("\n[*] All farming runs ended gracefully.")
    worker_mode = None
    current_worker_thread = None

# ==========================================
# [9] Interactive Command Line Interface
# ==========================================

def print_menu():
    print("\n================= MENU =================")
    print(" -c : Start Capture Proxy (Auto-extract Keys via network)")
    print(" -r : Run Auto-Farming")
    print(" -q : Stop Capture OR Stop Farm after current Macro")
    print(" -Q : Stop Capture OR Stop Farm after current Micro")
    print(" -s : Set configs (e.g. -s --uid 123 --key abc)")
    print(" -E : Exit program safely (Will auto-restore Proxy)")
    print("========================================\n")

def process_settings(cmd_str):
    try:
        parts = shlex.split(cmd_str)[1:]
        for i in range(0, len(parts), 2):
            key = parts[i]
            val = parts[i+1] if i+1 < len(parts) else None
            
            if key == '--uid' and val:
                CONFIG["USER_UID"] = val
                print(f"[*] Updated USER_UID = {val}")
            elif key == '--key' and val:
                CONFIG["SIGN_KEY"] = val
                print(f"[*] Updated SIGN_KEY = {val}")
            elif key == '--loop' and val:
                CONFIG["MACRO_LOOPS"] = int(val)
                print(f"[*] Updated MACRO_LOOPS = {val}")
            elif key == '--retire' and val:
                CONFIG["MISSIONS_PER_RETIRE"] = int(val)
                print(f"[*] Updated MISSIONS_PER_RETIRE = {val}")
            else:
                print(f"[!] Unrecognized setting format: {key} {val}")
    except Exception as e:
        print(f"[!] Failed to parse settings: {e}")

def main_loop():
    global current_worker_thread, worker_mode
    global stop_macro_flag, stop_micro_flag, stop_capture_flag
    
    print_menu()
    
    while True:
        try:
            cmd_input = input("GFL-F2P> ").strip()
            if not cmd_input:
                continue
                
            cmd = cmd_input.split()[0]
            
            if cmd == '-c':
                if current_worker_thread and current_worker_thread.is_alive():
                    print("[!] A task is already running. Please stop it first (-q or -Q).")
                else:
                    stop_capture_flag = False
                    worker_mode = 'c'
                    current_worker_thread = threading.Thread(target=proxy_server_worker)
                    current_worker_thread.daemon = True
                    current_worker_thread.start()
                    
            elif cmd == '-r':
                if current_worker_thread and current_worker_thread.is_alive():
                    print("[!] A task is already running. Please stop it first (-q or -Q).")
                else:
                    stop_macro_flag = False
                    stop_micro_flag = False
                    worker_mode = 'r'
                    current_worker_thread = threading.Thread(target=farm_worker)
                    current_worker_thread.daemon = True
                    current_worker_thread.start()
                    
            elif cmd == '-q':
                if worker_mode == 'c':
                    print("[*] Stopping Proxy and restoring network...")
                    stop_capture_flag = True
                elif worker_mode == 'r':
                    print("[*] Boundary Protection: Will safely exit after current MACRO batch completes...")
                    stop_macro_flag = True
                else:
                    print("[*] No task is currently running.")
                    
            elif cmd == '-Q':
                if worker_mode == 'c':
                    print("[*] Stopping Proxy and restoring network...")
                    stop_capture_flag = True
                elif worker_mode == 'r':
                    print("[*] Boundary Protection: Will safely exit after current MICRO run completes...")
                    stop_micro_flag = True
                else:
                    print("[*] No task is currently running.")
                    
            elif cmd == '-s':
                if current_worker_thread and current_worker_thread.is_alive():
                    print("[!] Cannot change settings while a task is running. Stop it first.")
                else:
                    process_settings(cmd_input)
                    
            elif cmd == '-E':
                print("[*] Emergency Exit requested. Cleaning up resources...")
                stop_capture_flag = True
                stop_macro_flag = True
                stop_micro_flag = True
                
                # Make sure to restore Windows proxy before exiting!
                set_windows_proxy(False)
                
                if current_worker_thread and current_worker_thread.is_alive():
                    print("[*] Waiting for background threads to terminate safely...")
                    current_worker_thread.join(timeout=3)
                print("[*] Goodbye!")
                sys.exit(0)
                
            else:
                print(f"[!] Unknown command: {cmd}")
                print_menu()
                
        except KeyboardInterrupt:
            print("\n[!] Please use '-E' to exit the program safely to avoid server desync and proxy stuck.")
            
if __name__ == '__main__':
    main_loop()