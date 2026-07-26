import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from system_ids import SystemIdAllocator, normalize_system_id  # noqa: E402


class SystemIdTests(unittest.TestCase):
    def test_allocator_never_repeats_reserved_id(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'id_registry.json'
            source.write_text(json.dumps({
                'version': 1,
                'nextId': 3000000000000001,
            }), encoding='utf-8')
            allocator = SystemIdAllocator(source)
            first = allocator.reserve()
            second = allocator.reserve()
            self.assertEqual(first, '3000000000000001')
            self.assertEqual(second, '3000000000000002')
            self.assertNotEqual(first, second)

    def test_numeric_ids_include_fixed_width_executor_slots(self):
        self.assertEqual(normalize_system_id('001'), '001')
        with self.assertRaisesRegex(ValueError, 'digits only'):
            normalize_system_id('clip_one')

    def test_repository_clip_and_executor_ids_do_not_overlap(self):
        config = Path(__file__).parents[1] / 'config'
        clips = json.loads(
            (config / 'clips.json').read_text(encoding='utf-8')
        )
        executors = json.loads(
            (config / 'executors.json').read_text(encoding='utf-8')
        )
        clip_ids = [item['id'] for item in clips['clips']]
        executor_ids = [item['id'] for item in executors['buttons']]
        self.assertEqual(executor_ids, [
            '{:03d}'.format(index) for index in range(1, 17)
        ])
        all_ids = clip_ids + executor_ids
        self.assertEqual(len(all_ids), len(set(all_ids)))


if __name__ == '__main__':
    unittest.main()
