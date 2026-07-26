from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from game_archetypes import (  # noqa: E402
    CategoryBoard,
    ContestantRoster,
    CounterDropResult,
    CounterEconomy,
    GameRuleError,
    HiddenValueBoard,
    PRESETS,
    PursuitTrack,
    QuestionLadder,
    RoundEliminator,
    ScoreLedger,
    SharedPrizePool,
    TerritoryBoard,
    TimedDuel,
)


class GameArchetypeTests(unittest.TestCase):
    def test_mass_elimination_ladder_supports_locked_answers_and_passes(self):
        ladder = QuestionLadder(
            [{'id': 'q1'}, {'id': 'q2'}],
            ('p1', 'p2'),
            passes_per_contestant=1,
        )
        ladder.open_question()
        ladder.submit('p1', 'A')
        ladder.submit('p2', use_pass=True)
        with self.assertRaisesRegex(GameRuleError, 'already locked'):
            ladder.submit('p1', 'B')
        self.assertEqual(
            ladder.reveal('A'),
            {'p1': True, 'p2': True},
        )

    def test_roster_elimination_can_be_corrected(self):
        roster = ContestantRoster([
            {'id': 'p1'},
            {'id': 'p2', 'name': 'Player Two'},
        ])
        roster.eliminate('p1')
        self.assertEqual(roster.active_ids, ('p2',))
        roster.restore('p1')
        self.assertEqual(roster.active_ids, ('p1', 'p2'))

    def test_counter_economy_accepts_external_machine_result(self):
        economy = CounterEconomy(('p1',), counter_value=50)
        economy.award('p1')
        value = economy.apply_drop(
            'p1',
            CounterDropResult(normal=2, double=1, bonus=25),
        )
        self.assertEqual(value, 225)
        self.assertEqual(economy.scores['p1'], 225)

    def test_pursuit_track_resolves_home_and_caught(self):
        escaped = PursuitTrack(4, 3)
        self.assertEqual(escaped.resolve_question(True, False), 'HOME')
        caught = PursuitTrack(4, 2, 1)
        self.assertEqual(caught.resolve_question(False, True), 'CAUGHT')

    def test_hidden_value_board_handles_offers(self):
        board = HiddenValueBoard({'box1': 1, 'box2': 100, 'box3': 1000})
        board.hold('box1')
        self.assertEqual(board.reveal('box2'), 100)
        board.make_offer(400)
        self.assertIsNone(board.decide(False))
        board.make_offer(500)
        self.assertEqual(board.decide(True), 500)

    def test_territory_transfer_requires_adjacent_choice_at_host_level(self):
        board = TerritoryBoard(2, 2, ['a', 'b', 'a', 'c'])
        self.assertEqual(board.neighbors('a'), ('b', 'c'))
        board.transfer('b', 'a')
        self.assertEqual(board.territory('a'), 3)

    def test_timed_duel_runs_only_active_clock(self):
        duel = TimedDuel('a', 'b', 5)
        self.assertIsNone(duel.tick(2))
        duel.pass_control()
        self.assertEqual(duel.tick(5), 'a')
        self.assertEqual(duel.remaining, {'a': 3.0, 'b': 0.0})

    def test_score_ledger_supports_positive_negative_and_wager_scoring(self):
        ledger = ScoreLedger(('p1',))
        ledger.adjust('p1', 400)
        ledger.adjust('p1', -200)
        ledger.apply_wager('p1', 150, correct=False, maximum=200)
        self.assertEqual(ledger.score('p1'), 50)

    def test_shared_pool_splits_between_finalists(self):
        pool = SharedPrizePool(1000)
        pool.contribute(500)
        self.assertEqual(pool.split(('p1', 'p2')), {'p1': 750, 'p2': 750})

    def test_round_elimination_reports_unresolved_cutoff_tie(self):
        result = RoundEliminator.lowest({'a': 0, 'b': 0, 'c': 2}, count=1)
        self.assertEqual(result['candidates'], ('a', 'b'))
        self.assertTrue(result['requiresTieBreak'])

    def test_category_board_prevents_reusing_clues(self):
        board = CategoryBoard([
            {'id': 'c1', 'category': 'Science', 'value': 200},
            {'id': 'c2', 'category': 'Science', 'value': 400, 'special': True},
        ])
        self.assertTrue(board.select('c2')['special'])
        board.resolve()
        with self.assertRaisesRegex(GameRuleError, 'already been used'):
            board.select('c2')

    def test_presets_cover_requested_archetypes(self):
        self.assertEqual(len(PRESETS), 7)
        self.assertIn('territory_timed_duel', PRESETS)
        self.assertIn('wagerable_clue_board', PRESETS)


if __name__ == '__main__':
    unittest.main()
