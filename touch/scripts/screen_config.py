"""Validated, TouchDesigner-independent logical-screen configuration."""

from dataclasses import dataclass
import json
from pathlib import Path
import re


class ScreenConfigError(ValueError):
    pass


SCREEN_ID_PATTERN = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')


@dataclass(frozen=True)
class Screen:
    id: str
    label: str
    width: int
    height: int
    background: tuple[float, float, float, float]
    master_fade: float


@dataclass(frozen=True)
class ScreenConfig:
    version: int
    source_file: str
    screens: dict[str, Screen]


def _number(value, field, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScreenConfigError('{} must be numeric'.format(field))
    result = float(value)
    if minimum is not None and result < minimum:
        raise ScreenConfigError('{} must be at least {}'.format(field, minimum))
    if maximum is not None and result > maximum:
        raise ScreenConfigError('{} must be at most {}'.format(field, maximum))
    return result


def load_screen_config(source_file):
    source = Path(source_file).resolve()
    if not source.is_file():
        raise ScreenConfigError(
            'Screen configuration does not exist: {}'.format(source)
        )

    try:
        raw = json.loads(source.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ScreenConfigError(
            'Unable to read screen configuration: {}'.format(exc)
        ) from exc

    if not isinstance(raw, dict):
        raise ScreenConfigError('Screen configuration root must be an object')
    if raw.get('version') != 1:
        raise ScreenConfigError('Unsupported screen configuration version')

    raw_screens = raw.get('screens')
    if not isinstance(raw_screens, list) or not raw_screens:
        raise ScreenConfigError('screens must be a non-empty list')

    screens = {}
    for index, item in enumerate(raw_screens):
        context = 'screens[{}]'.format(index)
        if not isinstance(item, dict):
            raise ScreenConfigError('{} must be an object'.format(context))

        screen_id = item.get('id')
        if not isinstance(screen_id, str) or not SCREEN_ID_PATTERN.match(screen_id):
            raise ScreenConfigError(
                '{}.id must be a valid TouchDesigner operator name'.format(
                    context
                )
            )
        if screen_id in screens:
            raise ScreenConfigError('Duplicate screen id: {}'.format(screen_id))

        label = item.get('label', screen_id)
        if not isinstance(label, str) or not label.strip():
            raise ScreenConfigError(
                '{}.label must be a non-empty string'.format(context)
            )

        width = item.get('width')
        height = item.get('height')
        if isinstance(width, bool) or not isinstance(width, int):
            raise ScreenConfigError('{}.width must be an integer'.format(context))
        if isinstance(height, bool) or not isinstance(height, int):
            raise ScreenConfigError('{}.height must be an integer'.format(context))
        if not 1 <= width <= 8192 or not 1 <= height <= 8192:
            raise ScreenConfigError(
                '{} resolution must be between 1 and 8192'.format(context)
            )

        background = item.get('background', [0, 0, 0, 1])
        if not isinstance(background, list) or len(background) != 4:
            raise ScreenConfigError(
                '{}.background must contain four values'.format(context)
            )
        background = tuple(
            _number(
                value,
                '{}.background[{}]'.format(context, component),
                0.0,
                1.0,
            )
            for component, value in enumerate(background)
        )

        screens[screen_id] = Screen(
            id=screen_id,
            label=label,
            width=width,
            height=height,
            background=background,
            master_fade=_number(
                item.get('masterFade', 1.0),
                '{}.masterFade'.format(context),
                0.0,
                1.0,
            ),
        )

    return ScreenConfig(
        version=1,
        source_file=str(source),
        screens=screens,
    )
