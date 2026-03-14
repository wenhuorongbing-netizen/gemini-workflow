import re

with open('app.py', 'r') as f:
    content = f.read()

# Make sure we add cycle detection early in compileNodesToSteps
cycle_block = """
def compileNodesToSteps(nodes, edges):
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

if "def compileNodesToSteps" in content and "Cycle detection" not in content:
    content = content.replace("def compileNodesToSteps(nodes, edges):", cycle_block)

with open('app.py', 'w') as f:
    f.write(content)
