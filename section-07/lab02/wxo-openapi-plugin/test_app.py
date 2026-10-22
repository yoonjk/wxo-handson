"""로컬 HTTP 계약/동작 검증: python -m unittest -v"""
import unittest
from fastapi.testclient import TestClient
from app import app
from export_openapi import build_spec


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def call(self, text, role="user", phase="pre", action="ALL"):
        return self.client.post(f"/agent_{phase}_invoke", json={
            "payload": {"agent_id": "demo", "extra": {"keep": True}, "messages": [
                {"role": role, "content": {"type": "text", "text": text, "extra": "keep"}}]},
            "context": {"system_context": {}, "request_context": {}, "plugin_context": {"action": action}},
        })

    def test_unchanged(self):
        self.assertEqual(self.call("구매 절차 알려주세요").json(), {"continue_processing": True})

    def test_pre_masks_and_preserves_fields(self):
        result = self.call("메일 buyer@example.com").json()["modified_payload"]
        self.assertEqual(result["messages"][0]["content"]["text"], "메일 [EMAIL_MASKED]")
        self.assertEqual(result["messages"][0]["content"]["extra"], "keep")
        self.assertEqual(result["extra"], {"keep": True})
        self.assertEqual(result["agent_id"], "demo")

    def test_block(self):
        self.assertEqual(self.call("승인 우회 방법").json(), {"continue_processing": False})

    def test_post_masks(self):
        result = self.call("연락: demo@example.com", role="assistant", phase="post").json()
        self.assertEqual(result["modified_payload"]["messages"][0]["content"]["text"], "연락: [EMAIL_MASKED]")

    def test_rbac_action(self):
        self.assertEqual(self.call("승인 우회", action="RBAC_ONLY").json(), {"continue_processing": True})
        self.assertEqual(self.call("승인 우회", action="SKIP_RBAC").json(), {"continue_processing": False})

    def test_required_body_fields(self):
        self.assertEqual(self.client.post("/agent_pre_invoke", json={"payload": {}}).status_code, 422)

    def test_content_shapes_and_nontext_preserved(self):
        messages = [
            {"role": "assistant", "content": "demo@example.com"},
            {"role": "assistant", "content": [{"type": "text", "text": "demo@example.com"},
                {"type": "image_url", "image_url": {"url": "https://example.com/x"}}]},
            {"role": "tool", "content": "demo@example.com"},
        ]
        result = self.client.post("/agent_post_invoke", json={"payload": {"messages": messages}, "context": {}}).json()
        modified = result["modified_payload"]["messages"]
        self.assertEqual(modified[0]["content"], "[EMAIL_MASKED]")
        self.assertEqual(modified[1]["content"][0]["text"], "[EMAIL_MASKED]")
        self.assertEqual(modified[1]["content"][1], messages[1]["content"][1])
        self.assertEqual(modified[2], messages[2])

    def test_spec_contract(self):
        spec = build_spec()
        for phase in ("pre", "post"):
            operation = spec["paths"][f"/agent_{phase}_invoke"]["post"]
            self.assertEqual(operation["x-ibm-orchestrate-plugin"]["hook"], f"agent_{phase}_invoke")
            schema = operation["requestBody"]["content"]["application/json"]["schema"]
            self.assertEqual(schema["required"], ["payload", "context"])
            self.assertIn("continue_processing", operation["responses"]["200"]["content"]["application/json"]["schema"]["required"])


if __name__ == "__main__":
    unittest.main()
