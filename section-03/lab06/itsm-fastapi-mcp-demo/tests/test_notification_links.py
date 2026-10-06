"""Validation and serialization tests for notification resource links."""

import unittest

from pydantic import ValidationError

from app.schemas.service_request_event import NotificationPublishRequest


class NotificationLinksTest(unittest.TestCase):
    def test_titled_http_links_are_included_in_json_payload(self):
        request = NotificationPublishRequest.model_validate(
            {
                "target_type": "all",
                "title": "Deployment notice",
                "message": "Read the attached release materials.",
                "links": [
                    {"title": "Runbook", "url": "https://example.com/runbook/123"},
                    {"title": "Release notes", "url": "https://example.com/releases/1.4"},
                ],
            }
        )

        self.assertEqual(
            request.model_dump(mode="json")["links"],
            [
                {"title": "Runbook", "url": "https://example.com/runbook/123"},
                {"title": "Release notes", "url": "https://example.com/releases/1.4"},
            ],
        )

    def test_non_http_link_is_rejected(self):
        with self.assertRaises(ValidationError):
            NotificationPublishRequest.model_validate(
                {
                    "target_type": "user",
                    "employee_no": "EMP1001",
                    "title": "Unsafe link",
                    "message": "This should fail validation.",
                    "links": [{"title": "Local file", "url": "file:///etc/passwd"}],
                }
            )

    def test_more_than_ten_links_is_rejected(self):
        with self.assertRaises(ValidationError):
            NotificationPublishRequest.model_validate(
                {
                    "target_type": "all",
                    "title": "Too many links",
                    "message": "A message allows up to ten links.",
                    "links": [
                        {"title": f"Link {number}", "url": f"https://example.com/{number}"}
                        for number in range(11)
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
