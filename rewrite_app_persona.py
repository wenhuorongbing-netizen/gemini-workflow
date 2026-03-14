import re

with open("app.py", "r") as f:
    content = f.read()

# Update `app.py` to handle system_prompt
persona_logic = """            step_type = step.get('type', 'standard')
            chat_url = step.get('chat_url', '').strip()
            show_result = step.get('show_result', True)
            system_prompt = step.get('system_prompt', '').strip()"""

content = content.replace("            step_type = step.get('type', 'standard')\n            chat_url = step.get('chat_url', '').strip()\n            show_result = step.get('show_result', True)", persona_logic)


# We need to prepend system_prompt to the prompt if it's standard or agentic loop
system_injection_standard = """                            final_prompt = prompt_template
                            if system_prompt:
                                final_prompt = f"System Instructions / Persona:\\n{system_prompt}\\n\\nUser Request:\\n{final_prompt}"

                            for past_id, past_output in results.items():"""
content = content.replace("""                            final_prompt = prompt_template
                            for past_id, past_output in results.items():""", system_injection_standard)


system_injection_loop = """                loop_result = ""
                current_gemini_prompt = prompt_template
                if system_prompt:
                    current_gemini_prompt = f"System Instructions / Persona:\\n{system_prompt}\\n\\nTask:\\n{current_gemini_prompt}"

                if stream_queue: yield f"data: {{json.dumps({{'step': step_id, 'status': 'Agent Loop Started', 'message': 'Initializing Dual-Bot Engine...'}})}}\\n\\n\""""
content = content.replace("""                loop_result = ""
                current_gemini_prompt = prompt_template

                if stream_queue: yield f"data: {json.dumps({'step': step_id, 'status': 'Agent Loop Started', 'message': 'Initializing Dual-Bot Engine...'})}\\n\\n\"""", system_injection_loop)


with open("app.py", "w") as f:
    f.write(content)
