"""Taxonomía de habilidades: canonicalización, detección en texto y seniority.

El matching no puede depender solo de embeddings: "JS" y "JavaScript" deben ser
la misma cosa, y un ATS real busca literales. Esta capa determinista es la que
produce los "hard skills coincidentes vs. faltantes" del informe.
"""

from __future__ import annotations

import re
from functools import lru_cache

from rapidfuzz import fuzz

# canónico -> alias. Las claves son lo que se muestra en la UI.
SKILL_ALIASES: dict[str, list[str]] = {
    # --- Lenguajes ---
    "Python": ["python", "py", "python3"],
    "JavaScript": ["javascript", "js", "ecmascript", "es6", "es2015"],
    "TypeScript": ["typescript", "ts"],
    "Java": ["java", "java8", "java 11", "java 17"],
    "C#": ["c#", "csharp", "c sharp", ".net c#"],
    "C++": ["c++", "cpp", "cplusplus"],
    "C": ["ansi c"],
    "Go": ["golang", "go lang"],
    "Rust": ["rust", "rustlang"],
    "PHP": ["php", "php8"],
    "Ruby": ["ruby"],
    "Kotlin": ["kotlin"],
    "Swift": ["swift", "swiftui"],
    "Scala": ["scala"],
    "R": ["r language", "lenguaje r"],
    "SQL": ["sql", "t-sql", "tsql", "pl/sql", "plsql", "ansi sql"],
    "Bash": ["bash", "shell scripting", "shell script", "zsh"],
    "PowerShell": ["powershell", "power shell"],
    "MATLAB": ["matlab"],
    "Dart": ["dart"],
    "Elixir": ["elixir"],
    # --- Frontend ---
    "React": ["react", "react.js", "reactjs"],
    "Next.js": ["next.js", "nextjs", "next js"],
    "Vue.js": ["vue", "vue.js", "vuejs", "nuxt"],
    "Angular": ["angular", "angularjs", "angular 2+"],
    "Svelte": ["svelte", "sveltekit"],
    "Tailwind CSS": ["tailwind", "tailwindcss", "tailwind css"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3", "sass", "scss", "less"],
    "Redux": ["redux", "redux toolkit", "rtk"],
    "React Native": ["react native", "react-native"],
    "Flutter": ["flutter"],
    "Webpack": ["webpack", "vite", "rollup", "esbuild"],
    "jQuery": ["jquery"],
    # --- Backend / frameworks ---
    "Node.js": ["node", "node.js", "nodejs"],
    "Express": ["express", "express.js", "expressjs"],
    "NestJS": ["nestjs", "nest.js", "nest js"],
    "Django": ["django", "django rest framework", "drf"],
    "FastAPI": ["fastapi", "fast api"],
    "Flask": ["flask"],
    "Spring Boot": ["spring", "spring boot", "springboot", "spring mvc"],
    "Laravel": ["laravel"],
    ".NET": [".net", "dotnet", "asp.net", "aspnet", ".net core", "entity framework"],
    "Ruby on Rails": ["rails", "ruby on rails", "ror"],
    "GraphQL": ["graphql", "apollo", "apollo server"],
    "REST API": ["rest", "rest api", "restful", "api rest", "apis rest"],
    "gRPC": ["grpc", "protobuf", "protocol buffers"],
    "Microservices": ["microservices", "microservicios", "micro-servicios"],
    "WebSockets": ["websocket", "websockets", "socket.io"],
    # --- Datos ---
    "PostgreSQL": ["postgres", "postgresql", "psql", "pgsql"],
    "MySQL": ["mysql", "mariadb"],
    "MongoDB": ["mongo", "mongodb", "mongoose"],
    "Redis": ["redis"],
    "Elasticsearch": ["elasticsearch", "elastic search", "opensearch", "elk"],
    "SQL Server": ["sql server", "sqlserver", "mssql", "microsoft sql server"],
    "Oracle": ["oracle db", "oracle database"],
    "SQLite": ["sqlite"],
    "DynamoDB": ["dynamodb", "dynamo db"],
    "Cassandra": ["cassandra"],
    "Snowflake": ["snowflake"],
    "BigQuery": ["bigquery", "big query"],
    "Redshift": ["redshift"],
    "Databricks": ["databricks"],
    "Apache Spark": ["spark", "pyspark", "apache spark"],
    "Apache Kafka": ["kafka", "apache kafka"],
    "Airflow": ["airflow", "apache airflow"],
    "dbt": ["dbt", "data build tool"],
    "ETL": ["etl", "elt", "pipelines de datos", "data pipeline"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau"],
    "Looker": ["looker", "looker studio", "data studio"],
    "Excel": ["excel", "advanced excel", "excel avanzado"],
    # --- Cloud / DevOps ---
    "AWS": ["aws", "amazon web services", "ec2", "s3", "lambda", "cloudformation"],
    "Azure": ["azure", "microsoft azure", "azure devops"],
    "Google Cloud": ["gcp", "google cloud", "google cloud platform"],
    "Docker": ["docker", "dockerfile", "containerization", "contenedores"],
    "Kubernetes": ["kubernetes", "k8s", "eks", "aks", "gke", "helm"],
    "Terraform": ["terraform", "iac", "infrastructure as code"],
    "Ansible": ["ansible"],
    "CI/CD": ["ci/cd", "cicd", "continuous integration", "integración continua", "jenkins",
              "github actions", "gitlab ci", "circleci", "travis"],
    "Linux": ["linux", "ubuntu", "debian", "centos", "rhel", "unix"],
    "Nginx": ["nginx", "apache http", "reverse proxy"],
    "Prometheus": ["prometheus", "grafana", "datadog", "new relic", "observability"],
    "Serverless": ["serverless", "lambda functions", "cloud functions"],
    # --- IA / ML ---
    "Machine Learning": ["machine learning", "ml", "aprendizaje automático", "aprendizaje automatico"],
    "Deep Learning": ["deep learning", "redes neuronales", "neural networks"],
    "TensorFlow": ["tensorflow", "keras"],
    "PyTorch": ["pytorch", "torch"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "NLP": ["nlp", "natural language processing", "procesamiento de lenguaje natural"],
    "Computer Vision": ["computer vision", "opencv", "visión por computador"],
    "LLM": ["llm", "large language model", "gpt", "claude", "gemini", "prompt engineering"],
    "RAG": ["rag", "retrieval augmented generation", "vector search", "embeddings"],
    "LangChain": ["langchain", "llamaindex"],
    "MLOps": ["mlops", "mlflow", "model deployment"],
    # --- Testing / calidad ---
    "Testing": ["testing", "unit testing", "pruebas unitarias", "tdd", "jest", "pytest",
                "junit", "mocha", "vitest"],
    "Selenium": ["selenium", "cypress", "playwright", "puppeteer", "e2e testing"],
    "QA": ["qa", "quality assurance", "aseguramiento de calidad"],
    # --- Herramientas / metodología ---
    "Git": ["git", "github", "gitlab", "bitbucket", "control de versiones"],
    "Agile": ["agile", "scrum", "kanban", "ágil", "agil", "sprint"],
    "Jira": ["jira", "confluence", "atlassian"],
    "Figma": ["figma", "sketch", "adobe xd"],
    "UX/UI": ["ux", "ui", "ux/ui", "diseño de interfaces", "user experience"],
    "SEO": ["seo", "sem", "posicionamiento web"],
    "Salesforce": ["salesforce", "apex", "crm salesforce"],
    "SAP": ["sap", "sap abap", "sap hana"],
    # --- Seguridad / redes ---
    "Cybersecurity": ["cybersecurity", "ciberseguridad", "seguridad informática", "infosec"],
    "Pentesting": ["pentesting", "ethical hacking", "owasp", "burp suite", "nmap"],
    "Networking": ["networking", "redes", "tcp/ip", "ccna", "cisco", "vlan", "routing"],
    "OAuth": ["oauth", "oauth2", "jwt", "sso", "saml", "openid"],
}

SOFT_SKILLS = {
    "Comunicación": ["comunicación", "comunicacion", "communication", "comunicación efectiva"],
    "Liderazgo": ["liderazgo", "leadership", "team lead", "mentoring", "mentoría"],
    "Trabajo en equipo": ["trabajo en equipo", "teamwork", "colaboración", "collaboration"],
    "Resolución de problemas": ["resolución de problemas", "problem solving", "analytical thinking"],
    "Autonomía": ["autonomía", "autonomia", "self-starter", "proactividad", "ownership"],
    "Gestión del tiempo": ["gestión del tiempo", "time management", "priorización"],
    "Adaptabilidad": ["adaptabilidad", "adaptability", "flexibilidad"],
}

SENIORITY_LEVELS = ["intern", "junior", "mid", "senior", "lead", "principal", "manager"]

_SENIORITY_PATTERNS: list[tuple[str, list[str]]] = [
    ("intern", ["intern", "becario", "practicante", "pasante", "trainee", "prácticas"]),
    ("junior", ["junior", "jr.", "jr ", "entry level", "entry-level", "graduate", "nivel inicial"]),
    ("principal", ["principal", "staff engineer", "distinguished"]),
    ("manager", ["manager", "head of", "director", "vp of", "jefe de", "gerente"]),
    ("lead", ["tech lead", "team lead", "lead engineer", "líder técnico", "lider tecnico"]),
    ("senior", ["senior", "sr.", "sr ", "ssr", "semi-senior", "experienced"]),
    ("mid", ["mid-level", "mid level", "intermediate", "nivel medio", "semi senior"]),
]


@lru_cache(maxsize=1)
def _alias_index() -> dict[str, str]:
    """alias en minúsculas -> nombre canónico."""
    index: dict[str, str] = {}
    for canonical, aliases in SKILL_ALIASES.items():
        index[canonical.lower()] = canonical
        for alias in aliases:
            index[alias.lower()] = canonical
    return index


@lru_cache(maxsize=1)
def _soft_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for canonical, aliases in SOFT_SKILLS.items():
        index[canonical.lower()] = canonical
        for alias in aliases:
            index[alias.lower()] = canonical
    return index


@lru_cache(maxsize=1)
def _compiled_patterns() -> list[tuple[re.Pattern[str], str]]:
    """Un regex por alias, ordenado de más largo a más corto para que
    'react native' gane sobre 'react'."""
    items = sorted(_alias_index().items(), key=lambda kv: -len(kv[0]))
    patterns = []
    for alias, canonical in items:
        # \b no funciona con '+'/'#' al final (C++, C#): se ancla con lookahead.
        escaped = re.escape(alias)
        left = r"(?<![\w+#.])"
        right = r"(?![\w+#])" if alias[-1] in "+#" else r"(?![\w.+#])"
        patterns.append((re.compile(left + escaped + right, re.IGNORECASE), canonical))
    return patterns


def canonicalize(term: str) -> str:
    """Devuelve el nombre canónico de una skill, o el término limpio si no la conocemos."""
    if not term:
        return ""
    cleaned = term.strip().strip(".,;:()[]")
    direct = _alias_index().get(cleaned.lower())
    if direct:
        return direct
    soft = _soft_index().get(cleaned.lower())
    if soft:
        return soft

    # Tolerancia a erratas y variantes ("Postgre SQL", "Kubernets").
    if len(cleaned) >= 4:
        best, best_score = None, 0.0
        for alias, canonical in _alias_index().items():
            if abs(len(alias) - len(cleaned)) > 4:
                continue
            score = fuzz.ratio(alias, cleaned.lower())
            if score > best_score:
                best, best_score = canonical, score
        if best and best_score >= 90:
            return best
    return cleaned


def extract_skills(text: str) -> dict[str, int]:
    """Skill canónica -> nº de menciones en el texto."""
    if not text:
        return {}
    counts: dict[str, int] = {}
    for pattern, canonical in _compiled_patterns():
        found = len(pattern.findall(text))
        if found:
            counts[canonical] = counts.get(canonical, 0) + found
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def normalize_skills(terms: list[str]) -> list[str]:
    """Canonicaliza y deduplica preservando el orden."""
    seen: dict[str, None] = {}
    for term in terms:
        canonical = canonicalize(term)
        if canonical:
            seen.setdefault(canonical, None)
    return list(seen.keys())


def detect_seniority(text: str) -> str:
    """Deduce el nivel a partir del título o la descripción. '' si no hay señal."""
    lowered = (text or "").lower()
    for level, markers in _SENIORITY_PATTERNS:
        if any(marker in lowered for marker in markers):
            return level
    return ""


def seniority_distance(a: str, b: str) -> int:
    """Distancia en niveles. -1 si alguno es desconocido."""
    if a not in SENIORITY_LEVELS or b not in SENIORITY_LEVELS:
        return -1
    return abs(SENIORITY_LEVELS.index(a) - SENIORITY_LEVELS.index(b))


def years_to_seniority(years: float) -> str:
    if years < 1:
        return "junior"
    if years < 3:
        return "mid"
    if years < 7:
        return "senior"
    return "lead"
