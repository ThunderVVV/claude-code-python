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
  "current_model": "openai:gpt-4",
  "theme": "atom-one-dark",
  "providers": {
    "openai": {
      "api_key": "your-openai-api-key",
      "api_url": "https://api.openai.com/v1",
      "models": {
        "gpt-4": {
          "model_name": "gpt-4",
          "context": 128000
        },
        "gpt-3.5-turbo": {
          "model_name": "gpt-3.5-turbo",
          "context": 16384
        }
      }
    },
    "doubao": {
      "api_key": "your-doubao-api-key",
      "api_url": "https://ark.cn-beijing.volces.com/api/v3",
      "models": {
        "doubao-pro": {
          "model_name": "doubao-seed-2-0-pro-260215",
          "context": 32000
        }
      }
    }
  }
}
"""


@dataclass
class ModelInProviderSettings:
    model_name: str
    context: int


@dataclass
class ProviderSettings:
    api_key: str
    api_url: str
    models: dict[str, ModelInProviderSettings] = field(default_factory=dict)


@dataclass
class AppSettings:
    current_model: str = ""
    theme: str = DEFAULT_THEME_NAME
    providers: dict[str, ProviderSettings] = field(default_factory=dict)
    instructions: list[str] = field(default_factory=list)

    def get_current_model(self) -> Optional[tuple[ProviderSettings, ModelInProviderSettings]]:
        if not self.current_model or ":" not in self.current_model:
            return None
        provider_id, model_id = self.current_model.split(":", 1)
        provider = self.providers.get(provider_id)
        if not provider:
            return None
        model = provider.models.get(model_id)
        if not model:
            return None
        return provider, model


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

        providers: dict[str, ProviderSettings] = {}
        raw_providers = payload.get("providers", {})
        if isinstance(raw_providers, dict):
            for provider_id, provider_payload in raw_providers.items():
                if not isinstance(provider_payload, dict):
                    continue
                api_key = str(provider_payload.get("api_key", "")).strip()
                api_url = str(provider_payload.get("api_url", "")).strip()
                if not api_key or not api_url:
                    continue
                raw_models = provider_payload.get("models", {})
                provider_models = {}
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
                        model_name = str(model_payload.get("model_name", "")).strip()
                        if not model_name:
                            continue
                        provider_models[str(model_id)] = ModelInProviderSettings(
                            model_name=model_name,
                            context=context,
                        )
                if provider_models:
                    providers[str(provider_id)] = ProviderSettings(
                        api_key=api_key,
                        api_url=api_url,
                        models=provider_models
                    )

        current_model = str(payload.get("current_model", "")).strip()
        # Validate current model exists
        valid_current = False
        if current_model and ":" in current_model:
            provider_id, model_id = current_model.split(":", 1)
            if provider_id in providers and model_id in providers[provider_id].models:
                valid_current = True
        if not valid_current and providers:
            # Pick first provider, first model as default
            first_provider_id = next(iter(providers))
            first_provider = providers[first_provider_id]
            first_model_id = next(iter(first_provider.models))
            current_model = f"{first_provider_id}:{first_model_id}"

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
            providers=providers,
            instructions=instructions,
        )

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "current_model": settings.current_model,
            "theme": settings.theme,
            "providers": {
                provider_id: asdict(provider_settings)
                for provider_id, provider_settings in settings.providers.items()
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
        if not settings.providers:
            print(f"Error: No provider settings found in {self.path}")
            print("\nPlease create the file with the following format:")
            print(SETTINGS_EXAMPLE)
            sys.exit(1)
        return settings


def build_client_config(
    settings: AppSettings, model_id: Optional[str] = None
) -> OpenAIClientConfig:
    """Build an OpenAI client config for the selected model."""
    resolved_model_id = model_id or settings.current_model
    if not resolved_model_id or ":" not in resolved_model_id:
        raise ValueError("No valid model configured, expected format provider:model_id")

    provider_id, model_short_id = resolved_model_id.split(":", 1)
    provider = settings.providers.get(provider_id)
    if provider is None:
        raise ValueError(f"Unknown provider: {provider_id}")
    model_settings = provider.models.get(model_short_id)
    if model_settings is None:
        raise ValueError(f"Unknown model {model_short_id} for provider {provider_id}")

    api_url = provider.api_url
    if api_url.endswith("/v1/chat/completions"):
        api_url = api_url.removesuffix("/chat/completions")

    return OpenAIClientConfig(
        api_url=api_url,
        api_key=provider.api_key,
        model_name=model_settings.model_name,
        model_id=resolved_model_id,
    )


def find_model_id_by_model_name(
    settings: AppSettings, model_name: str
) -> Optional[str]:
    """Resolve a saved model name back to a settings model id (format: provider:model_id)."""
    for provider_id, provider in settings.providers.items():
        for model_id, model_settings in provider.models.items():
            if model_settings.model_name == model_name:
                return f"{provider_id}:{model_id}"
    return None
