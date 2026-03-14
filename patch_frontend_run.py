import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

old_event_source = """        const eventSource = new EventSource(`http://127.0.0.1:8000/api/logs/${taskId}`);"""

new_event_source = """        localStorage.setItem('current_task_id', taskId);
        const eventSource = new EventSource(`http://127.0.0.1:8000/api/logs/${taskId}`);"""

if old_event_source in content:
    content = content.replace(old_event_source, new_event_source)
else:
    print("Could not find EventSource line")

old_close = """                    eventSource.close();
                }"""

new_close = """                    localStorage.removeItem('current_task_id');
                    eventSource.close();
                }"""

if old_close in content:
    content = content.replace(old_close, new_close)


with open('app/page.tsx', 'w') as f:
    f.write(content)
