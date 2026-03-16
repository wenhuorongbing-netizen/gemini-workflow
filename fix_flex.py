import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# Make the toolbar flex-wrap so the buttons don't get cut off on smaller screens.
content = content.replace(
    '<div className="bg-slate-100 border-b border-slate-200 px-6 py-2 flex items-center gap-2 z-10 shadow-sm overflow-x-auto">',
    '<div className="bg-slate-100 border-b border-slate-200 px-6 py-2 flex flex-wrap items-center gap-2 z-10 shadow-sm">'
)

# wait let's just use regex to replace it
content = re.sub(r'<div className="bg-slate-100 border-b border-slate-200 px-6 py-2 flex[^>]*>', '<div className="bg-slate-100 border-b border-slate-200 px-6 py-2 flex flex-wrap items-center gap-2 z-10 shadow-sm">', content)

with open('app/page.tsx', 'w') as f:
    f.write(content)
