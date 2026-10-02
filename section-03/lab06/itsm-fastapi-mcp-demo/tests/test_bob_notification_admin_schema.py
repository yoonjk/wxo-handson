"""Validation for Bob group names accepted by the management console."""

import unittest
from pydantic import ValidationError

from app.schemas.bob_notification_admin import BobGroupCreate


class BobGroupCreateSchemaTest(unittest.TestCase):
    def test_accepts_lowercase_group_name_and_optional_description(self):
        group = BobGroupCreate(group_name="operations.core-1", description="Operations team")
        self.assertEqual(group.group_name, "operations.core-1")
        self.assertEqual(group.description, "Operations team")

    def test_rejects_uppercase_or_invalid_start(self):
        for name in ("Operations", "1operations", "_operations", "ops team"):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                BobGroupCreate(group_name=name)
