import os
import json
import sys

DIR_HERE = os.path.dirname(os.path.abspath(__file__))
INC_DIR = os.path.join(DIR_HERE, "include")

INI_PATH = os.path.join(INC_DIR, "offsets.ini.json")
SCRIPT_PATH = os.path.join(INC_DIR, "script.json")
OUT_PATH = os.path.join(INC_DIR, "offsets.json")

def load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[-] Failed to parse {path}: {e}")
        return None

def main():
    print("[*] Generating absolute offsets map...")
    
    schema = load_json(INI_PATH)
    if not schema:
        print(f"[-] Fatal: Schema file {INI_PATH} missing.")
        sys.exit(1)

    script_data = load_json(SCRIPT_PATH)
    il2cpp_methods = script_data.get("ScriptMethod", []) if script_data else []
    
    if not script_data:
        print("[!] script.json not found or invalid. Using FALLBACK values from schema. (CI Mode)")

    final_offsets = {}
    
    for ph_name, config in schema.items():
        target_sig = config.get("sig", "")
        fallback_val = config.get("val", 0)
        found_val = None
        
        # Search exact match in script.json
        for method in il2cpp_methods:
            if method.get("Signature", "") == target_sig:
                found_val = method.get("Address")
                break
        
        # Determine final value
        if found_val is not None:
            final_offsets[ph_name] = found_val
            print(f"    [+] {ph_name:<25} : {found_val} (DUMP)")
        else:
            final_offsets[ph_name] = fallback_val
            print(f"    [-] {ph_name:<25} : {fallback_val} (FALLBACK)")

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(final_offsets, f, indent=4)
        
    print(f"[+] Offsets map written to {OUT_PATH}")

if __name__ == "__main__":
    main()