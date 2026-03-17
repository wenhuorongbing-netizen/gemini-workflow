import os

files_to_check = [
    "app/api/upload/route.ts",
    "agents/pm_agent.py",
    "agents/dev_agent.py"
]

for file_path in files_to_check:
    if not os.path.exists(file_path):
        raise Exception(f"CHEATING DETECTED: {file_path} does not exist!")

    size = os.path.getsize(file_path)
    if size < 300:
        raise Exception(f"CHEATING DETECTED: {file_path} is empty or insufficient! (Size: {size} bytes)")

    print(f"VERIFIED: {file_path} (Size: {size} bytes)")

print("\nSUCCESS: All critical files meet the byte-level anti-cheat protocol.")
