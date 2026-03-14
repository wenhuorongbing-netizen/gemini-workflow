import urllib.request
import json
import time

payload = {
    "steps": [{"id": "1", "type": "python", "prompt": "output = 'Hello async world'"}],
    "workspace_id": "test_ws"
}

req = urllib.request.Request("http://localhost:5000/execute", data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as response:
        resp_data = response.read().decode('utf-8')
        print(response.status, resp_data)
        data = json.loads(resp_data)
        task_id = data.get("task_id")

    if task_id:
        print(f"GET /api/logs/{task_id}")
        req2 = urllib.request.Request(f"http://localhost:5000/api/logs/{task_id}")
        with urllib.request.urlopen(req2) as response2:
            for line in response2:
                if line:
                    print(line.decode('utf-8').strip())
except Exception as e:
    print(f"Error: {e}")
