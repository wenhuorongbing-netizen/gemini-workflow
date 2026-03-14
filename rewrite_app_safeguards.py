import re

with open("app.py", "r") as f:
    content = f.read()

# Update loop breaking logic
loop_break = """                try:
                    stop_sequence = step.get('stop_sequence', 'FINAL_REVIEW_COMPLETE')
                except Exception:
                    stop_sequence = 'FINAL_REVIEW_COMPLETE'

                for i in range(max_iterations):
                    if cancel_event and cancel_event.is_set():
                        break"""

content = content.replace("""                for i in range(max_iterations):
                    if cancel_event and cancel_event.is_set():
                        break""", loop_break)

check_break = """                    # If Gemini outputs something indicating it's completely done, we break early
                    if stop_sequence in gemini_response:
                        loop_result = gemini_response
                        break"""

content = content.replace("""                    # If Gemini outputs something indicating it's completely done, we could break early
                    if "FINAL_REVIEW_COMPLETE" in gemini_response:
                        loop_result = gemini_response
                        break""", check_break)


# Budget Exhaustion check
# Inside the for loop, we check if we reached the end of the iterations without breaking
budget_exhausted = """                    # 3. Next iteration prompt
                    current_gemini_prompt = f"Jules has finished with the following output/status: {jules_response}\\n\\nPlease review this. If everything is correct and no further coding is needed, reply with '{stop_sequence}'. Otherwise, provide the next set of coding instructions for Jules."
                    loop_result = f"Latest Jules Output: {jules_response}\\nLatest Gemini Review: {gemini_response}"

                else:
                    # If we exit the loop without breaking (budget exhausted)
                    if stream_queue: yield f"data: {{json.dumps({{'step': step_id, 'status': 'Jules Error', 'message': '[SYSTEM] Budget Exceeded: Max Iterations reached without Stop Sequence.', 'screen': 'right'}})}}\\n\\n"
                    loop_result += "\\n\\n[SYSTEM WARNING]: Loop capped at max iterations without receiving the stop sequence."

                await jules_bot.quit()"""

content = re.sub(r"                    # 3\. Next iteration prompt\n                    current_gemini_prompt = f\"Jules has finished with the following output/status: \{jules_response\}\\\\n\\\\nPlease review this\. If everything is correct and no further coding is needed, reply with 'FINAL_REVIEW_COMPLETE'\. Otherwise, provide the next set of coding instructions for Jules\.\"\n                    loop_result = f\"Latest Jules Output: \{jules_response\}\\\\nLatest Gemini Review: \{gemini_response\}\"\n\n                await jules_bot\.quit\(\)", lambda m: budget_exhausted, content)

with open("app.py", "w") as f:
    f.write(content)
