import re

with open('app.py', 'r') as f:
    content = f.read()

import google.generativeai as genai

print("genai" in content)
