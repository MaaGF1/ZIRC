import os
import sys
import shutil
import subprocess

DIR_HERE = os.path.dirname(os.path.abspath(__file__))
COMMON_DIR = os.path.join(DIR_HERE, "..", "common")
APPLY_SCRIPT = os.path.join(COMMON_DIR, "apply_template.py")

SRC_DIR = os.path.join(DIR_HERE, "src")
BUILD_DIR = os.path.join(DIR_HERE, "..", "build", "python")

def main():
    print("[*] Building Python Artifacts...")
    os.makedirs(BUILD_DIR, exist_ok=True)
    
    # 1. Render JS template
    js_in = os.path.join(SRC_DIR, "hook_mitm.js.in")
    js_out = os.path.join(BUILD_DIR, "hook_mitm.js")
    
    subprocess.check_call([sys.executable, APPLY_SCRIPT, js_in, js_out])
    
    # 2. Copy main.py
    shutil.copy2(os.path.join(SRC_DIR, "main.py"), os.path.join(BUILD_DIR, "main.py"))
    
    print(f"[+] Python Build done. Artifacts at: {BUILD_DIR}")
    # Note: PyInstaller invocation can be added here in the future.

if __name__ == "__main__":
    main()