"""Safely reload playbackCore after external script/config changes.

Run from the TouchDesigner Textport:
exec(open(project.folder + '/scripts/rebuild_playback_core.py').read())
"""


ROOT_PATH = '/project1/playoutCore'


def _execute(filename):
    source = project.folder + '/scripts/' + filename
    exec(open(source, encoding='utf-8').read(), globals())


def rebuild():
    core = op(ROOT_PATH)
    if core is None:
        raise RuntimeError('Missing {}'.format(ROOT_PATH))

    # Install authoritative data before constructing the extension and UI.
    _execute('create_clip_library.py')
    _execute('create_control_extension.py')
    _execute('create_playback_ui.py')

    library = core.Library
    if library is None:
        raise RuntimeError('playbackCore rebuilt without a clip library')
    print(
        'Rebuilt playbackCore with {} clips'.format(len(library.clips))
    )
    return core


PLAYBACK_CORE = rebuild()
