from __future__ import annotations

from claude_code.ui.app import ClaudeCodeApp, DEFAULT_THEME_NAME, THEME_ENV_VAR


def test_claude_code_app_uses_theme_env_var(monkeypatch):
    monkeypatch.setenv(THEME_ENV_VAR, "atom-one-dark")

    app = ClaudeCodeApp(client=object(), working_directory="/tmp")

    assert app.theme == "atom-one-dark"


def test_claude_code_app_falls_back_to_default_theme(monkeypatch):
    monkeypatch.setenv(THEME_ENV_VAR, "not-a-real-theme")

    app = ClaudeCodeApp(client=object(), working_directory="/tmp")

    assert app.theme == DEFAULT_THEME_NAME
