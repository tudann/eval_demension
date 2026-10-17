from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from .cases import ConfigError


class JudgeClient:
    """OpenAI-compatible online judge client."""

    def __init__(self, modality: str, base_url: str | None = None, model: str | None = None,
                 api_key: str | None = None, timeout: int = 180, role: str = "judge"):
        self.modality = modality
        self.role = role
        audio_modality = modality in {"audio", "audio_visual"}
        prefix = "V_EVAL_AUDIO_JUDGE" if audio_modality else "V_EVAL_VISION_JUDGE"
        role_prefix = "V_EVAL_CHECKLIST"
        legacy_url = os.getenv("V_EVAL_JUDGE_URL")
        legacy_model = os.getenv("V_EVAL_JUDGE_MODEL")
        # Audio and audio-visual checklists use the Omni judge. The shared
        # checklist endpoint stays on the vision model for the other dimensions.
        use_checklist_endpoint = role == "checklist" and not audio_modality
        role_url = os.getenv(f"{role_prefix}_URL") if use_checklist_endpoint else None
        role_model = os.getenv(f"{role_prefix}_MODEL") if use_checklist_endpoint else None
        role_key = os.getenv(f"{role_prefix}_API_KEY") if use_checklist_endpoint else None
        self.base_url = base_url or role_url or os.getenv(f"{prefix}_URL") or legacy_url
        self.model = model or role_model or os.getenv(f"{prefix}_MODEL") or legacy_model or (
            "Qwen2.5-Omni-7B" if modality in {"audio", "audio_visual"} else "Qwen3-VL-32B-Instruct"
        )
        self.api_key = api_key or role_key or (
            os.getenv(f"{prefix}_API_KEY")
            or os.getenv("V_EVAL_JUDGE_API_KEY")
            or os.getenv("V_EVAL_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        self.timeout = timeout

    @property
    def online(self) -> bool:
        return bool(self.base_url)

    def complete(self, system: str, user: str | list[dict[str, Any]], *, temperature: float = 0,
                 max_tokens: int | None = None) -> dict[str, Any]:
        if not self.base_url:
            raise ConfigError(f"{self.role} judge endpoint is not configured for {self.modality}")
        request_body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
        }
        if max_tokens is not None:
            request_body["max_tokens"] = max_tokens
        payload = json.dumps(request_body).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(self.base_url.rstrip("/") + "/chat/completions", data=payload,
                                         headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return {"status": "ok", "response": json.loads(response.read().decode("utf-8")), "model": self.model}
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            detail = str(exc)
            if isinstance(exc, urllib.error.HTTPError):
                try:
                    detail = exc.read().decode("utf-8", errors="replace")[:2000]
                except OSError:
                    pass
            return {"status": "error", "error": detail, "model": self.model}


def _response_content(payload: Any) -> Any:
    if isinstance(payload, dict):
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {})
            content = message.get("content", "") if isinstance(message, dict) else ""
            if isinstance(content, list):
                return "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
            return content
    return payload


def _parse_json_response(payload: Any) -> dict[str, Any] | None:
    content = _response_content(payload)
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return None
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


