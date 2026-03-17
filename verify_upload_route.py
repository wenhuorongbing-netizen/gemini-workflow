import os

file_path = "app/api/upload/route.ts"
if os.path.exists(file_path):
    print(f"SUCCESS: {file_path} exists.")
else:
    print(f"FAILURE: {file_path} does not exist.")
