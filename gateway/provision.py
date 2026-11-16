"""Create the application's scoped LiteLLM virtual key during proxy startup."""

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

base = "http://127.0.0.1:4000"
master = os.environ["LITELLM_MASTER_KEY"]
app_key = os.environ["GATEWAY_APP_KEY"]
models = [
    "ticket-classification", "ticket-classification-tech", "ticket-classification-mini",
    "order-extraction", "order-extraction-tech",
    "reply-suggestion", "reply-suggestion-tech", "reply-suggestion-mini",
    "ticket-topics", "ticket-topics-tech", "ticket-topics-mini",
]


def call(path, method="GET", token=master, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = Request(base + path, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    with urlopen(request, timeout=3) as response:
        return json.load(response)


for attempt in range(60):
    try:
        # Existing keys survive a proxy restart because LiteLLM stores them in PostgreSQL.
        call("/key/info", token=app_key)
        call("/key/update", method="POST", body={"key": app_key, "models": models})
        break
    except HTTPError as error:
        if error.code not in (401, 403, 404):
            raise
        call("/key/generate", method="POST", body={
            "key": app_key,
            "key_alias": "helpdesk-app",
            "models": models,
            "max_budget": 10,
            "budget_duration": "monthly",
            "rpm_limit": 120,
        })
        break
    except (URLError, TimeoutError):
        time.sleep(1)
else:
    raise RuntimeError("LiteLLM virtual key provisioning did not become ready")
