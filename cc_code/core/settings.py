"""Application settings stored in ~/.cc-py/settings.json."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from cc_code.services.openai_client import OpenAIClientConfig

DEFAULT_SETTINGS_BASE_DIR = Path.home() / ".cc-py"
DEFAULT_SETTINGS_PATH = DEFAULT_SETTINGS_BASE_DIR / "settings.json"
DEFAULT_THEME_NAME = "atom-one-dark"

SETTINGS_EXAMPLE = """
{
  "current_model": "gpt-4",
  "theme": "atom-one-dark",
  "models": {
    "gpt-4": {
      "api_key": "your-api-key",
      "api_url": "https://api.openai.com/v1",
      "model_name": "gpt-4",
      "context": 128000
    }
  }
}
"""


@dataclass
class ModelSettings:
    api_key: str
    api_url: str
    model_name: str
    context: int


@dataclass
class AppSettings:
    current_model: str = ""
    theme: str = DEFAULT_THEME_NAME
    models: dict[str, ModelSettings] = field(default_factory=dict)
    instructions: list[str] = field(default_factory=list)

    def get_current_model(self) -> Optional[ModelSettings]:
        if not self.current_model:
            return None
        return self.models.get(self.current_model)


class SettingsStore:
    """Read and write persistent application settings."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path is not None else DEFAULT_SETTINGS_PATH

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return AppSettings()

        models: dict[str, ModelSettings] = {}
        raw_models = payload.get("models", {})
        if isinstance(raw_models, dict):
            for model_id, model_payload in raw_models.items():
                if not isinstance(model_payload, dict):
                    continue
                try:
                    context = int(model_payload.get("context", 0))
                except (TypeError, ValueError):
                    context = 0
                if context <= 0:
                    continue

                api_key = str(model_payload.get("api_key", "")).strip()
                api_url = str(model_payload.get("api_url", "")).strip()
                model_name = str(model_payload.get("model_name", "")).strip()
                if not api_key or not api_url or not model_name:
                    continue

                models[str(model_id)] = ModelSettings(
                    api_key=api_key,
                    api_url=api_url,
                    model_name=model_name,
                    context=context,
                )

        current_model = str(payload.get("current_model", "")).strip()
        if current_model not in models and models:
            current_model = next(iter(models))

        theme = (
            str(payload.get("theme", DEFAULT_THEME_NAME)).strip() or DEFAULT_THEME_NAME
        )

        instructions = []
        raw_instructions = payload.get("instructions", [])
        if isinstance(raw_instructions, list):
            for item in raw_instructions:
                if isinstance(item, str) and item.strip():
                    instructions.append(item.strip())

        return AppSettings(
            current_model=current_model,
            theme=theme,
            models=models,
            instructions=instructions,
        )

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "current_model": settings.current_model,
            "theme": settings.theme,
            "models": {
                model_id: asdict(model_settings)
                for model_id, model_settings in settings.models.items()
            },
            "instructions": settings.instructions,
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def ensure_settings(self) -> AppSettings:
        """Load settings, exit with error if not configured."""
        settings = self.load()
        if not settings.models:
            print(f"Error: No model settings found in {self.path}")
            print("\nPlease create the file with the following format:")
            print(SETTINGS_EXAMPLE)
            sys.exit(1)
        return settings


def build_client_config(
    settings: AppSettings, model_id: Optional[str] = None
) -> OpenAIClientConfig:
    """Build an OpenAI client config for the selected model."""
    resolved_model_id = model_id or settings.current_model
    if not resolved_model_id:
        raise ValueError("No model configured")

    model_settings = settings.models.get(resolved_model_id)
    if model_settings is None:
        raise ValueError(f"Unknown model configuration: {resolved_model_id}")

    api_url = model_settings.api_url
    if api_url.endswith("/v1/chat/completions"):
        api_url = api_url.removesuffix("/chat/completions")

    return OpenAIClientConfig(
        api_url=api_url,
        api_key=model_settings.api_key,
        model_name=model_settings.model_name,
        model_id=resolved_model_id,
    )


def find_model_id_by_model_name(
    settings: AppSettings, model_name: str
) -> Optional[str]:
    """Resolve a saved model name back to a settings model id."""
    for model_id, model_settings in settings.models.items():
        if model_settings.model_name == model_name:
            return model_id
    return None
