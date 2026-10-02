"""Scope-routing unit tests, independent of FastAPI/MySQL runtime services."""

import unittest

from itsm_event_mcp.routing import configured_recipients, matches_recipient


class NotificationRoutingTest(unittest.TestCase):
    def setUp(self):
        self.tokens = {"EMP1001": "token-1", "EMP1002": "token-2", "EMP1003": "token-3"}
        self.groups = {
            "EMP1001": {"operations", "payments"},
            "EMP1002": {"operations", "managers"},
            "EMP1003": set(),
        }

    def test_all_scope_selects_every_registered_user(self):
        recipients = configured_recipients("all", None, None, self.tokens, self.groups)
        self.assertEqual(set(recipients), set(self.tokens))
        event = {"event_type": "notification.created", "payload": {"recipient_scope": "all"}}
        self.assertTrue(all(matches_recipient(event, employee, self.tokens, self.groups) for employee in self.tokens))

    def test_group_scope_selects_only_group_members(self):
        recipients = configured_recipients("group", "operations", None, self.tokens, self.groups)
        self.assertEqual(set(recipients), {"EMP1001", "EMP1002"})
        event = {
            "event_type": "notification.created",
            "payload": {"recipient_scope": "group", "recipient_group": "operations"},
        }
        self.assertTrue(matches_recipient(event, "EMP1001", self.tokens, self.groups))
        self.assertFalse(matches_recipient(event, "EMP1003", self.tokens, self.groups))

    def test_user_scope_selects_only_employee(self):
        recipients = configured_recipients("user", None, "EMP1002", self.tokens, self.groups)
        self.assertEqual(recipients, ["EMP1002"])
        event = {
            "event_type": "notification.created",
            "payload": {"recipient_scope": "user", "recipient_employee_no": "EMP1002"},
        }
        self.assertTrue(matches_recipient(event, "EMP1002", self.tokens, self.groups))
        self.assertFalse(matches_recipient(event, "EMP1001", self.tokens, self.groups))

    def test_individual_multi_select_delivers_only_to_selected_employees(self):
        event = {
            "event_type": "notification.created",
            "payload": {
                "recipient_scope": "user",
                "recipient_employee_nos": ["EMP1001", "EMP1003"],
            },
        }
        self.assertTrue(matches_recipient(event, "EMP1001", self.tokens, self.groups))
        self.assertTrue(matches_recipient(event, "EMP1003", self.tokens, self.groups))
        self.assertFalse(matches_recipient(event, "EMP1002", self.tokens, self.groups))

    def test_unknown_user_and_empty_group_are_rejected(self):
        with self.assertRaises(ValueError):
            configured_recipients("user", None, "EMP9999", self.tokens, self.groups)
        with self.assertRaises(ValueError):
            configured_recipients("group", "unknown", None, self.tokens, self.groups)
        with self.assertRaises(ValueError):
            configured_recipients("all", None, None, {"EMP1004": ""}, self.groups)

    def test_group_members_without_registered_tokens_are_not_recipients(self):
        groups_without_token = {**self.groups, "EMP1004": {"operations"}}
        recipients = configured_recipients(
            "group", "operations", None, self.tokens, groups_without_token
        )
        self.assertEqual(set(recipients), {"EMP1001", "EMP1002"})

    def test_unrelated_event_is_not_delivered(self):
        event = {"event_type": "service_request.updated", "payload": {"status": "IN_PROGRESS"}}
        self.assertFalse(matches_recipient(event, "EMP1001", self.tokens, self.groups))

    def test_existing_sr_events_remain_assignee_specific(self):
        event = {
            "event_type": "service_request.created",
            "payload": {"recipient_employee_no": "EMP1001"},
        }
        self.assertTrue(matches_recipient(event, "EMP1001", self.tokens, self.groups))
        self.assertFalse(matches_recipient(event, "EMP1002", self.tokens, self.groups))


if __name__ == "__main__":
    unittest.main()
