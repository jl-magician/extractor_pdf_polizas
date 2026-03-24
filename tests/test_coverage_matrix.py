"""Unit tests for coverage matrix formatting helpers in conftest.py."""
import sys
from pathlib import Path

# Ensure conftest is importable as a module
sys.path.insert(0, str(Path(__file__).parent))

from conftest import _ALL_INSURERS, _format_coverage_matrix, _parse_insurer_from_nodeid


def test_parse_insurer_from_nodeid_known():
    """Test 1: Known insurer slug is extracted correctly."""
    nodeid = "tests/test_regression.py::test_regression_fixture[zurich_auto_001]"
    assert _parse_insurer_from_nodeid(nodeid) == "zurich"


def test_parse_insurer_from_nodeid_unknown_format():
    """Test 2: Unknown format returns 'unknown'."""
    nodeid = "tests/test_something.py::test_foo[bar]"
    assert _parse_insurer_from_nodeid(nodeid) == "unknown"


def test_parse_insurer_from_nodeid_no_brackets():
    """Test 2b: No parametrize brackets returns 'unknown'."""
    nodeid = "tests/test_regression.py::test_regression_fixture"
    assert _parse_insurer_from_nodeid(nodeid) == "unknown"


def test_parse_insurer_from_nodeid_all_insurers():
    """Test all 10 insurers are correctly parsed."""
    for insurer in _ALL_INSURERS:
        nodeid = f"tests/test_regression.py::test_regression_fixture[{insurer}_auto_001]"
        assert _parse_insurer_from_nodeid(nodeid) == insurer, f"Failed for insurer: {insurer}"


def test_format_coverage_matrix_all_insurers_listed():
    """Test 3: Matrix with mixed results shows all 10 insurers."""
    results = {
        "zurich": {"pass": 2, "fail": 0, "skip": 0},
        "qualitas": {"pass": 1, "fail": 1, "skip": 0},
    }
    matrix = _format_coverage_matrix(results)
    for insurer in _ALL_INSURERS:
        assert insurer in matrix, f"Insurer '{insurer}' not found in matrix"


def test_format_coverage_matrix_correct_counts():
    """Test 4: Matrix shows correct pass/fail/skip counts per insurer."""
    results = {
        "zurich": {"pass": 3, "fail": 1, "skip": 2},
        "axa": {"pass": 0, "fail": 2, "skip": 1},
    }
    matrix = _format_coverage_matrix(results)
    # zurich row should show 3, 1, 2
    lines = matrix.split("\n")
    zurich_line = next(l for l in lines if "zurich" in l)
    assert "3" in zurich_line
    assert "1" in zurich_line
    assert "2" in zurich_line


def test_format_coverage_matrix_missing_insurers_show_dash():
    """Test 5: Insurers with no fixtures show dashes in all columns."""
    # Only zurich has results, all others should show '-'
    results = {
        "zurich": {"pass": 1, "fail": 0, "skip": 0},
    }
    matrix = _format_coverage_matrix(results)
    lines = matrix.split("\n")
    # Check that at least one (missing) insurer row has '-'
    gnp_line = next((l for l in lines if "gnp" in l), None)
    assert gnp_line is not None
    assert "-" in gnp_line


def test_format_coverage_matrix_total_row():
    """Test 6: Matrix includes a total row at the bottom."""
    results = {
        "zurich": {"pass": 2, "fail": 1, "skip": 1},
        "qualitas": {"pass": 3, "fail": 0, "skip": 0},
    }
    matrix = _format_coverage_matrix(results)
    assert "TOTAL" in matrix


def test_format_coverage_matrix_total_sums():
    """Test 6b: Total row sums all pass/fail/skip correctly."""
    results = {
        "zurich": {"pass": 2, "fail": 1, "skip": 0},
        "qualitas": {"pass": 3, "fail": 0, "skip": 1},
    }
    matrix = _format_coverage_matrix(results)
    lines = matrix.split("\n")
    total_line = next(l for l in lines if "TOTAL" in l)
    # Total pass = 5, fail = 1, skip = 1
    assert "5" in total_line
    assert "1" in total_line


def test_format_coverage_matrix_header():
    """Matrix must include column headers."""
    results = {}
    matrix = _format_coverage_matrix(results)
    assert "Pass" in matrix or "pass" in matrix.lower()
    assert "Fail" in matrix or "fail" in matrix.lower()
    assert "Skip" in matrix or "skip" in matrix.lower()


def test_format_coverage_matrix_title():
    """Matrix must include the title line."""
    results = {}
    matrix = _format_coverage_matrix(results)
    assert "Coverage Matrix" in matrix
