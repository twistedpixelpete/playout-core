"""Create the Playout Core control DATs and promoted Python Extension."""


ROOT_PATH = '/project1/playoutCore'
EXTENSION_FILE = 'scripts/playout_core_ext.py'
CALLBACK_FILE = 'scripts/engine_callbacks.py'


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


def _set_par(operator, name, value):
    parameter = getattr(operator.par, name, None)
    if parameter is None:
        raise RuntimeError(
            '{} has no parameter {}'.format(operator.path, name)
        )
    parameter.val = value


def build():
    root = op(ROOT_PATH)
    if root is None:
        raise RuntimeError('Missing {}'.format(ROOT_PATH))

    control = root.op('control')
    if control is None:
        raise RuntimeError('Missing {}/control'.format(ROOT_PATH))

    extension_dat = _ensure(control, fileinDAT, 'PlayoutCoreExt')
    engine_status = _ensure(control, tableDAT, 'engineStatus')
    command_queue = _ensure(control, tableDAT, 'commandQueue')
    callbacks = _ensure(root, executeDAT, 'engineCallbacks')

    extension_dat.nodeX = 0
    extension_dat.nodeY = 0
    engine_status.nodeX = 200
    engine_status.nodeY = 0
    command_queue.nodeX = 400
    command_queue.nodeY = 0
    callbacks.nodeX = 800
    callbacks.nodeY = 0

    _set_par(extension_dat, 'file', EXTENSION_FILE)
    _set_par(extension_dat, 'converttable', False)
    _set_par(extension_dat, 'language', 'python')
    extension_dat.par.refreshpulse.pulse()

    _set_par(callbacks, 'file', CALLBACK_FILE)
    _set_par(callbacks, 'language', 'python')
    _set_par(callbacks, 'framestart', True)
    _set_par(callbacks, 'active', True)
    callbacks.par.loadonstartpulse.pulse()

    _set_par(
        root,
        'ext0object',
        "op('./control/PlayoutCoreExt').module.PlayoutCoreExt(me)",
    )
    _set_par(root, 'ext0name', 'PlayoutCore')
    _set_par(root, 'ext0promote', True)
    _set_par(root, 'initextonstart', True)
    root.par.reinitextensions.pulse()

    # Accessing a promoted member forces initialization and verifies setup.
    root.Stop()
    print('Installed promoted PlayoutCore Extension on {}'.format(root.path))
    return root


PLAYOUT_CORE = build()
