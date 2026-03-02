import urllib.request
import json
try:
    with urllib.request.urlopen("http://127.0.0.1:5170/api/library") as response:
        data = json.loads(response.read().decode())
        print(f"Library count: {len(data)}")
        for d in data[:5]:
            print(f"- {d.get('filename')} (taskId: {d.get('task_id')})")
except Exception as e:
    print(f"Error: {e}")
