import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import executor_model  # noqa: E402
from executor_editor import ExecutorEditor  # noqa: E402


class ExecutorEditorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.source = Path(self.directory.name) / 'executors.json'
        self.source.write_text(json.dumps({
            'version': 1,
            'buttons': [{
                'id': '001',
                'label': 'GO',
                'color': 'green',
                'actions': [{
                    'type': 'playback.take',
                    'clipId': '1001',
                }],
            }],
        }), encoding='utf-8')
        self.editor = ExecutorEditor(self.source, executor_model)

    def tearDown(self):
        self.directory.cleanup()

    def test_updates_executor_atomically(self):
        result = self.editor.update(
            '001',
            'TAKE WIN',
            'red',
            [{'type': 'playback.take', 'clipId': '1002'}],
        )
        self.assertEqual(result['label'], 'TAKE WIN')
        saved = json.loads(self.source.read_text(encoding='utf-8'))
        self.assertEqual(saved['buttons'][0]['color'], 'red')
        self.assertEqual(
            saved['buttons'][0]['actions'][0]['clipId'],
            '1002',
        )

    def test_invalid_update_does_not_change_file(self):
        before = self.source.read_text(encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'unknown action type'):
            self.editor.update(
                '001',
                'BAD',
                'green',
                [{'type': 'system.shell'}],
            )
        self.assertEqual(self.source.read_text(encoding='utf-8'), before)

    def test_reset_preserves_slot_id_and_clears_assignment(self):
        result = self.editor.reset('001')
        self.assertEqual(result['id'], '001')
        self.assertEqual(result['label'], 'UNASSIGNED 01')
        self.assertEqual(result['color'], 'raised')
        self.assertEqual(
            result['actions'][0]['eventType'],
            'EXECUTOR_UNASSIGNED',
        )


if __name__ == '__main__':
    unittest.main()
