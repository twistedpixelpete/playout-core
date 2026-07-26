"""Create independent audio voices, logical buses, and component outputs."""


ROOT_PATH = '/project1/playoutCore'
VOICE_COUNT = 4
AUDIO_BUSES = ('program', 'effects', 'aux1', 'aux2')


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


def _set_par(operator, name, value, required=False):
    parameter = getattr(operator.par, name, None)
    if parameter is None:
        if required:
            raise RuntimeError(
                '{} has no parameter {}'.format(operator.path, name)
            )
        return
    parameter.val = value


def _connect(source, destination):
    if destination.inputs and destination.inputs[0] == source:
        return
    for connector in destination.inputConnectors:
        connector.disconnect()
    source.outputConnectors[0].connect(destination)


def _connect_many(sources, destination):
    for connector in destination.inputConnectors:
        connector.disconnect()
    for source in sources:
        source.outputConnectors[0].connect(destination)


def _position(operator, x, y):
    operator.nodeX = x
    operator.nodeY = y


def _create_voice(audio_only, index):
    prefix = 'voice{}'.format(index)
    source = _ensure(audio_only, audiofileinCHOP, prefix + 'File')
    gain = _ensure(audio_only, mathCHOP, prefix + 'Gain')
    output = _ensure(audio_only, nullCHOP, prefix + 'Out')
    info = _ensure(audio_only, infoCHOP, prefix + 'Info')
    status = _ensure(audio_only, tableDAT, prefix + 'Status')

    _set_par(source, 'file', '')
    _set_par(source, 'play', False)
    _set_par(source, 'playmode', 'sequential')
    _set_par(source, 'repeat', False)
    _set_par(source, 'volume', 1.0)
    _set_par(gain, 'gain', 1.0)
    _set_par(gain, 'interppars', True)
    _set_par(info, 'op', source.name)

    _connect(source, gain)
    _connect(gain, output)

    x = (index - 1) * 250
    _position(source, x, 200)
    _position(gain, x, 50)
    _position(output, x, -100)
    _position(info, x, -250)
    _position(status, x, -400)

    if not status.text.strip():
        status.clear()
        status.appendRows([
            ['key', 'value'],
            ['state', 'IDLE'],
            ['clipId', ''],
            ['audioBus', ''],
            ['error', ''],
        ])

    return output


def _create_audio_mixer(mixer, voice_outputs):
    audio_mixer = _ensure(mixer, baseCOMP, 'audio')

    voice_selects = []
    for index, voice_output in enumerate(voice_outputs, start=1):
        select = _ensure(audio_mixer, selectCHOP, 'voice{}Select'.format(index))
        _set_par(
            select,
            'chop',
            '../../../audioOnly/{}'.format(voice_output.name),
            required=True,
        )
        _position(select, (index - 1) * 180, 500)
        voice_selects.append(select)

    bus_outputs = []
    route_nodes = {}
    for bus_index, bus in enumerate(AUDIO_BUSES):
        routes = []
        for voice_index, voice_select in enumerate(voice_selects, start=1):
            route = _ensure(
                audio_mixer,
                mathCHOP,
                '{}Voice{}'.format(bus, voice_index),
            )
            _set_par(route, 'gain', 0.0)
            _set_par(route, 'interppars', True)
            _connect(voice_select, route)
            _position(route, (voice_index - 1) * 180, 300 - bus_index * 220)
            routes.append(route)
            route_nodes[(bus, voice_index)] = route

        bus_sum = _ensure(audio_mixer, mathCHOP, bus + 'Sum')
        _set_par(bus_sum, 'chopop', 'add')
        _set_par(bus_sum, 'match', 'index')
        _set_par(bus_sum, 'interppars', True)
        _connect_many(routes, bus_sum)
        _position(bus_sum, 760, 300 - bus_index * 220)

        rename = _ensure(audio_mixer, renameCHOP, bus + 'Channels')
        _set_par(rename, 'renamefrom', 'chan1 chan2')
        _set_par(rename, 'renameto', '{}_l {}_r'.format(bus, bus))
        _connect(bus_sum, rename)
        _position(rename, 950, 300 - bus_index * 220)
        bus_outputs.append(rename)

    stems_merge = _ensure(audio_mixer, mergeCHOP, 'audioStems')
    _connect_many(bus_outputs, stems_merge)
    _position(stems_merge, 1180, 0)

    program_mix = _ensure(audio_mixer, mathCHOP, 'programAudio')
    _set_par(program_mix, 'chopop', 'add')
    _set_par(program_mix, 'match', 'index')
    _set_par(program_mix, 'interppars', True)
    _connect_many(bus_outputs, program_mix)
    _position(program_mix, 1180, 250)

    routing = _ensure(audio_mixer, tableDAT, 'routing')
    routing.clear()
    routing.appendRows(
        [['bus', 'leftChannel', 'rightChannel', 'stemIndexLeft', 'stemIndexRight']]
        + [
            [bus, bus + '_l', bus + '_r', index * 2, index * 2 + 1]
            for index, bus in enumerate(AUDIO_BUSES)
        ]
    )
    _position(routing, 1180, -250)

    return audio_mixer, route_nodes


def _create_component_outputs(root):
    program_select = _ensure(root, selectCHOP, 'programAudioSelect')
    stems_select = _ensure(root, selectCHOP, 'audioStemsSelect')
    program_out = _ensure(root, outCHOP, 'programAudio')
    stems_out = _ensure(root, outCHOP, 'audioStems')

    _set_par(program_select, 'chop', 'mixer/audio/programAudio', required=True)
    _set_par(stems_select, 'chop', 'mixer/audio/audioStems', required=True)
    _connect(program_select, program_out)
    _connect(stems_select, stems_out)

    _position(program_select, 1000, 100)
    _position(program_out, 1200, 100)
    _position(stems_select, 1000, -100)
    _position(stems_out, 1200, -100)


def build():
    root = op(ROOT_PATH)
    if root is None:
        raise RuntimeError('Missing {}'.format(ROOT_PATH))

    mixer = root.op('mixer')
    if mixer is None:
        raise RuntimeError('Missing {}/mixer'.format(ROOT_PATH))

    audio_only = _ensure(root, baseCOMP, 'audioOnly')
    _position(audio_only, 1000, -300)

    voice_outputs = [
        _create_voice(audio_only, index)
        for index in range(1, VOICE_COUNT + 1)
    ]
    audio_mixer, routes = _create_audio_mixer(mixer, voice_outputs)
    _create_component_outputs(root)

    root.store('audioBuses', AUDIO_BUSES)
    root.store('audioVoiceCount', VOICE_COUNT)

    print(
        'Created {} audio voices and {} stereo buses'.format(
            VOICE_COUNT,
            len(AUDIO_BUSES),
        )
    )
    return {
        'audioOnly': audio_only,
        'audioMixer': audio_mixer,
        'routes': routes,
    }


AUDIO_ROUTING = build()
