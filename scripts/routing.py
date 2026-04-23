"""Creators Studio — Model + provider routing resolution.

Given the registry, user flags, and user config, resolve which model and
which provider to use. Two independent resolutions: model first, then
provider-for-that-model.

Stdlib only. Python 3.12+.
"""

from typing import Any

from scripts.registry.registry import Registry


class RoutingError(Exception):
    """Resolution could not produce a valid (model, provider) pair."""


def resolve_model(
    registry: Registry,
    *,
    family: str,
    explicit_model: str | None,
    config: dict[str, Any],
) -> str:
    """Pick canonical model ID based on flag > config > registry default.

    Raises RoutingError if explicit_model names an unknown model, or if no
    default is configured and the registry has none for this family.
    """
    if explicit_model is not None:
        if explicit_model not in registry.models:
            raise RoutingError(
                f"unknown model: {explicit_model!r}. "
                f"Known models: {sorted(registry.models.keys())}"
            )
        return explicit_model

    cfg_default = config.get("defaults", {}).get(f"{family}_model")
    if cfg_default is not None:
        if cfg_default not in registry.models:
            raise RoutingError(
                f"config defaults.{family}_model = {cfg_default!r} but no such model"
            )
        return cfg_default

    reg_default = registry.family_default(family)
    if reg_default is not None:
        return reg_default

    raise RoutingError(
        f"no model could be resolved for family={family!r} "
        f"(no explicit, no config default, no registry default)"
    )


def resolve_provider(
    registry: Registry,
    *,
    model_id: str,
    explicit_provider: str | None,
    config: dict[str, Any],
) -> str:
    """Pick provider for model based on flag > family default > global > first-with-key.

    Raises RoutingError if the explicit provider doesn't host the model, or
    if no provider with a configured API key hosts the model.
    """
    model = registry.get_model(model_id)
    hosts = list(model.providers.keys())  # insertion order = routing fallback order
    configured_keys = {
        name for name, info in config.get("providers", {}).items()
        if isinstance(info, dict) and info.get("api_key")
    }

    # 1. Explicit flag wins — but only if provider hosts the model.
    if explicit_provider is not None:
        if explicit_provider not in hosts:
            raise RoutingError(
                f"{model_id} is not available on {explicit_provider}. "
                f"Available on: {hosts}"
            )
        return explicit_provider

    # 2. Task-family default.
    family_default = config.get("defaults", {}).get(model.family)
    if family_default is not None and family_default in hosts:
        return family_default

    # 3. Global default.
    global_default = config.get("default_provider")
    if global_default is not None and global_default in hosts:
        return global_default

    # 4. First-with-key in registry insertion order.
    for provider_name in hosts:
        if provider_name in configured_keys:
            return provider_name

    setup_cmd = "video" if model.family == "video" else "image"
    raise RoutingError(
        f"{model_id} is available on {hosts}, but no API key is configured "
        f"for any of those providers. Run /create-{setup_cmd} setup."
    )
