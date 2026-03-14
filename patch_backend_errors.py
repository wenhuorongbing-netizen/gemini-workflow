import re

with open('app.py', 'r') as f:
    content = f.read()

# 1. Stop Task endpoint
stop_task_endpoint = """
@app.post("/stop_task/{task_id}")
async def stop_specific_task(task_id: str):
    task = active_tasks.get(task_id)
    if task:
        task.cancel()
        del active_tasks[task_id]
        if task_id in task_streams:
            await task_streams[task_id].put({"status": "Error", "message": "🚫 Workflow execution manually cancelled by user."})
            # Give it a moment to send the message before removing the queue
            await asyncio.sleep(0.5)
            del task_streams[task_id]
        return {"status": "cancelled", "task_id": task_id}
    return {"status": "not_found", "task_id": task_id}
"""

if "def stop_specific_task" not in content:
    content = content.replace("@app.get(\"/stop\")", stop_task_endpoint + "\n@app.get(\"/stop\")")

# 2. Cycle Detection in compileNodesToSteps
cycle_detection = """
    # Cycle detection using Kahn's algorithm
    in_degree = {node['id']: 0 for node in nodes}
    for edge in edges:
        if edge['target'] in in_degree:
            in_degree[edge['target']] += 1

    queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
    visited_count = 0

    while queue:
        curr = queue.pop(0)
        visited_count += 1
        for edge in edges:
            if edge['source'] == curr:
                target = edge['target']
                if target in in_degree:
                    in_degree[target] -= 1
                    if in_degree[target] == 0:
                        queue.append(target)

    if visited_count != len(nodes):
        raise ValueError("Circular dependency detected in workflow diagram.")
"""

if "Circular dependency detected" not in content:
    content = content.replace(
        "    steps = []",
        cycle_detection + "\n    steps = []"
    )

# 3. Clamp Max Iterations
if "node_data.get('max_iterations', 3)" in content:
    content = content.replace(
        "node_data.get('max_iterations', 3)",
        "max(1, min(10, int(node_data.get('max_iterations', 3))))"
    )

with open('app.py', 'w') as f:
    f.write(content)
