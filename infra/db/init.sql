-- Se ejecuta una sola vez, cuando el volumen de Postgres se crea por primera vez.
-- Las tablas las crea SQLAlchemy al arrancar la API (app/db/init_db.py).
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
