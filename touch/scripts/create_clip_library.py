"""Create and populate the Playout Core clip-library DATs."""

import importlib.util
from pathlib import Path
import sys


ROOT_PATH = '/project1/playoutCore'
LIBRARY_RELATIVE_PATH = 'config/clips.json'


def _ensure(parent_op, op_class, name):
    existing = parent_op.op(name)
    if existing is not None:
        if not isinstance(existing, op_class):
            raise TypeError(
                '{} already exists as {}; expected {}'.format(
                    existing.path,
                    existing.__class__.__name__,
                    op_class.__name__,
                )
            )
        return existing
    return parent_op.create(op_class, name)


def _load_module():
    module_path = Path(project.folder) / 'scripts' / 'clip_library.py'
    spec = importlib.util.spec_from_file_location(
        'playout_core_clip_library',
        str(module_path),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError('Unable to load {}'.format(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _replace_rows(table, rows):
    table.clear()
    table.appendRows(rows)


def build():
    root = op(ROOT_PATH)
    if root is None:
        raise RuntimeError('Missing {}'.format(ROOT_PATH))

    config = root.op('config')
    if config is None:
        raise RuntimeError('Missing {}/config'.format(ROOT_PATH))

    # Older builds stored a dynamically loaded ClipLibrary instance here.
    # OP storage is persisted into the .toe and cannot safely pickle that
    # object after its Python module has been reloaded.
    root.unstore('clipLibrary')
    root.unstoreStartupValue('clipLibrary')

    library_table = _ensure(config, tableDAT, 'clipLibrary')
    status_table = _ensure(config, tableDAT, 'libraryStatus')
    library_table.nodeX = 0
    library_table.nodeY = 0
    status_table.nodeX = 200
    status_table.nodeY = 0

    loader = _load_module()
    source_path = Path(project.folder) / LIBRARY_RELATIVE_PATH

    try:
        library = loader.load_clip_library(source_path)
        _replace_rows(library_table, loader.clip_table_rows(library))

        missing_count = sum(
            not clip.file_exists for clip in library.clips.values()
        )
        _replace_rows(status_table, [
            ['key', 'value'],
            ['state', 'READY'],
            ['sourceFile', library.source_file],
            ['videoRoot', library.video_root],
            ['audioRoot', library.audio_root],
            ['audioBuses', ' '.join(library.audio_buses)],
            ['clipCount', len(library.clips)],
            ['missingFileCount', missing_count],
            ['error', ''],
        ])
        print(
            'Loaded {} clips ({} missing files)'.format(
                len(library.clips),
                missing_count,
            )
        )
        return library
    except Exception as exc:
        library_table.clear()
        _replace_rows(status_table, [
            ['key', 'value'],
            ['state', 'ERROR'],
            ['sourceFile', str(source_path.resolve())],
            ['videoRoot', ''],
            ['audioRoot', ''],
            ['audioBuses', ''],
            ['clipCount', 0],
            ['missingFileCount', 0],
            ['error', str(exc)],
        ])
        raise


CLIP_LIBRARY = build()
