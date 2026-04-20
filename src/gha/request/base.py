# src/gha/request/base.py

class BaseRequest:
    def __init__(self, agent):
        """
        Base class for making raw API requests.
        :param agent: The GFLAgent instance providing network context.
        """
        self.agent = agent

    def fetch(self) -> dict:
        """
        Executes the request and returns the raw parsed JSON dict.
        Must return None on fatal failure.
        """
        raise NotImplementedError