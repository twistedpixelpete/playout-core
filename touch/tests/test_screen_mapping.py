import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from layer_model import LayerTransform  # noqa: E402
from screen_config import ScreenConfigError, load_screen_config  # noqa: E402


class ScreenMappingTests(unittest.TestCase):
    def _write(self, payload):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        source = Path(temporary.name) / 'screens.json'
        source.write_text(json.dumps(payload), encoding='utf-8')
        return source

    def test_loads_multiple_screens(self):
        source = self._write({
            'version': 1,
            'screens': [
                {'id': 'main', 'width': 1920, 'height': 1080},
                {'id': 'stage_left', 'width': 1280, 'height': 720},
            ],
        })

        config = load_screen_config(source)

        self.assertEqual(list(config.screens), ['main', 'stage_left'])
        self.assertEqual(config.screens['stage_left'].width, 1280)

    def test_duplicate_screen_ids_are_rejected(self):
        source = self._write({
            'version': 1,
            'screens': [
                {'id': 'main', 'width': 1920, 'height': 1080},
                {'id': 'main', 'width': 1920, 'height': 1080},
            ],
        })

        with self.assertRaisesRegex(ScreenConfigError, 'Duplicate screen id'):
            load_screen_config(source)

    def test_transform_validation(self):
        transform = LayerTransform().updated(
            fit='cover',
            position_x=0.25,
            scale_x=1.5,
        )
        self.assertEqual(transform.fit, 'cover')
        with self.assertRaises(ValueError):
            transform.updated(opacity=1.1)


if __name__ == '__main__':
    unittest.main()
