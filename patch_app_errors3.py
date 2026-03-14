import re

with open('app.py', 'r') as f:
    content = f.read()

# Let's find compileNodesToSteps and insert cycle detection
if "def compileNodesToSteps" in content:
    print("compileNodesToSteps found")
    parts = content.split("def compileNodesToSteps(nodes, edges):\n")
    if len(parts) > 1:
        cycle_check = """    in_degree = {node['id']: 0 for node in nodes}
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
        new_content = parts[0] + "def compileNodesToSteps(nodes, edges):\n" + cycle_check + parts[1]
        with open('app.py', 'w') as f:
            f.write(new_content)
        print("Patched compileNodesToSteps")
