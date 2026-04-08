# src/gha/agent.py
import sys
import platform
import types

# 1. 拦截并伪造 Windows 注册表库，防报错
if platform.system() != "Windows":
    sys.modules["winreg"] = types.ModuleType("winreg")

import socket
# 2. 强制网络请求只走 IPv4 (防 WARP IPv6 被国内云盾拦截)
old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo

import os
import time
import json
from datetime import datetime

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
        
        config_str = os.environ.get("GFL_CONFIG", "{}")
        try:
            self.config = json.loads(config_str)
        except Exception as e:
            print(f"[-] FATAL: Failed to parse GFL_CONFIG JSON. {e}")
            sys.exit(1)
            
        self.sign_key = os.environ.get("GFL_SIGN_KEY", "").strip() # 强制去除可能的换行符/空格
        self.mission_type = os.environ.get("GFL_MISSION_TYPE", "f2p")
        
        if not self.sign_key or not self.config.get("USER_UID"):
            print("[-] FATAL: Missing UID or SIGN_KEY.")
            sys.exit(1)

        # 校验服务器配置
        server_key = self.config.get("SERVER_KEY", "M4A1")
        self.base_url = SERVERS.get(server_key)
        if not self.base_url:
            print(f"[-] FATAL: Invalid SERVER_KEY: {server_key}. Check your GFL_CONFIG secret.")
            sys.exit(1)
            
        print(f"[*] Target Server URL: {self.base_url}")
        
        self.client = GFLClient(
            str(self.config["USER_UID"]), 
            self.sign_key, 
            self.base_url
        )

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
                
                # --- 核心排障 Debug 信息 ---
                raw_type = type(resp)
                raw_len = len(str(resp))
                print(f"[DEBUG] {step_name} Attempt {attempt} | Type: {raw_type} | DataLength: {raw_len}")
                if raw_len < 300: # 如果返回值很短，直接打印出来看是不是报错信息
                    print(f"[DEBUG] Data Content: {resp}")
                
                # 修复: 必须判断 resp 里面真的有数据（不能是空字典 {}）
                if resp: 
                    return resp
                    
                print(f"[-] {step_name}: Request succeed but response is empty/invalid. (Attempt {attempt}/{max_retries})")
            except Exception as e:
                print(f"[-] {step_name}: Exception -> {e}. (Attempt {attempt}/{max_retries})")
            
            if attempt < max_retries:
                time.sleep(3)
                
        return {} # 最终失败返回空字典

    def check_step_error(self, resp: dict, step_name: str) -> bool:
        if not resp:
            print(f"[-] {step_name}: Final failure after retries.")
            self.error_count += 1
            return True
        if "error_local" in resp:
            print(f"[-] {step_name} Local Error: {resp['error_local']}")
            self.error_count += 1
            return True
        if "error" in resp:
            print(f"[-] {step_name} Server Error: {resp['error']}")
            self.error_count += 1
            return True
        
        self.error_count = 0
        return False

    def check_drop_result(self, response_data: dict) -> list:
        collected_guns = []
        win_result = response_data.get("mission_win_result", {})
        if not win_result: 
            return collected_guns
            
        reward_guns = win_result.get("reward_gun", [])
        if reward_guns:
            for gun in reward_guns:
                gun_id = gun.get('gun_id')
                gun_uid = int(gun.get('gun_with_user_id'))
                print(f"[+] Got T-Doll! Gun ID: {gun_id} | UID: {gun_uid}")
                collected_guns.append(gun_uid)
        return collected_guns

    def parse_random_node_drop(self, resp_data: dict):
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
        if not squad_id:
            print("[-] FATAL: SQUAD_ID not set in config.")
            return None

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
        if not team_id:
            print("[-] FATAL: TEAM_ID not set in config.")
            return None

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
        if resp and resp.get("success"): 
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
                    print("\n[!] FATAL: Too many consecutive errors. Aborting.")
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
                print(f"\n[!] Time limit reached ({elapsed}s). Preparing respawn.")
                with open("respawn.flag", "w") as f:
                    f.write("1")
                self.write_summary(status="Timeout Reached - Spawning Next Job")
                sys.exit(0)
                
        print("\n[*] All macros completed gracefully.")
        self.write_summary(status="Completed")

if __name__ == '__main__':
    agent = GFLAgent()
    agent.run()