"""Visual-layer transform model independent of TouchDesigner."""

from dataclasses import dataclass, replace


FIT_MODES = {
    'stretch': 'fill',
    'contain': 'fitbest',
    'cover': 'fitoutside',
    'native': 'nativeres',
}


@dataclass(frozen=True)
class LayerTransform:
    enabled: bool = True
    fit: str = 'contain'
    position_x: float = 0.0
    position_y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation: float = 0.0
    pivot_x: float = 0.0
    pivot_y: float = 0.0
    opacity: float = 1.0
    z_order: int = 0

    def updated(self, **changes):
        candidate = replace(self, **changes)
        candidate.validate()
        return candidate

    def validate(self):
        if self.fit not in FIT_MODES:
            raise ValueError(
                'fit must be one of {}'.format(', '.join(FIT_MODES))
            )
        if self.scale_x <= 0 or self.scale_y <= 0:
            raise ValueError('scale values must be greater than 0')
        if not 0 <= self.opacity <= 1:
            raise ValueError('opacity must be between 0 and 1')
        if not isinstance(self.z_order, int):
            raise TypeError('z_order must be an integer')
        return self
