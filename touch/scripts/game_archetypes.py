"""Composable, TouchDesigner-independent game-show rule primitives.

These classes model reusable mechanics rather than reproducing any protected
show format verbatim. Host projects combine them and add their own questions,
timings, presentation, scoring tables, and operator controls.
"""

from copy import deepcopy
from dataclasses import dataclass
import math


class GameRuleError(ValueError):
    """Raised when a command would violate a game rule."""


def _require_id(value, field):
    if not isinstance(value, str) or not value.strip():
        raise GameRuleError('{} must be a non-empty string'.format(field))
    return value


def _require_number(value, field, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GameRuleError('{} must be numeric'.format(field))
    if not math.isfinite(value):
        raise GameRuleError('{} must be finite'.format(field))
    if minimum is not None and value < minimum:
        raise GameRuleError('{} must be at least {}'.format(field, minimum))
    return value


class ContestantRoster:
    """Stable contestant identities with active/eliminated state and tags."""

    def __init__(self, contestants):
        if not contestants:
            raise GameRuleError('contestants must not be empty')
        self._contestants = {}
        for contestant in contestants:
            contestant_id = _require_id(contestant['id'], 'contestant id')
            if contestant_id in self._contestants:
                raise GameRuleError('Duplicate contestant id: {}'.format(
                    contestant_id
                ))
            self._contestants[contestant_id] = {
                'id': contestant_id,
                'name': str(contestant.get('name', contestant_id)),
                'active': bool(contestant.get('active', True)),
                'tags': deepcopy(contestant.get('tags', {})),
            }

    def require(self, contestant_id, active=None):
        if contestant_id not in self._contestants:
            raise GameRuleError('Unknown contestant: {}'.format(contestant_id))
        contestant = self._contestants[contestant_id]
        if active is not None and contestant['active'] is not active:
            expected = 'active' if active else 'eliminated'
            raise GameRuleError('{} must be {}'.format(contestant_id, expected))
        return contestant

    def eliminate(self, contestant_id):
        contestant = self.require(contestant_id, active=True)
        contestant['active'] = False

    def restore(self, contestant_id):
        contestant = self.require(contestant_id, active=False)
        contestant['active'] = True

    @property
    def active_ids(self):
        return tuple(
            item['id'] for item in self._contestants.values()
            if item['active']
        )

    def snapshot(self):
        return deepcopy(list(self._contestants.values()))


class ScoreLedger:
    """Numeric scores with corrections, wagers, and optional floor limits."""

    def __init__(self, contestant_ids, initial=0):
        _require_number(initial, 'initial score')
        self._scores = {
            _require_id(item, 'contestant id'): initial
            for item in contestant_ids
        }
        if not self._scores:
            raise GameRuleError('contestant_ids must not be empty')

    def require(self, contestant_id):
        if contestant_id not in self._scores:
            raise GameRuleError('Unknown contestant: {}'.format(contestant_id))

    def adjust(self, contestant_id, amount, floor=None):
        self.require(contestant_id)
        _require_number(amount, 'amount')
        result = self._scores[contestant_id] + amount
        if floor is not None and result < floor:
            raise GameRuleError('score cannot fall below {}'.format(floor))
        self._scores[contestant_id] = result
        return result

    def apply_wager(self, contestant_id, wager, correct, maximum=None):
        self.require(contestant_id)
        _require_number(wager, 'wager', 0)
        if maximum is not None and wager > maximum:
            raise GameRuleError('wager exceeds maximum')
        return self.adjust(contestant_id, wager if correct else -wager)

    def score(self, contestant_id):
        self.require(contestant_id)
        return self._scores[contestant_id]

    def snapshot(self):
        return deepcopy(self._scores)


class SharedPrizePool:
    """A shared pot with explicit contributions and deterministic splitting."""

    def __init__(self, initial=0):
        _require_number(initial, 'initial prize pool', 0)
        self.amount = initial

    def contribute(self, amount):
        _require_number(amount, 'contribution', 0)
        self.amount += amount
        return self.amount

    def split(self, winner_ids):
        winners = tuple(winner_ids)
        if not winners:
            raise GameRuleError('at least one winner is required')
        share = self.amount / len(winners)
        return {winner_id: share for winner_id in winners}


class RoundEliminator:
    """Selects lowest scorers while leaving tie resolution to the operator."""

    @staticmethod
    def lowest(score_by_id, count=1):
        if not score_by_id:
            raise GameRuleError('scores must not be empty')
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise GameRuleError('count must be a positive integer')
        ordered_values = sorted(set(score_by_id.values()))
        if count > len(score_by_id):
            raise GameRuleError('count exceeds contestant count')
        cutoff = sorted(score_by_id.values())[count - 1]
        candidates = tuple(sorted(
            contestant_id
            for contestant_id, score in score_by_id.items()
            if score <= cutoff
        ))
        return {
            'candidates': candidates,
            'requiresTieBreak': len(candidates) > count,
            'requestedCount': count,
            'scoreLevels': tuple(ordered_values),
        }


class CategoryBoard:
    """Selectable category/value clues with control and special-clue flags."""

    def __init__(self, clues):
        if not clues:
            raise GameRuleError('clues must not be empty')
        self._clues = {}
        for clue in clues:
            clue_id = _require_id(clue['id'], 'clue id')
            if clue_id in self._clues:
                raise GameRuleError('Duplicate clue id: {}'.format(clue_id))
            value = _require_number(clue['value'], 'clue value', 0)
            self._clues[clue_id] = {
                'id': clue_id,
                'category': _require_id(clue['category'], 'category'),
                'value': value,
                'special': bool(clue.get('special', False)),
                'used': False,
            }
        self.active_clue_id = None

    def select(self, clue_id):
        if self.active_clue_id is not None:
            raise GameRuleError('resolve the active clue first')
        if clue_id not in self._clues:
            raise GameRuleError('Unknown clue: {}'.format(clue_id))
        clue = self._clues[clue_id]
        if clue['used']:
            raise GameRuleError('clue has already been used')
        clue['used'] = True
        self.active_clue_id = clue_id
        return deepcopy(clue)

    def resolve(self):
        if self.active_clue_id is None:
            raise GameRuleError('there is no active clue')
        clue = deepcopy(self._clues[self.active_clue_id])
        self.active_clue_id = None
        return clue

    def snapshot(self):
        return deepcopy(list(self._clues.values()))


class QuestionLadder:
    """Ordered questions supporting simultaneous answers, passes, and exits."""

    def __init__(self, questions, contestant_ids, passes_per_contestant=0):
        if not questions:
            raise GameRuleError('questions must not be empty')
        self.questions = tuple(deepcopy(questions))
        self.index = 0
        self.open = False
        self.answers = {}
        self.passes = {
            contestant_id: passes_per_contestant
            for contestant_id in contestant_ids
        }

    @property
    def current(self):
        if self.index >= len(self.questions):
            return None
        return deepcopy(self.questions[self.index])

    def open_question(self):
        if self.current is None:
            raise GameRuleError('question ladder is complete')
        if self.open:
            raise GameRuleError('question is already open')
        self.open = True
        self.answers = {}
        return self.current

    def submit(self, contestant_id, answer=None, use_pass=False):
        if not self.open:
            raise GameRuleError('question is not open')
        if contestant_id in self.answers:
            raise GameRuleError('answer is already locked')
        if use_pass:
            if self.passes.get(contestant_id, 0) <= 0:
                raise GameRuleError('no pass available')
            self.passes[contestant_id] -= 1
        self.answers[contestant_id] = {
            'answer': deepcopy(answer),
            'passed': bool(use_pass),
        }

    def reveal(self, correct_answer):
        if not self.open:
            raise GameRuleError('question is not open')
        results = {}
        for contestant_id, submission in self.answers.items():
            results[contestant_id] = (
                True if submission['passed']
                else submission['answer'] == correct_answer
            )
        self.open = False
        self.index += 1
        return results


class TimedDuel:
    """Two independent countdown clocks where only the active side runs."""

    def __init__(self, first_id, second_id, seconds):
        if first_id == second_id:
            raise GameRuleError('duel contestants must be different')
        _require_number(seconds, 'seconds', 0)
        self.remaining = {first_id: float(seconds), second_id: float(seconds)}
        self.active_id = first_id
        self.complete = False

    def pass_control(self):
        if self.complete:
            raise GameRuleError('duel is complete')
        self.active_id = next(
            contestant_id for contestant_id in self.remaining
            if contestant_id != self.active_id
        )

    def tick(self, seconds):
        if self.complete:
            raise GameRuleError('duel is complete')
        _require_number(seconds, 'seconds', 0)
        self.remaining[self.active_id] = max(
            0.0,
            self.remaining[self.active_id] - seconds,
        )
        if self.remaining[self.active_id] == 0:
            self.complete = True
            return next(
                contestant_id for contestant_id in self.remaining
                if contestant_id != self.active_id
            )
        return None


class TerritoryBoard:
    """Orthogonal territory ownership and winner-takes-loser transfer."""

    def __init__(self, width, height, owners):
        if not isinstance(width, int) or width <= 0:
            raise GameRuleError('width must be a positive integer')
        if not isinstance(height, int) or height <= 0:
            raise GameRuleError('height must be a positive integer')
        if len(owners) != width * height:
            raise GameRuleError('owners must fill the board')
        self.width = width
        self.height = height
        self.owners = list(owners)

    def neighbors(self, contestant_id):
        result = set()
        for index, owner in enumerate(self.owners):
            if owner != contestant_id:
                continue
            x, y = index % self.width, index // self.width
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    neighbor = self.owners[ny * self.width + nx]
                    if neighbor != contestant_id:
                        result.add(neighbor)
        return tuple(sorted(result))

    def transfer(self, loser_id, winner_id):
        if loser_id == winner_id:
            raise GameRuleError('winner and loser must be different')
        if loser_id not in self.owners:
            raise GameRuleError('loser owns no territory')
        self.owners = [
            winner_id if owner == loser_id else owner
            for owner in self.owners
        ]

    def territory(self, contestant_id):
        return sum(owner == contestant_id for owner in self.owners)


class HiddenValueBoard:
    """Sealed containers, staged reveals, offers, and a terminal deal."""

    def __init__(self, values_by_container):
        if len(values_by_container) < 2:
            raise GameRuleError('at least two containers are required')
        self._values = deepcopy(values_by_container)
        self._available = set(values_by_container)
        self.held_id = None
        self.revealed = {}
        self.offer = None
        self.accepted_offer = None

    def hold(self, container_id):
        if self.held_id is not None:
            raise GameRuleError('a container is already held')
        if container_id not in self._available:
            raise GameRuleError('unknown container')
        self.held_id = container_id

    def reveal(self, container_id):
        if self.accepted_offer is not None:
            raise GameRuleError('game is complete')
        if container_id == self.held_id:
            raise GameRuleError('cannot reveal the held container')
        if container_id not in self._available:
            raise GameRuleError('container is not available')
        self._available.remove(container_id)
        value = self._values[container_id]
        self.revealed[container_id] = value
        self.offer = None
        return value

    def make_offer(self, amount):
        if self.held_id is None:
            raise GameRuleError('choose a held container first')
        _require_number(amount, 'offer', 0)
        self.offer = amount

    def decide(self, accept):
        if self.offer is None:
            raise GameRuleError('there is no active offer')
        if accept:
            self.accepted_offer = self.offer
        self.offer = None
        return self.accepted_offer

    @property
    def remaining_values(self):
        return tuple(
            self._values[item]
            for item in self._available
        )


class PursuitTrack:
    """Contestant-versus-opponent track used by chase-style quiz rounds."""

    def __init__(self, home_step, contestant_step, opponent_step=0):
        if not all(isinstance(item, int) for item in (
            home_step, contestant_step, opponent_step
        )):
            raise GameRuleError('track steps must be integers')
        if not opponent_step < contestant_step < home_step:
            raise GameRuleError('track positions must be ordered')
        self.home_step = home_step
        self.contestant_step = contestant_step
        self.opponent_step = opponent_step
        self.complete = False

    def resolve_question(self, contestant_correct, opponent_correct):
        if self.complete:
            raise GameRuleError('pursuit is complete')
        if contestant_correct:
            self.contestant_step += 1
        if opponent_correct:
            self.opponent_step += 1
        if self.opponent_step >= self.contestant_step:
            self.complete = True
            return 'CAUGHT'
        if self.contestant_step >= self.home_step:
            self.complete = True
            return 'HOME'
        return 'IN_PLAY'


@dataclass
class CounterDropResult:
    normal: int = 0
    double: int = 0
    bonus: int = 0
    jackpot: bool = False


class CounterEconomy:
    """Question-earned tokens converted into externally reported drop results."""

    def __init__(self, contestant_ids, counter_value=50):
        _require_number(counter_value, 'counter value', 0)
        self.counter_value = counter_value
        self.available = {contestant_id: 0 for contestant_id in contestant_ids}
        self.scores = {contestant_id: 0 for contestant_id in contestant_ids}

    def award(self, contestant_id, count=1):
        if contestant_id not in self.available:
            raise GameRuleError('Unknown contestant: {}'.format(contestant_id))
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise GameRuleError('count must be a non-negative integer')
        self.available[contestant_id] += count

    def apply_drop(self, contestant_id, result):
        if self.available.get(contestant_id, 0) <= 0:
            raise GameRuleError('no counter available')
        if not isinstance(result, CounterDropResult):
            raise GameRuleError('result must be a CounterDropResult')
        if min(result.normal, result.double, result.bonus) < 0:
            raise GameRuleError('drop counts must not be negative')
        self.available[contestant_id] -= 1
        amount = (
            result.normal * self.counter_value
            + result.double * self.counter_value * 2
            + result.bonus
        )
        self.scores[contestant_id] += amount
        return amount


PRESETS = {
    'mass_elimination_ladder': (
        'contestant_roster',
        'question_ladder',
        'passes',
        'shared_prize_pool',
    ),
    'counter_drop_elimination': (
        'contestant_roster',
        'score_ledger',
        'counter_economy',
        'round_elimination',
        'jackpot_objective',
    ),
    'team_pursuit_quiz': (
        'contestant_roster',
        'score_ledger',
        'cash_builder',
        'pursuit_track',
        'team_final',
    ),
    'hidden_value_offer': (
        'hidden_value_board',
        'offer_decision',
        'staged_reveals',
    ),
    'territory_timed_duel': (
        'contestant_roster',
        'territory_board',
        'timed_duel',
        'category_ownership',
    ),
    'specialist_round_elimination': (
        'contestant_roster',
        'score_ledger',
        'specialist_categories',
        'round_elimination',
        'head_to_head_final',
    ),
    'wagerable_clue_board': (
        'contestant_roster',
        'score_ledger',
        'category_board',
        'buzzer_lockout',
        'hidden_wagers',
        'final_wager',
    ),
}
