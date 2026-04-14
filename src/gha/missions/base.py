# src/gha/missions/base.py

class BaseMission:
    def __init__(self, agent):
        """
        Base class for all farming missions.
        :param agent: The GFLAgent instance providing network and state context.
        """
        self.agent = agent
        self.config = agent.config
        
    def get_mission_id(self) -> int:
        """
        Returns the mission ID to be used for aborting if things fail.
        """
        raise NotImplementedError

    def farm(self) -> list:
        """
        Executes one loop of the mission.
        Returns a list of T-Doll UIDs dropped during the mission.
        If it returns None, the agent will trigger an abort and retry.
        """
        raise NotImplementedError