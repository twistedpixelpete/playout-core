"""Create program video mixing and logical screen canvases."""

import importlib.util
from pathlib import Path
import sys


ROOT_PATH = '/project1/playoutCore'
SCREEN_CONFIG_FILE = 'config/screens.json'


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
    if len(sources) > len(destination.inputConnectors):
        raise RuntimeError(
            '{} has {} input connectors; {} sources were supplied'.format(
                destination.path,
                len(destination.inputConnectors),
                len(sources),
            )
        )
    for connector in destination.inputConnectors:
        connector.disconnect()
    for index, source in enumerate(sources):
        source.outputConnectors[0].connect(
            destination.inputConnectors[index]
        )


def _position(operator, x, y):
    operator.nodeX = x
    operator.nodeY = y


def _load_screen_module():
    module_path = Path(project.folder) / 'scripts' / 'screen_config.py'
    module_name = 'playout_core_screen_config'
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        raise RuntimeError('Unable to load {}'.format(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _create_program_mixer(root):
    mixer = root.op('mixer')
    if mixer is None:
        raise RuntimeError('Missing {}/mixer'.format(ROOT_PATH))

    video = _ensure(mixer, baseCOMP, 'video')
    deck_a = _ensure(video, selectTOP, 'deckA')
    deck_b = _ensure(video, selectTOP, 'deckB')
    cross = _ensure(video, crossTOP, 'cross')
    program = _ensure(video, nullTOP, 'program')

    _set_par(deck_a, 'top', '../../decks/deckA/videoOut', required=True)
    _set_par(deck_b, 'top', '../../decks/deckB/videoOut', required=True)
    _set_par(cross, 'cross', 0.0, required=True)
    _connect_many([deck_a, deck_b], cross)
    _connect(cross, program)

    _position(deck_a, 0, 100)
    _position(deck_b, 0, -100)
    _position(cross, 220, 0)
    _position(program, 440, 0)

    program_select = _ensure(root, selectTOP, 'programVideoSelect')
    program_out = _ensure(root, outTOP, 'programVideo')
    _set_par(program_select, 'top', 'mixer/video/program', required=True)
    _connect(program_select, program_out)
    _position(program_select, 1000, 350)
    _position(program_out, 1200, 350)


def _create_screen(screen_parent, screen):
    component = _ensure(screen_parent, baseCOMP, screen.id)
    source = _ensure(component, selectTOP, 'programSource')
    fit = _ensure(component, fitTOP, 'programFit')
    layer_level = _ensure(component, levelTOP, 'programLevel')
    background = _ensure(component, constantTOP, 'background')
    composite = _ensure(component, compositeTOP, 'composite')
    master = _ensure(component, levelTOP, 'masterFade')
    output = _ensure(component, nullTOP, 'screenOut')
    layers = _ensure(component, tableDAT, 'layers')
    status = _ensure(component, tableDAT, 'status')

    _set_par(source, 'top', '../../mixer/video/program', required=True)
    _set_par(fit, 'fit', 'fitbest')
    _set_par(fit, 'outputresolution', 'custom', required=True)
    _set_par(fit, 'resolutionw', screen.width, required=True)
    _set_par(fit, 'resolutionh', screen.height, required=True)
    _set_par(fit, 'outputaspect', 'resolution')
    _set_par(fit, 'tunit', 'fraction')
    _set_par(fit, 'punit', 'fraction')
    _set_par(fit, 'tx', 0.0)
    _set_par(fit, 'ty', 0.0)
    _set_par(fit, 'sx', 1.0)
    _set_par(fit, 'sy', 1.0)
    _set_par(fit, 'r', 0.0)
    _set_par(fit, 'px', 0.0)
    _set_par(fit, 'py', 0.0)
    _set_par(fit, 'bgcolora', 0.0)

    _set_par(layer_level, 'opacity', 1.0)
    _set_par(layer_level, 'premultrgbbyalpha', True)

    _set_par(background, 'outputresolution', 'custom', required=True)
    _set_par(background, 'resolutionw', screen.width, required=True)
    _set_par(background, 'resolutionh', screen.height, required=True)
    _set_par(background, 'colorr', screen.background[0])
    _set_par(background, 'colorg', screen.background[1])
    _set_par(background, 'colorb', screen.background[2])
    _set_par(background, 'alpha', screen.background[3])

    _set_par(composite, 'operand', 'over', required=True)
    _set_par(composite, 'size', 'input2')
    _connect(source, fit)
    _connect(fit, layer_level)
    _connect_many([layer_level, background], composite)
    _connect(composite, master)
    _connect(master, output)

    _set_par(master, 'opacity', screen.master_fade)
    _set_par(master, 'premultrgbbyalpha', True)

    layers.clear()
    layers.appendRows([
        [
            'layerId', 'source', 'enabled', 'fit',
            'positionX', 'positionY', 'scaleX', 'scaleY',
            'rotation', 'pivotX', 'pivotY', 'opacity', 'zOrder',
        ],
        [
            'program', 'mixer/video/program', 1, 'contain',
            0.0, 0.0, 1.0, 1.0,
            0.0, 0.0, 0.0, 1.0, 0,
        ],
    ])

    status.clear()
    status.appendRows([
        ['key', 'value'],
        ['state', 'READY'],
        ['screenId', screen.id],
        ['label', screen.label],
        ['width', screen.width],
        ['height', screen.height],
        ['masterFade', screen.master_fade],
        ['error', ''],
    ])

    operators = [
        source, fit, layer_level, background, composite, master, output,
    ]
    for index, operator in enumerate(operators):
        _position(operator, index * 180, 100 if operator != background else -100)
    _position(layers, 720, -200)
    _position(status, 900, -200)
    return component


def _create_screen_output(root, screen_id, output_index):
    select = _ensure(root, selectTOP, 'screen_{}_select'.format(screen_id))
    output = _ensure(root, outTOP, 'screen_{}'.format(screen_id))
    _set_par(
        select,
        'top',
        'screens/{}/screenOut'.format(screen_id),
        required=True,
    )
    _connect(select, output)
    _position(select, 1000, -400 - output_index * 160)
    _position(output, 1200, -400 - output_index * 160)


def build():
    root = op(ROOT_PATH)
    if root is None:
        raise RuntimeError('Missing {}'.format(ROOT_PATH))

    module = _load_screen_module()
    config_path = Path(project.folder) / SCREEN_CONFIG_FILE
    config = module.load_screen_config(config_path)

    _create_program_mixer(root)
    screens_parent = _ensure(root, baseCOMP, 'screens')
    _position(screens_parent, 1000, -600)

    registry = _ensure(screens_parent, tableDAT, 'registry')
    registry.clear()
    registry.appendRow(['id', 'label', 'width', 'height', 'outputTOP'])

    for index, screen in enumerate(config.screens.values()):
        component = _create_screen(screens_parent, screen)
        _position(component, index * 250, 0)
        _create_screen_output(root, screen.id, index)
        registry.appendRow([
            screen.id,
            screen.label,
            screen.width,
            screen.height,
            component.path + '/screenOut',
        ])

    _position(registry, 0, -200)
    root.store('screenConfig', config)
    print('Created {} logical screen outputs'.format(len(config.screens)))
    return config


SCREEN_CONFIG = build()
