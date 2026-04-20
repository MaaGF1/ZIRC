# src/demo/utils/parser/request_index.py

import sys
import time
import os
import json
from gflzirc import (
    GFLClient, GFLProxy, set_windows_proxy,
    SERVERS, STATIC_KEY, DEFAULT_SIGN
)

API_INDEX = "Index/index"

CONFIG = {
    "USER_UID": "_InputYourID_",
    "SIGN_KEY": DEFAULT_SIGN,
    "BASE_URL": SERVERS["M4A1"],
    "PROXY_PORT": 8080,
    "OUTPUT_FILE": "index.json"
}

proxy_instance = None
worker_mode = None

def save_json(content_obj, filepath):
    """
    Robust JSON saver adapted from monitor.py.
    Saves directly to the target filepath for immediate use by epa_export.py.
    """
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(content_obj, f, indent=4)
        print(f"[+] Saved successfully: {filepath}")
        print(f"[*] You can now run 'epa_export.py' to generate your GHA configuration.")
    except Exception as e:
        print(f"[!] Error saving file: {e}")

def on_traffic(event_type: str, url: str, data: dict):
    if event_type == "SYS_KEY_UPGRADE":
        CONFIG["USER_UID"] = data.get("uid")
        CONFIG["SIGN_KEY"] = data.get("sign")
        print(f"\n[+] SUCCESS! Keys Auto-Configured:")
        print(f"    UID  : {CONFIG['USER_UID']}")
        print(f"    SIGN : {CONFIG['SIGN_KEY']}")
        print("\n[!] CRITICAL: Please wait for the game to fully load into the Commander Screen!")
        print("[!] Then type '-r' to stop proxy and request the Index data.")

def request_index_worker():
    global worker_mode
    
    if CONFIG["SIGN_KEY"] == DEFAULT_SIGN:
        print("[!] SIGN_KEY is default. Run Capture (-c) first!")
        return

    client = GFLClient(CONFIG["USER_UID"], CONFIG["SIGN_KEY"], CONFIG["BASE_URL"])
    
    print(f"\n[*] Sending Request - Fetching Commander Index Data ...")
    
    # Constructing payload with dynamic timestamp
    payload = {
        "time": int(time.time()),
        "furniture_data": False
    }
    
    response = client.send_request(API_INDEX, payload)
    
    # 1. Handle local library errors
    if isinstance(response, dict) and "error_local" in response:
        print(f"[-] Local Error: {response['error_local']}")
        print(f"    Raw Response: '{response.get('raw', 'N/A')}'")
        return
        
    # 2. Handle server-side logical errors
    if isinstance(response, dict) and "error" in response:
        print(f"[-] Server Error: {response['error']}")
        return
        
    # 3. Handle successful fetch
    if isinstance(response, dict):
        # Basic validation to ensure we got actual commander data
        user_info = response.get("user_info")
        if user_info:
            print(f"[+] SUCCESS! Retrieved Index Data for UID: {user_info.get('user_id', 'Unknown')}")
            save_json(response, CONFIG["OUTPUT_FILE"])
            return
            
    # 4. Handle unexpected formats
    print(f"[!] Request finished, but response lacks expected data structure.")
    print(f"    Parsed JSON preview: {str(response)[:200]}...")

def print_menu():
    print("\n================= MENU =================")
    print(" -c         : Start Capture Proxy (Get UID/SIGN)")
    print(" -r         : Request 'Index/index' and save to index.json")
    print(" -E         : Exit program")
    print("========================================\n")

if __name__ == '__main__':
    print_menu()
    while True:
        try:
            cmd = input("GFL-INDEX> ").strip()
            if not cmd: continue
            
            cmd_parts = cmd.split()
            cmd_prefix = cmd_parts[0]
            
            if cmd_prefix == '-c':
                if proxy_instance:
                    print("[!] Proxy is already running!")
                    continue
                proxy_instance = GFLProxy(CONFIG["PROXY_PORT"], STATIC_KEY, on_traffic)
                proxy_instance.start()
                set_windows_proxy(True, f"127.0.0.1:{CONFIG['PROXY_PORT']}")
                worker_mode = 'c'
                print(f"[*] Capture Proxy Started on {CONFIG['PROXY_PORT']}. Windows Proxy SET.")
                
            elif cmd_prefix == '-r':
                if worker_mode == 'c' and proxy_instance:
                    print("[*] Stopping Proxy before sending request...")
                    proxy_instance.stop()
                    set_windows_proxy(False)
                    proxy_instance = None
                    time.sleep(1)
                    
                worker_mode = 'r'
                request_index_worker()
                
            elif cmd_prefix == '-E':
                if proxy_instance: proxy_instance.stop()
                set_windows_proxy(False)
                print("[*] Exited cleanly. Windows proxy restored.")
                sys.exit(0)
                
            else:
                print(f"[!] Unknown command: {cmd_prefix}")
                print_menu()
                
        except KeyboardInterrupt:
            print("\n[!] Use '-E' to exit safely!")