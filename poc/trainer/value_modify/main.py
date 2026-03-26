# god_mod/main.py

import frida
import sys
import os
import time

def on_message(message, data):
    """
    Handle callback messages from Frida JS
    """
    if message['type'] == 'send':
        payload = message.get('payload', {})
        msg_type = payload.get('type') if isinstance(payload, dict) else 'info'
        msg_text = payload.get('payload') if isinstance(payload, dict) else payload
        
        if msg_type == 'error':
            print(f"[Frida Error] {msg_text}")
        elif msg_type == 'info':
            print(f"[Frida] {msg_text}")
        else:
            print(f"[Frida Raw] {message}")
    else:
        print(f"[Frida System] {message}")

def main():
    # Note: Change Name
    process_name = "GrilsFrontLine.exe" 
    print(f"[*] Initializing God Mode... Attaching to process: {process_name}")
    
    session = None
    for i in range(3):
        try:
            session = frida.attach(process_name)
            break
        except Exception as e:
            print(f"[*] Attach retry {i+1}/3: {e}")
            time.sleep(1)
    
    if not session:
        print("[Error] Attach failed! Check if the game is running or requires admin privileges.")
        return

    script_path = "hook.js"
    if not os.path.exists(script_path):
        print(f"[Error] JS script not found: {script_path}")
        return

    with open(script_path, "r", encoding="utf-8") as f:
        script_code = f.read()

    script = session.create_script(script_code)
    script.on('message', on_message)
    script.load()
    
    print("[*] Shield deployed! (Underlying damage calculator hijacked...)")
    print("[*] Listening for battle events... Press Enter to exit.")
    sys.stdin.read()

if __name__ == '__main__':
    main()