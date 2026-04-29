from __future__ import annotations

import subprocess
from unittest.mock import Mock

from cc_code import cli


def test_start_api_server_passes_debug_to_child(monkeypatch) -> None:
    popen = Mock(return_value=object())
    monkeypatch.setattr(cli.subprocess, "Popen", popen)
    monkeypatch.setattr(cli.sys, "frozen", False, raising=False)

    cli.start_api_server("localhost", 8000, debug=True)

    kwargs = popen.call_args.kwargs
    cmd = popen.call_args.args[0]

    assert cmd[-1] == "--debug"
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL
    assert kwargs["stdin"] is subprocess.DEVNULL


def test_start_api_server_omits_debug_flag_by_default(monkeypatch) -> None:
    popen = Mock(return_value=object())
    monkeypatch.setattr(cli.subprocess, "Popen", popen)
    monkeypatch.setattr(cli.sys, "frozen", False, raising=False)

    cli.start_api_server("localhost", 8000)

    cmd = popen.call_args.args[0]
    assert "--debug" not in cmd
