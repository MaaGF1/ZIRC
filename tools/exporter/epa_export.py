# tools/exporter

import os
import json

# ==========================================
# CONSTANTS & CONFIGURATION
# ==========================================
INPUT_JSON_PATH = "index.json"
OUTPUT_JSON_PATH = "GFL_EPA_CONFIG.json"

DEFAULT_SERVER_KEY = "M4A1"
DEFAULT_MACRO_LOOPS = 9999
DEFAULT_MISSIONS_PER_RETIRE = 10

def main():
    print(f"[*] Starting GFL EPA Config Exporter...")
    
    if not os.path.exists(INPUT_JSON_PATH):
        print(f"[-] FATAL: Input file '{INPUT_JSON_PATH}' not found in the current directory.")
        return

    # 1. Load the raw index.json
    try:
        with open(INPUT_JSON_PATH, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        print(f"[-] FATAL: Failed to parse '{INPUT_JSON_PATH}'. Exception: {e}")
        return

    # 2. Extract User UID
    user_uid = str(raw_data.get("user_info", {}).get("user_id", ""))
    if not user_uid:
        print("[-] WARNING: Could not find 'user_id' in user_info. UID will be empty.")

    # 3. Initialize the temporary dictionary mapping TEAM_ID to team data
    # Format: { team_id_int: {"FAIRY_ID": 0, "GUNS": []} }
    teams_map = {}

    def get_or_create_team(tid: int):
        if tid not in teams_map:
            teams_map[tid] = {
                "TEAM_ID": tid,
                "FAIRY_ID": 0,
                "GUNS": []
            }
        return teams_map[tid]

    # 4. Process Fairies
    # fairy_with_user_info is a dict: { "fairy_uid": { ... } }
    fairies_data = raw_data.get("fairy_with_user_info", {})
    if isinstance(fairies_data, dict):
        for fairy in fairies_data.values():
            team_id = int(fairy.get("team_id", "0"))
            if 1 <= team_id <= 14:
                team = get_or_create_team(team_id)
                team["FAIRY_ID"] = int(fairy.get("id", "0"))

    # 5. Process Guns (T-Dolls)
    # gun_with_user_info is a list: [ { ... }, { ... } ]
    guns_data = raw_data.get("gun_with_user_info", [])
    if isinstance(guns_data, list):
        for gun in guns_data:
            team_id = int(gun.get("team_id", "0"))
            if 1 <= team_id <= 14:
                team = get_or_create_team(team_id)
                team["GUNS"].append({
                    "id": int(gun.get("id", "0")),
                    "life": int(gun.get("life", "0"))
                })

    # 6. Sort and Filter valid TEAMS
    # We sort by TEAM_ID (ascending order)
    sorted_team_ids = sorted(teams_map.keys())
    
    final_teams_array = []
    for tid in sorted_team_ids:
        team_data = teams_map[tid]
        # Only export echelons that actually have dolls in them
        if len(team_data["GUNS"]) > 0:
            final_teams_array.append(team_data)

    print(f"[+] Successfully extracted {len(final_teams_array)} valid combat echelons.")

    # 7. Assemble final configuration
    final_config = {
        "USER_UID": user_uid,
        "SERVER_KEY": DEFAULT_SERVER_KEY,
        "MACRO_LOOPS": DEFAULT_MACRO_LOOPS,
        "MISSIONS_PER_RETIRE": DEFAULT_MISSIONS_PER_RETIRE,
        "TEAMS": final_teams_array
    }

    # 8. Export to file (Pretty-Printed)
    try:
        with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(final_config, f, indent=4)
        print(f"[+] Configuration successfully saved to '{OUTPUT_JSON_PATH}'.")
        print(f"[*] Remember to minify (remove newlines) before pasting into GitHub Secrets!")
    except Exception as e:
        print(f"[-] FATAL: Failed to write output file. Exception: {e}")

if __name__ == "__main__":
    main()