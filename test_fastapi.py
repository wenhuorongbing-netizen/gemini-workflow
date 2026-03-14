import urllib.request

try:
    resp = urllib.request.urlopen('http://127.0.0.1:8000')
    print("FastAPI is running")
except Exception as e:
    print("FastAPI not running:", e)
