"""Application settings stored in ~/.claude-code-python/settings.json."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from claude_code.services.openai_client import OpenAIClientConfig

DEFAULT_SETTINGS_BASE_DIR = Path.home() / ".claude-code-python"
DEFAULT_SETTINGS_PATH = DEFAULT_SETTINGS_BASE_DIR / "settings.json"
DEFAULT_THEME_NAME = "tokyo-night"

_ENV_ASSIGNMENT_PATTERN = re.compile(
    r"^(?P<comment>\s*#\s*)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>.*)$"
)


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

        theme = str(payload.get("theme", DEFAULT_THEME_NAME)).strip() or DEFAULT_THEME_NAME
        return AppSettings(current_model=current_model, theme=theme, models=models)

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "current_model": settings.current_model,
            "theme": settings.theme,
            "models": {
                model_id: asdict(model_settings)
                for model_id, model_settings in settings.models.items()
            },
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def ensure_settings(self, env_path: Optional[Path] = None) -> AppSettings:
        settings = self.load()
        if settings.models:
            return settings

        env_candidate = Path(env_path) if env_path is not None else Path.cwd() / ".env"
        migrated = migrate_env_to_settings(env_candidate, self.path)
        if migrated.models:
            return migrated
        return settings


def migrate_env_to_settings(env_path: Path, settings_path: Optional[Path] = None) -> AppSettings:
    """Convert a legacy .env file into settings.json format."""
    if not env_path.exists():
        return AppSettings()

    lines = env_path.read_text(encoding="utf-8").splitlines()
    settings = _parse_legacy_env(lines)
    if not settings.models:
        return settings

    store = SettingsStore(settings_path)
    store.save(settings)
    return settings


def build_client_config(settings: AppSettings, model_id: Optional[str] = None) -> OpenAIClientConfig:
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


def find_model_id_by_model_name(settings: AppSettings, model_name: str) -> Optional[str]:
    """Resolve a saved model name back to a settings model id."""
    for model_id, model_settings in settings.models.items():
        if model_settings.model_name == model_name:
            return model_id
    return None


def _parse_legacy_env(lines: list[str]) -> AppSettings:
    theme = DEFAULT_THEME_NAME
    current_model = ""
    models: dict[str, ModelSettings] = {}
    current_block: dict[str, str] = {}
    current_block_is_active = False

    def flush_block() -> None:
        nonlocal current_block, current_block_is_active, current_model
        model_settings = _build_model_settings(current_block)
        if model_settings is None:
            current_block = {}
            current_block_is_active = False
            return

        model_id = _make_model_id(model_settings.model_name, models)
        models[model_id] = model_settings
        if current_block_is_active:
            current_model = model_id
        current_block = {}
        current_block_is_active = False

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            flush_block()
            continue

        match = _ENV_ASSIGNMENT_PATTERN.match(raw_line)
        if not match:
            continue

        is_active = match.group("comment") is None
        key = match.group("key").strip()
        value = match.group("value").strip()

        if key == "CLAUDE_CODE_THEME":
            if is_active and value:
                theme = value
            continue

        normalized_key = _normalize_model_setting_key(key)
        if normalized_key is None:
            continue

        if normalized_key == "api_url" and current_block and "api_url" in current_block:
            flush_block()

        current_block[normalized_key] = value
        current_block_is_active = current_block_is_active or is_active

    flush_block()

    if not current_model and models:
        current_model = next(iter(models))

    return AppSettings(
        current_model=current_model,
        theme=theme,
        models=models,
    )


def _normalize_model_setting_key(key: str) -> Optional[str]:
    mapping = {
        "CLAUDE_CODE_API_KEY": "api_key",
        "CLAUDE_CODE_API_URL": "api_url",
        "CLAUDE_CODE_MODEL": "model_name",
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "context",
    }
    return mapping.get(key)


def _build_model_settings(raw_block: dict[str, str]) -> Optional[ModelSettings]:
    required = ("api_key", "api_url", "model_name", "context")
    if any(not raw_block.get(key, "").strip() for key in required):
        return None

    try:
        context = int(raw_block["context"])
    except ValueError:
        return None

    if context <= 0:
        return None

    return ModelSettings(
        api_key=raw_block["api_key"].strip(),
        api_url=raw_block["api_url"].strip(),
        model_name=raw_block["model_name"].strip(),
        context=context,
    )


def _make_model_id(model_name: str, existing_models: dict[str, ModelSettings]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", model_name.lower()).strip("-") or "model"
    candidate = base
    suffix = 2
    while candidate in existing_models:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate
