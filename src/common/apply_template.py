import os
import json
import sys

def main():
    if len(sys.argv) < 3:
        print("Usage: python apply_template.py <template.in> <output.file>")
        sys.exit(1)
        
    template_path = sys.argv[1]
    output_path = sys.argv[2]
    
    dir_here = os.path.dirname(os.path.abspath(__file__))
    offsets_json = os.path.join(dir_here, "include", "offsets.json")
    
    if not os.path.exists(offsets_json):
        print(f"[-] offsets.json not found! Run gen_offsets.py first.")
        sys.exit(1)
        
    with open(offsets_json, 'r', encoding='utf-8') as f:
        offsets = json.load(f)
        
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    for key, val in offsets.items():
        content = content.replace(f"@{key}@", str(val))
        
    # Ensure output dir exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print(f"[+] Rendered {output_path} successfully.")

if __name__ == "__main__":
    main()