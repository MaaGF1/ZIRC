# src/demo/farm/greyzone/greyzone_halloween.py

import sys
import time
import threading
from gflzirc import (
    GFLClient, GFLProxy, set_windows_proxy,
    SERVERS, STATIC_KEY, DEFAULT_SIGN,
    API_DAILY_RESET_MAP, API_MISSION_COMBINFO, API_MISSION_START,
    API_MISSION_TEAM_MOVE, API_MISSION_ALLY_MYSIDE_MOVE,
    API_MISSION_END_TURN, API_MISSION_START_ENEMY_TURN,
    API_MISSION_END_ENEMY_TURN, API_MISSION_START_TURN,
    API_MISSION_ABORT, API_GUN_RETIRE
)

CONFIG = {
    "USER_UID": "_InputYourID_",
    "SIGN_KEY": DEFAULT_SIGN,
    "BASE_URL": SERVERS["M4A1"],
    "PROXY_PORT": 8080,
    "TEAM_ID": 1,
    "TICKET_TYPE": 1
}

# ==========================================
# Mission Configurations
# ==========================================
MISSION_CONFIGS = {
    580002: {
        "type": "MOVE",
        "start_spot": 78138,
        "route": [78139, 78140, 78141, 78145, 78149, 78153, 78152, 78148, 
                  78147, 78151, 78150, 78146, 78142, 78143, 78144],
        "has_ally_move": True
    },
    580003: {
        "type": "MOVE",
        "start_spot": 78154,
        "route": [78155, 78156, 78157, 78161, 78165, 78169, 78168, 78164, 
                  78160, 78159, 78158, 78162, 78166, 78167, 78163, 78164, 78160],
        "has_ally_move": True
    },
    580004: {
        "type": "MOVE",
        "start_spot": 78170,
        "route": [78171, 78172, 78173, 78177, 78181, 78185, 78184, 78180, 
                  78176, 78175, 78174, 78178, 78182, 78183, 78179, 78175, 78174],
        "has_ally_move": True
    },
    580005: {
        "type": "MOVE",
        "start_spot": 78587,
        "route": [78588, 78592, 78591, 78595, 78599, 78600, 78601,
                  78602, 78598, 78594, 78590, 78589, 78593, 78597, 78596],
        "has_ally_move": True
    }

    # Note: Add 580002, 580003 here when routes are known
}

# ==========================================
# Global State
# ==========================================
current_worker_thread = None
worker_mode = None
proxy_instance = None
stop_macro_flag = False

total_halloween_points = 0


def check_step_error(resp: dict, step_name: str) -> bool:
    if not isinstance(resp, dict):
        print("[-] %s Error: Server returned invalid format." % step_name)
        return True
    if "error_local" in resp:
        print("[-] %s Local Error: %s" % (step_name, resp['error_local']))
        return True
    if "error" in resp:
        print("[-] %s Server Error: %s" % (step_name, resp['error']))
        return True
    return False


def on_traffic(event_type: str, url: str, data: dict):
    if event_type == "SYS_KEY_UPGRADE":
        CONFIG["USER_UID"] = data.get("uid")
        CONFIG["SIGN_KEY"] = data.get("sign")
        print("\n[+] SUCCESS! Keys Auto-Configured:")
        print("    UID  : %s" % CONFIG['USER_UID'])
        print("    SIGN : %s" % CONFIG['SIGN_KEY'])
        print("\n[!] CRITICAL: Please wait for the game to fully load into the Commander Screen!")
        print("[!] Then type '-f' to auto-farm Halloween GreyZone.")


# ==========================================
# Class: MapParser
# ==========================================
class MapParser:
    SPAWN_MAP = {
        "63": ["64", "56"],
        "70": ["62", "69"],
        "64": ["2", "10"], 
        "8": ["16", "7"]
    }

    @classmethod
    def parse(cls, resp: dict) -> list:
        status = resp.get("daily_status_with_user_info", {})
        map_list = resp.get("daily_map_with_user_info", [])
        
        respawn_spot = str(status.get("spot_id"))
        spots = {str(spot.get("spot_id")): spot.get("mission", "") for spot in map_list}
        
        results = []
        
        if respawn_spot in cls.SPAWN_MAP:
            adjacents = cls.SPAWN_MAP[respawn_spot]
            for adj in adjacents:
                mission_str = spots.get(adj, "")
                if not mission_str:
                    continue
                
                # mission_str usually looks like "1:580005,2:12345"
                mission_parts = mission_str.split(",")
                for part in mission_parts:
                    if part.startswith("1:58"):
                        try:
                            m_id = int(part.split(":")[1])
                            results.append({
                                "spot_id": int(adj),
                                "mission_id": m_id
                            })
                        except ValueError:
                            pass
        return results


# ==========================================
# Class Hierarchy: MissionRunner
# ==========================================
class MissionRunner:
    def __init__(self, client: GFLClient, team_id: int, mission_id: int, map_spot_id: int):
        self.client = client
        self.team_id = team_id
        self.mission_id = mission_id
        self.map_spot_id = map_spot_id
        
        cfg = MISSION_CONFIGS.get(mission_id, {})
        self.start_spot = cfg.get("start_spot", 0)
        self.route = cfg.get("route", [])
        self.has_ally_move = cfg.get("has_ally_move", False)

    def run(self):
        raise NotImplementedError("Base run() method must be overridden.")

    def process_win_result(self, resp: dict):
        win_result = resp.get("mission_win_result", {})
        dropped_guns = []
        points = 0
        
        if win_result:
            # Extract Guns
            rg = win_result.get("reward_gun", [])
            for gun in rg:
                gun_uid = int(gun.get("gun_with_user_id"))
                dropped_guns.append(gun_uid)
                print("    [+] Dropped Gun UID: %d" % gun_uid)
            
            # Extract Halloween Points (Item ID: 10736)
            type5_drop = win_result.get("mission_type5_drop", {})
            item_dict = type5_drop.get("item", {})
            points = int(item_dict.get("10736", 0))
            
        return dropped_guns, points


class MissionRunnerMove(MissionRunner):
    def run(self):
        print("[>] Starting Mission %d on Map Spot %d..." % (self.mission_id, self.map_spot_id))
        start_payload = {
            "mission_id": self.mission_id,
            "spots": [],
            "squad_spots": [], 
            "sangvis_spots": [], 
            "vehicle_spots": [],
            "ally_spots": [], 
            "mission_ally_spots": [
                {
                    "spot_id": self.start_spot,
                    "ally_team_id": 78001,
                    "mission_myside_data": {
                        "sangvis": [],
                        "gun": {
                            "1": {"position": 8},
                            "2": {"position": 9},
                            "3": {"position": 7},
                            "4": {"position": 14},
                            "5": {"position": 13}
                        }
                    }
                }
            ],
            "ally_id": int(time.time()),
            "daily_param": {
                "spot_id": self.map_spot_id,
                "ticket_type": CONFIG["TICKET_TYPE"]
            },
            "fight_environment_skill_info": {}
        }
        
        print(start_payload)

        if check_step_error(self.client.send_request(API_MISSION_START, start_payload), "startMission"):
            return None, 0

        # Execute Moves
        curr_spot = self.start_spot
        for step, next_spot in enumerate(self.route, 1):
            print("[>] Step %d: Moving %d -> %d..." % (step, curr_spot, next_spot))
            move_payload = {
                "person_type": 3, "person_id": self.team_id,
                "from_spot_id": curr_spot, "to_spot_id": next_spot, "move_type": 1
            }
            if check_step_error(self.client.send_request(API_MISSION_TEAM_MOVE, move_payload), "teamMove"):
                return None, 0
            curr_spot = next_spot
            time.sleep(0.1)

        # Optional Ally Move
        if self.has_ally_move:
            print("[>] Triggering Ally Move...")
            if check_step_error(self.client.send_request(API_MISSION_ALLY_MYSIDE_MOVE, {}), "allyMove"):
                return None, 0
            time.sleep(0.3)

        # End Sequence
        print("[>] Ending Turn sequence...")
        if check_step_error(self.client.send_request(API_MISSION_END_TURN, {}), "endTurn"): return None, 0
        time.sleep(0.2)
        if check_step_error(self.client.send_request(API_MISSION_START_ENEMY_TURN, {}), "startEnemyTurn"): return None, 0
        time.sleep(0.2)
        if check_step_error(self.client.send_request(API_MISSION_END_ENEMY_TURN, {}), "endEnemyTurn"): return None, 0
        time.sleep(0.2)

        win_resp = self.client.send_request(API_MISSION_START_TURN, {})
        if check_step_error(win_resp, "startTurn"): return None, 0
        
        return self.process_win_result(win_resp)


class MissionRunnerBattle(MissionRunner):
    def run(self):
        print("[!] BATTLE MISSION IS NOT YET IMPLEMENTED. Mission ID: %d" % self.mission_id)
        return None, 0


# ==========================================
# Worker Logic
# ==========================================
def retire_guns(client: GFLClient, gun_uids: list):
    if not gun_uids: 
        return
    print("[*] Submitting %d T-Dolls for Auto-Retire..." % len(gun_uids))
    resp = client.send_request(API_GUN_RETIRE, gun_uids)
    if resp.get("success"): 
        print("[+] Auto-Retire Successful!")
    else: 
        print("[-] Retire Failed: %s" % str(resp))


def halloween_farm_worker():
    global stop_macro_flag, worker_mode, current_worker_thread, total_halloween_points
    
    if CONFIG["SIGN_KEY"] == DEFAULT_SIGN:
        print("[!] SIGN_KEY is default. Run Capture (-c) first!")
        worker_mode, current_worker_thread = None, None
        return

    client = GFLClient(CONFIG["USER_UID"], CONFIG["SIGN_KEY"], CONFIG["BASE_URL"])
    print("=== GFL Halloween GreyZone Auto-Farm Started ===")
    
    attempts = 0
    while not stop_macro_flag:
        attempts += 1
        print("\n[*] Reset Map Attempt %d..." % attempts)
        
        resp = client.send_request(API_DAILY_RESET_MAP, {"difficulty": 3})
        if check_step_error(resp, "resetMap"):
            time.sleep(3)
            continue
            
        targets = MapParser.parse(resp)
        if not targets:
            print("    [-] No valid Halloween found. Retrying...")
            time.sleep(0.1)
            continue
            
        for target in targets:
            m_id = target["mission_id"]
            s_id = target["spot_id"]
            print("\n[+] FOUND HALLOWEEN MISSION! Spot: %d | Mission ID: %d" % (s_id, m_id))
            
            if m_id not in MISSION_CONFIGS:
                print("[!] Mission %d is not configured in MISSION_CONFIGS!" % m_id)
                print("[!] Worker Paused.")
                stop_macro_flag = True
                break
                
            m_type = MISSION_CONFIGS[m_id].get("type")
            if m_type == "MOVE":
                runner = MissionRunnerMove(client, CONFIG["TEAM_ID"], m_id, s_id)
            elif m_type == "BATTLE":
                runner = MissionRunnerBattle(client, CONFIG["TEAM_ID"], m_id, s_id)
            else:
                print("[!] Unknown mission type for %d" % m_id)
                stop_macro_flag = True
                break
                
            dropped_guns, points = runner.run()
            
            if dropped_guns is None:
                print("[-] Run failed or aborted. Worker Paused.")
                stop_macro_flag = True
                break
                
            retire_guns(client, dropped_guns)
            
            total_halloween_points += points
            r_num = total_halloween_points // 6000
            r_rem = total_halloween_points % 6000
            
            print("\n========================================")
            print("[+] Mission Completed! Points Gained: %d" % points)
            print("[+] TOTAL HALLOWEEN POINTS: %d" % total_halloween_points)
            print("[+] Progress: %d/6000 (Completed %d Rounds)" % (r_rem, r_num))
            print("========================================\n")
            
            time.sleep(1)

        if stop_macro_flag:
            break
        
    print("\n[*] Halloween Farm Worker ended.")
    worker_mode, current_worker_thread = None, None


def print_menu():
    print("\n================= MENU =================")
    print(" -c : Start Capture Proxy")
    print(" -f : Run Halloween Auto-Farm")
    print(" -q : Stop safely")
    print(" -E : Exit program")
    print("========================================\n")


def shutdown_proxy_if_running():
    global proxy_instance
    if worker_mode == 'c' and proxy_instance:
        print("[*] Stopping Proxy to begin worker...")
        proxy_instance.stop()
        set_windows_proxy(False)
        proxy_instance = None
        time.sleep(1)


if __name__ == '__main__':
    print_menu()
    while True:
        try:
            cmd = input("GFL-HW-GZ> ").strip()
            if not cmd: continue
            cmd_prefix = cmd.split()[0]
            
            if cmd_prefix == '-c':
                if proxy_instance:
                    print("[!] Proxy is already running!")
                    continue
                proxy_instance = GFLProxy(CONFIG["PROXY_PORT"], STATIC_KEY, on_traffic)
                proxy_instance.start()
                set_windows_proxy(True, "127.0.0.1:%d" % CONFIG['PROXY_PORT'])
                worker_mode = 'c'
                print("[*] Capture Proxy Started on %d. Windows Proxy SET." % CONFIG['PROXY_PORT'])
                
            elif cmd_prefix == '-f':
                shutdown_proxy_if_running()
                stop_macro_flag = False
                worker_mode = 'f'
                current_worker_thread = threading.Thread(target=halloween_farm_worker)
                current_worker_thread.daemon = True
                current_worker_thread.start()
                
            elif cmd_prefix == '-q':
                stop_macro_flag = True
                print("[*] Will stop loop after current execution...")
                
            elif cmd_prefix == '-E':
                if proxy_instance: proxy_instance.stop()
                set_windows_proxy(False)
                stop_macro_flag = True
                print("[*] Exited cleanly. Windows proxy restored.")
                sys.exit(0)
                
        except KeyboardInterrupt:
            print("\n[!] Use '-E' to exit safely!")