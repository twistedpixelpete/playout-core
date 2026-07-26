from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from logic_model import LogicError, LogicModel  # noqa: E402


class LogicModelTests(unittest.TestCase):
    def setUp(self):
        self.model = LogicModel(
            {'phase': 'IDLE', 'score': 0, 'locked': False},
            ('IDLE', 'RUNNING', 'COMPLETE'),
        )

    def test_patch_is_revisioned_and_emits_event(self):
        event = self.model.patch({'score': 10})
        self.assertEqual(self.model.state['score'], 10)
        self.assertEqual(self.model.revision, 1)
        self.assertEqual(event.event_type, 'STATE_CHANGED')
        self.assertEqual(event.revision, 1)

    def test_rejects_unknown_state_field_atomically(self):
        with self.assertRaisesRegex(LogicError, 'Unknown state field'):
            self.model.patch({'surprise': 1})
        self.assertEqual(self.model.revision, 0)
        self.assertEqual(self.model.events, [])

    def test_phase_is_validated(self):
        with self.assertRaisesRegex(LogicError, 'phase must be one of'):
            self.model.set_phase('INVALID')

    def test_events_are_ordered_and_consumable(self):
        self.model.emit('FIRST')
        self.model.emit('SECOND', {'value': 2})
        first = self.model.pop_events(1)
        self.assertEqual(first[0].sequence, 1)
        self.assertEqual(self.model.events[0].sequence, 2)

    def test_increment_requires_numeric_state(self):
        self.model.increment('score', 2)
        self.assertEqual(self.model.state['score'], 2)
        with self.assertRaisesRegex(LogicError, 'not numeric'):
            self.model.increment('locked')


if __name__ == '__main__':
    unittest.main()
