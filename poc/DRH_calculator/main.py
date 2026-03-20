import frida
import sys
import gzip
import os
import json
import time

# --- Configuration ---
OUTPUT_DIR = "traffic_dumps"
SCORE_FILE = os.path.join("table", "ep11.5.reign_of_chaos.json")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

packet_counter = 1
id_score_map = {}

# --- Load Score Reference ---
def load_score_config():
    global id_score_map
    if os.path.exists(SCORE_FILE):
        try:
            with open(SCORE_FILE, "r", encoding="utf-8") as f:
                id_score_map = json.load(f)
            print(f"[*] Loaded score database: {len(id_score_map)} entries.")
        except Exception as e:
            print(f"[!] Failed to load score file: {e}")
    else:
        print(f"[!] Score file not found at: {SCORE_FILE}")

def process_s2c_logic(raw_data):
    """
    Decompress, Modify JSON for visibility, Calculate scores, Re-compress
    """
    try:
        # 1. Decompress
        decompressed_data = gzip.decompress(raw_data)
        json_obj = json.loads(decompressed_data.decode('utf-8'))
        
        # Check if this is a map/battle packet
        if "night_spots" in json_obj:
            print("-" * 55)
            
            # --- Calculate Enemy Efficiency (Score) ---
            total_score = 0
            enemy_info = json_obj.get("enemy_instance_info", {})
            for eid, info in enemy_info.items():
                team_id = str(info.get("enemy_team_id", ""))
                total_score += id_score_map.get(team_id, 0)
            
            # Print with comma separator (e.g., 790,908)
            print(f"\033[92m[>>>] 地图数据到达! 当前敌方总能效 (Score): {total_score:,}\033[0m")
            print("-" * 55)

        # Save unmodified packet for analysis
        # save_json(json_obj, "S2C")

    except Exception as e:
        print(f"[!] S2C Process Error: {e}")

def save_json(content_obj, tag):
    global packet_counter
    timestamp = int(time.time())
    filename = f"{packet_counter:04d}_{tag}_{timestamp}.json"
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(content_obj, f, indent=4, ensure_ascii=False)
        packet_counter += 1
    except:
        pass

def on_message(message, data):
    if message['type'] == 'error':
        print(f"\n[JS Error] {message.get('description')}")
        return

    if message['type'] == 'send':
        payload = message['payload']
        msg_id = payload.get('id')

        if msg_id == 'S2C':
            process_s2c_logic(data)
        elif msg_id == 'C2S':
            pass # Silent C2S to avoid console spam

def main():
    process_name = "GrilsFrontLine.exe" 
    load_score_config()
    
    print(f"[*] Attaching to process: {process_name} ...")
    try:
        session = frida.attach(process_name)
    except Exception as e:
        print(f"[!] Attach failed: {e}")
        return

    if not os.path.exists("hook.js"):
        print("[!] Cannot find hook.js")
        return

    with open("hook.js", "r", encoding="utf-8") as f:
        script_code = f.read()

    script = session.create_script(script_code)
    script.on('message', on_message)
    script.load()
    
    print("[*] Read-Only Mode (Score Calculator) is running. (Press Ctrl+C to exit)")
    sys.stdin.read()

if __name__ == '__main__':
    main()