"""Validation tests for fields used by the in-popup administrator composer."""

import unittest
from pydantic import ValidationError

from app.schemas.service_request_event import NotificationPublishRequest


class AdminNotificationRequestTest(unittest.TestCase):
    def test_accepts_request_id_and_200_character_message(self):
        request = NotificationPublishRequest(
            target_type="all",
            request_id="REQ-2026-1042",
            title="REQ-2026-1042",
            message="x" * 200,
        )

        self.assertEqual(request.request_id, "REQ-2026-1042")
        self.assertEqual(len(request.message), 200)

    def test_rejects_message_over_200_characters(self):
        with self.assertRaises(ValidationError):
            NotificationPublishRequest(
                target_type="all",
                title="REQ-2026-1042",
                message="x" * 201,
            )

    def test_accepts_multiple_individual_recipients(self):
        request = NotificationPublishRequest(
            target_type="user",
            title="Notification",
            message="Please review this update.",
            employee_nos=["EMP1001", "EMP1002"],
        )
        self.assertEqual(request.employee_nos, ["EMP1001", "EMP1002"])

    def test_rejects_duplicate_individual_recipients(self):
        with self.assertRaises(ValidationError):
            NotificationPublishRequest(
                target_type="user",
                title="Notification",
                message="Update",
                employee_nos=["EMP1001", "EMP1001"],
            )
