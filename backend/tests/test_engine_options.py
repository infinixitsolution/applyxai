"""
automation/options.py must match modules/validator.py exactly. The validator is parsed, not
imported, because importing it loads config/*.py and the local user_config.json.
"""

import ast
from pathlib import Path

from automation.options import ENGINE_INT_MINIMUMS, ENGINE_OPTIONS

VALIDATOR = Path(__file__).resolve().parents[2] / "modules" / "validator.py"


def _validator_calls():
    options, int_minimums = {}, {}
    for node in ast.walk(ast.parse(VALIDATOR.read_text(encoding="utf-8"))):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        args = node.args
        if len(args) < 2 or not isinstance(args[1], ast.Constant):
            continue
        name = args[1].value
        if node.func.id in ("check_string", "check_list") and len(args) >= 3 and isinstance(args[2], ast.List):
            options[name] = [ast.literal_eval(e) for e in args[2].elts]
        if node.func.id == "check_int":
            int_minimums[name] = ast.literal_eval(args[2]) if len(args) >= 3 else 0
    return options, int_minimums


def test_option_lists_match_the_engine_validator():
    validator_options, _ = _validator_calls()
    for name, values in ENGINE_OPTIONS.items():
        assert name in validator_options, f"{name} has no option list in modules/validator.py"
        assert values == validator_options[name], f"{name} drifted from modules/validator.py"


def test_int_minimums_match_the_engine_validator():
    _, validator_ints = _validator_calls()
    for name, minimum in ENGINE_INT_MINIMUMS.items():
        assert validator_ints.get(name) == minimum, name


def test_every_validator_option_list_is_mirrored():
    validator_options, _ = _validator_calls()
    unmirrored = set(validator_options) - set(ENGINE_OPTIONS) - {"ai_provider"}   # AI config isn't stored server-side
    assert unmirrored == set(), f"add these to automation/options.py: {unmirrored}"
