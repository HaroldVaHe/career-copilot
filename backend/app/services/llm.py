"""Cliente de Claude: extracción estructurada, texto libre e investigación web.

Todas las llamadas al modelo del proyecto pasan por aquí. Dos razones:
 1. Un único sitio donde ajustar modelo, effort y manejo de errores.
 2. Salida estructurada garantizada — se usa `output_config.format` con un JSON
    Schema derivado del modelo Pydantic, así que el parseo nunca depende de que
    el modelo "se acuerde" de responder JSON.
"""

from __future__ import annotations

import copy
import json
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# Server tool de búsqueda web. Requiere Opus 4.6+ / Sonnet 4.6+.
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 6}


class LLMError(RuntimeError):
    """Fallo al hablar con Claude."""


class LLMUnavailable(LLMError):
    """No hay ANTHROPIC_API_KEY configurada."""


# --------------------------------------------------------------------------
# JSON Schema estricto a partir de Pydantic
# --------------------------------------------------------------------------
_DROP_KEYS = {"default", "title", "examples", "$comment", "format", "additionalProperties"}


def _inline_refs(node: Any, defs: dict[str, Any], depth: int = 0) -> Any:
    """Sustituye cada `$ref` por su definición. Los esquemas del proyecto no son
    recursivos; el límite de profundidad solo evita un bucle infinito accidental."""
    if depth > 12:
        return {"type": "object"}
    if isinstance(node, list):
        return [_inline_refs(n, defs, depth + 1) for n in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        target = copy.deepcopy(defs.get(name, {}))
        merged = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
        return _inline_refs(merged, defs, depth + 1)
    return {k: _inline_refs(v, defs, depth + 1) for k, v in node.items() if k != "$defs"}


def _strictify(node: Any) -> Any:
    """Deja el esquema en la forma que exige el modo estricto de la API:
    todo objeto cerrado (`additionalProperties: false`) y con todas sus
    propiedades en `required`."""
    if isinstance(node, list):
        return [_strictify(n) for n in node]
    if not isinstance(node, dict):
        return node

    out = {k: _strictify(v) for k, v in node.items() if k not in _DROP_KEYS}

    if out.get("type") == "object" or "properties" in out:
        props = out.get("properties") or {}
        out["type"] = "object"
        out["properties"] = props
        out["additionalProperties"] = False
        out["required"] = list(props.keys())
    return out


def json_schema_for(model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    defs = raw.get("$defs", {})
    return _strictify(_inline_refs(raw, defs))


def as_prompt_json(data: Any) -> str:
    """Serializa datos para meterlos en un prompt. `sort_keys` mantiene el prefijo
    estable, que es lo que permite que el prompt caching acierte."""
    if isinstance(data, BaseModel):
        data = data.model_dump()
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, default=str)


# --------------------------------------------------------------------------
# Cliente
# --------------------------------------------------------------------------
class ClaudeClient:
    def __init__(self) -> None:
        self._client: anthropic.Anthropic | None = None

    @property
    def available(self) -> bool:
        return bool(settings.anthropic_api_key)

    @property
    def client(self) -> anthropic.Anthropic:
        if not self.available:
            raise LLMUnavailable(
                "Falta ANTHROPIC_API_KEY. Añádela al .env de la raíz del repo para "
                "habilitar parsing de CV, tailoring, intel y simulacros de entrevista."
            )
        if self._client is None:
            self._client = anthropic.Anthropic(
                api_key=settings.anthropic_api_key, max_retries=3, timeout=180.0
            )
        return self._client

    # -- texto libre -------------------------------------------------------
    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        effort: str | None = None,
        max_tokens: int = 8000,
        cache_system: bool = True,
    ) -> str:
        system_block: Any = system
        if cache_system:
            system_block = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]
        try:
            resp = self.client.messages.create(
                model=model or settings.llm_model,
                max_tokens=max_tokens,
                system=system_block,
                thinking={"type": "adaptive"},
                output_config={"effort": effort or settings.llm_effort},
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.APIError as exc:  # red, 4xx, 5xx
            raise LLMError(_describe(exc)) from exc

        if resp.stop_reason == "refusal":
            raise LLMError(f"Claude declinó la petición: {_refusal_detail(resp)}")
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    # -- extracción estructurada ------------------------------------------
    def extract(
        self,
        *,
        system: str,
        user: str,
        output_model: type[T],
        model: str | None = None,
        effort: str | None = None,
        max_tokens: int = 16000,
        cache_system: bool = True,
    ) -> T:
        """Pide a Claude una respuesta que valide contra `output_model`."""
        system_block: Any = system
        if cache_system:
            system_block = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]
        try:
            resp = self.client.messages.create(
                model=model or settings.llm_model,
                max_tokens=max_tokens,
                system=system_block,
                thinking={"type": "adaptive"},
                output_config={
                    "effort": effort or settings.llm_effort,
                    "format": {"type": "json_schema", "schema": json_schema_for(output_model)},
                },
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.APIError as exc:
            raise LLMError(_describe(exc)) from exc

        if resp.stop_reason == "refusal":
            raise LLMError(f"Claude declinó la petición: {_refusal_detail(resp)}")
        if resp.stop_reason == "max_tokens":
            raise LLMError(
                "La respuesta se cortó por max_tokens. Reduce el tamaño del documento de entrada."
            )

        text = next((b.text for b in resp.content if b.type == "text"), "")
        return _validate(text, output_model)

    # -- investigación con búsqueda web -----------------------------------
    def research(
        self,
        *,
        system: str,
        user: str,
        output_model: type[T],
        model: str | None = None,
        max_tokens: int = 16000,
        max_pause_turns: int = 4,
    ) -> tuple[T, list[str]]:
        """Dos fases: Claude busca en la web, y luego se estructura lo hallado.

        Separar las fases evita mezclar `output_config.format` con las citas del
        server tool, y deja las URLs disponibles para mostrarlas como fuentes.
        """
        messages: list[Any] = [{"role": "user", "content": user}]
        sources: list[str] = []
        notes: list[str] = []

        for _ in range(max_pause_turns):
            try:
                resp = self.client.messages.create(
                    model=model or settings.llm_model,
                    max_tokens=max_tokens,
                    system=system,
                    thinking={"type": "adaptive"},
                    tools=[WEB_SEARCH_TOOL],
                    messages=messages,
                )
            except anthropic.APIError as exc:
                raise LLMError(_describe(exc)) from exc

            if resp.stop_reason == "refusal":
                raise LLMError(f"Claude declinó la investigación: {_refusal_detail(resp)}")

            for block in resp.content:
                if block.type == "text":
                    notes.append(block.text)
                elif block.type == "web_search_tool_result":
                    # En error, `content` es un objeto con error_code; en éxito, una lista.
                    content = block.content
                    if isinstance(content, list):
                        for item in content:
                            url = getattr(item, "url", None)
                            if url and url not in sources:
                                sources.append(url)
                    else:
                        log.warning(
                            "web_search falló: %s", getattr(content, "error_code", "desconocido")
                        )

            if resp.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": resp.content})

        findings = "\n\n".join(n for n in notes if n.strip())
        if not findings:
            findings = "(la búsqueda no devolvió información utilizable)"

        structured = self.extract(
            system=(
                "Estructuras hallazgos de investigación en JSON. Usa únicamente lo que aparece "
                "en las notas. Si un dato no está, déjalo vacío y baja `confidence`. "
                "No inventes cifras, fechas ni nombres."
            ),
            user=(
                f"Notas de investigación:\n\n{findings}\n\n"
                f"Fuentes consultadas:\n" + "\n".join(sources[:30])
            ),
            output_model=output_model,
            effort="medium",
            cache_system=False,
        )
        return structured, sources

    # -- conversación multi-turno (entrevistas) ---------------------------
    def converse(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        output_model: type[T],
        model: str | None = None,
        effort: str | None = None,
        max_tokens: int = 8000,
    ) -> T:
        try:
            resp = self.client.messages.create(
                model=model or settings.llm_model,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                thinking={"type": "adaptive"},
                output_config={
                    "effort": effort or settings.llm_effort,
                    "format": {"type": "json_schema", "schema": json_schema_for(output_model)},
                },
                messages=messages,
            )
        except anthropic.APIError as exc:
            raise LLMError(_describe(exc)) from exc

        if resp.stop_reason == "refusal":
            raise LLMError(f"Claude declinó la petición: {_refusal_detail(resp)}")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return _validate(text, output_model)


def _validate(text: str, output_model: type[T]) -> T:
    if not text.strip():
        raise LLMError("Claude devolvió una respuesta vacía.")
    try:
        return output_model.model_validate_json(text)
    except ValidationError as exc:
        log.error("Respuesta no válida para %s: %s", output_model.__name__, text[:800])
        raise LLMError(f"La respuesta no encaja con el esquema esperado: {exc}") from exc


def _describe(exc: anthropic.APIError) -> str:
    if isinstance(exc, anthropic.AuthenticationError):
        return "ANTHROPIC_API_KEY inválida o revocada."
    if isinstance(exc, anthropic.RateLimitError):
        return "Límite de rate de la API alcanzado. Reintenta en unos segundos."
    if isinstance(exc, anthropic.APIConnectionError):
        return "No se pudo conectar con la API de Anthropic. Revisa tu conexión."
    if isinstance(exc, anthropic.APIStatusError):
        return f"Error de la API ({exc.status_code}): {exc.message}"
    return f"Error llamando a Claude: {exc}"


def _refusal_detail(resp: Any) -> str:
    details = getattr(resp, "stop_details", None)
    if details is None:
        return "sin detalle"
    return f"{getattr(details, 'category', '?')} — {getattr(details, 'explanation', '')}"


llm = ClaudeClient()
