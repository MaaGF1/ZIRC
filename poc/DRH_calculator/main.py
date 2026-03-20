import frida
import sys
import gzip
import os
import json
import time

# --- Configuration ---
OUTPUT_DIR = "traffic_dumps"
SCORE_FILE = os.path.join("Reign_of_Chaos", "id_score.json")
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
        
        modified = False
        
        # 2. Logic: Full Visibility & Score Calc
        if "night_spots" in json_obj:
            # --- CE Calculation ---
            total_score = 0
            enemy_info = json_obj.get("enemy_instance_info", {})
            for eid in enemy_info:
                team_id = str(enemy_info[eid].get("enemy_team_id", ""))
                total_score += id_score_map.get(team_id, 0)
            
            # Print Total Score in Green (ANSI)
            print(f"\033[92m[>>>] MAP DATA DETECTED! TOTAL ENEMY SCORE: {total_score}\033[0m")
            
            # --- Visibility Modification ---
            all_spot_ids = [spot.get("spot_id") for spot in json_obj["night_spots"] if "spot_id" in spot]
            if all_spot_ids:
                # Add all spots to can_see_spots
                current_seen = set(json_obj.get("can_see_spots", []))
                current_seen.update(all_spot_ids)
                json_obj["can_see_spots"] = list(current_seen)
                modified = True
                print(f"[+] Visibility expanded: {len(all_spot_ids)} spots are now visible.")

        # 3. Save original/modified JSON for logging
        # save_json(json_obj, "S2C_MOD" if modified else "S2C")

        # 4. If modified, re-compress and return
        if modified:
            new_json_str = json.dumps(json_obj, ensure_ascii=False)
            return gzip.compress(new_json_str.encode('utf-8'))
        
    except Exception as e:
        print(f"[!] S2C Logic Error: {e}")
    
    return None

def save_json(content_obj, tag):
    global packet_counter
    timestamp = int(time.time())
    filename = f"{packet_counter:04d}_{tag}_{timestamp}.json"
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(content_obj, f, indent=4, ensure_ascii=False)
        packet_counter += 1
    except Exception as e:
        print(f"[!] Error saving file: {e}")

def on_message(message, data):
    if message['type'] == 'send':
        payload = message['payload']
        msg_id = payload.get('id')

        if msg_id == 'S2C_REQ':
            # This is a synchronous request from JS to process data
            processed_data = process_s2c_logic(data)
            if processed_data:
                # Send back modified data
                script.post({'type': 'S2C_RES', 'status': 'modified'}, processed_data)
            else:
                # Tell JS to use original data
                script.post({'type': 'S2C_RES', 'status': 'original'}, None)

        elif msg_id == 'C2S':
            content = payload.get('content')
            try:
                json_obj = json.loads(content)
                # save_json(json_obj, "C2S")
                print(f"[--> C2S] Request captured and saved.")
            except Exception as e:
                print(f"[!] C2S Parse Error: {e}")

def main():
    global script
    process_name = "GrilsFrontLine.exe"
    load_score_config()
    
    print(f"[*] Attaching to {process_name}...")
    try:
        session = frida.attach(process_name)
    except Exception as e:
        print(f"[!] Attachment failed: {e}")
        return

    with open("hook.js", "r", encoding="utf-8") as f:
        script_code = f.read()

    script = session.create_script(script_code)
    script.on('message', on_message)
    script.load()
    
    print("[*] System active. Listening for traffic...")
    sys.stdin.read()

if __name__ == '__main__':
    main()