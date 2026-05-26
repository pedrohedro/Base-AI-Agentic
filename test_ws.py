from hyperliquid.info import Info
from hyperliquid.utils import constants
import time

def on_mids(msg):
    print(msg)

info = Info(constants.TESTNET_API_URL, skip_ws=False)
info.subscribe({"type": "allMids"}, on_mids)
time.sleep(3)
info.disconnect_websocket()
