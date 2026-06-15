from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout_seconds: int = 60


class DeepSeekClient:
    def __init__(self, config: DeepSeekConfig) -> None:
        self.config = config

    @classmethod
    def from_env(cls, env_path: str | Path = ".env") -> "DeepSeekClient | None":
        _load_dotenv(env_path)
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            return None

        base_url = os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
        model = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL).strip()
        timeout_raw = os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "60").strip()
        try:
            timeout_seconds = int(timeout_raw)
        except ValueError:
            timeout_seconds = 60

        return cls(
            DeepSeekConfig(
                api_key=api_key,
                base_url=base_url,
                model=model,
                timeout_seconds=timeout_seconds,
            )
        )

    def create_chat_completion(self, messages: list[dict[str, str]]) -> str:
        url = f"{self.config.base_url}/chat/completions"
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.2,
            "stream": False,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            url=url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DeepSeek API 请求失败：HTTP {exc.code} {error_body}") from exc
        except URLError as exc:
            raise RuntimeError(f"DeepSeek API 网络请求失败：{exc}") from exc

        parsed: dict[str, Any] = json.loads(body)
        choices = parsed.get("choices") or []
        if not choices:
            raise RuntimeError("DeepSeek API 没有返回 choices。")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not content:
            raise RuntimeError("DeepSeek API 返回内容为空。")
        return str(content)


def _load_dotenv(env_path: str | Path) -> None:
    path = Path(env_path)
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
