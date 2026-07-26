import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from clip_library import ClipLibraryError, load_clip_library  # noqa: E402


def _write_library(tmp_path, clips):
    config = tmp_path / 'config'
    config.mkdir()
    source = config / 'clips.json'
    source.write_text(
        json.dumps({
            'version': 1,
            'mediaRoots': {
                'video': '../media/video',
                'audio': '../media/audio',
            },
            'audioBuses': ['program', 'effects', 'aux1', 'aux2'],
            'clips': clips,
        }),
        encoding='utf-8',
    )
    return source


class ClipLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_paths_resolve_relative_to_library(self):
        source = _write_library(self.tmp_path, [{
            'id': '1001',
            'videoFile': 'shows/intro.mp4',
            'audioFile': None,
        }])

        library = load_clip_library(source)

        self.assertEqual(
            library.video_root,
            str((self.tmp_path / 'media/video').resolve()),
        )
        self.assertEqual(
            library.clips['1001'].resolved_video_file,
            str((self.tmp_path / 'media/video/shows/intro.mp4').resolve()),
        )
        self.assertFalse(library.clips['1001'].file_exists)

    def test_duplicate_ids_are_rejected(self):
        source = _write_library(self.tmp_path, [
            {'id': '1001', 'videoFile': 'one.mp4'},
            {'id': '1001', 'videoFile': 'two.mp4'},
        ])

        with self.assertRaisesRegex(ClipLibraryError, 'Duplicate clip id'):
            load_clip_library(source)

    def test_audio_only_clip_uses_audio_root(self):
        source = _write_library(self.tmp_path, [{
            'id': '1001',
            'videoFile': None,
            'audioFile': 'stings/correct.wav',
        }])

        library = load_clip_library(source)
        clip = library.clips['1001']

        self.assertEqual(clip.media_type, 'audio')
        self.assertEqual(clip.audio_bus, 'effects')
        self.assertIsNone(clip.resolved_video_file)
        self.assertEqual(
            clip.resolved_audio_file,
            str(
                (self.tmp_path / 'media/audio/stings/correct.wav').resolve()
            ),
        )

    def test_media_escape_is_rejected(self):
        source = _write_library(self.tmp_path, [{
            'id': '1001',
            'audioFile': '../outside.wav',
        }])

        with self.assertRaisesRegex(ClipLibraryError, 'inside mediaRoot'):
            load_clip_library(source)


if __name__ == '__main__':
    unittest.main()
