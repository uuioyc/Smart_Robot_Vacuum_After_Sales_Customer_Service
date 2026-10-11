import requests
import json

url = "http://127.0.0.1:8080/api/chat"
payload = {
    "message": "你好",
    "session_id": "test",
    "history": []
}

print("发送请求...")
with requests.post(url, json=payload, stream=True) as r:
    print(f"状态码：{r.status_code}\n")
    for line in r.iter_lines():
        if not line:
            continue
        line = line.decode('utf-8')
        if line.startswith("data: "):
            data = line[6:]
            if data == "[DONE]":
                print("\n[流结束]")
                break
            try:
                obj = json.loads(data)
                print(obj["content"], end="", flush=True)
            except Exception as e:
                print(f"\n解析失败: {data}")