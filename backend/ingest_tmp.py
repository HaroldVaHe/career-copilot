from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
r = c.post("/api/v1/jobs/ingest", json={"query": "python", "limit": 8, "analyze": False})
print(r.status_code)
for item in r.json()["results"]:
    print(" ", item)
s = c.post("/api/v1/jobs/search", json={"semantic": "backend python kubernetes remoto", "limit": 5}).json()
print("\nTop semántico:")
for it in s["results"]:
    j, m = it["job"], it["match"]
    print(f"  [{m['score'] if m else '--':>5}] {j['title'][:48]:50} {j['company'][:20]:22} {j['source']}")
