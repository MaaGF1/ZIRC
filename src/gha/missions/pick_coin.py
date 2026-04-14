# src/gha/missions/pick_coin.py

import time
import json
from .base import BaseMission

from gflzirc import (
    API_MISSION_COMBINFO, API_MISSION_START, API_INDEX_GUIDE,
    API_MISSION_TEAM_MOVE, API_MISSION_ABORT,
    GUIDE_COURSE_10352
)

class PickCoinMission(BaseMission):
    def __init__(self, agent):
        super().__init__(agent)
        self.mission_id = 10352

    def get_mission_id(self) -> int:
        return self.mission_id

    def farm(self) -> list:
        team_id = self.config.get("TEAM_ID")

        if self.agent.check_step_error(self.agent.safe_request(API_MISSION_COMBINFO, {"mission_id": self.mission_id}, "combinationInfo"), "combinationInfo"): return None
        
        start_payload = {
            "mission_id": self.mission_id, 
            "spots": [{"spot_id": 13280, "team_id": team_id}],
            "squad_spots": [], "sangvis_spots": [], "vehicle_spots": [], 
            "ally_spots": [], "mission_ally_spots": [],
            "ally_id": int(time.time())
        }
        if self.agent.check_step_error(self.agent.safe_request(API_MISSION_START, start_payload, "startMission"), "startMission"): return None
        if self.agent.check_step_error(self.agent.safe_request(API_INDEX_GUIDE, {"guide": json.dumps({"course": GUIDE_COURSE_10352}, separators=(',', ':'))}, "guide"), "guide"): return None
        time.sleep(0.2)

        move1_payload = {
            "person_type": 1, "person_id": team_id,
            "from_spot_id": 13280, "to_spot_id": 13277, "move_type": 1
        }
        if self.agent.check_step_error(self.agent.safe_request(API_MISSION_TEAM_MOVE, move1_payload, "teamMove1"), "teamMove1"): return None
        time.sleep(0.2)

        move2_payload = {
            "person_type": 1, "person_id": team_id,
            "from_spot_id": 13277, "to_spot_id": 13278, "move_type": 1
        }
        move2_resp = self.agent.safe_request(API_MISSION_TEAM_MOVE, move2_payload, "teamMove2")
        if self.agent.check_step_error(move2_resp, "teamMove2"): return None
        
        self.agent.parse_random_node_drop(move2_resp)
        time.sleep(0.2)

        self.agent.safe_request(API_MISSION_ABORT, {"mission_id": self.mission_id}, "missionAbort", max_retries=1)
        time.sleep(0.5)
        
        return []