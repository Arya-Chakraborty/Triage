from __future__ import annotations

from typing import Any

from triage.ports.llm import FunctionCall, LLMClient, LLMError, LLMRequest, LLMResponse


class DisabledLLM(LLMClient):
    def generate(self, request: LLMRequest) -> LLMResponse:
        raise LLMError("GEMINI_API_KEY missing")


class GeminiLLM(LLMClient):
    """Manual tool loop only — automatic function calling is disabled."""

    def __init__(self, api_key: str) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)

    def generate(self, request: LLMRequest) -> LLMResponse:
        from google.genai import types

        try:
            config = types.GenerateContentConfig(
                system_instruction=request.system,
                tools=[types.Tool(function_declarations=_decls(request.tools))]
                if request.tools
                else None,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
                max_output_tokens=request.max_tokens,
            )
            response = self._client.models.generate_content(
                model=request.model,
                contents=_contents(request.contents),
                config=config,
            )
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(str(exc)) from exc

        text = ""
        calls: list[FunctionCall] = []
        cand = (response.candidates or [None])[0]
        parts = cand.content.parts if cand and cand.content else []
        for part in parts or []:
            fc = getattr(part, "function_call", None)
            if fc and getattr(fc, "name", None):
                args = dict(fc.args) if getattr(fc, "args", None) else {}
                calls.append(
                    FunctionCall(
                        name=fc.name,
                        args=args,
                        thought_signature=getattr(part, "thought_signature", None),
                    )
                )
            elif getattr(part, "text", None):
                text += part.text
        usage = getattr(response, "usage_metadata", None)
        tokens = 0
        if usage is not None:
            tokens = int(getattr(usage, "total_token_count", 0) or 0)
        return LLMResponse(text=text.strip(), function_calls=calls, tokens_used=tokens)


def _decls(tools: list[dict[str, Any]]) -> list[Any]:
    from google.genai import types

    out = []
    for tool in tools:
        schema = tool.get("schema") or {"type": "object", "properties": {}}
        out.append(
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description") or "",
                parameters=_schema(schema),
            )
        )
    return out


def _schema(schema: dict[str, Any]) -> Any:
    from google.genai import types

    props = {}
    for key, spec in (schema.get("properties") or {}).items():
        spec = spec or {}
        typ = str(spec.get("type") or "string").upper()
        if typ == "ARRAY":
            props[key] = types.Schema(
                type=types.Type.ARRAY,
                description=spec.get("description"),
                items=types.Schema(type=types.Type.STRING),
            )
        elif typ == "INTEGER":
            props[key] = types.Schema(
                type=types.Type.INTEGER, description=spec.get("description")
            )
        elif typ == "BOOLEAN":
            props[key] = types.Schema(
                type=types.Type.BOOLEAN, description=spec.get("description")
            )
        elif typ == "NUMBER":
            props[key] = types.Schema(
                type=types.Type.NUMBER, description=spec.get("description")
            )
        else:
            props[key] = types.Schema(
                type=types.Type.STRING, description=spec.get("description")
            )
    return types.Schema(
        type=types.Type.OBJECT,
        properties=props,
        required=list(schema.get("required") or []),
    )


def _contents(contents: list[dict[str, Any]]) -> list[Any]:
    from google.genai import types

    converted = []
    for item in contents:
        role = item.get("role") or "user"
        if item.get("calls"):
            parts = []
            for c in item["calls"]:
                part = types.Part.from_function_call(
                    name=c["name"], args=c.get("args") or {}
                )
                sig = c.get("thought_signature")
                if sig is not None:
                    part.thought_signature = sig
                parts.append(part)
            converted.append(types.Content(role="model", parts=parts))
            continue
        if item.get("tool"):
            converted.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=item["tool"],
                            response={"output": item.get("text") or ""},
                        )
                    ],
                )
            )
            continue
        converted.append(
            types.Content(
                role="model" if role == "model" else "user",
                parts=[types.Part.from_text(text=item.get("text") or "")],
            )
        )
    return converted
