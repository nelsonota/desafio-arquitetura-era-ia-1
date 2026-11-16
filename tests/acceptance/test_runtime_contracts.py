import json
import os
import time
import unittest
import urllib.error
import urllib.request
import uuid
from datetime import datetime

EDGE = os.environ.get("HELPDESK_URL", "http://edge").rstrip("/")
GATEWAY = os.environ.get("GATEWAY_URL", "http://gateway:4000/v1").rstrip("/").removesuffix("/v1")
FAKE = os.environ.get("PROVIDER_FAKE_URL", "http://provider-fake:8090").rstrip("/")
MASTER = os.environ.get("LITELLM_MASTER_KEY", "sk-litellm-gateway-dev")
TICKET = {"ticket_id": "TK-00042", "text": "Meu pedido #481516 não chegou e já passou do prazo, urgente"}


def request(url, data=None, token=None, timeout=10):
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, body, headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read()
            return response.status, json.loads(content) if content else {}, response.headers
    except urllib.error.HTTPError as error:
        content = error.read()
        try:
            decoded = json.loads(content) if content else {}
        except json.JSONDecodeError:
            decoded = content.decode(errors="replace")
        return error.code, decoded, error.headers


def provider_calls():
    return request(FAKE + "/admin/calls")[1]


def reset_provider():
    request(FAKE + "/admin/reset", {})


class RuntimeContracts(unittest.TestCase):
    def setUp(self):
        reset_provider()

    def tearDown(self):
        reset_provider()

    def test_f1_sync_latency_and_fallback(self):
        started = time.monotonic()
        status, body, _ = request(EDGE + "/tickets/classification", TICKET, timeout=10)
        self.assertEqual(status, 200)
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(body["category"], "delivery")

        request(FAKE + "/admin/failures", {"provider": "openai", "model": "gpt-fake-large", "mode": "timeout"})
        started = time.monotonic()
        status, body, _ = request(EDGE + "/tickets/classification", TICKET, timeout=15)
        self.assertEqual(status, 200)
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual(body["category"], "delivery")
        self.assertTrue(any(c["provider"] == "anthropic" and c["status"] == 200 for c in provider_calls()))

        reset_provider()
        request(FAKE + "/admin/failures", {"provider": "openai", "model": "gpt-fake-large", "mode": "error_500"})
        request(FAKE + "/admin/failures", {"provider": "anthropic", "model": "claude-fake-large", "mode": "error_500"})
        status, body, _ = request(EDGE + "/tickets/classification", TICKET, timeout=15)
        self.assertEqual(status, 200)
        self.assertEqual(body["category"], "delivery")
        self.assertTrue(any(c["model"] == "gpt-fake-mini" and c["status"] == 200 for c in provider_calls()))

    def test_transient_500_retries_once_with_backoff_before_fallback(self):
        request(FAKE + "/admin/failures", {
            "provider": "openai", "model": "gpt-fake-large", "mode": "error_500",
        })
        started = time.monotonic()
        status, body, _ = request(EDGE + "/tickets/classification", TICKET, timeout=15)
        self.assertEqual(status, 200)
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual(body["category"], "delivery")
        calls = provider_calls()
        primary = [c for c in calls if c["provider"] == "openai" and c["model"] == "gpt-fake-large"]
        self.assertEqual(len(primary), 2)
        timestamps = sorted(datetime.fromisoformat(c["ts"]) for c in primary)
        self.assertGreaterEqual((timestamps[1] - timestamps[0]).total_seconds(), 0.5)
        self.assertTrue(any(c["provider"] == "anthropic" and c["status"] == 200 for c in calls))

    def test_f2_streams_early_and_midstream_error_is_visible(self):
        req = urllib.request.Request(
            EDGE + "/tickets/reply-suggestion",
            json.dumps(TICKET).encode(),
            {"Content-Type": "application/json"},
        )
        started = time.monotonic()
        with urllib.request.urlopen(req, timeout=60) as response:
            first = response.readline().decode()
            first_latency = time.monotonic() - started
            self.assertEqual(response.status, 200)
            self.assertLess(first_latency, 1.5)
            self.assertIn('"chunk"', first)
            remaining = response.read().decode()
            total_latency = time.monotonic() - started
            self.assertIn("event: end", remaining)
        self.assertLess(first_latency, total_latency / 2)
        reset_provider()
        request(FAKE + "/admin/failures", {
            "provider": "anthropic", "model": "claude-fake-large", "mode": "midstream_error",
        })
        req = urllib.request.Request(
            EDGE + "/tickets/reply-suggestion",
            json.dumps(TICKET).encode(),
            {"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            events = response.read().decode()
        self.assertIn("event: error", events)
        self.assertNotIn("event: end", events)
        calls = provider_calls()
        primary = [c for c in calls if c["provider"] == "anthropic" and c["model"] == "claude-fake-large"]
        self.assertEqual(len(primary), 1)
        self.assertFalse(any(c["provider"] == "openai" for c in calls))

    def test_f2_uses_equivalent_fallback_before_first_chunk(self):
        request(FAKE + "/admin/failures", {
            "provider": "anthropic", "model": "claude-fake-large", "mode": "error_500",
        })
        req = urllib.request.Request(
            EDGE + "/tickets/reply-suggestion",
            json.dumps(TICKET).encode(),
            {"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            events = response.read().decode()
        self.assertIn("event: end", events)
        calls = provider_calls()
        self.assertTrue(any(c["provider"] == "anthropic" and c["status"] == 500 for c in calls))
        self.assertTrue(any(c["provider"] == "openai" and c["model"] == "gpt-fake-large" and c["status"] == 200 for c in calls))

    def test_f2_uses_weak_fallback_before_first_chunk(self):
        request(FAKE + "/admin/failures", {"provider": "anthropic", "model": "claude-fake-large", "mode": "error_500"})
        request(FAKE + "/admin/failures", {"provider": "openai", "model": "gpt-fake-large", "mode": "error_500"})
        req = urllib.request.Request(
            EDGE + "/tickets/reply-suggestion",
            json.dumps(TICKET).encode(),
            {"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            events = response.read().decode()
        self.assertIn("event: end", events)
        self.assertTrue(any(c["model"] == "gpt-fake-mini" and c["status"] == 200 for c in provider_calls()))

    def test_f3_request_reply_delivers_all_tickets(self):
        started = time.monotonic()
        status, _, headers = request(EDGE + "/reports/topics", {
            "start": "2026-08-01", "end": "2026-08-31",
        })
        self.assertEqual(status, 202)
        self.assertLess(time.monotonic() - started, 1)
        self.assertLess(float(headers["Retry-After"]), 2)
        status_url = EDGE + headers["Location"]
        while time.monotonic() - started < 60:
            status, state, _ = request(status_url)
            if status == 200 and state.get("total_tickets") == 5000:
                break
            if state.get("state") == "failed":
                self.fail(state)
            time.sleep(1)
        else:
            self.fail("report did not finish within 60 seconds")
        self.assertTrue(any(c.get("task") == "topics" for c in provider_calls()))

    def test_f3_uses_weak_fallback_when_both_large_models_fail(self):
        request(FAKE + "/admin/failures", {"provider": "anthropic", "model": "claude-fake-large", "mode": "error_500"})
        request(FAKE + "/admin/failures", {"provider": "openai", "model": "gpt-fake-large", "mode": "error_500"})
        _, _, headers = request(EDGE + "/reports/topics", {
            "start": "2026-08-01", "end": "2026-08-01",
        })
        location = headers["Location"]
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            _, body, _ = request(EDGE + location)
            if "total_tickets" in body:
                self.assertTrue(any(c["model"] == "gpt-fake-mini" and c["status"] == 200 for c in provider_calls()))
                return
            if body.get("state") == "failed":
                self.fail(body)
            time.sleep(0.5)
        self.fail("report did not complete using its weak fallback")

    def test_f3_uses_equivalent_fallback_when_primary_fails(self):
        request(FAKE + "/admin/failures", {
            "provider": "anthropic", "model": "claude-fake-large", "mode": "error_500",
        })
        _, _, headers = request(EDGE + "/reports/topics", {
            "start": "2026-08-01", "end": "2026-08-01",
        })
        location = headers["Location"]
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            _, body, _ = request(EDGE + location)
            if "total_tickets" in body:
                calls = provider_calls()
                self.assertTrue(any(c["provider"] == "anthropic" and c["status"] == 500 for c in calls))
                self.assertTrue(any(c["provider"] == "openai" and c["model"] == "gpt-fake-large" and c["status"] == 200 for c in calls))
                return
            if body.get("state") == "failed":
                self.fail(body)
            time.sleep(0.5)
        self.fail("report did not finish using the equivalent fallback")

    def test_f3_all_providers_down_reaches_failed(self):
        request(FAKE + "/admin/failures", {"provider": "openai", "mode": "error_500"})
        request(FAKE + "/admin/failures", {"provider": "anthropic", "mode": "error_500"})
        _, _, headers = request(EDGE + "/reports/topics", {
            "start": "2026-08-01", "end": "2026-08-31",
        })
        location = headers["Location"]
        started = time.monotonic()
        while time.monotonic() - started < 60:
            _, body, _ = request(EDGE + location)
            if body.get("state") == "failed":
                self.assertTrue(body.get("reason"))
                return
            time.sleep(1)
        self.fail("report remained active longer than 60 seconds")

    def test_f4_never_uses_weak_model(self):
        request(FAKE + "/admin/failures", {"provider": "openai", "model": "gpt-fake-large", "mode": "error_500"})
        request(FAKE + "/admin/failures", {"provider": "anthropic", "model": "claude-fake-large", "mode": "error_500"})
        status, _, _ = request(EDGE + "/tickets/extraction", TICKET)
        self.assertEqual(status, 502)
        self.assertFalse(any("mini" in call["model"] for call in provider_calls()))

    def test_f4_uses_equivalent_large_fallback(self):
        request(FAKE + "/admin/failures", {
            "provider": "openai", "model": "gpt-fake-large", "mode": "error_500",
        })
        status, body, _ = request(EDGE + "/tickets/extraction", {
            "ticket_id": "TK-EXTRACT", "text": "O mouse sem fio do pedido #605065 não chegou",
        })
        self.assertEqual(status, 200)
        self.assertEqual(body["order_number"], "#605065")
        self.assertEqual(body["product"], "mouse sem fio")
        calls = provider_calls()
        self.assertTrue(any(c["provider"] == "openai" and c["status"] == 500 for c in calls))
        self.assertTrue(any(c["provider"] == "anthropic" and c["model"] == "claude-fake-large" and c["status"] == 200 for c in calls))

    def test_gateway_budget_and_rpm_rejections_never_reach_provider(self):
        suffix = uuid.uuid4().hex[:8]
        budget_key = "sk-acceptance-budget-" + suffix
        rpm_key = "sk-acceptance-rpm-" + suffix
        request(GATEWAY + "/key/generate", {
            "key": budget_key, "models": ["ticket-classification"],
            "max_budget": 0.000001, "budget_duration": "monthly",
        }, MASTER)
        request(GATEWAY + "/key/generate", {
            "key": rpm_key, "models": ["ticket-classification"], "rpm_limit": 1,
        }, MASTER)

        def completion(key):
            return request(GATEWAY + "/v1/chat/completions", {
                "model": "ticket-classification",
                "messages": [{"role": "user", "content": "TASK: classify\nurgente"}],
            }, key)

        try:
            completion(budget_key)
            count = len(provider_calls())
            status, _, _ = completion(budget_key)
            self.assertEqual(status, 429)
            self.assertEqual(count, len(provider_calls()))

            completion(rpm_key)
            count = len(provider_calls())
            status, _, _ = completion(rpm_key)
            self.assertEqual(status, 429)
            self.assertEqual(count, len(provider_calls()))
        finally:
            request(GATEWAY + "/key/delete", {"keys": [budget_key, rpm_key]}, MASTER)


if __name__ == "__main__":
    unittest.main()
