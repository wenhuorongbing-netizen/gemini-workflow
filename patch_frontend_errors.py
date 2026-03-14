import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

url_search = 'placeholder="https://example.com"'

if url_search in content:
    print("Found url search string.")

    parts = content.split('<input')
    for i, part in enumerate(parts):
        if url_search in part:
            parts[i] = part.replace(
                'className="w-full bg-slate-900 border border-slate-700 rounded-md p-2 text-sm text-slate-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"',
                '''className={`w-full bg-slate-900 border rounded-md p-2 text-sm text-slate-300 focus:outline-none ${
                        (node.data.url && !(node.data.url as string).startsWith('http://') && !(node.data.url as string).startsWith('https://'))
                        ? 'border-red-500 focus:ring-1 focus:ring-red-500'
                        : 'border-slate-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500'
                    }`}'''
            )
            parts[i] = parts[i].replace('/>', '/>\n                  {(node.data.url && !(node.data.url as string).startsWith(\'http://\') && !(node.data.url as string).startsWith(\'https://\')) && (\n                      <div className="text-xs text-red-500 mt-1 flex items-center gap-1">\n                          <AlertCircle size={12}/> ⚠️ Must start with http:// or https://\n                      </div>\n                  )}')

    content = '<input'.join(parts)


stop_search = 'Stop Execution'
if stop_search in content:
    print("Found stop search string.")

    parts = content.split('<button')
    for i, part in enumerate(parts):
        if stop_search in part:
            parts[i] = part.replace(
                'onClick={async () => {\n                                        try {\n                                            await fetch("http://127.0.0.1:8000/stop");\n                                        } catch (e) {}\n                                    }}',
                '''onClick={async () => {
                                        try {
                                            const taskId = localStorage.getItem('current_task_id');
                                            if (taskId) {
                                                await fetch(`http://127.0.0.1:8000/stop_task/${taskId}`, { method: 'POST' });
                                            } else {
                                                await fetch("http://127.0.0.1:8000/stop");
                                            }
                                            setIsExecuting(false);
                                        } catch (e) {}
                                    }}'''
            )
            parts[i] = parts[i].replace('> Stop Execution', '> ⏹ Stop Workflow')

    content = '<button'.join(parts)


with open('app/page.tsx', 'w') as f:
    f.write(content)
