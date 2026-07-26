from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from engine_model import DeckState, EngineModel, EngineState  # noqa: E402


class EngineModelTests(unittest.TestCase):
    def test_take_moves_to_loading_and_requests_autoplay(self):
        model = EngineModel()

        self.assertEqual(model.take('intro'), 'ACCEPTED')

        self.assertEqual(model.engine_state, EngineState.LOADING)
        self.assertEqual(model.deck_states['A'], DeckState.LOADING)
        self.assertTrue(model.autoplay_when_ready)

    def test_latest_request_wins_during_transition(self):
        model = EngineModel()
        model.take('intro')
        model.deck_ready()
        model.begin_transition()

        self.assertEqual(model.take('question'), 'QUEUED')
        self.assertEqual(model.take('answer'), 'QUEUED')

        self.assertEqual(model.pending_request.command, 'Take')
        self.assertEqual(model.pending_request.clip_id, 'answer')

    def test_queued_take_preserves_transition_override(self):
        model = EngineModel()
        model.take('intro')
        model.deck_ready()
        model.begin_transition()

        self.assertEqual(
            model.take('winner', transition='cut'),
            'QUEUED',
        )

        request = model.finish_transition()
        self.assertEqual(request.transition, 'cut')

    def test_duplicate_take_while_loading_does_not_restart_load(self):
        model = EngineModel()
        model.take('winner')

        self.assertEqual(model.take('winner'), 'ALREADY_PENDING')
        self.assertTrue(model.autoplay_when_ready)
        self.assertEqual(model.standby_clip, 'winner')

    def test_transition_swaps_program_and_standby(self):
        model = EngineModel()
        model.take('intro')
        model.deck_ready()
        model.begin_transition()
        request = model.finish_transition()

        self.assertIsNone(request)
        self.assertEqual(model.active_deck, 'A')
        self.assertEqual(model.standby_deck, 'B')
        self.assertEqual(model.on_air_clip, 'intro')
        self.assertEqual(model.engine_state, EngineState.PLAYING)
        self.assertTrue(model.validate_decks())

    def test_deck_selection_alternates_without_overlap(self):
        model = EngineModel()
        active_decks = []
        for clip_id in ('one', 'two', 'three', 'four'):
            model.take(clip_id)
            model.deck_ready()
            model.begin_transition()
            model.finish_transition()
            active_decks.append(model.active_deck)
            self.assertNotEqual(model.active_deck, model.standby_deck)

        self.assertEqual(active_decks, ['A', 'B', 'A', 'B'])

    def test_invalid_seek_does_not_change_position(self):
        model = EngineModel()

        with self.assertRaises(ValueError):
            model.seek(-1)

        self.assertEqual(model.position_seconds, 0.0)

    def test_decoder_error_cancels_autoplay(self):
        model = EngineModel()
        model.take('winner')

        model.set_error('decoder failed', 'A')

        self.assertEqual(model.engine_state, EngineState.ERROR)
        self.assertFalse(model.autoplay_when_ready)


if __name__ == '__main__':
    unittest.main()
