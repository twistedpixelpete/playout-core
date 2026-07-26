"""Load the first available test movie into deck A and play it to program."""

from pathlib import Path


ROOT_PATH = '/project1/playoutCore'
VIDEO_FOLDER = Path(project.folder) / 'media' / 'video'
SUPPORTED_EXTENSIONS = {'.mp4', '.mov', '.m4v', '.avi', '.wmv'}


def _required(path):
    operator = op(path)
    if operator is None:
        raise RuntimeError('Missing {}'.format(path))
    return operator


def _set_if_present(operator, name, value):
    parameter = getattr(operator.par, name, None)
    if parameter is not None:
        parameter.val = value


def run_test():
    movies = sorted(
        path for path in VIDEO_FOLDER.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not movies:
        raise RuntimeError('No test movies found in {}'.format(VIDEO_FOLDER))

    movie_path = movies[0]
    deck_a = _required(ROOT_PATH + '/decks/deckA/movie')
    deck_b = _required(ROOT_PATH + '/decks/deckB/movie')
    cross = _required(ROOT_PATH + '/mixer/video/cross')
    program = _required(ROOT_PATH + '/mixer/video/program')

    _set_if_present(deck_b, 'play', False)
    _set_if_present(deck_a, 'play', False)
    _set_if_present(deck_a, 'playmode', 'sequential')
    _set_if_present(deck_a, 'speed', 1.0)
    _set_if_present(deck_a, 'repeat', True)
    _set_if_present(deck_a, 'cuepointunit', 'seconds')
    _set_if_present(deck_a, 'cuepoint', 0.0)
    deck_a.par.file = str(movie_path)

    reload_pulse = getattr(deck_a.par, 'reloadpulse', None)
    if reload_pulse is not None:
        reload_pulse.pulse()
    cue_pulse = getattr(deck_a.par, 'cuepulse', None)
    if cue_pulse is not None:
        cue_pulse.pulse()

    cross.par.cross = 0.0
    _set_if_present(deck_a, 'play', True)
    program.cook(force=True)

    print('Playing:', movie_path)
    print('Deck A errors:', deck_a.errors())
    print('Deck A warnings:', deck_a.warnings())
    print('Program errors:', program.errors())
    print(
        'Inspect:',
        ROOT_PATH + '/programVideo',
        ROOT_PATH + '/screen_main',
    )
    return str(movie_path)


run_test()
