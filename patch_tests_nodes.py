import sys

with open('test_e2e_engine.py', 'r') as f:
    content = f.read()

# For test_circular_dependency, add 3 gemini nodes
replacement_circ = """
        # Add 2 nodes manually
        page.locator("button").filter(has_text="Gemini AI").first.click()
        page.wait_for_timeout(500)
        page.locator("button").filter(has_text="Gemini AI").first.click()
        page.wait_for_timeout(500)

        nodes = page.locator(".react-flow__node").all()
        node_1 = nodes[0]
        node_2 = nodes[1]
"""

# For test_variable_chaining
replacement_var = """
        # Add 2 nodes manually
        page.locator("button").filter(has_text="Gemini AI").first.click()
        page.wait_for_timeout(500)
        page.locator("button").filter(has_text="Gemini AI").first.click()
        page.wait_for_timeout(500)

        nodes = page.locator(".react-flow__node").all()
        node_1 = nodes[0]
        node_2 = nodes[1]
"""

import re
content = re.sub(r'# Removed Load Starter Workflow click\n\s*page\.wait_for_timeout\(1000\)\n\n\s*nodes = page\.locator\("\.react-flow__node"\)\.all\(\)\n\s*node_1 = nodes\[1\]\n\s*node_2 = nodes\[2\]', replacement_circ, content)

with open('test_e2e_engine.py', 'w') as f:
    f.write(content)
