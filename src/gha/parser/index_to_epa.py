# src/gha/parser/index_to_epa.py

from .base import BaseParser

class IndexToEpaParser(BaseParser):
    def __init__(self, target_teams: list):
        """
        :param target_teams: List of integers representing team IDs to extract (e.g., [1, 2]).
        """
        # Ensure all elements are integers for safe matching
        self.target_teams = [int(t) for t in target_teams]

    def parse(self, raw_data: dict) -> list:
        print(f"[>] Parsing Index Data for EPA TEAMS: {self.target_teams} ...")
        teams_map = {}

        def get_or_create_team(tid: int):
            if tid not in teams_map:
                teams_map[tid] = {
                    "TEAM_ID": tid,
                    "FAIRY_ID": 0,
                    "GUNS": []
                }
            return teams_map[tid]

        # 1. Process Fairies
        fairies_data = raw_data.get("fairy_with_user_info", {})
        if isinstance(fairies_data, dict):
            for fairy in fairies_data.values():
                team_id = int(fairy.get("team_id", "0"))
                if team_id in self.target_teams:
                    team = get_or_create_team(team_id)
                    team["FAIRY_ID"] = int(fairy.get("id", "0"))

        # 2. Process Guns
        guns_data = raw_data.get("gun_with_user_info", [])
        if isinstance(guns_data, list):
            for gun in guns_data:
                team_id = int(gun.get("team_id", "0"))
                if team_id in self.target_teams:
                    team = get_or_create_team(team_id)
                    team["GUNS"].append({
                        "id": int(gun.get("id", "0")),
                        "life": int(gun.get("life", "0"))
                    })

        # 3. Filter and Sort
        sorted_team_ids = sorted(teams_map.keys())
        final_teams_array = []
        for tid in sorted_team_ids:
            team_data = teams_map[tid]
            if len(team_data["GUNS"]) > 0:
                final_teams_array.append(team_data)
            else:
                print(f"[!] WARNING: EPA_TEAM {tid} has no deployed T-Dolls. Ignoring.")

        print(f"[+] Successfully extracted {len(final_teams_array)} valid EPA echelons.")
        return final_teams_array