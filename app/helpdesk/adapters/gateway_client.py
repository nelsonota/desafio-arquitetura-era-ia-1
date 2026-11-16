"""The single application component that calls the AI Gateway."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException

from ..ports import TextGenerationGateway


class HttpGatewayClient(TextGenerationGateway):
    def __init__(self, base_url: str, api_key: str, timeout: float = 60):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def generate(self, capability: str, task: str, content: str) -> str:
        payload = json.dumps({
            "model": capability,
            "messages": [{"role": "user", "content": f"TASK: {task}\n{content}"}],
            "max_tokens": 2000,
        }).encode()
        request = Request(
            f"{self.base_url}/chat/completions", data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.load(response)
        except HTTPError as exc:
            try:
                detail = json.load(exc).get("detail", "Gateway request failed")
            except Exception:
                detail = "Gateway request failed"
            raise HTTPException(status_code=502, detail=detail) from exc
        except (TimeoutError, URLError) as exc:
            raise HTTPException(status_code=502, detail="AI Gateway indisponível") from exc
        except (json.JSONDecodeError, OSError) as exc:
            raise HTTPException(status_code=502, detail="Resposta inválida do AI Gateway") from exc
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise HTTPException(status_code=502, detail="Invalid response from AI Gateway") from exc


def create_gateway_client() -> HttpGatewayClient:
    return HttpGatewayClient(
        base_url=os.environ.get("GATEWAY_URL", "http://gateway:4000/v1"),
        api_key=os.environ["GATEWAY_API_KEY"],
    )
