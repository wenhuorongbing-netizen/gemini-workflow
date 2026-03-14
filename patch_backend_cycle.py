import re

with open('app.py', 'r') as f:
    content = f.read()

cycle_code = """
    # Cycle detection
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])
    if nodes and edges:
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
            return JSONResponse({"error": "Circular dependency detected in workflow diagram."}, status_code=400)
"""

old_block = """    except Exception as e:
        return JSONResponse({"error": f"Invalid JSON payload: {str(e)}"}, status_code=400)"""

if old_block in content and "Cycle detection" not in content:
    content = content.replace(old_block, old_block + cycle_code)

with open('app.py', 'w') as f:
    f.write(content)
