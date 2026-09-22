from __future__ import annotations

from sqlalchemy import select, text

from app.core.config import settings
from app.core.logging import get_logger
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import User

log = get_logger(__name__)


def init_db() -> None:
    """Crea extensión, tablas e índices, y siembra el usuario local.

    Para un proyecto de un solo usuario esto sustituye a Alembic. Si el esquema
    empieza a evolucionar en producción, cambiar por migraciones.
    """
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    # Importa las entidades para que estén registradas en el metadata.
    import app.models.entities  # noqa: F401

    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        # ivfflat necesita datos para entrenar; con pocos registros el escaneo
        # secuencial es más rápido de todas formas. HNSW no necesita entrenamiento.
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_jobs_embedding_hnsw "
                "ON jobs USING hnsw (embedding vector_cosine_ops)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_jobs_desc_trgm "
                "ON jobs USING gin (description_raw gin_trgm_ops)"
            )
        )

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == settings.default_user_email))
        if user is None:
            db.add(
                User(
                    email=settings.default_user_email,
                    full_name=settings.default_user_name,
                    preferences={},
                )
            )
            db.commit()
            log.info("Usuario local creado: %s", settings.default_user_email)

    log.info("Base de datos lista.")
