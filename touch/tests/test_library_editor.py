import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import clip_library  # noqa: E402
from library_editor import LibraryEditor  # noqa: E402


class LibraryEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        (root / 'config').mkdir()
        (root / 'media/video').mkdir(parents=True)
        (root / 'media/audio').mkdir(parents=True)
        (root / 'media/video/one.mp4').touch()
        self.source = root / 'config/clips.json'
        self.source.write_text(json.dumps({
            'version': 1,
            'mediaRoots': {'video': '../media/video', 'audio': '../media/audio'},
            'audioBuses': ['program', 'effects'],
            'clips': [],
        }), encoding='utf-8')
        self.editor = LibraryEditor(self.source, clip_library)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_update_duplicate_remove(self):
        library = self.editor.add('1001', video_file='one.mp4', label='One')
        self.assertIn('1001', library.clips)
        library = self.editor.update('1001', loop=True, transition_type='cut')
        self.assertTrue(library.clips['1001'].loop)
        self.assertEqual(library.clips['1001'].transition_seconds, 0.0)
        library = self.editor.duplicate('1001', '1002')
        self.assertIn('1002', library.clips)
        library = self.editor.remove('1002')
        self.assertNotIn('1002', library.clips)

    def test_rejects_unknown_field_without_changing_file(self):
        before = self.source.read_text(encoding='utf-8')
        with self.assertRaisesRegex(TypeError, 'Unknown clip field'):
            self.editor.add('1001', video_file='one.mp4', surprise=True)
        self.assertEqual(before, self.source.read_text(encoding='utf-8'))

    def test_accepts_absolute_path_inside_media_root(self):
        media = self.source.parent.parent / 'media/video/one.mp4'
        library = self.editor.add('1001', video_file=str(media))
        self.assertEqual(library.clips['1001'].video_file, 'one.mp4')

    def test_system_id_cannot_be_renamed(self):
        self.editor.add('1001', video_file='one.mp4', label='One')
        before = self.source.read_text(encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'immutable'):
            self.editor.rename('1001', '1002')
        self.assertEqual(self.source.read_text(encoding='utf-8'), before)


if __name__ == '__main__':
    unittest.main()
