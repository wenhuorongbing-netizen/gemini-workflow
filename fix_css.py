import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# Make the toolbar flex-wrap so the buttons don't get cut off on smaller screens.
content = content.replace(
    '<div className="bg-slate-100 border-b border-slate-200 px-6 py-2 flex items-center gap-2 z-10 shadow-sm">',
    '<div className="bg-slate-100 border-b border-slate-200 px-6 py-2 flex flex-wrap items-center gap-2 z-10 shadow-sm">'
)

with open('app/page.tsx', 'w') as f:
    f.write(content)
