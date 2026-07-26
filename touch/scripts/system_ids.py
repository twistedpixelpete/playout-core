"""Global, persistent numeric identifiers for playout-core entities."""

import json
import os
from pathlib import Path
import tempfile


class SystemIdError(ValueError):
    pass


def normalize_system_id(value, field='id'):
    """Return a canonical decimal-string ID or raise."""
    if isinstance(value, bool):
        raise SystemIdError('{} must be a numeric system ID'.format(field))
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str) or not value.isdigit():
        raise SystemIdError('{} must contain digits only'.format(field))
    return value


class SystemIdAllocator:
    """Atomically reserves monotonically increasing IDs.

    Reserved numbers are never returned again, even when an entity is deleted.
    IDs remain strings in Python/JSON consumers to avoid numeric precision loss
    in external JavaScript systems.
    """

    def __init__(self, registry_file):
        self.source = Path(registry_file).resolve()

    def _read(self):
        try:
            raw = json.loads(self.source.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SystemIdError(
                'Unable to read ID registry {}: {}'.format(self.source, exc)
            ) from exc
        if raw.get('version') != 1:
            raise SystemIdError('ID registry version must be 1')
        next_id = raw.get('nextId')
        if isinstance(next_id, bool) or not isinstance(next_id, int):
            raise SystemIdError('nextId must be an integer')
        normalize_system_id(next_id, 'nextId')
        return raw

    def reserve(self):
        raw = self._read()
        identifier = normalize_system_id(raw['nextId'])
        raw['nextId'] += 1
        self.source.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=self.source.stem + '.',
            suffix='.tmp',
            dir=str(self.source.parent),
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, 'w', encoding='utf-8', newline='\n') as stream:
                json.dump(raw, stream, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(str(temporary), str(self.source))
        finally:
            if temporary.exists():
                temporary.unlink()
        return identifier
