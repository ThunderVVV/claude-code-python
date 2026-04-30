from __future__ import annotations

from pathlib import Path

from cc_code.core.settings import (
    AppSettings,
    ProviderSettings,
    ModelInProviderSettings,
    DEFAULT_THEME_NAME,
    SettingsStore,
)
import cc_code.ui.app as ui_app


def test_cc_code_app_uses_theme_from_settings(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    SettingsStore(settings_path).save(
        AppSettings(
            current_model="demo:demo-model",
            theme="atom-one-dark",
            providers={
                "demo": ProviderSettings(
                    api_key="test-key",
                    api_url="https://api.example.com/v1",
                    models={
                        "demo-model": ModelInProviderSettings(
                            model_name="demo-model",
                            context=128000,
                        )
                    },
                )
            },
        )
    )

    original_settings_store = ui_app.SettingsStore
    ui_app.SettingsStore = lambda: SettingsStore(settings_path)  # type: ignore[assignment]
    try:
        app = ui_app.CCCodeApp(client=object(), working_directory="/tmp")
    finally:
        ui_app.SettingsStore = original_settings_store

    assert app.theme == "atom-one-dark"


def test_cc_code_app_falls_back_to_default_theme(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    SettingsStore(settings_path).save(
        AppSettings(
            current_model="demo:demo-model",
            theme="not-a-real-theme",
            providers={
                "demo": ProviderSettings(
                    api_key="test-key",
                    api_url="https://api.example.com/v1",
                    models={
                        "demo-model": ModelInProviderSettings(
                            model_name="demo-model",
                            context=128000,
                        )
                    },
                )
            },
        )
    )

    original_settings_store = ui_app.SettingsStore
    ui_app.SettingsStore = lambda: SettingsStore(settings_path)  # type: ignore[assignment]
    try:
        app = ui_app.CCCodeApp(client=object(), working_directory="/tmp")
    finally:
        ui_app.SettingsStore = original_settings_store

    assert app.theme == DEFAULT_THEME_NAME
