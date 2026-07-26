"""Validated, TouchDesigner-independent Playout Core clip-library loader."""

from dataclasses import dataclass
import json
from pathlib import Path


class ClipLibraryError(ValueError):
    """Raised when the clip library cannot be loaded or validated."""


@dataclass(frozen=True)
class Clip:
    id: str
    label: str
    media_type: str
    video_file: str | None
    audio_file: str | None
    audio_bus: str
    resolved_video_file: str | None
    resolved_audio_file: str | None
    file_exists: bool
    missing_files: tuple[str, ...]
    enabled: bool
    loop: bool
    speed: float
    in_seconds: float
    out_seconds: float | None
    volume: float
    audio_enabled: bool
    transition_seconds: float
    transition_type: str
    pre_read_frames: int
    hardware_decode: bool
    category: str


@dataclass(frozen=True)
class ClipLibrary:
    version: int
    source_file: str
    video_root: str
    audio_root: str
    audio_buses: tuple[str, ...]
    clips: dict[str, Clip]


def _require_type(value, expected_type, field):
    # bool is a subclass of int, so reject it for numeric fields.
    if expected_type in (int, float) and isinstance(value, bool):
        raise ClipLibraryError('{} must be numeric'.format(field))
    if not isinstance(value, expected_type):
        if isinstance(expected_type, tuple):
            expected_name = ' or '.join(
                item.__name__ for item in expected_type
            )
        else:
            expected_name = expected_type.__name__
        raise ClipLibraryError(
            '{} must be {}; got {}'.format(
                field,
                expected_name,
                type(value).__name__,
            )
        )
    return value


def _number(value, field, minimum=None, strictly_greater=False):
    _require_type(value, (int, float), field)
    result = float(value)
    if minimum is not None:
        invalid = result <= minimum if strictly_greater else result < minimum
        if invalid:
            operator = 'greater than' if strictly_greater else 'at least'
            raise ClipLibraryError(
                '{} must be {} {}'.format(field, operator, minimum)
            )
    return result


def _bool(raw, key, default, context):
    value = raw.get(key, default)
    return _require_type(value, bool, '{}.{}'.format(context, key))


def _string(raw, key, default, context, allow_empty=False):
    value = raw.get(key, default)
    _require_type(value, str, '{}.{}'.format(context, key))
    if not allow_empty and not value.strip():
        raise ClipLibraryError('{}.{} must not be empty'.format(context, key))
    return value


def _optional_string(raw, key, context):
    value = raw.get(key)
    if value is None:
        return None
    return _string(raw, key, None, context)


def _numeric_id(value, field):
    if not value.isdigit():
        raise ClipLibraryError('{} must contain digits only'.format(field))
    return value


def _resolve_child(root, relative_file, field):
    candidate = Path(relative_file)
    if candidate.is_absolute():
        raise ClipLibraryError('{} must be relative'.format(field))

    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ClipLibraryError(
            '{} must remain inside mediaRoot'.format(field)
        ) from exc
    return resolved


def _parse_clip(raw, video_root, audio_root, audio_buses, index):
    context = 'clips[{}]'.format(index)
    _require_type(raw, dict, context)

    clip_id = _numeric_id(
        _string(raw, 'id', None, context),
        context + '.id',
    )
    video_file = _optional_string(raw, 'videoFile', context)
    audio_file = _optional_string(raw, 'audioFile', context)
    if video_file is None and audio_file is None:
        raise ClipLibraryError(
            '{} requires videoFile, audioFile, or both'.format(context)
        )

    resolved_video = (
        _resolve_child(
            video_root,
            video_file,
            '{}.videoFile'.format(context),
        )
        if video_file is not None
        else None
    )
    resolved_audio = (
        _resolve_child(
            audio_root,
            audio_file,
            '{}.audioFile'.format(context),
        )
        if audio_file is not None
        else None
    )

    in_seconds = _number(
        raw.get('inSeconds', 0.0),
        '{}.inSeconds'.format(context),
        minimum=0.0,
    )
    raw_out = raw.get('outSeconds')
    out_seconds = None
    if raw_out is not None:
        out_seconds = _number(
            raw_out,
            '{}.outSeconds'.format(context),
            minimum=in_seconds,
            strictly_greater=True,
        )

    transition_type = _string(
        raw,
        'transitionType',
        'crossfade',
        context,
    ).lower()
    if transition_type not in ('cut', 'crossfade'):
        raise ClipLibraryError(
            '{}.transitionType must be cut or crossfade'.format(context)
        )

    pre_read_frames = raw.get('preReadFrames', 12)
    _require_type(pre_read_frames, int, '{}.preReadFrames'.format(context))
    if pre_read_frames < 0:
        raise ClipLibraryError(
            '{}.preReadFrames must be at least 0'.format(context)
        )

    transition_seconds = _number(
        raw.get('transitionSeconds', 0.5),
        '{}.transitionSeconds'.format(context),
        minimum=0.0,
    )
    if transition_type == 'cut':
        transition_seconds = 0.0

    audio_enabled = _bool(raw, 'audioEnabled', True, context)
    if video_file is None and not audio_enabled:
        raise ClipLibraryError(
            '{} audio-only clip must have audioEnabled true'.format(context)
        )

    default_bus = 'program' if video_file is not None else 'effects'
    audio_bus = _string(raw, 'audioBus', default_bus, context)
    if audio_bus not in audio_buses:
        raise ClipLibraryError(
            '{}.audioBus must be one of {}'.format(
                context,
                ', '.join(audio_buses),
            )
        )

    resolved_files = tuple(
        str(path)
        for path in (resolved_video, resolved_audio)
        if path is not None
    )
    missing_files = tuple(
        str(path)
        for path in (resolved_video, resolved_audio)
        if path is not None and not path.is_file()
    )

    return Clip(
        id=clip_id,
        label=_string(raw, 'label', clip_id, context),
        media_type='video' if video_file is not None else 'audio',
        video_file=video_file,
        audio_file=audio_file,
        audio_bus=audio_bus,
        resolved_video_file=(
            str(resolved_video) if resolved_video is not None else None
        ),
        resolved_audio_file=(
            str(resolved_audio) if resolved_audio is not None else None
        ),
        file_exists=not missing_files and bool(resolved_files),
        missing_files=missing_files,
        enabled=_bool(raw, 'enabled', True, context),
        loop=_bool(raw, 'loop', False, context),
        speed=_number(
            raw.get('speed', 1.0),
            '{}.speed'.format(context),
            minimum=0.0,
            strictly_greater=True,
        ),
        in_seconds=in_seconds,
        out_seconds=out_seconds,
        volume=_number(
            raw.get('volume', 1.0),
            '{}.volume'.format(context),
            minimum=0.0,
        ),
        audio_enabled=audio_enabled,
        transition_seconds=transition_seconds,
        transition_type=transition_type,
        pre_read_frames=pre_read_frames,
        hardware_decode=_bool(raw, 'hardwareDecode', True, context),
        category=_string(
            raw,
            'category',
            'general',
            context,
            allow_empty=True,
        ),
    )


def load_clip_library(source_file):
    """Load and validate a clip library from a filesystem path."""
    source = Path(source_file).resolve()
    if not source.is_file():
        raise ClipLibraryError(
            'Clip library does not exist: {}'.format(source)
        )

    try:
        raw = json.loads(source.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ClipLibraryError(
            'Unable to read clip library {}: {}'.format(source, exc)
        ) from exc

    _require_type(raw, dict, 'root')
    version = raw.get('version')
    _require_type(version, int, 'version')
    if version != 1:
        raise ClipLibraryError('Unsupported library version: {}'.format(version))

    media_roots = raw.get('mediaRoots')
    _require_type(media_roots, dict, 'mediaRoots')
    video_root_value = _string(media_roots, 'video', None, 'mediaRoots')
    audio_root_value = _string(media_roots, 'audio', None, 'mediaRoots')
    video_root_path = Path(video_root_value)
    audio_root_path = Path(audio_root_value)
    if video_root_path.is_absolute() or audio_root_path.is_absolute():
        raise ClipLibraryError('mediaRoots entries must be relative')
    video_root = (source.parent / video_root_path).resolve()
    audio_root = (source.parent / audio_root_path).resolve()

    raw_audio_buses = raw.get(
        'audioBuses',
        ['program', 'effects', 'aux1', 'aux2'],
    )
    _require_type(raw_audio_buses, list, 'audioBuses')
    audio_buses = []
    for index, bus in enumerate(raw_audio_buses):
        _require_type(bus, str, 'audioBuses[{}]'.format(index))
        if not bus.strip():
            raise ClipLibraryError(
                'audioBuses[{}] must not be empty'.format(index)
            )
        if bus in audio_buses:
            raise ClipLibraryError('Duplicate audio bus: {}'.format(bus))
        audio_buses.append(bus)
    if 'program' not in audio_buses or 'effects' not in audio_buses:
        raise ClipLibraryError(
            'audioBuses must include program and effects'
        )
    audio_buses = tuple(audio_buses)

    raw_clips = raw.get('clips')
    _require_type(raw_clips, list, 'clips')

    clips = {}
    for index, raw_clip in enumerate(raw_clips):
        clip = _parse_clip(
            raw_clip,
            video_root,
            audio_root,
            audio_buses,
            index,
        )
        if clip.id in clips:
            raise ClipLibraryError('Duplicate clip id: {}'.format(clip.id))
        clips[clip.id] = clip

    return ClipLibrary(
        version=version,
        source_file=str(source),
        video_root=str(video_root),
        audio_root=str(audio_root),
        audio_buses=audio_buses,
        clips=clips,
    )


CLIP_TABLE_COLUMNS = (
    'id',
    'label',
    'mediaType',
    'videoFile',
    'audioFile',
    'audioBus',
    'resolvedVideoFile',
    'resolvedAudioFile',
    'fileExists',
    'enabled',
    'loop',
    'speed',
    'inSeconds',
    'outSeconds',
    'volume',
    'audioEnabled',
    'transitionSeconds',
    'transitionType',
    'preReadFrames',
    'hardwareDecode',
    'category',
)


def clip_table_rows(library):
    """Return strings suitable for direct insertion into a Table DAT."""
    rows = [list(CLIP_TABLE_COLUMNS)]
    for clip in library.clips.values():
        rows.append([
            clip.id,
            clip.label,
            clip.media_type,
            clip.video_file or '',
            clip.audio_file or '',
            clip.audio_bus,
            clip.resolved_video_file or '',
            clip.resolved_audio_file or '',
            int(clip.file_exists),
            int(clip.enabled),
            int(clip.loop),
            clip.speed,
            clip.in_seconds,
            '' if clip.out_seconds is None else clip.out_seconds,
            clip.volume,
            int(clip.audio_enabled),
            clip.transition_seconds,
            clip.transition_type,
            clip.pre_read_frames,
            int(clip.hardware_decode),
            clip.category,
        ])
    return rows
