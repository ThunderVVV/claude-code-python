from __future__ import annotations

from pathlib import Path

from claude_code.core.settings import AppSettings, ModelSettings
from claude_code.core.settings import (
    DEFAULT_THEME_NAME,
    SettingsStore,
    migrate_env_to_settings,
)
import claude_code.ui.app as ui_app


def test_settings_migrates_legacy_env_with_commented_models(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    settings_path = tmp_path / "settings.json"
    env_path.write_text(
        "\n".join(
            [
                "# CLAUDE_CODE_API_URL=https://cloud.infini-ai.com/maas/coding/v1",
                "# CLAUDE_CODE_API_KEY=test-key-1",
                "# CLAUDE_CODE_MODEL=glm-5",
                "# CLAUDE_CODE_MAX_CONTEXT_TOKENS=200000",
                "",
                "CLAUDE_CODE_API_URL=https://integrate.api.nvidia.com/v1",
                "CLAUDE_CODE_API_KEY=test-key-2",
                "CLAUDE_CODE_MODEL=openai/gpt-oss-120b",
                "CLAUDE_CODE_MAX_CONTEXT_TOKENS=200000",
                "CLAUDE_CODE_THEME=atom-one-dark",
            ]
        ),
        encoding="utf-8",
    )

    settings = migrate_env_to_settings(env_path, settings_path)

    assert settings.current_model == "openai-gpt-oss-120b"
    assert settings.theme == "atom-one-dark"
    assert set(settings.models) == {"glm-5", "openai-gpt-oss-120b"}
    assert settings.models["glm-5"].context == 200000
    assert settings.models["openai-gpt-oss-120b"].api_url == "https://integrate.api.nvidia.com/v1"


def test_claude_code_app_uses_theme_from_settings(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    SettingsStore(settings_path).save(
        AppSettings(
            current_model="demo-model",
            theme="atom-one-dark",
            models={
                "demo-model": ModelSettings(
                    api_key="test-key",
                    api_url="https://api.example.com/v1",
                    model_name="demo-model",
                    context=128000,
                )
            },
        )
    )

    original_settings_store = ui_app.SettingsStore
    ui_app.SettingsStore = lambda: SettingsStore(settings_path)  # type: ignore[assignment]
    try:
        app = ui_app.ClaudeCodeApp(client=object(), working_directory="/tmp")
    finally:
        ui_app.SettingsStore = original_settings_store

    assert app.theme == "atom-one-dark"


def test_claude_code_app_falls_back_to_default_theme(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    SettingsStore(settings_path).save(
        AppSettings(
            current_model="demo-model",
            theme="not-a-real-theme",
            models={
                "demo-model": ModelSettings(
                    api_key="test-key",
                    api_url="https://api.example.com/v1",
                    model_name="demo-model",
                    context=128000,
                )
            },
        )
    )

    original_settings_store = ui_app.SettingsStore
    ui_app.SettingsStore = lambda: SettingsStore(settings_path)  # type: ignore[assignment]
    try:
        app = ui_app.ClaudeCodeApp(client=object(), working_directory="/tmp")
    finally:
        ui_app.SettingsStore = original_settings_store

    assert app.theme == DEFAULT_THEME_NAME
