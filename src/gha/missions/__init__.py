from .f2p import F2PMission
from .pick_coin import PickCoinMission

# Route table for mission handlers
MISSION_HANDLERS = {
    "f2p": F2PMission,
    "pick_coin": PickCoinMission
}