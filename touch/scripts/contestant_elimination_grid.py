"""Authoritative model for the contestantEliminationGrid game variant."""

from copy import deepcopy
from dataclasses import dataclass
import json


class ContestantGridError(ValueError):
    pass


@dataclass(frozen=True)
class ContestantGridEvent:
    sequence: int
    revision: int
    event_type: str
    payload: dict


REQUIRED_SUMMARY_FIELDS = {
    'prizePool',
    'question',
    'remaining',
    'eliminated',
    'players',
}
REQUIRED_PLAYER_FIELDS = {
    'number',
    'active',
    'freePass',
    'boughtOut',
    'boughtOutEndgame',
}


def _integer(value, field, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContestantGridError('{} must be an integer'.format(field))
    if value < minimum:
        raise ContestantGridError('{} must be at least {}'.format(
            field, minimum
        ))
    return value


def _strict_json(value, field):
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ContestantGridError(
            '{} must contain strict JSON values'.format(field)
        ) from exc


class ContestantEliminationGrid:
    """Validates ordered snapshots and owns the normalized game state."""

    def __init__(self, stake=1000, verify_transitions=True):
        _integer(stake, 'stake', 1)
        if not isinstance(verify_transitions, bool):
            raise ContestantGridError(
                'verify_transitions must be boolean'
            )
        self.stake = stake
        self.verify_transitions = verify_transitions
        self.state = None
        self.revision = 0
        self._sequence = 0
        self.events = []

    @staticmethod
    def _validate_snapshot(snapshot):
        if not isinstance(snapshot, dict):
            raise ContestantGridError('snapshot must be an object')
        _strict_json(snapshot, 'snapshot')
        missing = REQUIRED_SUMMARY_FIELDS.difference(snapshot)
        if missing:
            raise ContestantGridError(
                'Missing snapshot field(s): {}'.format(
                    ', '.join(sorted(missing))
                )
            )
        unknown = set(snapshot).difference(REQUIRED_SUMMARY_FIELDS)
        if unknown:
            raise ContestantGridError(
                'Unknown snapshot field(s): {}'.format(
                    ', '.join(sorted(unknown))
                )
            )

        normalized = {
            'prizePool': _integer(snapshot['prizePool'], 'prizePool'),
            'question': _integer(snapshot['question'], 'question'),
            'remaining': _integer(snapshot['remaining'], 'remaining'),
            'eliminated': _integer(snapshot['eliminated'], 'eliminated'),
            'players': [],
        }
        players = snapshot['players']
        if not isinstance(players, list) or not players:
            raise ContestantGridError('players must be a non-empty list')

        numbers = set()
        for index, player in enumerate(players):
            field = 'players[{}]'.format(index)
            if not isinstance(player, dict):
                raise ContestantGridError('{} must be an object'.format(field))
            missing = REQUIRED_PLAYER_FIELDS.difference(player)
            if missing:
                raise ContestantGridError(
                    '{} missing field(s): {}'.format(
                        field, ', '.join(sorted(missing))
                    )
                )
            unknown = set(player).difference(REQUIRED_PLAYER_FIELDS)
            if unknown:
                raise ContestantGridError(
                    '{} unknown field(s): {}'.format(
                        field, ', '.join(sorted(unknown))
                    )
                )
            number = _integer(player['number'], '{}.number'.format(field), 1)
            if number in numbers:
                raise ContestantGridError(
                    'Duplicate player number: {}'.format(number)
                )
            numbers.add(number)
            flags = {}
            for name in (
                'active',
                'freePass',
                'boughtOut',
                'boughtOutEndgame',
            ):
                value = player[name]
                if not isinstance(value, bool):
                    raise ContestantGridError(
                        '{}.{} must be boolean'.format(field, name)
                    )
                flags[name] = value
            if flags['active'] and (
                flags['boughtOut'] or flags['boughtOutEndgame']
            ):
                raise ContestantGridError(
                    'active player {} cannot be bought out'.format(number)
                )
            normalized['players'].append({'number': number, **flags})

        normalized['players'].sort(key=lambda item: item['number'])
        active_count = sum(item['active'] for item in normalized['players'])
        if normalized['remaining'] != active_count:
            raise ContestantGridError(
                'remaining must equal active player count'
            )
        if normalized['eliminated'] > len(normalized['players']):
            raise ContestantGridError(
                'eliminated exceeds player count'
            )
        return normalized

    def _emit(self, event_type, payload):
        self._sequence += 1
        event = ContestantGridEvent(
            sequence=self._sequence,
            revision=self.revision,
            event_type=event_type,
            payload=deepcopy(payload),
        )
        self.events.append(event)
        return event

    @staticmethod
    def _by_number(snapshot):
        return {item['number']: item for item in snapshot['players']}

    def set_transition_verification(self, enabled):
        if not isinstance(enabled, bool):
            raise ContestantGridError('enabled must be boolean')
        self.verify_transitions = enabled
        return self.verify_transitions

    def load_snapshot(self, snapshot):
        candidate = self._validate_snapshot(snapshot)
        if self.state is None:
            self.state = candidate
            self.revision += 1
            event = self._emit('EPISODE_LOADED', {
                'summary': self.summary(),
            })
            self._emit('SNAPSHOT_APPLIED', {
                'question': candidate['question'],
                'initial': True,
            })
            return (event,) + tuple(self.events[-1:])

        previous = self.state
        if not self.verify_transitions:
            self.state = candidate
            self.revision += 1
            events = []
            if candidate['question'] != previous['question']:
                events.append(self._emit('STAGE_CHANGED', {
                    'from': previous['question'],
                    'to': candidate['question'],
                    'verificationBypassed': True,
                }))
            events.append(self._emit(
                'SNAPSHOT_VERIFICATION_BYPASSED',
                {
                    'fromQuestion': previous['question'],
                    'toQuestion': candidate['question'],
                },
            ))
            events.append(self._emit('SNAPSHOT_APPLIED', {
                'question': candidate['question'],
                'initial': False,
                'verificationBypassed': True,
                'summary': self.summary(),
            }))
            return tuple(events)

        old_players = self._by_number(previous)
        new_players = self._by_number(candidate)
        if set(old_players) != set(new_players):
            raise ContestantGridError(
                'player numbers cannot change during an episode'
            )
        if candidate['question'] < previous['question']:
            raise ContestantGridError('question cannot move backwards')
        if candidate['prizePool'] < previous['prizePool']:
            raise ContestantGridError('prizePool cannot decrease')

        new_passes = []
        eliminated = []
        bought_out = []
        endgame_bought_out = []
        fresh_stake_eliminations = []
        for number in sorted(old_players):
            old = old_players[number]
            new = new_players[number]
            for sticky in ('freePass', 'boughtOut', 'boughtOutEndgame'):
                if old[sticky] and not new[sticky]:
                    raise ContestantGridError(
                        '{} cannot be cleared for player {}'.format(
                            sticky, number
                        )
                    )
            if not old['active'] and new['active']:
                raise ContestantGridError(
                    'player {} cannot be restored without correction'.format(
                        number
                    )
                )
            if not old['freePass'] and new['freePass']:
                new_passes.append(number)
            if old['active'] and not new['active']:
                if new['boughtOutEndgame']:
                    endgame_bought_out.append(number)
                elif new['boughtOut']:
                    bought_out.append(number)
                else:
                    eliminated.append(number)
                    if not old['freePass']:
                        fresh_stake_eliminations.append(number)

        if candidate['eliminated'] != len(eliminated):
            raise ContestantGridError(
                'eliminated must equal newly eliminated non-buyout players'
            )
        expected_delta = self.stake * (
            len(new_passes) + len(fresh_stake_eliminations)
        )
        actual_delta = candidate['prizePool'] - previous['prizePool']
        if actual_delta != expected_delta:
            raise ContestantGridError(
                'prizePool delta must be {}; got {}'.format(
                    expected_delta, actual_delta
                )
            )

        self.state = candidate
        self.revision += 1
        emitted = []
        if candidate['question'] != previous['question']:
            emitted.append(self._emit('STAGE_CHANGED', {
                'from': previous['question'],
                'to': candidate['question'],
            }))
        for number in new_passes:
            emitted.append(self._emit('FREE_PASS_GRANTED', {
                'number': number,
                'stakeContribution': self.stake,
            }))
        for number in eliminated:
            emitted.append(self._emit('CONTESTANT_ELIMINATED', {
                'number': number,
                'stakeContribution': (
                    self.stake if number in fresh_stake_eliminations else 0
                ),
            }))
        for number in bought_out:
            emitted.append(self._emit('CONTESTANT_BOUGHT_OUT', {
                'number': number,
            }))
        for number in endgame_bought_out:
            emitted.append(self._emit('CONTESTANT_ENDGAME_BOUGHT_OUT', {
                'number': number,
            }))
        if actual_delta:
            emitted.append(self._emit('PRIZE_POOL_CHANGED', {
                'from': previous['prizePool'],
                'to': candidate['prizePool'],
                'delta': actual_delta,
            }))
        emitted.append(self._emit('SNAPSHOT_APPLIED', {
            'question': candidate['question'],
            'initial': False,
            'summary': self.summary(),
        }))
        return tuple(emitted)

    def apply_correction(self, snapshot, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ContestantGridError(
                'correction reason must be a non-empty string'
            )
        candidate = self._validate_snapshot(snapshot)
        if self.state is not None:
            if set(self._by_number(candidate)) != set(
                self._by_number(self.state)
            ):
                raise ContestantGridError(
                    'correction cannot change player numbers'
                )
        previous = self.snapshot()
        self.state = candidate
        self.revision += 1
        return self._emit('CORRECTION_APPLIED', {
            'reason': reason.strip(),
            'before': previous,
            'after': self.snapshot(),
        })

    @staticmethod
    def _status(player):
        if player['boughtOutEndgame']:
            return 'BOUGHT_OUT_ENDGAME'
        if player['boughtOut']:
            return 'BOUGHT_OUT'
        if not player['active'] and player['freePass']:
            return 'ELIMINATED_WITH_PASS'
        if not player['active']:
            return 'ELIMINATED'
        if player['freePass']:
            return 'ACTIVE_WITH_PASS'
        return 'ACTIVE'

    def summary(self):
        if self.state is None:
            return None
        players = self.state['players']
        return {
            'prizePool': self.state['prizePool'],
            'question': self.state['question'],
            'remaining': self.state['remaining'],
            'eliminatedThisStage': self.state['eliminated'],
            'totalContestants': len(players),
            'totalEliminated': sum(
                not item['active']
                and not item['boughtOut']
                and not item['boughtOutEndgame']
                for item in players
            ),
            'totalBoughtOut': sum(item['boughtOut'] for item in players),
            'totalBoughtOutEndgame': sum(
                item['boughtOutEndgame'] for item in players
            ),
            'totalFreePass': sum(item['freePass'] for item in players),
            'revision': self.revision,
        }

    def contestant_rows(self, columns=10):
        if self.state is None:
            return []
        _integer(columns, 'columns', 1)
        result = []
        for index, player in enumerate(self.state['players']):
            result.append({
                **deepcopy(player),
                'status': self._status(player),
                'column': index % columns,
                'row': index // columns,
            })
        return result

    def snapshot(self):
        if self.state is None:
            return None
        return {
            **deepcopy(self.state),
            'revision': self.revision,
        }

    def pop_events(self, count=None):
        if count is None:
            count = len(self.events)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ContestantGridError(
                'count must be a non-negative integer'
            )
        result = self.events[:count]
        del self.events[:count]
        return result
