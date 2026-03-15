import re

with open("test_e2e_engine.py", "r") as f:
    content = f.read()

content = content.replace(
    'def test_circular_dependency():\n        import asyncio\n    with sync_playwright() as p:',
    'def test_circular_dependency():\n    import asyncio\n    with sync_playwright() as p:'
).replace(
    '            page.once("dialog", lambda dialog: asyncio.create_task(dialog.accept("My Test Emtpy Workspace")))\n        page.get_by_text("+ New Workspace").click()',
    '        page.once("dialog", lambda dialog: asyncio.create_task(dialog.accept("My Test Emtpy Workspace")))\n        page.get_by_text("+ New Workspace").click()'
).replace(
    'def test_variable_chaining():\n        import asyncio\n    # Variables:',
    'def test_variable_chaining():\n    import asyncio\n    # Variables:'
)

with open("test_e2e_engine.py", "w") as f:
    f.write(content)
