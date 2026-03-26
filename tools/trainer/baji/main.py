import frida
import sys
import gzip
import os
import json
import time

OUTPUT_DIR = "traffic_dumps"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

packet_counter = 1

def save_json(content_obj, tag):
    global packet_counter
    timestamp = int(time.time())
    filename = f"{packet_counter:04d}_{tag}_{timestamp}.json"
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(content_obj, f, indent=4, ensure_ascii=False)
        print(f"[+] Saved: {filename}")
        packet_counter += 1
    except Exception as e:
        print(f"[!] Error saving file: {e}")

def on_message(message, data):
    if message['type'] == 'send':
        payload = message['payload']
        msg_id = payload.get('id')

        if msg_id == 'LOG':
            print(f"[*] {payload.get('content')}")
            return
        if msg_id == 'ERROR':
            print(f"[!] {payload.get('content')}")
            return

        # --- S2C ---
        if msg_id == 'S2C':
            print(f"\n[<-- S2C] Received Gzip Data: {len(data)} bytes")
            try:
                decompressed_data = gzip.decompress(data)
                json_str = decompressed_data.decode('utf-8')
                json_obj = json.loads(json_str)
                save_json(json_obj, "S2C")
            except Exception as e:
                print(f"[!] S2C Decompression/Parse Error: {e}")
                with open(os.path.join(OUTPUT_DIR, f"error_s2c_{packet_counter}.gz"), "wb") as f:
                    f.write(data)

        # --- C2S ---
        elif msg_id == 'C2S':
            content = payload.get('content')
            print(f"\n[--> C2S] Captured Request: {len(content)} chars")
            try:
                json_obj = json.loads(content)
                save_json(json_obj, "C2S")
            except Exception as e:
                print(f"[!] C2S Parse Error: {e}")

    # Catch
    elif message['type'] == 'error':
        print(f"[JS EXCEPTION] {message.get('description', 'Unknown')}")

def main():
    process_name = "GrilsFrontLine.exe"
    print(f"[*] Attaching to process: {process_name} ...")
    try:
        session = frida.attach(process_name)
    except Exception as e:
        print(f"[!] Failed to attach: {e}")
        return

    if not os.path.exists("hook_dual.js"):
        print("[!] Error: hook_dual.js not found.")
        return

    with open("hook_dual.js", "r", encoding="utf-8") as f:
        script_code = f.read()

    script = session.create_script(script_code)
    script.on('message', on_message)
    script.load()
    
    print("[*] Python Controller Started.")
    print("[*] Press Ctrl+C to stop.")
    sys.stdin.read()

if __name__ == '__main__':
    main()