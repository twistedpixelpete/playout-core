from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from effects_model import EffectsModel  # noqa: E402


class EffectsModelTests(unittest.TestCase):
    def test_uses_idle_voices_before_stealing(self):
        model = EffectsModel(2)

        self.assertEqual(model.play('one', 'effects'), (1, ''))
        self.assertEqual(model.play('two', 'aux1'), (2, ''))

    def test_steals_oldest_voice_when_full(self):
        model = EffectsModel(2)
        model.play('one', 'effects')
        model.play('two', 'effects')

        self.assertEqual(model.play('three', 'effects'), (1, 'one'))

    def test_stop_clip_only_stops_matching_voices(self):
        model = EffectsModel(2)
        model.play('one', 'effects')
        model.play('two', 'aux1')

        self.assertEqual(model.stop_clip('one'), [1])
        self.assertEqual(model.voices[1].state, 'IDLE')
        self.assertEqual(model.voices[2].state, 'PLAYING')


if __name__ == '__main__':
    unittest.main()
