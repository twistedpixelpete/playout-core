"""Atomic, UI-neutral editing API for the Playout Core clip library."""

import json
import os
from pathlib import Path
import tempfile


FIELD_NAMES = {
    'label': 'label',
    'video_file': 'videoFile',
    'audio_file': 'audioFile',
    'audio_bus': 'audioBus',
    'enabled': 'enabled',
    'loop': 'loop',
    'speed': 'speed',
    'in_seconds': 'inSeconds',
    'out_seconds': 'outSeconds',
    'volume': 'volume',
    'audio_enabled': 'audioEnabled',
    'transition_seconds': 'transitionSeconds',
    'transition_type': 'transitionType',
    'pre_read_frames': 'preReadFrames',
    'hardware_decode': 'hardwareDecode',
    'category': 'category',
}


class LibraryEditor:
    def __init__(self, source_file, loader):
        self.source = Path(source_file).resolve()
        self.loader = loader

    def _read(self):
        return json.loads(self.source.read_text(encoding='utf-8'))

    @staticmethod
    def _find(raw, clip_id):
        for index, clip in enumerate(raw['clips']):
            if clip.get('id') == clip_id:
                return index, clip
        raise KeyError('Unknown clip id: {}'.format(clip_id))

    def _normalise_media_path(self, value, media_kind):
        if value is None:
            return None
        value_path = Path(value)
        if not value_path.is_absolute():
            return value_path.as_posix()
        library = self.loader.load_clip_library(self.source)
        root = Path(
            library.video_root if media_kind == 'video' else library.audio_root
        )
        try:
            return value_path.resolve().relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(
                '{} file must be inside {}'.format(media_kind, root)
            ) from exc

    def _write_validated(self, raw):
        self.source.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=self.source.stem + '.',
            suffix='.tmp',
            dir=str(self.source.parent),
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, 'w', encoding='utf-8', newline='\n') as stream:
                json.dump(raw, stream, indent=2, ensure_ascii=False)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            library = self.loader.load_clip_library(temporary)
            os.replace(str(temporary), str(self.source))
            return self.loader.load_clip_library(self.source)
        finally:
            if temporary.exists():
                temporary.unlink()

    def add(self, clip_id, video_file=None, audio_file=None, label=None, **values):
        raw = self._read()
        try:
            self._find(raw, clip_id)
        except KeyError:
            pass
        else:
            raise ValueError('Clip id already exists: {}'.format(clip_id))

        clip = {
            'id': clip_id,
            'label': label or clip_id,
            'videoFile': self._normalise_media_path(video_file, 'video'),
            'audioFile': self._normalise_media_path(audio_file, 'audio'),
        }
        self._apply_values(clip, values)
        raw['clips'].append(clip)
        return self._write_validated(raw)

    def update(self, clip_id, **values):
        raw = self._read()
        _, clip = self._find(raw, clip_id)
        if 'video_file' in values:
            values['video_file'] = self._normalise_media_path(
                values['video_file'], 'video'
            )
        if 'audio_file' in values:
            values['audio_file'] = self._normalise_media_path(
                values['audio_file'], 'audio'
            )
        self._apply_values(clip, values)
        return self._write_validated(raw)

    def rename(self, clip_id, new_id):
        raise RuntimeError(
            'System IDs are immutable; edit the clip label instead'
        )

    def remove(self, clip_id):
        raw = self._read()
        index, _ = self._find(raw, clip_id)
        del raw['clips'][index]
        return self._write_validated(raw)

    def duplicate(self, clip_id, new_id, label=None):
        raw = self._read()
        _, source = self._find(raw, clip_id)
        try:
            self._find(raw, new_id)
        except KeyError:
            pass
        else:
            raise ValueError('Clip id already exists: {}'.format(new_id))
        duplicate = dict(source)
        duplicate['id'] = new_id
        duplicate['label'] = label or '{} Copy'.format(source.get('label', clip_id))
        raw['clips'].append(duplicate)
        return self._write_validated(raw)

    def save(self):
        return self._write_validated(self._read())

    @staticmethod
    def _apply_values(clip, values):
        unknown = set(values).difference(FIELD_NAMES)
        if unknown:
            raise TypeError(
                'Unknown clip field(s): {}'.format(', '.join(sorted(unknown)))
            )
        for key, value in values.items():
            clip[FIELD_NAMES[key]] = value
