#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click==8.3.3",
#     "pytest==9.0.3",
# ]
#
# [tool.uv]
# exclude-newer = "2026-10-27T00:00:00Z"
# ///
"""Offline tests for macos_osascript_cli: `subprocess.run` is stubbed, no app is driven."""

from __future__ import annotations

import importlib.util
import json
import plistlib
import subprocess
import sys
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

# The CLI is a script at the repo root, not an installed package.
_SPEC = importlib.util.spec_from_file_location(
    "macos_osascript_cli", Path(__file__).resolve().parent.parent / "macos_osascript_cli.py"
)
osa = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(osa)

SDEF = """<?xml version="1.0"?>
<dictionary>
  <suite name="Standard Suite">
    <command name="close" description="Close a window."/>
    <class name="window" description="A window.">
      <property name="name"/>
      <property name="bounds"/>
    </class>
  </suite>
  <suite name="Empty Suite"/>
</dictionary>
"""


class StubRun:
    """Records `subprocess.run` calls and answers with a canned result."""

    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = "") -> None:
        self.calls: list[dict] = []
        self.result = subprocess.CompletedProcess([], returncode, stdout, stderr)

    def __call__(self, cmd, **kwargs):
        self.calls.append({"cmd": cmd, **kwargs})
        return self.result


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def stub_ok(monkeypatch) -> StubRun:
    stub = StubRun(stdout="Macintosh HD\n")
    monkeypatch.setattr(osa.subprocess, "run", stub)
    return stub


def make_app(root: Path, name: str, plist: dict | None = None, sdef: bool = False) -> Path:
    app = root / f"{name}.app"
    (app / "Contents" / "Resources").mkdir(parents=True)
    if plist is not None:
        with (app / "Contents" / "Info.plist").open("wb") as fh:
            plistlib.dump(plist, fh)
    if sdef:
        (app / "Contents" / "Resources" / f"{name}.sdef").write_text(SDEF)
    return app


@pytest.mark.parametrize(
    "script",
    [
        'tell app "Finder" to delete file "x"',
        "empty the trash",
        'do shell script "ls"',
        'move file "x" to trash',
        "tell app \"System Events\" to shut down",
        "ERASE disk",
    ],
)
def test_guard_refuses_destructive(script: str) -> None:
    with pytest.raises(click.ClickException):
        osa._guard(script, write=False)


@pytest.mark.parametrize(
    "script",
    [
        'tell app "Finder" to get name of every disk',
        'set x to "deleted"',
        "make new reminder",
    ],
)
def test_guard_allows_reads(script: str) -> None:
    assert osa._guard(script, write=False) is None


def test_guard_allows_destructive_with_write() -> None:
    assert osa._guard('do shell script "ls"', write=True) is None


@pytest.mark.parametrize(
    ("plist", "sdef", "expected"),
    [
        ({"NSAppleScriptEnabled": True}, False, True),
        ({"NSAppleScriptEnabled": "YES"}, False, True),
        ({"OSAScriptingDefinition": "App.sdef"}, False, True),
        ({}, True, True),
        ({"NSAppleScriptEnabled": "NO"}, False, False),
        ({}, False, False),
        (None, True, False),
    ],
)
def test_is_scriptable(tmp_path: Path, plist, sdef: bool, expected: bool) -> None:
    assert osa._is_scriptable(make_app(tmp_path, "Example", plist, sdef)) is expected


def test_scriptable_apps_filters_coreservices(tmp_path: Path, monkeypatch) -> None:
    apps_dir, core = tmp_path / "Applications", tmp_path / "CoreServices"
    apps_dir.mkdir()
    core.mkdir()
    make_app(apps_dir, "zeta", {"NSAppleScriptEnabled": True})
    make_app(apps_dir, "Alpha", {"NSAppleScriptEnabled": True})
    make_app(apps_dir, "Plain", {})
    make_app(core, "Finder", {"NSAppleScriptEnabled": True})
    make_app(core, "Some Agent", {"NSAppleScriptEnabled": True})
    monkeypatch.setattr(osa, "APP_DIRS", [apps_dir])
    monkeypatch.setattr(osa, "CORESERVICES", core)
    assert osa._scriptable_apps(include_all=False) == ["Alpha", "Finder", "zeta"]


def test_scriptable_apps_all_includes_agents(tmp_path: Path, monkeypatch) -> None:
    core = tmp_path / "CoreServices"
    core.mkdir()
    make_app(core, "Some Agent", {"NSAppleScriptEnabled": True})
    monkeypatch.setattr(osa, "APP_DIRS", [])
    monkeypatch.setattr(osa, "CORESERVICES", core)
    assert osa._scriptable_apps(include_all=True) == ["Some Agent"]


def test_run_osascript_applescript_command(stub_ok: StubRun) -> None:
    osa._run_osascript("return 1", "applescript")
    assert stub_ok.calls[0]["cmd"] == ["osascript"]


def test_run_osascript_javascript_command(stub_ok: StubRun) -> None:
    osa._run_osascript("1", "javascript")
    assert stub_ok.calls[0]["cmd"] == ["osascript", "-l", "JavaScript"]


def test_run_osascript_feeds_script_on_stdin(stub_ok: StubRun) -> None:
    osa._run_osascript("return 1", "applescript")
    assert stub_ok.calls[0]["input"] == "return 1"


def test_resolve_app_path_uses_launch_services(monkeypatch) -> None:
    monkeypatch.setattr(osa.subprocess, "run", StubRun(stdout="/Applications/Example.app/\n"))
    assert osa._resolve_app_path("Example") == Path("/Applications/Example.app/")


def test_resolve_app_path_falls_back_to_fuzzy_scan(tmp_path: Path, monkeypatch) -> None:
    app = make_app(tmp_path, "Google Chrome", {})
    monkeypatch.setattr(osa.subprocess, "run", StubRun(returncode=1))
    monkeypatch.setattr(osa, "APP_DIRS", [tmp_path])
    monkeypatch.setattr(osa, "CORESERVICES", tmp_path / "missing")
    assert osa._resolve_app_path("chrome") == app


def test_apps_json_is_a_list(runner: CliRunner, monkeypatch) -> None:
    monkeypatch.setattr(osa, "_scriptable_apps", lambda include_all: ["Finder", "Mail"])
    result = runner.invoke(osa.cli, ["apps", "--json"])
    assert json.loads(result.output) == ["Finder", "Mail"]


def test_apps_text_one_per_line(runner: CliRunner, monkeypatch) -> None:
    monkeypatch.setattr(osa, "_scriptable_apps", lambda include_all: ["Finder", "Mail"])
    assert runner.invoke(osa.cli, ["apps"]).output == "Finder\nMail\n"


def test_tell_wraps_body(runner: CliRunner, stub_ok: StubRun) -> None:
    runner.invoke(osa.cli, ["tell", "Finder", "get name of every disk"])
    assert stub_ok.calls[0]["input"] == 'tell application "Finder"\nget name of every disk\nend tell'


def test_tell_prints_result(runner: CliRunner, stub_ok: StubRun) -> None:
    assert runner.invoke(osa.cli, ["tell", "Finder", "get name of every disk"]).output == "Macintosh HD\n"


def test_tell_refuses_destructive_without_write(runner: CliRunner, stub_ok: StubRun) -> None:
    result = runner.invoke(osa.cli, ["tell", "Finder", 'delete file "x"'])
    assert "--write" in result.output


def test_tell_destructive_never_calls_osascript(runner: CliRunner, stub_ok: StubRun) -> None:
    runner.invoke(osa.cli, ["tell", "Finder", 'delete file "x"'])
    assert stub_ok.calls == []


def test_run_reads_script_from_file(runner: CliRunner, stub_ok: StubRun, tmp_path: Path) -> None:
    script = tmp_path / "s.applescript"
    script.write_text("return 42")
    runner.invoke(osa.cli, ["run", "-f", str(script)])
    assert stub_ok.calls[0]["input"] == "return 42"


def test_run_reads_script_from_stdin(runner: CliRunner, stub_ok: StubRun) -> None:
    runner.invoke(osa.cli, ["run"], input="return 7")
    assert stub_ok.calls[0]["input"] == "return 7"


def test_run_propagates_osascript_exit_code(runner: CliRunner, monkeypatch) -> None:
    monkeypatch.setattr(osa.subprocess, "run", StubRun(returncode=1, stderr="execution error"))
    assert runner.invoke(osa.cli, ["run", "error 1"]).exit_code == 1


def test_dict_summarizes_commands(runner: CliRunner, monkeypatch) -> None:
    monkeypatch.setattr(osa, "_resolve_app_path", lambda name: Path("/Applications/Example.app"))
    monkeypatch.setattr(osa.subprocess, "run", StubRun(stdout=SDEF))
    result = runner.invoke(osa.cli, ["dict", "Example"])
    assert "  command  close  — Close a window." in result.output.splitlines()


def test_dict_lists_class_properties(runner: CliRunner, monkeypatch) -> None:
    monkeypatch.setattr(osa, "_resolve_app_path", lambda name: Path("/Applications/Example.app"))
    monkeypatch.setattr(osa.subprocess, "run", StubRun(stdout=SDEF))
    result = runner.invoke(osa.cli, ["dict", "Example"])
    assert "  class    window  (props: name, bounds)  — A window." in result.output.splitlines()


def test_dict_skips_empty_suites(runner: CliRunner, monkeypatch) -> None:
    monkeypatch.setattr(osa, "_resolve_app_path", lambda name: Path("/Applications/Example.app"))
    monkeypatch.setattr(osa.subprocess, "run", StubRun(stdout=SDEF))
    assert "Empty Suite" not in runner.invoke(osa.cli, ["dict", "Example"]).output


def test_dict_raw_prints_xml(runner: CliRunner, monkeypatch) -> None:
    monkeypatch.setattr(osa, "_resolve_app_path", lambda name: Path("/Applications/Example.app"))
    monkeypatch.setattr(osa.subprocess, "run", StubRun(stdout=SDEF))
    assert runner.invoke(osa.cli, ["dict", "Example", "--raw"]).output == SDEF + "\n"


def test_dict_unknown_app_fails(runner: CliRunner, monkeypatch) -> None:
    monkeypatch.setattr(osa, "_resolve_app_path", lambda name: None)
    assert runner.invoke(osa.cli, ["dict", "Nope"]).exit_code == 1


def test_dict_no_dictionary_fails(runner: CliRunner, monkeypatch) -> None:
    monkeypatch.setattr(osa, "_resolve_app_path", lambda name: Path("/Applications/Example.app"))
    monkeypatch.setattr(osa.subprocess, "run", StubRun(returncode=1))
    assert "has no scripting dictionary" in runner.invoke(osa.cli, ["dict", "Example"]).output


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, *sys.argv[1:]]))
