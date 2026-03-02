import urllib.request
import json
try:
    with urllib.request.urlopen("http://127.0.0.1:5170/health") as response:
        print(response.read().decode())
except Exception as e:
    print(f"Error: {e}")
