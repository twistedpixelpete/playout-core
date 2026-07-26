from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from contestant_elimination_grid import (  # noqa: E402
    ContestantEliminationGrid,
    ContestantGridError,
)


def start_snapshot(count=4):
    return {
        'prizePool': 0,
        'question': 0,
        'remaining': count,
        'eliminated': 0,
        'players': [
            {
                'number': number,
                'active': True,
                'freePass': False,
                'boughtOut': False,
                'boughtOutEndgame': False,
            }
            for number in range(1, count + 1)
        ],
    }


class ContestantEliminationGridTests(unittest.TestCase):
    def setUp(self):
        self.game = ContestantEliminationGrid(stake=1000)
        self.start = start_snapshot()

    def test_initial_snapshot_publishes_normalized_outputs(self):
        self.game.load_snapshot(self.start)
        self.assertEqual(self.game.summary()['remaining'], 4)
        self.assertEqual(self.game.summary()['totalEliminated'], 0)
        rows = self.game.contestant_rows(columns=2)
        self.assertEqual(rows[3]['status'], 'ACTIVE')
        self.assertEqual((rows[3]['column'], rows[3]['row']), (1, 1))

    def test_repository_start_json_populates_summary_and_all_tiles(self):
        path = (
            Path(__file__).parents[1]
            / 'components'
            / 'logicCore'
            / 'data'
            / 'ep02'
            / '00 Start.json'
        )
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        self.game.load_snapshot(snapshot)
        rows = self.game.contestant_rows()
        self.assertEqual(len(rows), 100)
        self.assertEqual(rows[0]['number'], 1)
        self.assertEqual(rows[-1]['number'], 100)
        self.assertEqual(self.game.summary()['remaining'], 100)
        self.assertEqual(self.game.summary()['revision'], 1)

    def test_elimination_contributes_stake_and_emits_ordered_events(self):
        self.game.load_snapshot(self.start)
        next_state = deepcopy(self.start)
        next_state.update({
            'prizePool': 1000,
            'question': 1,
            'remaining': 3,
            'eliminated': 1,
        })
        next_state['players'][3]['active'] = False
        events = self.game.load_snapshot(next_state)
        self.assertEqual(
            [event.event_type for event in events],
            [
                'STAGE_CHANGED',
                'CONTESTANT_ELIMINATED',
                'PRIZE_POOL_CHANGED',
                'SNAPSHOT_APPLIED',
            ],
        )
        self.assertEqual(events[1].payload['stakeContribution'], 1000)

    def test_free_pass_contributes_once_then_elimination_contributes_zero(self):
        self.game.load_snapshot(self.start)
        passed = deepcopy(self.start)
        passed.update({
            'prizePool': 1000,
            'question': 1,
            'eliminated': 0,
        })
        passed['players'][0]['freePass'] = True
        self.game.load_snapshot(passed)

        eliminated = deepcopy(passed)
        eliminated.update({
            'question': 2,
            'remaining': 3,
            'eliminated': 1,
        })
        eliminated['players'][0]['active'] = False
        events = self.game.load_snapshot(eliminated)
        event = next(
            item for item in events
            if item.event_type == 'CONTESTANT_ELIMINATED'
        )
        self.assertEqual(event.payload['stakeContribution'], 0)
        self.assertEqual(self.game.summary()['prizePool'], 1000)

    def test_buyout_reduces_remaining_without_elimination_or_pool_change(self):
        self.game.load_snapshot(self.start)
        bought_out = deepcopy(self.start)
        bought_out.update({'remaining': 3, 'eliminated': 0})
        bought_out['players'][1]['active'] = False
        bought_out['players'][1]['boughtOut'] = True
        events = self.game.load_snapshot(bought_out)
        self.assertIn(
            'CONTESTANT_BOUGHT_OUT',
            [event.event_type for event in events],
        )
        self.assertEqual(self.game.summary()['totalBoughtOut'], 1)

    def test_invalid_transition_is_atomic(self):
        self.game.load_snapshot(self.start)
        before = self.game.snapshot()
        invalid = deepcopy(self.start)
        invalid['remaining'] = 3
        invalid['players'][0]['active'] = False
        with self.assertRaisesRegex(
            ContestantGridError,
            'eliminated must equal',
        ):
            self.game.load_snapshot(invalid)
        self.assertEqual(self.game.snapshot(), before)

    def test_pool_delta_must_follow_inferred_episode_rule(self):
        self.game.load_snapshot(self.start)
        invalid = deepcopy(self.start)
        invalid['prizePool'] = 2000
        invalid['players'][0]['freePass'] = True
        with self.assertRaisesRegex(ContestantGridError, 'delta must be 1000'):
            self.game.load_snapshot(invalid)

    def test_sticky_flags_require_operator_correction_to_clear(self):
        self.game.load_snapshot(self.start)
        passed = deepcopy(self.start)
        passed['prizePool'] = 1000
        passed['players'][0]['freePass'] = True
        self.game.load_snapshot(passed)
        corrected = deepcopy(self.start)
        corrected['prizePool'] = 1000
        with self.assertRaisesRegex(ContestantGridError, 'cannot be cleared'):
            self.game.load_snapshot(corrected)
        event = self.game.apply_correction(
            corrected,
            'Pass was assigned to the wrong contestant',
        )
        self.assertEqual(event.event_type, 'CORRECTION_APPLIED')
        self.assertFalse(self.game.snapshot()['players'][0]['freePass'])

    def test_rejects_duplicate_players_and_bad_summary(self):
        duplicate = start_snapshot()
        duplicate['players'][1]['number'] = 1
        with self.assertRaisesRegex(ContestantGridError, 'Duplicate'):
            self.game.load_snapshot(duplicate)
        mismatch = start_snapshot()
        mismatch['remaining'] = 3
        with self.assertRaisesRegex(ContestantGridError, 'active player count'):
            self.game.load_snapshot(mismatch)

    def test_verification_can_be_disabled_for_nonsequential_testing(self):
        self.game.load_snapshot(self.start)
        later = deepcopy(self.start)
        later['question'] = 10
        self.game.load_snapshot(later)

        earlier = deepcopy(self.start)
        earlier['question'] = 2
        with self.assertRaisesRegex(
            ContestantGridError,
            'cannot move backwards',
        ):
            self.game.load_snapshot(earlier)

        self.game.set_transition_verification(False)
        events = self.game.load_snapshot(earlier)
        self.assertEqual(self.game.snapshot()['question'], 2)
        self.assertIn(
            'SNAPSHOT_VERIFICATION_BYPASSED',
            [event.event_type for event in events],
        )

    def test_disabled_transition_verification_keeps_schema_validation(self):
        self.game.set_transition_verification(False)
        invalid = deepcopy(self.start)
        invalid['remaining'] = 3
        with self.assertRaisesRegex(
            ContestantGridError,
            'active player count',
        ):
            self.game.load_snapshot(invalid)


if __name__ == '__main__':
    unittest.main()
