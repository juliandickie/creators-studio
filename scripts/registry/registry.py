"""Creators Studio — Model registry loader and query API.

Loads scripts/registry/models.json and exposes a typed query API. The
registry is the single source of truth for canonical model IDs, hosting
providers, capabilities, pricing, and canonical constraints.

Stdlib only. Python 3.12+.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RegistryValidationError(Exception):
    """Registry failed structural validation."""


@dataclass(slots=True)
class ModelEntry:
    id: str
    display_name: str
    family: str
    tasks: list[str]
    doc: str
    canonical_constraints: dict[str, Any]
    providers: dict[str, dict[str, Any]]  # name -> {slug, capabilities, pricing, availability, notes}


@dataclass(slots=True)
class Registry:
    version: int
    family_defaults: dict[str, str]
    models: dict[str, ModelEntry]

    def get_model(self, model_id: str) -> ModelEntry:
        if model_id not in self.models:
            raise KeyError(f"unknown model id: {model_id!r}")
        return self.models[model_id]

    def models_by_family(self, family: str) -> list[str]:
        return [mid for mid, m in self.models.items() if m.family == family]

    def providers_for_model(self, model_id: str) -> list[str]:
        """Provider names in registry insertion order (matters for routing fallback)."""
        return list(self.get_model(model_id).providers.keys())

    def family_default(self, family: str) -> str | None:
        return self.family_defaults.get(family)

    def validate(self) -> None:
        """Structural validation. Raises RegistryValidationError on problems."""
        # Every family default must point at an existing model of matching family.
        for family, model_id in self.family_defaults.items():
            if model_id not in self.models:
                raise RegistryValidationError(
                    f"family_defaults[{family!r}] = {model_id!r} but no such model exists"
                )
            if self.models[model_id].family != family:
                raise RegistryValidationError(
                    f"family_defaults[{family!r}] = {model_id!r} but that model's "
                    f"family is {self.models[model_id].family!r}"
                )
        # Every model must have at least one provider with a slug.
        for mid, m in self.models.items():
            if not m.providers:
                raise RegistryValidationError(f"model {mid!r} has no providers")
            for pname, pinfo in m.providers.items():
                if "slug" not in pinfo:
                    raise RegistryValidationError(
                        f"model {mid!r} provider {pname!r} missing 'slug'"
                    )


_DEFAULT_PATH = Path(__file__).parent / "models.json"


def load_registry(path: Path | None = None) -> Registry:
    """Load the registry JSON and return a typed Registry."""
    p = path or _DEFAULT_PATH
    with open(p, "r", encoding="utf-8") as f:
        raw = json.load(f)

    models: dict[str, ModelEntry] = {}
    for mid, m in raw.get("models", {}).items():
        models[mid] = ModelEntry(
            id=mid,
            display_name=m["display_name"],
            family=m["family"],
            tasks=list(m["tasks"]),
            doc=m.get("doc", ""),
            canonical_constraints=dict(m.get("canonical_constraints", {})),
            providers=dict(m.get("providers", {})),
        )

    return Registry(
        version=raw.get("version", 1),
        family_defaults=dict(raw.get("family_defaults", {})),
        models=models,
    )
