import os
import time
import json
import threading
import sys

# Write a dummy workspace
epic_data = {
    "test_epic": {
        "name": "Test Watch",
        "watch_folder": "./watch_test_folder",
        "steps": [{"prompt": "test prompt", "type": "standard"}]
    }
}
with open("epics.json", "w") as f:
    json.dump(epic_data, f)

os.makedirs("./watch_test_folder", exist_ok=True)

# Run server
import subprocess
server = subprocess.Popen([sys.executable, "app.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(3)

# Drop a file
with open("./watch_test_folder/test.md", "w") as f:
    f.write("Hello from watcher!")
time.sleep(3)

server.terminate()
out, err = server.communicate()
out_str = out.decode('utf-8') + err.decode('utf-8')

if "Triggering workflow for workspace test_epic" in out_str:
    print("File watcher test passed!")
else:
    print("Failed!")
    print(out_str)
