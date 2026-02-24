from __future__ import annotations

try:
    from tests.utils.server._unittest_guard import ensure_server_test_env
except Exception:
    from _unittest_guard import ensure_server_test_env

ensure_server_test_env()


import unittest

from schedula.utils.form.server.contracts.schedule import explode_cron


class TestContractsScheduleUnit(unittest.TestCase):
    def test_explode_cron_with_steps_ranges_and_wildcards(self) -> None:
        cron = explode_cron("*/15 9-17 * * 1-5")
        self.assertEqual(cron["minutes"], [0, 15, 30, 45])
        self.assertEqual(cron["hours"], list(range(9, 18)))
        self.assertIs(cron["dom_any"], True)
        self.assertIs(cron["dow_any"], False)
        self.assertEqual(cron["dow"], [1, 2, 3, 4, 5])

    def test_explode_cron_maps_sunday_7_to_0(self) -> None:
        cron = explode_cron("0 8 * * 7")
        self.assertEqual(cron["minutes"], [0])
        self.assertEqual(cron["hours"], [8])
        self.assertEqual(cron["dow"], [0])

    def test_explode_cron_rejects_invalid_expression(self) -> None:
        with self.assertRaises(ValueError):
            explode_cron("*/5 * * *")

        with self.assertRaises(ValueError):
            explode_cron("61 * * * *")
