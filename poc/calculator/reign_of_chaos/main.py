import frida
import sys
import gzip
import os
import json
import time

# --- Configuration ---
OUTPUT_DIR = "traffic_dumps"
SCORE_FILE = os.path.join("res", "table.json")
INTEREST_FILE = os.path.join("res", "interest.json")
EFFICIENCY_COEFFICIENT = 0.1

# --- ANSI Color Codes (Strictly ASCII) ---
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

packet_counter = 1
id_score_map = {}
interest_map = {}

# --- Load Configs ---
def load_configs():
    global id_score_map, interest_map
    
    # Load Table (Scores)
    if os.path.exists(SCORE_FILE):
        try:
            with open(SCORE_FILE, "r", encoding="utf-8") as f:
                id_score_map = json.load(f)
            print(f"[*] Loaded score database: {len(id_score_map)} entries.")
        except Exception as e:
            print(f"[!] Failed to load score file: {e}")
    else:
        print(f"[!] Score file not found at: {SCORE_FILE}")

    # Load Interest List
    if os.path.exists(INTEREST_FILE):
        try:
            with open(INTEREST_FILE, "r", encoding="utf-8") as f:
                interest_map = json.load(f)
            print(f"[*] Loaded interest database: {len(interest_map)} categories.")
        except Exception as e:
            print(f"[!] Failed to load interest file: {e}")
    else:
        print(f"[!] Interest file not found at: {INTEREST_FILE}")

def process_s2c_logic(raw_data):
    try:
        # 1. Decompress
        decompressed_data = gzip.decompress(raw_data)
        json_obj = json.loads(decompressed_data.decode('utf-8'))
        
        # Check if this is a map/battle packet
        if "night_spots" in json_obj:

            # --- Extract Current Score ---
            current_score_str = json_obj.get("type5_score", "0")
            try:
                current_score = int(current_score_str)
            except ValueError:
                current_score = 0
            
            # --- Initialize Trackers ---
            total_efficiency = 0
            unknown_team_ids = set()
            
            # Pre-fill interest counters with 0 based on JSON keys
            interest_counts = {key: 0 for key in interest_map.keys()}
            
            # --- Iterate Enemy Info ---
            enemy_info = json_obj.get("enemy_instance_info", {})
            for eid, info in enemy_info.items():
                team_id = str(info.get("enemy_team_id", ""))
                
                # 1. Calculate Score & Track Unknowns
                if team_id in id_score_map:
                    total_efficiency += id_score_map[team_id]
                else:
                    if team_id:
                        unknown_team_ids.add(team_id)
                        
                # 2. Track Interests
                if team_id:
                    for interest_name, id_list in interest_map.items():
                        if team_id in id_list:
                            interest_counts[interest_name] += 1
                
            # --- Calculate Predicted Score ---
            predicted_score = int(current_score + (total_efficiency * EFFICIENCY_COEFFICIENT))
            
            # --- Console Output ---
            print("-" * 55)
            print("[*] Map Data Received!")
            print(f"    Current Score          : {current_score:,}")
            print(f"    Total Enemy Efficiency : {total_efficiency:,}")
            print(f"    Predicted Score        : {predicted_score:,}")
            
            # Print Interest List (Highlighted in Yellow)
            print(f"{COLOR_YELLOW}[*] Interest List:{COLOR_RESET}")
            for i_name, count in interest_counts.items():
                print(f"{COLOR_YELLOW}    \"{i_name}\": {count}{COLOR_RESET}")
            
            # Print Unknown IDs (Highlighted in Red)
            if unknown_team_ids:
                print(f"{COLOR_RED}[*] unknown ID:{COLOR_RESET}")
                for uid in sorted(unknown_team_ids):
                    print(f"{COLOR_RED}    {uid}{COLOR_RESET}")
                    
            print("-" * 55)

        # Optional: Save unmodified packet for analysis
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
            pass

def main():
    process_name = "GrilsFrontLine.exe" 
    load_configs()
    
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