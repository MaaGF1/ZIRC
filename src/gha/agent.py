# src/gha/agent.py
import os
import sys
import time
import json
import platform
import types
from datetime import datetime

# Cross-platform compatibility for gflzirc
if platform.system() != "Windows":
    sys.modules["winreg"] = types.ModuleType("winreg")

from gflzirc import (
    GFLClient, SERVERS,
    API_MISSION_COMBINFO, API_MISSION_START, API_INDEX_GUIDE,
    API_MISSION_END_TURN, API_MISSION_START_ENEMY_TURN,
    API_MISSION_END_ENEMY_TURN, API_MISSION_START_TURN,
    API_MISSION_ABORT, API_GUN_RETIRE, API_MISSION_TEAM_MOVE,
    GUIDE_COURSE_11880, GUIDE_COURSE_10352
)

# Constants
MAX_RUNTIME_SEC = 5 * 3600 + 30 * 60  # 5 hours 30 mins
MAX_CONSECUTIVE_ERRORS = 5

class GFLAgent:
    def __init__(self):
        self.start_time = time.time()
        self.total_dolls = 0
        self.macro_count = 0
        self.error_count = 0
        
        # Load Configs
        config_str = os.environ.get("GFL_CONFIG", "{}").strip()
        try:
            self.config = json.loads(config_str)
        except Exception as e:
            print(f"[-] FATAL: Failed to parse GFL_CONFIG JSON. Exception: {e}")
            sys.exit(1)
            
        self.sign_key = os.environ.get("GFL_SIGN_KEY", "").strip().strip('"').strip("'")
        self.mission_type = os.environ.get("GFL_MISSION_TYPE", "f2p")
        
        uid = str(self.config.get("USER_UID", "")).strip()
        server_key = self.config.get("SERVER_KEY", "M4A1")
        self.base_url = SERVERS.get(server_key)
        
        # === CONFIGURATION AUDIT ===
        print("\n================ CONFIGURATION AUDIT ================")
        print(f"[*] Mission Type : {self.mission_type.upper()}")
        
        masked_uid = uid[:-3] + "***" if len(uid) > 3 else "INVALID"
        print(f"[*] USER_UID     : {masked_uid} (Length: {len(uid)})")
        
        if len(self.sign_key) > 12:
            masked_sign = self.sign_key[:8] + "*" * (len(self.sign_key)-12) + self.sign_key[-4:]
            print(f"[*] SIGN_KEY     : {masked_sign} (Length: {len(self.sign_key)})")
        else:
            print(f"[*] SIGN_KEY     : INVALID_OR_TOO_SHORT")
            
        print(f"[*] SERVER_KEY   : {server_key}")
        print(f"[*] BASE_URL     : {self.base_url}")
        print("=====================================================\n")

        if not self.sign_key or not uid or len(self.sign_key) < 12:
            print("[-] FATAL: Missing or Invalid UID / SIGN_KEY.")
            sys.exit(1)
        if not self.base_url:
            print(f"[-] FATAL: Invalid SERVER_KEY: {server_key}.")
            sys.exit(1)
            
        self.client = GFLClient(uid, self.sign_key, self.base_url)

    def write_summary(self, status="Running"):
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if not summary_path:
            return
            
        elapsed = int(time.time() - self.start_time)
        hours, rem = divmod(elapsed, 3600)
        mins, secs = divmod(rem, 60)
        time_str = f"{hours:02d}h {mins:02d}m {secs:02d}s"
        
        content = (
            f"### GFL Auto-Farm Report ({self.mission_type.upper()})\n"
            f"| Metric | Value |\n"
            f"| ------ | ----- |\n"
            f"| **Status** | {status} |\n"
            f"| **Runtime** | {time_str} |\n"
            f"| **Macros Completed** | {self.macro_count} |\n"
            f"| **Total Dolls Dropped** | {self.total_dolls} |\n"
            f"| **Timestamp** | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} |\n"
            f"---\n"
        )
        with open(summary_path, "w") as f:
            f.write(content)

    def safe_request(self, api_endpoint: str, payload: dict, step_name: str, max_retries=3):
        for attempt in range(1, max_retries + 1):
            try:
                resp = self.client.send_request(api_endpoint, payload)
                
                # BUG FIXED: Accept ANY valid parsed JSON (including empty list [])
                if resp is not None:
                    if isinstance(resp, list) and not resp:
                        print(f"[*] {step_name}: Server returned []. (Normal behavior, proceeding)")
                    return resp
                    
            except Exception as e:
                print(f"[-] {step_name}: Exception -> {e}. (Attempt {attempt}/{max_retries})")
            
            if attempt < max_retries:
                time.sleep(3)
                
        return {"error_local": "Max retries reached or empty server response."}

    def check_step_error(self, resp, step_name: str) -> bool:
        if resp is None:
            self.error_count += 1
            return True
            
        # Only check for error strings if the response is actually a dictionary
        if isinstance(resp, dict):
            if "error_local" in resp:
                print(f"[-] {step_name} Local Error: {resp['error_local']}")
                if 'raw' in resp:
                    print(f"[DEBUG] Raw Server Payload: {resp['raw']}")
                self.error_count += 1
                return True
            if "error" in resp:
                print(f"[-] {step_name} Server Error: {resp['error']}")
                self.error_count += 1
                return True
        
        # If it's a list [] or valid dict without errors, we are safe.
        self.error_count = 0
        return False

    def check_drop_result(self, response_data: dict) -> list:
        collected_guns = []
        if not isinstance(response_data, dict):
            return collected_guns
            
        win_result = response_data.get("mission_win_result", {})
        if not win_result: 
            return collected_guns
            
        reward_guns = win_result.get("reward_gun", [])
        if reward_guns:
            for gun in reward_guns:
                gun_id = gun.get('gun_id')
                gun_uid = int(gun.get('gun_with_user_id'))
                print(f"[+] Got T-Doll! Gun ID: {gun_id} | UID: {gun_uid} | Time: {time.strftime('%H:%M:%S')}")
                collected_guns.append(gun_uid)
        return collected_guns

    def parse_random_node_drop(self, resp_data: dict):
        if not isinstance(resp_data, dict):
            return
        keys = list(resp_data.keys())
        try:
            target_idx = keys.index("building_defender_change") - 1
            if target_idx >= 0:
                reward_key = keys[target_idx]
                if reward_key not in ["trigger_para", "mission_win_step_control_ids", "spot_act_info"]:
                    reward_val = resp_data[reward_key]
                    print(f"[+] Random Node Drop Captured -> {reward_key} : {reward_val}")
        except ValueError:
            pass

    def farm_mission_11880(self):
        mission_id = 11880
        squad_id = self.config.get("SQUAD_ID")

        if self.check_step_error(self.safe_request(API_MISSION_COMBINFO, {"mission_id": mission_id}, "combinationInfo"), "combinationInfo"): return None
        
        start_payload = {
            "mission_id": mission_id, "spots": [],
            "squad_spots": [{"spot_id": 901926, "squad_with_user_id": squad_id, "battleskill_switch": 1}],
            "sangvis_spots": [], "vehicle_spots": [], "ally_spots": [], "mission_ally_spots": [],
            "ally_id": int(time.time())
        }
        
        if self.check_step_error(self.safe_request(API_MISSION_START, start_payload, "startMission"), "startMission"): return None
        if self.check_step_error(self.safe_request(API_INDEX_GUIDE, {"guide": json.dumps({"course": GUIDE_COURSE_11880}, separators=(',', ':'))}, "guide"), "guide"): return None
        time.sleep(0.5)
        if self.check_step_error(self.safe_request(API_MISSION_END_TURN, {}, "endTurn"), "endTurn"): return None
        time.sleep(0.2)
        if self.check_step_error(self.safe_request(API_MISSION_START_ENEMY_TURN, {}, "startEnemyTurn"), "startEnemyTurn"): return None
        time.sleep(0.2)
        if self.check_step_error(self.safe_request(API_MISSION_END_ENEMY_TURN, {}, "endEnemyTurn"), "endEnemyTurn"): return None
        time.sleep(0.2)
        
        final_resp = self.safe_request(API_MISSION_START_TURN, {}, "startTurn")
        if self.check_step_error(final_resp, "startTurn"): return None
        
        return self.check_drop_result(final_resp)

    def farm_mission_10352(self):
        mission_id = 10352
        team_id = self.config.get("TEAM_ID")

        if self.check_step_error(self.safe_request(API_MISSION_COMBINFO, {"mission_id": mission_id}, "combinationInfo"), "combinationInfo"): return None
        
        start_payload = {
            "mission_id": mission_id, 
            "spots": [{"spot_id": 13280, "team_id": team_id}],
            "squad_spots": [], "sangvis_spots": [], "vehicle_spots": [], 
            "ally_spots": [], "mission_ally_spots": [],
            "ally_id": int(time.time())
        }
        if self.check_step_error(self.safe_request(API_MISSION_START, start_payload, "startMission"), "startMission"): return None
        if self.check_step_error(self.safe_request(API_INDEX_GUIDE, {"guide": json.dumps({"course": GUIDE_COURSE_10352}, separators=(',', ':'))}, "guide"), "guide"): return None
        time.sleep(0.2)

        move1_payload = {
            "person_type": 1, "person_id": team_id,
            "from_spot_id": 13280, "to_spot_id": 13277, "move_type": 1
        }
        if self.check_step_error(self.safe_request(API_MISSION_TEAM_MOVE, move1_payload, "teamMove1"), "teamMove1"): return None
        time.sleep(0.2)

        move2_payload = {
            "person_type": 1, "person_id": team_id,
            "from_spot_id": 13277, "to_spot_id": 13278, "move_type": 1
        }
        move2_resp = self.safe_request(API_MISSION_TEAM_MOVE, move2_payload, "teamMove2")
        if self.check_step_error(move2_resp, "teamMove2"): return None
        
        self.parse_random_node_drop(move2_resp)
        time.sleep(0.2)

        self.safe_request(API_MISSION_ABORT, {"mission_id": mission_id}, "missionAbort", max_retries=1)
        time.sleep(0.5)
        
        return []

    def retire_guns(self, gun_uids: list):
        if not gun_uids: return
        print(f"[*] Submitting {len(gun_uids)} T-Dolls for Auto-Retire...")
        resp = self.safe_request(API_GUN_RETIRE, gun_uids, "retireGuns")
        if isinstance(resp, dict) and resp.get("success"): 
            print("[+] Auto-Retire Successful!")
        else: 
            print(f"[-] Retire Failed: {resp}")

    def run(self):
        print(f"=== GHA Auto-Farming Started: {self.mission_type.upper()} ===")
        
        macro_target = self.config.get("MACRO_LOOPS", 200)
        micro_target = self.config.get("MISSIONS_PER_RETIRE", 50)
        
        for macro in range(1, macro_target + 1):
            print(f"\n--- MACRO BATCH {macro} / {macro_target} ---")
            batch_guns = []
            
            for micro in range(1, micro_target + 1):
                if self.error_count >= MAX_CONSECUTIVE_ERRORS:
                    print("\n[!] FATAL: Too many consecutive errors. Server WAF blocked or Auth Expired.")
                    self.write_summary(status="FATAL ERROR (Aborted)")
                    sys.exit(1)
                    
                print(f"[*] Micro Run: {micro}/{micro_target}")
                
                if self.mission_type == "f2p":
                    dropped = self.farm_mission_11880()
                    abort_id = 11880
                else:
                    dropped = self.farm_mission_10352()
                    abort_id = 10352
                    
                if dropped is None:
                    self.safe_request(API_MISSION_ABORT, {"mission_id": abort_id}, "missionAbort", max_retries=1)
                    time.sleep(3)
                    continue
                    
                batch_guns.extend(dropped)
                self.total_dolls += len(dropped)
                time.sleep(1)
                
            self.retire_guns(batch_guns)
            self.macro_count += 1
            self.write_summary(status="Running")
            time.sleep(2)
            
            elapsed = time.time() - self.start_time
            if elapsed > MAX_RUNTIME_SEC:
                print(f"\n[!] Time limit reached ({elapsed}s). Preparing to respawn.")
                with open("respawn.flag", "w")