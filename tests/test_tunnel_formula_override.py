#!/usr/bin/env python3
"""Regression tests for tunnel formula override persistence and password resolution."""

import json
import os
import tempfile
from pathlib import Path

# Import from repository root.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tunnel_traffic_widget import TunnelTrafficWidget


def test_apply_formula_overrides_marks_override_and_updates_value():
    cells = [
        {
            "coordinate": "P8",
            "formula": "=1/D10",
            "value": 10,
            "manual_override": False,
        },
        {
            "coordinate": "D22",
            "formula": None,
            "value": 0.01,
            "manual_override": False,
        },
    ]

    changed = TunnelTrafficWidget._apply_formula_overrides(cells, {"P8": ""})

    assert changed is True
    assert cells[0]["value"] == ""
    assert cells[0]["manual_override"] is True
    # Non-formula cell remains unchanged.
    assert cells[1]["value"] == 0.01


def test_apply_formula_overrides_no_change_when_no_formula_table_values():
    cells = [
        {
            "coordinate": "Q8",
            "formula": "=1/D11",
            "value": 12,
            "manual_override": True,
        }
    ]

    changed = TunnelTrafficWidget._apply_formula_overrides(cells, {})

    assert changed is False
    assert cells[0]["value"] == 12
    assert cells[0]["manual_override"] is True


def test_resolve_admin_password_prefers_env_over_default():
    previous = os.environ.get("QRA_ADMIN_PASSWORD")
    try:
        os.environ["QRA_ADMIN_PASSWORD"] = "secure123"
        assert TunnelTrafficWidget._resolve_admin_password() == "secure123"
    finally:
        if previous is None:
            os.environ.pop("QRA_ADMIN_PASSWORD", None)
        else:
            os.environ["QRA_ADMIN_PASSWORD"] = previous


if __name__ == "__main__":
    test_apply_formula_overrides_marks_override_and_updates_value()
    test_apply_formula_overrides_no_change_when_no_formula_table_values()
    test_resolve_admin_password_prefers_env_over_default()
    print("All tunnel formula override regression tests passed.")
