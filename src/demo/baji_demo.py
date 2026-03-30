import time
from gflzirc import GFLClient

# User Config
USER_UID = "_Input_Your_User_ID_"
SIGN_KEY = "Key_From_Monitor" 
BASE_URL = "http://gfcn-game.gw.merge.sunborngame.com/index.php/1000"

def add_target_practice_enemy(client: GFLClient, enemy_id: int, order_id: int):
    # Using GFLClient handles the JSON conversion, encryption, req_id and network requests
    payload = {
        "enemy_team_id": enemy_id,
        "fight_type": 0,
        "fight_coef": "",
        "fight_environment_group": "",
        "order_id": order_id
    }
    
    print(f"[*] Sending Request - Enemy ID: {enemy_id} | Order ID: {order_id} ...", end=" ")
    response = client.send_request("Targettrain/addCollect", payload)
    
    if response.get("success") or "1" in str(response.get("raw", "")):
        print("[ SUCCESS ]")
    else:
        print(f"[ FAIL ] Server returned: {response}")

if __name__ == '__main__':
    # Initialize the reusable client from our ZIRC core library
    client = GFLClient(USER_UID, SIGN_KEY, BASE_URL)
    
    target_enemies = [6519263, 6519225, 6519223, 6519246, 6519206]
    target_orders = [1, 2, 3, 4, 5]
    
    use_custom_orders = (len(target_enemies) == len(target_orders))
    
    if use_custom_orders:
        print("[*] Order list length matches. Using custom order IDs.")
    else:
        print("[!] Order list length mismatch. Using auto-increment sequence.")

    print("[*] Starting Batch Injection with ZIRC Core...")
    
    for idx, enemy in enumerate(target_enemies):
        current_order = target_orders[idx] if use_custom_orders else (idx + 1)
        add_target_practice_enemy(client, enemy, current_order)
        time.sleep(1)
        
    print("[*] All done.")