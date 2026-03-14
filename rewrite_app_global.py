import re

with open("app.py", "r") as f:
    content = f.read()

# Update the endpoint to accept global_state
route_mod = """    workspace_id = data.get('workspace_id')
    profile_id = data.get('profile_id', '1')
    run_variables = data.get('run_variables', {})
    global_state = data.get('global_state', {})"""
content = re.sub(r"    workspace_id = data\.get\('workspace_id'\)\n    profile_id = data\.get\('profile_id', '1'\)\n    run_variables = data\.get\('run_variables', \{\}\)", route_mod, content)

route_pass = """    async def sse_wrapper():
        try:
            async for event in run_workflow_engine(steps, workspace_id, stream_queue, profile_id, run_variables, global_state):
                yield event
        finally:"""
content = re.sub(r"    async def sse_wrapper\(\):\n        try:\n            async for event in run_workflow_engine\(steps, workspace_id, stream_queue, profile_id, run_variables\):\n                yield event\n        finally:", route_pass, content)


engine_sig = """async def run_workflow_engine(steps, workspace_id, stream_queue=None, profile_id="1", run_variables=None, global_state=None):
    if run_variables is None:
        run_variables = {}
    if global_state is None:
        global_state = {}"""
content = re.sub(r"async def run_workflow_engine\(steps, workspace_id, stream_queue=None, profile_id=\"1\", run_variables=None\):\n    if run_variables is None:\n        run_variables = \{\}", engine_sig, content)

engine_var_replace = """            step_type = step.get('type', 'standard')
            chat_url = step.get('chat_url', '').strip()
            show_result = step.get('show_result', True)
            system_prompt = step.get('system_prompt', '').strip()

            # Global Context State Injection (Blackboard)
            for g_key, g_val in global_state.items():
                g_tag = f"{{{{GLOBAL_{g_key}}}}}"
                if g_tag in prompt_template:
                    prompt_template = prompt_template.replace(g_tag, g_val)
                if system_prompt and g_tag in system_prompt:
                    system_prompt = system_prompt.replace(g_tag, g_val)"""

content = re.sub(r"            step_type = step\.get\('type', 'standard'\)\n            chat_url = step\.get\('chat_url', ''\)\.strip\(\)\n            show_result = step\.get\('show_result', True\)\n            system_prompt = step\.get\('system_prompt', ''\)\.strip\(\)", engine_var_replace, content)

with open("app.py", "w") as f:
    f.write(content)
