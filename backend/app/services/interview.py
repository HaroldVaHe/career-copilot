"""Simulador de entrevista: preguntas contextuales + feedback inmediato."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import InterviewSession, Job, Resume
from app.schemas.intel import InterviewIntelData
from app.schemas.interview import InterviewReply, InterviewSummary
from app.schemas.resume import ResumeData
from app.services.llm import as_prompt_json, llm

MAX_QUESTIONS = 8

_BASE_SYSTEM = """Eres un entrevistador técnico experimentado conduciendo una entrevista simulada.

Cómo te comportas:
- Una pregunta por turno. Nunca dos.
- Preguntas ANCLADAS en el CV del candidato y en los requisitos de la vacante. Si el CV dice
  que migró un monolito, pregunta por esa migración concreta, no por teoría genérica.
- Repreguntas cuando la respuesta es vaga o suena a memorizada. Un entrevistador bueno
  presiona una vez, no tres.
- El feedback es directo y accionable: qué faltó, qué habría dicho un candidato fuerte.
  No adulas. Tampoco humillas.
- `model_answer` es una respuesta de referencia CONCISA (4-6 frases), no un ensayo.
- Para preguntas behavioral evalúas STAR explícitamente en `star_compliance`.
- `is_final: true` cuando ya hayas hecho {max_questions} preguntas; entonces `next_question` va vacío.

Modo de la entrevista: {mode}. Dificultad: {difficulty}. Idioma: {language}."""


def _system_prompt(mode: str, difficulty: str, language: str) -> str:
    return _BASE_SYSTEM.format(
        max_questions=MAX_QUESTIONS,
        mode=mode,
        difficulty=difficulty,
        language="español" if language == "es" else "inglés",
    )


def _context_block(
    job: Job | None, resume: Resume | None, interview_data: InterviewIntelData | None
) -> str:
    parts = []
    if job is not None:
        parts.append(
            f"VACANTE\n{job.title} en {job.company}\n"
            f"Requisitos:\n{as_prompt_json(job.requirements or {})}\n"
            f"Descripción:\n{(job.description_raw or '')[:8000]}"
        )
    if resume is not None:
        data = ResumeData.model_validate(resume.parsed or {})
        parts.append(f"CV DEL CANDIDATO\n{as_prompt_json(data)}")
    if interview_data is not None:
        parts.append(
            f"CÓMO ENTREVISTA ESTA EMPRESA (investigado)\n{as_prompt_json(interview_data)}"
        )
    return "\n\n".join(parts) or "(sin contexto: haz una entrevista técnica general)"


def start(
    db: Session,
    user_id: int,
    job: Job | None,
    resume: Resume | None,
    mode: str = "mixed",
    difficulty: str = "medium",
    language: str = "es",
    interview_data: InterviewIntelData | None = None,
) -> tuple[InterviewSession, InterviewReply]:
    context = _context_block(job, resume, interview_data)

    reply = llm.converse(
        system=_system_prompt(mode, difficulty, language),
        messages=[
            {
                "role": "user",
                "content": f"{context}\n\n---\nEmpieza la entrevista con la primera pregunta. "
                f"Como aún no hay respuesta que evaluar, deja `feedback` con score 0 y listas vacías.",
            }
        ],
        output_model=InterviewReply,
        max_tokens=6000,
    )

    session = InterviewSession(
        user_id=user_id,
        job_id=job.id if job else None,
        resume_id=resume.id if resume else None,
        mode=mode,
        transcript=[
            {"role": "context", "content": context},
            {
                "role": "interviewer",
                "content": reply.next_question,
                "question_type": reply.question_type,
            },
        ],
        summary={"difficulty": difficulty, "language": language},
    )
    db.add(session)
    db.flush()
    return session, reply


def answer(db: Session, session: InterviewSession, text: str) -> InterviewReply:
    if session.finished:
        raise ValueError("Esta entrevista ya terminó.")

    transcript = list(session.transcript or [])
    context = next((t["content"] for t in transcript if t["role"] == "context"), "")
    meta = session.summary or {}

    messages = _rebuild_messages(transcript, context)
    messages.append({"role": "user", "content": text})

    questions_asked = sum(1 for t in transcript if t["role"] == "interviewer")
    hint = (
        "\n\nYa has hecho todas las preguntas previstas: da el feedback de esta respuesta, "
        "pon `is_final: true` y deja `next_question` vacío."
        if questions_asked >= MAX_QUESTIONS
        else ""
    )
    if hint:
        messages[-1]["content"] += hint

    reply = llm.converse(
        system=_system_prompt(
            session.mode, meta.get("difficulty", "medium"), meta.get("language", "es")
        ),
        messages=messages,
        output_model=InterviewReply,
        max_tokens=8000,
    )

    transcript.append(
        {"role": "candidate", "content": text, "feedback": reply.feedback.model_dump()}
    )
    if reply.next_question and not reply.is_final:
        transcript.append(
            {
                "role": "interviewer",
                "content": reply.next_question,
                "question_type": reply.question_type,
            }
        )

    session.transcript = transcript
    if reply.is_final:
        session.finished = True
    db.flush()
    return reply


def _rebuild_messages(transcript: list[dict], context: str) -> list[dict]:
    """La API es stateless: se reenvía la conversación completa en cada turno."""
    messages: list[dict] = [
        {"role": "user", "content": f"{context}\n\n---\nEmpieza la entrevista."}
    ]
    for turn in transcript:
        if turn["role"] == "interviewer":
            messages.append({"role": "assistant", "content": turn["content"]})
        elif turn["role"] == "candidate":
            messages.append({"role": "user", "content": turn["content"]})
    return messages


_SUMMARY_SYSTEM = """Cierras una entrevista simulada con una evaluación honesta.

- `verdict`: ¿pasaría esta persona a la siguiente ronda? Sí o no, y por qué. Sin rodeos.
- `study_plan`: 4-6 acciones concretas y ordenadas por impacto, derivadas de los fallos reales
  de esta entrevista. Nada genérico.
- Puntúa de 0 a 100 con criterio de empresa exigente.
Responde en español."""


def finish(db: Session, session: InterviewSession) -> InterviewSummary:
    transcript = [t for t in (session.transcript or []) if t["role"] != "context"]

    summary = llm.extract(
        system=_SUMMARY_SYSTEM,
        user=f"Transcripción de la entrevista:\n{as_prompt_json(transcript)}\n\nEvalúa al candidato.",
        output_model=InterviewSummary,
        max_tokens=8000,
    )

    session.summary = {**(session.summary or {}), **summary.model_dump()}
    session.finished = True
    db.flush()
    return summary
