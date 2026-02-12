from __future__ import annotations

import pytest

from schedula.utils.form.server.contracts.schedule import explode_cron


def test_explode_cron_with_steps_ranges_and_wildcards() -> None:
    cron = explode_cron("*/15 9-17 * * 1-5")
    assert cron["minutes"] == [0, 15, 30, 45]
    assert cron["hours"] == list(range(9, 18))
    assert cron["dom_any"] is True
    assert cron["dow_any"] is False
    assert cron["dow"] == [1, 2, 3, 4, 5]


def test_explode_cron_maps_sunday_7_to_0() -> None:
    cron = explode_cron("0 8 * * 7")
    assert cron["minutes"] == [0]
    assert cron["hours"] == [8]
    assert cron["dow"] == [0]


def test_explode_cron_rejects_invalid_expression() -> None:
    with pytest.raises(ValueError):
        explode_cron("*/5 * * *")

    with pytest.raises(ValueError):
        explode_cron("61 * * * *")
