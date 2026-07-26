"""
Create the initial Playout Core network inside /project1/playoutCore.

Run this file from a TouchDesigner Textport:

    exec(open(project.folder + '/scripts/create_deck_shells.py').read())

The script is idempotent: running it again reuses operators with the expected
types. It raises an error instead of replacing an existing operator whose type
does not match.
"""

ROOT_PATH = '/project1/playoutCore'


def _ensure(parent_op, op_class, name):
    """Return an existing compatible child or create it."""
    existing = parent_op.op(name)
    expected_type = op_class.__name__

    if existing is not None:
        if not isinstance(existing, op_class):
            raise TypeError(
                '{} already exists as {}; expected {}'.format(
                    existing.path,
                    existing.__class__.__name__,
                    expected_type,
                )
            )
        return existing

    return parent_op.create(op_class, name)


def _set_par_if_present(operator, parameter_name, value):
    """Set a parameter when it exists in the installed TouchDesigner build."""
    parameter = getattr(operator.par, parameter_name, None)
    if parameter is not None:
        parameter.val = value


def _connect(source, destination):
    """Connect source output 0 to destination input 0 if not connected."""
    if destination.inputs and destination.inputs[0] == source:
        return

    for connector in destination.inputConnectors:
        connector.disconnect()
    source.outputConnectors[0].connect(destination)


def _connect_input(source, destination, input_index):
    """Connect a source to a specific input without disturbing other inputs."""
    connector = destination.inputConnectors[input_index]
    if connector.connections:
        current_source = connector.connections[0].owner
        if current_source == source:
            return
        connector.disconnect()
    source.outputConnectors[0].connect(connector)


def _position(operator, x, y):
    operator.nodeX = x
    operator.nodeY = y


def _build_deck(deck):
    movie = _ensure(deck, moviefileinTOP, 'movie')
    movie_info = _ensure(deck, infoCHOP, 'movieInfo')
    video_out = _ensure(deck, nullTOP, 'videoOut')

    audio = _ensure(deck, audiomovieCHOP, 'audio')
    audio_file = _ensure(deck, audiofileinCHOP, 'audioFile')
    audio_source = _ensure(deck, switchCHOP, 'audioSource')
    audio_gain = _ensure(deck, mathCHOP, 'audioGain')
    audio_out = _ensure(deck, nullCHOP, 'audioOut')
    status = _ensure(deck, tableDAT, 'status')

    _set_par_if_present(movie, 'play', False)
    _set_par_if_present(movie, 'loop', False)
    _set_par_if_present(movie, 'file', '')
    _set_par_if_present(movie, 'playmode', 'sequential')

    _set_par_if_present(audio, 'play', False)
    # These operators are siblings, so relative paths keep the deck portable.
    _set_par_if_present(audio, 'moviefileintop', 'movie')

    _set_par_if_present(audio_file, 'file', '')
    _set_par_if_present(audio_file, 'play', False)
    _set_par_if_present(audio_file, 'playmode', 'sequential')
    _set_par_if_present(audio_file, 'repeat', False)
    _set_par_if_present(audio_source, 'index', 0)

    # Both parameter names are documented by Derivative:
    # https://docs.derivative.ca/Info_CHOP
    # https://docs.derivative.ca/Audio_Movie_CHOP
    _set_par_if_present(movie_info, 'op', 'movie')

    _connect(movie, video_out)
    _connect_input(audio, audio_source, 0)
    _connect_input(audio_file, audio_source, 1)
    _connect(audio_source, audio_gain)
    _connect(audio_gain, audio_out)

    video_out.display = True
    audio_out.display = True

    positions = {
        movie: (0, 150),
        movie_info: (0, 0),
        video_out: (200, 150),
        audio: (0, -150),
        audio_file: (0, -300),
        audio_source: (200, -200),
        audio_gain: (400, -200),
        audio_out: (600, -200),
        status: (600, 0),
    }
    for operator, (x, y) in positions.items():
        _position(operator, x, y)

    # A new Table DAT starts with one blank cell, rather than zero rows.
    if not status.text.strip():
        status.clear()
        status.appendRows([
            ['key', 'value'],
            ['state', 'EMPTY'],
            ['clipId', ''],
            ['error', ''],
        ])

    return {
        'movie': movie,
        'movieInfo': movie_info,
        'videoOut': video_out,
        'audio': audio,
        'audioFile': audio_file,
        'audioSource': audio_source,
        'audioGain': audio_gain,
        'audioOut': audio_out,
        'status': status,
    }


def build():
    root = op(ROOT_PATH)
    if root is None:
        raise RuntimeError(
            'Missing {}. Create the Playout Core Base COMP first.'.format(
                ROOT_PATH
            )
        )

    containers = {}
    for index, name in enumerate(('config', 'control', 'decks', 'mixer', 'monitor')):
        container = _ensure(root, baseCOMP, name)
        _position(container, index * 200, 0)
        containers[name] = container

    decks = containers['decks']
    deck_a = _ensure(decks, baseCOMP, 'deckA')
    deck_b = _ensure(decks, baseCOMP, 'deckB')
    _position(deck_a, 0, 0)
    _position(deck_b, 250, 0)

    result = {
        'deckA': _build_deck(deck_a),
        'deckB': _build_deck(deck_b),
    }

    print('Created Playout Core deck shells under {}'.format(decks.path))
    return result


BUILD_RESULT = build()
