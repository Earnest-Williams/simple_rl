import pytest

from scripts.run_auto_regression import run_regression

pytest.importorskip("numpy")


def test_auto_regression_headless_run_completes():
    summary = run_regression(seed=12345, num_runs=1, max_turns=25)

    assert summary["completed_runs"] == 1
    assert summary["num_runs"] == 1
    assert summary["max_turns"] == 25
    assert len(summary["runs"]) == 1

    run = summary["runs"][0]
    assert 0 < run["turns_survived"] <= summary["max_turns"]
    assert isinstance(run["outcome"], str)
