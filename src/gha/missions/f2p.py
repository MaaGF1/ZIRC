# src/gha/missions/f2p.py

import time
import json
from .base import BaseMission

from gflzirc import (
    API_MISSION_COMBINFO, API_MISSION_START, API_INDEX_GUIDE,
    API_MISSION_END_TURN, API_MISSION_START_ENEMY_TURN,
    API_MISSION_END_ENEMY_TURN, API_MISSION_START_TURN,
    GUIDE_COURSE_11880
)

class F2PMission(BaseMission):
    def __init__(self, agent):
        super().__init__(agent)
        self.mission_id = 11880

    def get_mission_id(self) -> int:
        return self.mission_id

    def farm(self) -> list:
        squad_id = self.config.get("SQUAD_ID")

        if self.agent.check_step_error(self.agent.safe_request(API_MISSION_COMBINFO, {"mission_id": self.mission_id}, "combinationInfo"), "combinationInfo"): return None
        
        start_payload = {
            "mission_id": self.mission_id, "spots": [],
            "squad_spots": [{"spot_id": 901926, "squad_with_user_id": squad_id, "battleskill_switch": 1}],
            "sangvis_spots": [], "vehicle_spots": [], "ally_spots": [], "mission_ally_spots": [],
            "ally_id": int(time.time())
        }
        
        if self.agent.check_step_error(self.agent.safe_request(API_MISSION_START, start_payload, "startMission"), "startMission"): return None
        if self.agent.check_step_error(self.agent.safe_request(API_INDEX_GUIDE, {"guide": json.dumps({"course": GUIDE_COURSE_11880}, separators=(',', ':'))}, "guide"), "guide"): return None
        time.sleep(0.5)
        if self.agent.check_step_error(self.agent.safe_request(API_MISSION_END_TURN, {}, "endTurn"), "endTurn"): return None
        time.sleep(0.2)
        if self.agent.check_step_error(self.agent.safe_request(API_MISSION_START_ENEMY_TURN, {}, "startEnemyTurn"), "startEnemyTurn"): return None
        time.sleep(0.2)
        if self.agent.check_step_error(self.agent.safe_request(API_MISSION_END_ENEMY_TURN, {}, "endEnemyTurn"), "endEnemyTurn"): return None
        time.sleep(0.2)
        
        final_resp = self.agent.safe_request(API_MISSION_START_TURN, {}, "startTurn")
        if self.agent.check_step_error(final_resp, "startTurn"): return None
        
        return self.agent.check_drop_result(final_resp)