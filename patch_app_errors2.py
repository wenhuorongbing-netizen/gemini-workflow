import re

with open('app.py', 'r') as f:
    content = f.read()

cycle_code = """def compileNodesToSteps(nodes, edges):
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
    if visited_count != len(nodes) and len(nodes) > 0:
        raise ValueError("Circular dependency detected in workflow diagram.")
"""

if "def compileNodesToSteps(nodes, edges):" in content:
    content = content.replace("def compileNodesToSteps(nodes, edges):", cycle_code)

# Add stop_task endpoint
stop_endpoint = """
@app.post("/stop_task/{task_id}")
async def stop_specific_task(task_id: str):
    task = active_tasks.get(task_id)
    if task:
        task.cancel()
        del active_tasks[task_id]
        if task_id in task_streams:
            await task_streams[task_id].put({"status": "Error", "message": "🚫 Workflow execution manually cancelled by user."})
            await asyncio.sleep(0.5)
        return {"status": "cancelled", "task_id": task_id}
    return {"status": "not_found", "task_id": task_id}
"""
if "@app.get(\"/stop\")" in content and "stop_specific_task" not in content:
    content = content.replace("@app.get(\"/stop\")", stop_endpoint + "\n@app.get(\"/stop\")")

# Clamp max_iterations
content = re.sub(r"node_data\.get\('max_iterations',\s*3\)", r"max(1, min(10, int(node_data.get('max_iterations', 3))))", content)
content = re.sub(r"int\(node_data\.get\('max_iterations',\s*3\)\)", r"max(1, min(10, int(node_data.get('max_iterations', 3))))", content)

with open('app.py', 'w') as f:
    f.write(content)
