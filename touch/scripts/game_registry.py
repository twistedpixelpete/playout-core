"""Variant registry and project-game factory for logicCore."""

from copy import deepcopy
from dataclasses import dataclass
import json


class RegistryError(ValueError):
    pass


def _identifier(value, field):
    if not isinstance(value, str) or not value.strip():
        raise RegistryError('{} must be a non-empty string'.format(field))
    return value.strip()


def _json_object(value, field):
    if not isinstance(value, dict):
        raise RegistryError('{} must be an object'.format(field))
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RegistryError('{} must contain strict JSON values'.format(
            field
        )) from exc
    return deepcopy(value)


@dataclass(frozen=True)
class VariantDefinition:
    variant_id: str
    modules: tuple
    inspired_by: tuple

    def snapshot(self):
        return {
            'id': self.variant_id,
            'modules': list(self.modules),
            'inspiredBy': list(self.inspired_by),
        }


class GameProject:
    """A configured project instance created from a reusable variant."""

    def __init__(self, game_id, variant, settings=None):
        self.game_id = _identifier(game_id, 'game_id')
        if not isinstance(variant, VariantDefinition):
            raise RegistryError('variant must be a VariantDefinition')
        self.variant = variant
        self.settings = _json_object(settings or {}, 'settings')
        self.revision = 0

    def configure(self, changes):
        changes = _json_object(changes, 'changes')
        if not changes:
            raise RegistryError('changes must not be empty')
        self.settings.update(changes)
        self.revision += 1
        return self.snapshot()

    def snapshot(self):
        return {
            'gameId': self.game_id,
            'variantId': self.variant.variant_id,
            'modules': list(self.variant.modules),
            'settings': deepcopy(self.settings),
            'revision': self.revision,
        }


class VariantRegistry:
    """Validated registry loaded from the external archetype configuration."""

    def __init__(self, config):
        config = _json_object(config, 'registry config')
        if config.get('version') != 1:
            raise RegistryError('Unsupported variant registry version')
        raw_presets = config.get('presets')
        if not isinstance(raw_presets, dict) or not raw_presets:
            raise RegistryError('presets must be a non-empty object')

        self.version = config['version']
        self._variants = {}
        for variant_id, raw in raw_presets.items():
            variant_id = _identifier(variant_id, 'variant id')
            if not isinstance(raw, dict):
                raise RegistryError('{} must be an object'.format(variant_id))
            modules = raw.get('modules')
            if not isinstance(modules, list) or not modules:
                raise RegistryError(
                    '{} modules must be a non-empty list'.format(variant_id)
                )
            validated_modules = tuple(
                _identifier(module, 'module id') for module in modules
            )
            if len(set(validated_modules)) != len(validated_modules):
                raise RegistryError(
                    '{} contains duplicate modules'.format(variant_id)
                )
            inspired_by = raw.get('inspiredBy', [])
            if not isinstance(inspired_by, list):
                raise RegistryError(
                    '{} inspiredBy must be a list'.format(variant_id)
                )
            self._variants[variant_id] = VariantDefinition(
                variant_id=variant_id,
                modules=validated_modules,
                inspired_by=tuple(str(item) for item in inspired_by),
            )

    @classmethod
    def from_path(cls, path):
        try:
            config = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise RegistryError(
                'Unable to load variant registry: {}'.format(path)
            ) from exc
        return cls(config)

    def get(self, variant_id):
        if variant_id not in self._variants:
            raise RegistryError('Unknown variant: {}'.format(variant_id))
        return self._variants[variant_id]

    def create(self, game_id, variant_id, settings=None):
        return GameProject(game_id, self.get(variant_id), settings)

    def list_variants(self):
        return tuple(
            variant.snapshot() for variant in self._variants.values()
        )
