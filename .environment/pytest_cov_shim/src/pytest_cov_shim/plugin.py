"""Minimal plugin that accepts pytest-cov CLI flags when pytest-cov is unavailable."""

from __future__ import annotations


def pytest_addoption(parser):
    group = parser.getgroup(
        "cov", "coverage reporting with distributed testing support"
    )
    group.addoption(
        "--cov",
        action="append",
        nargs="?",
        const=True,
        default=[],
        metavar="SOURCE",
        help="(shim) accepted but ignored",
    )
    group.addoption(
        "--cov-report",
        action="append",
        default=[],
        metavar="TYPE",
        help="(shim) accepted but ignored",
    )


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    cov_targets = config.getoption("--cov")
    cov_reports = config.getoption("--cov-report")
    if cov_targets or cov_reports:
        terminalreporter.section("coverage (shim)")
        terminalreporter.write_line(
            "pytest-cov is not installed in this offline environment; "
            "--cov options were accepted by a local shim and no coverage report was generated."
        )
