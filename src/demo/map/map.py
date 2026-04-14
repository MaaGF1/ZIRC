import sys
import time
import os
import json
import threading
import http.server
import socketserver
import webview

from gflzirc import GFLProxy, set_windows_proxy, STATIC_KEY

CONFIG = {
    "PROXY_PORT": 8080,
    "LOCAL_WEB_PORT": 8081,
    "OUTPUT_DIR": "traffic_dumps",
    # Offline mode: access local HTTP service directly
    "TARGET_URL": "http://127.0.0.1:8081/gflmaps/index.html"
}

proxy_instance = None
packet_counter = 1
radar_window = None

# ==============================================================
# 1. Local Lightweight HTTP Server (Provides offline frontend & GFLData JSON)
# ==============================================================
class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Disable local cache to prevent frontend modifications from being ignored
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

def start_local_web_server():
    """Run local HTTP service in background, map root directory to current script directory"""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("127.0.0.1", CONFIG["LOCAL_WEB_PORT"]), NoCacheHTTPRequestHandler) as httpd:
            print(f"[*] Offline Web Server running at http://127.0.0.1:{CONFIG['LOCAL_WEB_PORT']}")
            httpd.serve_forever()
    except Exception as e:
        print(f"[!] Offline Web Server failed to start: {e}")


# ==============================================================
# 2. Core Packet Capture Proxy Logic (Derived from monitor.py)
# ==============================================================
def save_json(content_obj, tag, url=""):
    pass
    # global packet_counter
    # 
    # if not os.path.exists(CONFIG["OUTPUT_DIR"]):
    #     os.makedirs(CONFIG["OUTPUT_DIR"])
    #     
    # timestamp = int(time.time())
    # 
    # endpoint = "unknown"
    # if url and "index.php" in url:
    #     parts = url.split("index.php")
    #     if len(parts) > 1 and parts[1]:
    #         endpoint = parts[1].strip('/').replace('/', '_')
    #         
    # filename = f"{packet_counter:04d}_{tag}_{endpoint}_{timestamp}.json"
    # filepath = os.path.join(CONFIG["OUTPUT_DIR"], filename)
    # 
    # try:
    #     with open(filepath, "w", encoding="utf-8") as f:
    #         json.dump(content_obj, f, indent=4, ensure_ascii=False)
    #     print(f"[+] Saved: {filename}")
    #     packet_counter += 1
    # except Exception as e:
    #     print(f"[!] Error saving file: {e}")

def parse_payload(payload):
    """
    Robust payload parser to prevent json.dump crashes.
    Always returns a dictionary.
    """
    if isinstance(payload, dict):
        return payload
    elif isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception:
            return {"raw_string": payload}
    elif isinstance(payload, bytes):
        try:
            return json.loads(payload.decode('utf-8'))
        except Exception:
            return {"raw_hex": payload.hex()}
    else:
        return {"raw_type": str(type(payload))}

def on_traffic(event_type: str, url: str, data):
    event_upper = str(event_type).upper()
    
    if event_upper == "SYS_KEY_UPGRADE":
        print(f"\n[!] SYSTEM UPGRADE: Sniffed dynamic user keys.")
        if isinstance(data, dict):
            print(f"    New UID  : {data.get('uid')}")
            print(f"    New SIGN : {data.get('sign')}")
        print("[*] Proxy crypto key has been updated automatically.\n")
        
    elif event_upper == "C2S":
        print(f"\n[--> C2S] Captured Request: {url}")
        json_obj = parse_payload(data)
        # save_json(json_obj, "C2S", url)
        
    elif event_upper == "S2C":
        print(f"[<-- S2C] Decrypted Server Response.")
        json_obj = parse_payload(data)
        # save_json(json_obj, "S2C", url)
        
        # Push dynamic map data to radar window (PyWebView)
        if isinstance(json_obj, dict) and "spot_act_info" in json_obj:
            if radar_window:
                try:
                    js_code = f"if(window.updateLiveMap) window.updateLiveMap({json.dumps(json_obj)});"
                    radar_window.evaluate_js(js_code)
                except Exception as e:
                    print(f"[!] WebView JS Execute Error: {e}")
        
    else:
        print(f"\n[?] UNKNOWN/FALLBACK EVENT ({event_type}): {url}")
        json_obj = parse_payload(data)
        # save_json(json_obj, f"UNHANDLED_{event_upper}", url)


# ==============================================================
# 3. CLI Console Logic (Background execution)
# ==============================================================
def print_menu():
    print("\n================= MENU =================")
    print(" -c : Start Network Monitor (MITM)")
    print(" -q : Stop Network Monitor")
    print(" -E : Exit program")
    print("========================================\n")

def cli_loop():
    global proxy_instance
    print_menu()
    # Short delay to prevent input prompt overlapping with Web Server startup prompt
    time.sleep(0.5) 
    
    while True:
        try:
            cmd = input("GFL-MONITOR> ").strip()
            if not cmd: continue
            cmd_prefix = cmd.split()[0]
            
            if cmd_prefix == '-c':
                if proxy_instance:
                    print("[!] Monitor is already running!")
                    continue
                proxy_instance = GFLProxy(CONFIG["PROXY_PORT"], STATIC_KEY, on_traffic)
                proxy_instance.start()
                set_windows_proxy(True, f"127.0.0.1:{CONFIG['PROXY_PORT']}")
                print(f"[*] Network Monitor Started on {CONFIG['PROXY_PORT']}. Windows Proxy SET.")
                # print("[*] All decrypted C2S and S2C traffic will be saved to /traffic_dumps/.")
                
            elif cmd_prefix == '-q':
                if proxy_instance:
                    print("[*] Stopping Network Monitor...")
                    proxy_instance.stop()
                    set_windows_proxy(False)
                    proxy_instance = None
                    print("[*] Monitor stopped safely.")
                else:
                    print("[!] Monitor is not running.")
                
            elif cmd_prefix == '-E':
                print("[*] Exiting cleanly...")
                if proxy_instance:
                    proxy_instance.stop()
                set_windows_proxy(False)
                print("[*] Windows proxy restored.")
                
                # Close GUI window
                if radar_window:
                    radar_window.destroy()
                
                # Force terminate the entire process
                os._exit(0)
                
            else:
                print(f"[!] Unknown command: {cmd_prefix}")
                print_menu()
                
        except KeyboardInterrupt:
            print("\n[!] Use '-E' to exit safely!")


def on_window_closed():
    """Cleanup tasks when WebView window is closed via 'X'"""
    print("\n[*] Window closed via UI. Cleaning up proxy settings and exiting...")
    if proxy_instance:
        proxy_instance.stop()
    set_windows_proxy(False)
    os._exit(0)


# ==============================================================
# 4. Main Entry Point
# ==============================================================
if __name__ == '__main__':
    # Configure PyWebView startup environment to bypass system proxy and access local Web service directly
    os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--proxy-bypass-list=127.0.0.1,localhost'

    # 1. Start local static Web service thread
    web_thread = threading.Thread(target=start_local_web_server, daemon=True)
    web_thread.start()

    # 2. Start CLI interactive thread
    cli_thread = threading.Thread(target=cli_loop, daemon=True)
    cli_thread.start()

    # 3. Launch PyWebView window in main thread
    radar_window = webview.create_window(
        title='GFL Live Radar (Offline Mode)',
        url=CONFIG["TARGET_URL"],
        width=1300,
        height=850
    )
   
    radar_window.events.closed += on_window_closed
    
    # This step blocks the main thread until the window is closed
    webview.start(gui='edgechromium')