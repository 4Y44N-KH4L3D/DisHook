import unittest
from datetime import datetime

from discord_logic import (
    MAX_CONTENT,
    MAX_EMBED_CONTENT,
    build_embed,
    build_payload,
    embed_size,
    payload_errors,
    unwrap_payload,
    valid_url,
    valid_webhook,
    color_values,
    replace_placeholders,
    sanitize_payload,
    normalize_template,
    validate_payload,
)
from network import broadcast_requests


class DiscordLogicTests(unittest.TestCase):
    def test_url_validation(self):
        self.assertTrue(valid_url("https://example.com/image.png"))
        self.assertFalse(valid_url("javascript:alert(1)"))
        self.assertFalse(valid_url("not a URL"))

    def test_webhook_validation(self):
        self.assertTrue(valid_webhook("https://discord.com/api/webhooks/123/token"))
        self.assertTrue(valid_webhook("https://discordapp.com/api/webhooks/123/token"))
        self.assertFalse(valid_webhook("http://discord.com/api/webhooks/123/token"))
        self.assertFalse(valid_webhook("https://example.com/api/webhooks/123/token"))

    def test_embed_trims_fields_and_omits_invalid_urls(self):
        embed = build_embed(
            enabled=True,
            title=" title ",
            description=" description ",
            url="not-a-url",
            fields=[{"name": " name ", "value": " value ", "inline": True}],
            image_url="https://example.com/image.png",
            color="#123456",
        )
        self.assertEqual(embed["title"], "title")
        self.assertNotIn("url", embed)
        self.assertEqual(embed["fields"], [{"name": "name", "value": "value", "inline": True}])
        self.assertEqual(embed["color"], 0x123456)

    def test_empty_embed_is_none(self):
        self.assertIsNone(build_embed(enabled=True))

    def test_payload_and_limits(self):
        embed = build_embed(enabled=True, title="hello")
        payload = build_payload("hello", "sender", embed)
        self.assertEqual(payload["allowed_mentions"], {"parse": []})
        self.assertEqual(payload["content"], "hello")
        self.assertEqual(payload["embeds"], [embed])
        self.assertEqual(payload_errors("x" * (MAX_CONTENT + 1), embed), [
            "Message content exceeds 2,000 characters."
        ])
        oversized = {"description": "x" * (MAX_EMBED_CONTENT + 1), "color": 1}
        self.assertEqual(embed_size(oversized), MAX_EMBED_CONTENT + 1)
        self.assertTrue(payload_errors("", oversized))

    def test_unwrap_payload_containers(self):
        payload = {"content": "hello"}
        self.assertEqual(unwrap_payload({"messages": [payload]}), payload)
        self.assertEqual(unwrap_payload([payload]), payload)
        with self.assertRaises(ValueError):
            unwrap_payload({"messages": [payload, payload]})

    def test_color_values_and_placeholders(self):
        self.assertEqual(color_values("#abc"), ("#AABBCC", 0xAABBCC))
        self.assertEqual(
            replace_placeholders(
                "{date} {time} {computer_name}",
                datetime(2024, 1, 2, 3, 4, 5),
                "desk",
            ),
            "2024-01-02 03:04:05.000 desk",
        )

    def test_payload_validation_keeps_mentions_safe(self):
        self.assertTrue(validate_payload({"content": "hello", "allowed_mentions": {"parse": []}}))
        with self.assertRaises(ValueError):
            validate_payload({"content": "hello", "allowed_mentions": {"parse": ["users"]}})

    def test_import_sanitizes_nested_types_and_limits(self):
        payload = sanitize_payload({
            "content": "hello",
            "embeds": [{
                "author": {"name": "A"},
                "footer": {"text": "F"},
                "image": {"url": "https://example.com/a.png"},
                "thumbnail": {"url": "https://example.com/t.png"},
                "fields": [{"name": "N", "value": "V", "inline": True}],
            }],
        })
        self.assertEqual(payload["allowed_mentions"], {"parse": []})
        self.assertEqual(payload["embeds"][0]["fields"][0]["inline"], True)
        with self.assertRaisesRegex(ValueError, "author"):
            sanitize_payload({"embeds": [{"author": "bad"}]})

    def test_template_normalization_clears_bad_avatar_type(self):
        data = normalize_template({"avatar_path": 4, "embed": {}})
        self.assertEqual(data["avatar_path"], "")

    def test_payload_sanitization_rejects_limits(self):
        with self.assertRaisesRegex(ValueError, "2,000"):
            sanitize_payload({"content": "x" * (MAX_CONTENT + 1)})

    def test_broadcast_factory_runs_per_webhook(self):
        class Response:
            status_code = 204
            ok = True

        class Session:
            def __init__(self):
                self.payloads = []

            def post(self, url, json, timeout):
                self.payloads.append((url, json))
                return Response()

        session = Session()
        values = iter(("one", "two"))
        result = broadcast_requests(
            ["a", "b"], payload_factory=lambda: {"content": next(values)}, session=session
        )
        self.assertEqual([item["ok"] for item in result], [True, True])
        self.assertEqual([item[1]["content"] for item in session.payloads], ["one", "two"])

    def test_malformed_rate_limit_body_is_safe(self):
        class Response:
            def __init__(self, status):
                self.status_code = status
                self.ok = status in (200, 204)
                self.headers = {"Retry-After": "0"}

            def json(self):
                return []

        class Session:
            def __init__(self):
                self.responses = iter((Response(429), Response(204)))

            def post(self, url, json, timeout):
                return next(self.responses)

        result = broadcast_requests(["a"], {"content": "x"}, session=Session())
        self.assertEqual(result, [{"ok": True, "status": 204}])


if __name__ == "__main__":
    unittest.main()
