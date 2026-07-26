"""Build configured native UDP connections for the Show Controller."""

import importlib.util
from pathlib import Path
import sys


SHOW_PATH = '/project1/showController'


def _set(operator, name, value):
    parameter = getattr(operator.par, name, None)
    if parameter is None:
        raise RuntimeError('{} has no parameter {}'.format(
            operator.path, name
        ))
    parameter.val = value


def _custom_page(show):
    page = next(
        (item for item in show.customPages if item.name == 'Connections'),
        None,
    )
    return (
        page if page is not None
        else show.appendCustomPage('Connections')
    )


def _ensure_parameters(show):
    page = _custom_page(show)
    if getattr(show.par, 'Connectionsfile', None) is None:
        parameter = page.appendFile(
            'Connectionsfile',
            label='Connections JSON',
        )[0]
        parameter.default = 'config/connections.json'
        parameter.val = parameter.default
    if getattr(show.par, 'Reloadconnections', None) is None:
        page.appendMomentary(
            'Reloadconnections',
            label='Reload Connections',
        )


def _config(show):
    filename = show.par.Connectionsfile.eval().strip()
    path = Path(filename)
    if not path.is_absolute():
        path = Path(project.folder) / path
    module_path = Path(project.folder) / 'scripts' / 'connection_model.py'
    name = 'logic_core_connection_build_model'
    spec = importlib.util.spec_from_file_location(name, str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.ConnectionConfig.from_path(path)


def _build_reload_execute(show):
    execute = show.op('connectionConfigExecute')
    if execute is None:
        execute = show.create(
            parameterexecuteDAT,
            'connectionConfigExecute',
        )
    _set(execute, 'active', True)
    _set(execute, 'op', show.path)
    _set(execute, 'pars', 'Connectionsfile Reloadconnections')
    _set(execute, 'custom', True)
    _set(execute, 'builtin', False)
    _set(execute, 'valuechange', True)
    _set(execute, 'onpulse', True)
    execute.text = '''def _rebuild():
    run(
        "exec(open(project.folder + "
        "'/scripts/create_connections.py').read()); "
        "exec(open(project.folder + "
        "'/scripts/create_show_controller_ui.py').read())",
        delayFrames=1,
    )


def onValueChange(par, prev):
    if (
        par.name == 'Connectionsfile'
        or (par.name == 'Reloadconnections' and par.eval())
    ):
        _rebuild()
    return


def onPulse(par):
    if par.name == 'Reloadconnections':
        _rebuild()
    return
'''
    execute.nodeX = -250
    execute.nodeY = -150


def build():
    project_comp = op('/project1')
    if project_comp is None:
        raise RuntimeError('Missing /project1')
    show = project_comp.op('showController')
    if show is None:
        show = project_comp.create(baseCOMP, 'showController')
    _ensure_parameters(show)
    _build_reload_execute(show)
    config = _config(show)

    old = show.op('connections')
    if old is not None:
        old.destroy()
    connections = show.create(baseCOMP, 'connections')
    status = connections.create(tableDAT, 'status')
    status.appendRow([
        'id', 'label', 'direction', 'protocol', 'enabled',
        'address', 'port', 'purpose', 'state',
        'peer', 'lastMessage', 'error',
    ])

    old_actions = show.op('connectionActions')
    if old_actions is not None:
        old_actions.destroy()
    actions = show.create(fileinDAT, 'connectionActions')
    _set(actions, 'file', 'scripts/connection_actions.py')
    _set(actions, 'converttable', False)
    _set(actions, 'language', 'python')
    actions.par.refreshpulse.pulse()

    for index, item in enumerate(config.connections):
        if item['direction'] == 'receive':
            endpoint = connections.create(udpinDAT, item['id'])
            _set(endpoint, 'protocol', 'msging')
            _set(endpoint, 'port', item['port'])
            _set(endpoint, 'localaddress', item['address'])
            _set(endpoint, 'format', 'permessage')
            _set(endpoint, 'clamp', True)
            _set(endpoint, 'maxlines', 20)
            callbacks = connections.create(
                textDAT,
                item['id'] + 'Callbacks',
            )
            callbacks.text = '''def onReceive(
    dat, rowIndex, message, byteData, peer
):
    op('/project1/showController/connectionActions').module.receive(
        {!r},
        message,
        peer.address,
        peer.port,
    )
    return
'''.format(item['id'])
            _set(endpoint, 'callbacks', callbacks.path)
            callbacks.nodeX = index * 220
            callbacks.nodeY = -150
            state = 'LISTENING' if item['enabled'] else 'DISABLED'
        else:
            endpoint = connections.create(udpoutDAT, item['id'])
            _set(endpoint, 'protocol', 'msging')
            _set(endpoint, 'address', item['address'])
            _set(endpoint, 'port', item['port'])
            _set(endpoint, 'format', 'permessage')
            state = 'READY' if item['enabled'] else 'DISABLED'
        _set(endpoint, 'active', item['enabled'])
        endpoint.nodeX = index * 220
        endpoint.nodeY = 0
        status.appendRow([
            item['id'],
            item['label'],
            item['direction'],
            item['protocol'],
            int(item['enabled']),
            item['address'] or '*',
            item['port'],
            item['purpose'],
            state,
            '',
            '',
            '',
        ])

    connections.nodeX = 0
    connections.nodeY = -250
    actions.nodeX = 250
    actions.nodeY = -250
    errors = connections.errors(recurse=True)
    print('Created Show Controller connections:', len(config.connections))
    if errors:
        print('Connection errors:')
        for error in errors:
            print(error)
    return connections


CONNECTIONS = build()
