import hashlib
import base64
import time
import requests
import urllib.parse

# ==========================================
# Basic
# ==========================================

def md5(text: str) -> str:
    """Helper function for MD5 hashing"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def gf_authcode(string: str, operation: str = 'ENCODE', key: str = '', expiry: int = 3600) -> str:
    """
    100% Accurate Girls' Frontline Custom AuthCode Algorithm
    Based on static analysis of AC.AuthCode$$Authcode (0x181B06A50)
    """
    # 1. Basic (Same with Discuz)
    key_hash = md5(key)
    keya = md5(key_hash[0:16])
    keyb = md5(key_hash[16:32])
    
    # 2. Diff(1&2): Delete salt, then cryptkey = keyb + MD5(keyb)
    cryptkey = keyb + md5(keyb)
    key_length = len(cryptkey)
    
    if operation == 'DECODE':
        try:
            # Complete the equals sign for Base64
            b64_str = string + "=" * ((4 - len(string) % 4) % 4)
            string_bytes = base64.b64decode(b64_str)
        except Exception:
            return ""
    else:
        # Timeout (Always 3600 due to src code)
        expiry_time = (expiry + int(time.time())) if expiry > 0 else 0
        header = f"{expiry_time:010d}"
        
        # 3. Diff(3): checksum = MD5(string + keya), not keyb
        checksum = md5(string + keya)[0:16]
        
        # Payload: 10-bit time + 16-bit checksum + plaintext
        payload = header + checksum + string
        string_bytes = payload.encode('utf-8')

    # 4. RC4 encryption
    string_length = len(string_bytes)
    result = bytearray()
    box = list(range(256))
    rndkey = [ord(cryptkey[i % key_length]) for i in range(256)]
    
    j = 0
    for i in range(256):
        j = (j + box[i] + rndkey[i]) % 256
        box[i], box[j] = box[j], box[i]
        
    a = j = 0
    for i in range(string_length):
        a = (a + 1) % 256
        j = (j + box[a]) % 256
        box[a], box[j] = box[j], box[a]
        result.append(string_bytes[i] ^ box[(box[a] + box[j]) % 256])
        
    # 5. Result
    if operation == 'DECODE':
        try:
            res_str = bytes(result)
            ext_time = int(res_str[0:10])
            # If it has expired
            if (ext_time == 0 or ext_time - int(time.time()) > 0):
                ext_checksum = res_str[10:26].decode('utf-8')
                ext_text = res_str[26:].decode('utf-8')
                # MD5 Checksum
                if ext_checksum == md5(ext_text + keya)[0:16]:
                    return ext_text
            return ""
        except:
            return ""
    else:
        # Base64 directly, without any prefix
        return base64.b64encode(bytes(result)).decode('utf-8')

# ==========================================
# APIs
# ==========================================
def add_target_practice_enemy(uid: str, sign_key: str, enemy_id: int, req_idx: int):
    json_payload = f'{{"enemy_team_id":{enemy_id},"fight_type":0,"fight_coef":"","fight_environment_group":"","order_id":1}}'
    
    # Call encrypted(GFL)
    encrypted_payload = gf_authcode(json_payload, 'ENCODE', sign_key)
    
    # Construct req_id
    timestamp = int(time.time())
    req_id = f"{timestamp}000{req_idx}"
    
    payload_data = {
        "uid": uid,
        "outdatacode": encrypted_payload,
        "req_id": req_id
    }
    
    url = "http://gfcn-game.gw.merge.sunborngame.com/index.php/1000/Targettrain/addCollect"
    headers = {
        "User-Agent": "UnityPlayer/2018.4.36f1 (UnityWebRequest/1.0, libcurl/7.52.0-DEV)",
        "X-Unity-Version": "2018.4.36f1"
    }
    
    print(f"[*] Sending Request for Enemy ID: {enemy_id} ...", end=" ")
    try:
        response = requests.post(url, headers=headers, data=payload_data, timeout=10)
        if "1" in response.text:
            print("[ SUCCESS ]")
        else:
            print(f"[ FAIL ] Server returned: {response.text.strip()}")
    except Exception as e:
        print(f"[-] Request Failed: {e}")

if __name__ == '__main__':
    
    # User Config
    USER_UID = "_Input_Your_User_ID_"
    SIGN_KEY = "Key_From_Monitor" 

    # TeamID List
    target_enemies = [6519263, 6519225, 6519223, 6519246, 6519206]
    
    print("[*] Starting Batch Injection (Python Standalone)...")
    for idx, enemy in enumerate(target_enemies):
        add_target_practice_enemy(USER_UID, SIGN_KEY, enemy, idx)
        # sleep interval
        time.sleep(1)
    print("[*] All done.")