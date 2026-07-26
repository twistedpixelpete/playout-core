"""Atomic, TouchDesigner-independent executor configuration editing."""

import json
import os
from pathlib import Path
import tempfile


class ExecutorEditor:
    def __init__(self, source_file, validator_module):
        self.source = Path(source_file).resolve()
        self.validator = validator_module

    def _read(self):
        return json.loads(self.source.read_text(encoding='utf-8'))

    @staticmethod
    def _find(raw, button_id):
        for button in raw.get('buttons', []):
            if button.get('id') == button_id:
                return button
        raise KeyError('Unknown executor ID: {}'.format(button_id))

    def update(self, button_id, label, color, actions):
        raw = self._read()
        button = self._find(raw, button_id)
        button['label'] = label
        button['color'] = color
        button['actions'] = actions

        # Validate the complete document before touching the source file.
        validated = self.validator.ExecutorConfig(raw)
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
            os.replace(str(temporary), str(self.source))
        finally:
            if temporary.exists():
                temporary.unlink()
        return validated.button(button_id)

    def reset(self, button_id):
        return self.update(
            button_id,
            'UNASSIGNED {}'.format(button_id[-2:]),
            'raised',
            [{
                'type': 'logic.emitEvent',
                'eventType': 'EXECUTOR_UNASSIGNED',
                'payload': {'slot': button_id},
            }],
        )
