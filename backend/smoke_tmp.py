import io, json
from fastapi.testclient import TestClient
from app.main import app

CV = """Ana Vargas
Backend Engineer
ana.vargas@example.com | +34 600 123 456 | Madrid, España
linkedin.com/in/anavargas | github.com/anavargas

RESUMEN
Ingeniera backend con 5 años construyendo APIs en Python y Go.

EXPERIENCIA
Senior Backend Engineer - Fintech SA (2021-01 - present)
• Lideré la migración de un monolito Django a microservicios en Kubernetes, reduciendo el p99 de 800ms a 180ms
• Diseñé la capa de eventos con Kafka procesando 2M mensajes/día
• Responsable de las integraciones con PostgreSQL y Redis

Backend Developer - Startup XYZ (2019-06 - 2020-12)
• Desarrollé APIs REST con FastAPI y Docker
• Automaticé el despliegue con GitHub Actions

EDUCACIÓN
Ingeniería Informática - Universidad Politécnica (2015 - 2019)

HABILIDADES
Python, Go, FastAPI, Django, PostgreSQL, Redis, Kafka, Docker, Kubernetes, AWS, Terraform
"""

JD = """Senior Backend Engineer (Remoto)
Empresa: Acme Cloud

Buscamos un Senior Backend Engineer para nuestro equipo de plataforma.

Requisitos imprescindibles:
- 5+ años de experiencia en Python
- Experiencia sólida con Kubernetes y Docker
- PostgreSQL y diseño de esquemas
- Kafka o sistemas de mensajería
- Inglés profesional

Valorable:
- Go
- Terraform
- Experiencia con GraphQL

Ofrecemos 65000 - 85000 EUR anuales. 100% remoto.
"""

c = TestClient(app)

print("health:", c.get("/api/v1/health").json()["status"])

r = c.post("/api/v1/resumes",
    files={"file": ("cv.txt", io.BytesIO(CV.encode()), "text/plain")},
    data={"label": "CV principal", "target_role": "Backend Engineer", "make_primary": "true"})
assert r.status_code == 201, r.text
resume = r.json()
print(f"CV #{resume['id']} score={resume['ats_score']} skills={len(resume['parsed']['skills']['other'])}")
print("  findings:", [f["area"] for f in resume["ats_report"]["findings"]][:5])
print("  keywords:", list(resume["ats_report"]["keyword_density"])[:10])

r = c.post("/api/v1/jobs", json={"title": "Senior Backend Engineer", "company": "Acme Cloud",
                                  "description_raw": JD, "analyze": True})
assert r.status_code == 201, r.text
job = r.json()
print(f"Vacante #{job['id']} remote={job['remote_type']} salario={job['salary_min']}-{job['salary_max']} {job['salary_currency']}")
print("  hard skills:", [s["name"] for s in job["requirements"]["hard_skills"]][:12])

m = c.get(f"/api/v1/jobs/{job['id']}/match").json()
print(f"MATCH total={m['score']} skills={m['skill_score']} sem={m['semantic_score']} sen={m['seniority_score']}")
print("  coinciden:", m["matched_skills"])
print("  faltan:", m["missing_skills"])

s = c.post("/api/v1/jobs/search", json={"q": "backend", "sort": "score"}).json()
print("search:", s["total"], "resultados")

a = c.post("/api/v1/applications", json={"job_id": job["id"], "status": "saved"})
assert a.status_code == 201, a.text
app_row = a.json()
print(f"Postulación #{app_row['id']} tareas={len(app_row['tasks'])}")

c.patch(f"/api/v1/applications/{app_row['id']}", json={"status": "applied"})
b = c.get("/api/v1/applications/board").json()
print("board stats:", json.dumps(b["stats"], ensure_ascii=False))
print("columnas:", [(col["label"], len(col["applications"])) for col in b["columns"] if col["applications"]])
af = c.get("/api/v1/capture/autofill").json()
print("autofill:", af["full_name"], "|", af["email"], "|", af["years_experience"], "años")
print("\nTODO OK")
