# src/gha/parser/base.py

class BaseParser:
    def parse(self, raw_data: dict):
        """
        Takes raw dictionary data and returns processed/filtered structures.
        """
        raise NotImplementedError