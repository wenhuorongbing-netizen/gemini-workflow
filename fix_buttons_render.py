import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# I see it in the previous grep
# 1740-                <button onClick={() => addNode('scraper')} className="...">
# 1741-                <button onClick={() => addNode('webhook')} className="...">
# 1742-                <button onClick={() => addNode('router')} className="...">
# 1743-                <button onClick={() => addNode('approval')} className="...">

# Wait, the screenshot shows "Gemini AI", "Web Scraper", "Upload File", "Agent Loop", "Global State".
# There is a second toolbar! Let's find "Upload File"

print("Looking for Upload File in page.tsx...")
for line in content.split('\n'):
    if "Upload File" in line:
        print(line.strip())
