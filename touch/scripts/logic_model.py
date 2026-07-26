"""TouchDesigner-independent authoritative state model for logicCore."""

from copy import deepcopy
from dataclasses import dataclass
import json


class LogicError(ValueError):
    pass


@dataclass(frozen=True)
class LogicEvent:
    sequence: int
    revision: int
    event_type: str
    payload: dict


class LogicModel:
    def __init__(self, initial_state, allowed_phases):
        if not isinstance(initial_state, dict) or not initial_state:
            raise LogicError('initial_state must be a non-empty object')
        self._initial_state = deepcopy(initial_state)
        self.allowed_phases = tuple(allowed_phases)
        if not self.allowed_phases:
            raise LogicError('allowed_phases must not be empty')
        if initial_state.get('phase') not in self.allowed_phases:
            raise LogicError('Initial phase is not allowed')
        self.state = deepcopy(initial_state)
        self.revision = 0
        self._sequence = 0
        self.events = []

    @staticmethod
    def _json_value(value, field):
        try:
            json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise LogicError('{} must be JSON serializable'.format(field)) from exc
        return deepcopy(value)

    def _emit(self, event_type, payload=None):
        if not isinstance(event_type, str) or not event_type.strip():
            raise LogicError('event_type must be a non-empty string')
        payload = self._json_value(payload or {}, 'payload')
        self._sequence += 1
        event = LogicEvent(
            sequence=self._sequence,
            revision=self.revision,
            event_type=event_type,
            payload=payload,
        )
        self.events.append(event)
        return event

    def reset(self):
        self.state = deepcopy(self._initial_state)
        self.revision += 1
        return self._emit('STATE_RESET', {'state': self.snapshot()})

    def patch(self, changes, event_type='STATE_CHANGED'):
        if not isinstance(changes, dict) or not changes:
            raise LogicError('changes must be a non-empty object')
        unknown = set(changes).difference(self.state)
        if unknown:
            raise LogicError(
                'Unknown state field(s): {}'.format(', '.join(sorted(unknown)))
            )
        validated = {
            key: self._json_value(value, key)
            for key, value in changes.items()
        }
        if 'phase' in validated and validated['phase'] not in self.allowed_phases:
            raise LogicError(
                'phase must be one of {}'.format(', '.join(self.allowed_phases))
            )
        self.state.update(validated)
        self.revision += 1
        return self._emit(event_type, {'changes': validated})

    def set_phase(self, phase):
        return self.patch({'phase': phase}, 'PHASE_CHANGED')

    def increment(self, field, amount=1):
        if field not in self.state:
            raise LogicError('Unknown state field: {}'.format(field))
        current = self.state[field]
        if isinstance(current, bool) or not isinstance(current, (int, float)):
            raise LogicError('{} is not numeric'.format(field))
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise LogicError('amount must be numeric')
        return self.patch({field: current + amount}, 'VALUE_INCREMENTED')

    def emit(self, event_type, payload=None):
        return self._emit(event_type, payload)

    def pop_events(self, count=None):
        if count is None:
            count = len(self.events)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise LogicError('count must be a non-negative integer')
        result = self.events[:count]
        del self.events[:count]
        return result

    def snapshot(self):
        result = deepcopy(self.state)
        result['revision'] = self.revision
        return result
