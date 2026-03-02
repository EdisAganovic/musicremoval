import urllib.request
import json
try:
    with urllib.request.urlopen("http://127.0.0.1:5170/api/library") as response:
        data = json.loads(response.read().decode())
        print(json.dumps(data[0], indent=2))
except Exception as e:
    print(f"Error: {e}")
