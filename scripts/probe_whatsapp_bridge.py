import httpx

base = "http://127.0.0.1:39219"
root = httpx.get(f"{base}/", timeout=10).json()
print("root", root)
r = httpx.get(f"{base}/chats", params={"limit": 1}, timeout=120)
print("chats", r.status_code, r.text[:300])
