"""Creators Studio — Model registry loader and query API.

Loads the JSON registry at scripts/registry/models.json and exposes a typed
query API. The registry is the single source of truth for canonical model
IDs, which providers host each model, capabilities, pricing, and canonical
constraints.

Stdlib only. typing.X forms for Python 3.6+ compat.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


class RegistryValidationError(Exception):
    """Registry failed structural validation."""


@dataclass
class ModelEntry:
    id: str
    display_name: str
    family: str
    tasks: List[str]
    doc: str
    canonical_constraints: Dict[str, Any]
    providers: Dict[str, Dict[str, Any]]  # name -> {slug, capabilities, pricing, availability, notes}


@dataclass
class Registry:
    version: int
    family_defaults: Dict[str, str]
    models: Dict[str, ModelEntry]

    def get_model(self, model_id: str) -> ModelEntry:
        if model_id not in self.models:
            raise KeyError("unknown model id: {!r}".format(model_id))
        return self.models[model_id]

    def models_by_family(self, family: str) -> List[str]:
        return [mid for mid, m in self.models.items() if m.family == family]

    def providers_for_model(self, model_id: str) -> List[str]:
        """Provider names in registry insertion order (matters for routing fallback)."""
        return list(self.get_model(model_id).providers.keys())

    def family_default(self, family: str) -> Optional[str]:
        return self.family_defaults.get(family)

    def validate(self) -> None:
        """Structural validation. Raises RegistryValidationError on problems."""
        # Every family default must point at an existing model.
        for family, model_id in self.family_defaults.items():
            if model_id not in self.models:
                raise RegistryValidationError(
                    "family_defaults[{!r}] = {!r} but no such model exists".format(
                        family, model_id
                    )
                )
            if self.models[model_id].family != family:
                raise RegistryValidationError(
                    "family_defaults[{!r}] = {!r} but that model's family is {!r}".format(
                        family, model_id, self.models[model_id].family
                    )
                )
        # Every model must have at least one provider.
        for mid, m in self.models.items():
            if not m.providers:
                raise RegistryValidationError(
                    "model {!r} has no providers".format(mid)
                )
            for pname, pinfo in m.providers.items():
                if "slug" not in pinfo:
                    raise RegistryValidationError(
                        "model {!r} provider {!r} missing 'slug'".format(mid, pname)
                    )


_DEFAULT_PATH = Path(__file__).parent / "models.json"


def load_registry(path: Optional[Path] = None) -> Registry:
    """Load the registry JSON and return a typed Registry."""
    p = path or _DEFAULT_PATH
    with open(str(p), "r", encoding="utf-8") as f:
        raw = json.load(f)

    models = {}  # type: Dict[str, ModelEntry]
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
