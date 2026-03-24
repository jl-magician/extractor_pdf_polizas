"""Shared test fixtures for policy_extractor tests."""
import re

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from policy_extractor.storage.models import Base, IngestionCache  # noqa: F401


@pytest.fixture
def engine():
    """In-memory SQLite engine with all tables created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """SQLAlchemy session bound to in-memory engine."""
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Coverage matrix plugin
# ---------------------------------------------------------------------------

_ALL_INSURERS = [
    "zurich", "qualitas", "mapfre", "axa", "gnp",
    "chubb", "ana", "hdi", "planseguro", "prudential",
]


def _parse_insurer_from_nodeid(nodeid: str) -> str:
    """Extract insurer slug from a pytest node ID.

    Expected format: path::test_name[{insurer}_{type}_{seq}]
    Returns the first token (insurer slug) if it is in _ALL_INSURERS,
    otherwise returns 'unknown'.
    """
    match = re.search(r"\[([^\]]+)\]$", nodeid)
    if not match:
        return "unknown"
    param_id = match.group(1)
    first_token = param_id.split("_")[0]
    if first_token in _ALL_INSURERS:
        return first_token
    return "unknown"


def _format_coverage_matrix(results: dict) -> str:
    """Format a coverage matrix table as an ASCII string.

    Args:
        results: dict mapping insurer slug -> {"pass": N, "fail": N, "skip": N}.
                 Insurers present in results but with all-zero counts are
                 treated as having fixtures (show 0s).
                 Insurers NOT present in results show '-' in all columns.

    Returns:
        Multi-line string with the matrix table.
    """
    col_widths = {"insurer": 14, "pass": 6, "fail": 6, "skip": 6, "total": 7}
    sep = (
        "-" * col_widths["insurer"]
        + "+"
        + "-" * col_widths["pass"]
        + "+"
        + "-" * col_widths["fail"]
        + "+"
        + "-" * col_widths["skip"]
        + "+"
        + "-" * col_widths["total"]
    )

    header = (
        f"{'Insurer':<{col_widths['insurer']}}"
        f"| {'Pass':>{col_widths['pass'] - 2}} "
        f"| {'Fail':>{col_widths['fail'] - 2}} "
        f"| {'Skip':>{col_widths['skip'] - 2}} "
        f"| {'Total':>{col_widths['total'] - 2}} "
    )

    lines = ["=== Regression Coverage Matrix ===", header, sep]

    total_pass = 0
    total_fail = 0
    total_skip = 0

    for insurer in sorted(_ALL_INSURERS):
        if insurer in results:
            p = results[insurer]["pass"]
            f = results[insurer]["fail"]
            s = results[insurer]["skip"]
            t = p + f + s
            total_pass += p
            total_fail += f
            total_skip += s
            row = (
                f"{insurer:<{col_widths['insurer']}}"
                f"| {p:>{col_widths['pass'] - 2}} "
                f"| {f:>{col_widths['fail'] - 2}} "
                f"| {s:>{col_widths['skip'] - 2}} "
                f"| {t:>{col_widths['total'] - 2}} "
            )
        else:
            dash = "-"
            row = (
                f"{'(missing)':<{col_widths['insurer']}}"
                f"| {dash:>{col_widths['pass'] - 2}} "
                f"| {dash:>{col_widths['fail'] - 2}} "
                f"| {dash:>{col_widths['skip'] - 2}} "
                f"| {dash:>{col_widths['total'] - 2}} "
            )
            # Append insurer name in row for readability — replace (missing) with name
            row = (
                f"{insurer:<{col_widths['insurer']}}"
                f"| {dash:>{col_widths['pass'] - 2}} "
                f"| {dash:>{col_widths['fail'] - 2}} "
                f"| {dash:>{col_widths['skip'] - 2}} "
                f"| {dash:>{col_widths['total'] - 2}} "
            )
        lines.append(row)

    # Total row
    lines.append(sep)
    total = total_pass + total_fail + total_skip
    total_row = (
        f"{'TOTAL':<{col_widths['insurer']}}"
        f"| {total_pass:>{col_widths['pass'] - 2}} "
        f"| {total_fail:>{col_widths['fail'] - 2}} "
        f"| {total_skip:>{col_widths['skip'] - 2}} "
        f"| {total:>{col_widths['total'] - 2}} "
    )
    lines.append(total_row)

    return "\n".join(lines)


class RegressionCoveragePlugin:
    """Pytest plugin that collects regression test results and prints a coverage matrix."""

    def __init__(self):
        self._results: dict = {
            ins: {"pass": 0, "fail": 0, "skip": 0} for ins in _ALL_INSURERS
        }
        self._has_regression = False

    def pytest_runtest_logreport(self, report):
        if "regression" not in report.keywords:
            return
        if report.when != "call" and not (report.when == "setup" and report.skipped):
            return
        self._has_regression = True
        insurer = _parse_insurer_from_nodeid(report.nodeid)
        if insurer not in self._results:
            self._results[insurer] = {"pass": 0, "fail": 0, "skip": 0}
        if report.passed:
            self._results[insurer]["pass"] += 1
        elif report.failed:
            self._results[insurer]["fail"] += 1
        elif report.skipped:
            self._results[insurer]["skip"] += 1

    def pytest_terminal_summary(self, terminalreporter, config):
        if not self._has_regression:
            return
        terminalreporter.write_line("")
        terminalreporter.write_line(_format_coverage_matrix(self._results))


def pytest_configure(config):
    config.pluginmanager.register(RegressionCoveragePlugin(), "regression_coverage")
