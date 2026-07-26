"""TouchDesigner-independent validation and planning for executor buttons."""

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path


class ExecutorConfigError(ValueError):
    pass


COLORS = {
    'raised',
    'cyan',
    'blue',
    'green',
    'lime',
    'red',
}

ACTION_FIELDS = {
    'wait': {'type', 'durationMs'},
    'executor.cancelPending': {'type'},
    'logic.resetEpisode': {'type'},
    'logic.emitEvent': {'type', 'eventType', 'payload'},
    'playback.cue': {'type', 'clipId'},
    'playback.take': {'type', 'clipId', 'transition'},
    'playback.playAudio': {'type', 'clipId'},
    'playback.play': {'type'},
    'playback.pause': {'type'},
    'playback.stop': {'type'},
    'connection.sendState': {'type', 'connectionId'},
    'connection.send': {'type', 'connectionId', 'payload'},
}


@dataclass(frozen=True)
class ExecutorBatch:
    at_ms: int
    actions: tuple


def _non_empty_string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ExecutorConfigError('{} must be a non-empty string'.format(
            field
        ))
    return value.strip()


def _system_id(value, field):
    value = _non_empty_string(value, field)
    if not value.isdigit():
        raise ExecutorConfigError(
            '{} must contain digits only'.format(field)
        )
    return value


def _strict_json(value, field):
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ExecutorConfigError(
            '{} must contain strict JSON values'.format(field)
        ) from exc


def _validate_action(action, field):
    if not isinstance(action, dict):
        raise ExecutorConfigError('{} must be an object'.format(field))
    action_type = _non_empty_string(action.get('type'), field + '.type')
    allowed = ACTION_FIELDS.get(action_type)
    if allowed is None:
        raise ExecutorConfigError(
            '{} has unknown action type {}'.format(field, action_type)
        )
    unknown = set(action).difference(allowed)
    if unknown:
        raise ExecutorConfigError(
            '{} has unknown field(s): {}'.format(
                field, ', '.join(sorted(unknown))
            )
        )
    missing = allowed.difference(action)
    if action_type == 'playback.take':
        missing.discard('transition')
    if missing:
        raise ExecutorConfigError(
            '{} missing field(s): {}'.format(
                field, ', '.join(sorted(missing))
            )
        )

    result = deepcopy(action)
    result['type'] = action_type
    if action_type == 'wait':
        duration = action['durationMs']
        if (
            isinstance(duration, bool)
            or not isinstance(duration, int)
            or duration < 0
        ):
            raise ExecutorConfigError(
                '{}.durationMs must be a non-negative integer'.format(field)
            )
    if action_type.startswith('playback.') and 'clipId' in action:
        result['clipId'] = _system_id(
            action['clipId'], field + '.clipId'
        )
    if action_type == 'playback.take' and 'transition' in action:
        result['transition'] = _non_empty_string(
            action['transition'], field + '.transition'
        )
    if action_type == 'logic.emitEvent':
        result['eventType'] = _non_empty_string(
            action['eventType'], field + '.eventType'
        )
        if not isinstance(action['payload'], dict):
            raise ExecutorConfigError(
                '{}.payload must be an object'.format(field)
            )
    if action_type.startswith('connection.'):
        result['connectionId'] = _non_empty_string(
            action['connectionId'], field + '.connectionId'
        )
    if action_type == 'connection.send':
        if not isinstance(action['payload'], (dict, list, str)):
            raise ExecutorConfigError(
                '{}.payload must be an object, list, or string'.format(field)
            )
    _strict_json(result, field)
    return result


class ExecutorConfig:
    def __init__(self, data):
        if not isinstance(data, dict):
            raise ExecutorConfigError('executor config must be an object')
        _strict_json(data, 'executor config')
        if data.get('version') != 1:
            raise ExecutorConfigError('executor config version must be 1')
        unknown = set(data).difference({'version', 'buttons'})
        if unknown:
            raise ExecutorConfigError(
                'Unknown executor config field(s): {}'.format(
                    ', '.join(sorted(unknown))
                )
            )
        buttons = data.get('buttons')
        if not isinstance(buttons, list):
            raise ExecutorConfigError('buttons must be a list')

        normalized = []
        identifiers = set()
        for index, button in enumerate(buttons):
            field = 'buttons[{}]'.format(index)
            if not isinstance(button, dict):
                raise ExecutorConfigError('{} must be an object'.format(field))
            allowed = {'id', 'label', 'color', 'actions'}
            unknown = set(button).difference(allowed)
            if unknown:
                raise ExecutorConfigError(
                    '{} has unknown field(s): {}'.format(
                        field, ', '.join(sorted(unknown))
                    )
                )
            missing = allowed.difference(button)
            if missing:
                raise ExecutorConfigError(
                    '{} missing field(s): {}'.format(
                        field, ', '.join(sorted(missing))
                    )
                )
            identifier = _system_id(button['id'], field + '.id')
            if identifier in identifiers:
                raise ExecutorConfigError(
                    'Duplicate executor button id: {}'.format(identifier)
                )
            identifiers.add(identifier)
            label = _non_empty_string(button['label'], field + '.label')
            color = _non_empty_string(button['color'], field + '.color')
            if color not in COLORS:
                raise ExecutorConfigError(
                    '{}.color must be one of {}'.format(
                        field, ', '.join(sorted(COLORS))
                    )
                )
            actions = button['actions']
            if not isinstance(actions, list) or not actions:
                raise ExecutorConfigError(
                    '{}.actions must be a non-empty list'.format(field)
                )
            normalized_actions = tuple(
                _validate_action(
                    action,
                    '{}.actions[{}]'.format(field, action_index),
                )
                for action_index, action in enumerate(actions)
            )
            if not any(
                action['type'] != 'wait'
                for action in normalized_actions
            ):
                raise ExecutorConfigError(
                    '{}.actions must contain an executable action'.format(
                        field
                    )
                )
            normalized.append({
                'id': identifier,
                'label': label,
                'color': color,
                'actions': normalized_actions,
            })
        self._buttons = tuple(normalized)
        self._by_id = {button['id']: button for button in self._buttons}

    @classmethod
    def from_path(cls, path):
        path = Path(path)
        return cls(json.loads(path.read_text(encoding='utf-8')))

    @property
    def buttons(self):
        return tuple(deepcopy(button) for button in self._buttons)

    def button(self, identifier):
        try:
            return deepcopy(self._by_id[identifier])
        except KeyError as exc:
            raise ExecutorConfigError(
                'Unknown executor button: {}'.format(identifier)
            ) from exc

    def plan(self, identifier):
        button = self.button(identifier)
        at_ms = 0
        batches = []
        pending = []
        for action in button['actions']:
            if action['type'] == 'wait':
                if pending:
                    batches.append(ExecutorBatch(at_ms, tuple(pending)))
                    pending = []
                at_ms += action['durationMs']
            else:
                pending.append(action)
        if pending:
            batches.append(ExecutorBatch(at_ms, tuple(pending)))
        return tuple(batches)
