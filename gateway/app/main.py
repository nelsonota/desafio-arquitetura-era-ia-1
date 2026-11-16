"""Small self-hosted AI gateway for the helpdesk's logical capabilities."""

import os
import tomllib
from pathlib import Path

from anthropic import Anthropic
from fastapi import FastAPI, Header, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field

CONFIG_PATH = Path(os.environ.get("GATEWAY_CONFIG", "/srv/config.toml"))
with CONFIG_PATH.open("rb") as config_file:
    CAPABILITIES = tomllib.load(config_file)["capabilities"]

GATEWAY_API_KEY = os.environ["GATEWAY_API_KEY"]
OPENAI = OpenAI(
    api_key=os.environ["FAKE_OPENAI_KEY"],
    base_url="http://provider-fake:8090/openai/v1",
)
ANTHROPIC = Anthropic(
    api_key=os.environ["FAKE_ANTHROPIC_KEY"],
    base_url="http://provider-fake:8090/anthropic",
)

app = FastAPI(title="helpdesk-ai-gateway", docs_url=None, redoc_url=None)


class GenerationRequest(BaseModel):
    capability: str = Field(min_length=1)
    task: str = Field(min_length=1)
    content: str


def authorized(authorization: str | None) -> bool:
    return authorization == f"Bearer {GATEWAY_API_KEY}"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/generate")
def generate(body: GenerationRequest, authorization: str | None = Header(default=None)):
    if not authorized(authorization):
        raise HTTPException(status_code=401, detail="Invalid gateway API key")
    target = CAPABILITIES.get(body.capability)
    if target is None:
        raise HTTPException(status_code=404, detail="Unknown capability")

    prompt = f"TASK: {body.task}\n{body.content}"
    try:
        if target["provider"] == "openai":
            response = OPENAI.chat.completions.create(
                model=target["model"],
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.choices[0].message.content
        else:
            response = ANTHROPIC.messages.create(
                model=target["model"],
                max_tokens=target.get("max_tokens", 2000),
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Upstream model request failed") from exc
    if text is None:
        raise HTTPException(status_code=502, detail="Upstream returned no text")
    return {"text": text}
