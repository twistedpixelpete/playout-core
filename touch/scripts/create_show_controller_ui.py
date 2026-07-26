"""Build the host operator console joining logicCore and playbackCore."""

import importlib.util
import json
from pathlib import Path
import sys


SHOW_PATH = '/project1/showController'
LOGIC_PATH = '/project1/logicCore'
PLAYBACK_PATH = '/project1/playoutCore'
WIDTH = 1280
HEIGHT = 720

C = {
    'canvas': (0.0, 0.0, 0.0),
    'surface': (0.025, 0.039, 0.052),
    'raised': (0.070, 0.096, 0.118),
    'border': (0.16, 0.21, 0.25),
    'text': (0.95, 0.97, 0.98),
    'muted': (0.60, 0.66, 0.70),
    'cyan': (0.09, 0.75, 0.82),
    'blue': (0.09, 0.55, 0.80),
    'green': (0.22, 0.79, 0.57),
    'lime': (0.55, 0.83, 0.35),
    'yellow': (0.97, 0.85, 0.15),
    'red': (0.94, 0.36, 0.40),
}


def _set(operator, name, value):
    if operator is None:
        return
    parameter = getattr(operator.par, name, None)
    if parameter is not None:
        parameter.val = value


def _expression(operator, name, expression):
    parameter = getattr(operator.par, name, None)
    if parameter is not None:
        parameter.expr = expression


def _place(operator, x, y, width, height, color=None):
    for name, value in (
        ('x', x),
        ('y', y),
        ('w', width),
        ('h', height),
        ('width', width),
        ('height', height),
        ('display', True),
        ('enable', True),
    ):
        _set(operator, name, value)
    if color is not None:
        for suffix, value in zip('rgb', color):
            _set(operator, 'bgcolor' + suffix, value)
        _set(operator, 'bgalpha', 1)


def _text(
    parent_op,
    name,
    text,
    x,
    y,
    width,
    height,
    size,
    color,
    justify='centerleft',
):
    item = parent_op.create(textCOMP, name)
    _place(item, x, y, width, height)
    _set(item, 'text', text)
    _set(item, 'fontsize', size)
    _set(item, 'scaletofit', 'onlyshrink')
    _set(item, 'textpaddingl', 6)
    _set(item, 'textpaddingr', 6)
    _set(item, 'justify', justify)
    for prefix in ('fontcolor', 'textcolor'):
        for suffix, value in zip('rgb', color):
            _set(item, prefix + suffix, value)
    _set(item, 'bgalpha', 0)
    return item


def _field(
    parent_op, name, value, x, y, width, height,
    multiline=False,
):
    item = parent_op.create(textCOMP, name)
    _place(item, x, y, width, height, C['canvas'])
    _set(item, 'text', str(value))
    _set(item, 'type', 'multiline' if multiline else 'string')
    _set(item, 'editmode', 'editable')
    _set(item, 'fontsize', 12 if multiline else 14)
    _set(item, 'justify', 'topleft' if multiline else 'centerleft')
    _set(item, 'wordwrap', multiline)
    _set(item, 'textpaddingl', 8)
    _set(item, 'textpaddingr', 8)
    _set(item, 'textpaddingt', 6)
    _set(item, 'textpaddingb', 6)
    for prefix in ('fontcolor', 'textcolor'):
        for suffix, value in zip('rgb', C['text']):
            _set(item, prefix + suffix, value)
    return item


def _button(
    parent_op,
    name,
    label,
    x,
    y,
    width,
    height,
    color,
    code,
):
    # Draw the surface explicitly. The stock Button COMP skin can override
    # background colours, making enabled controls look disabled.
    item = parent_op.create(containerCOMP, name)
    _place(item, x, y, width, height, color)
    _set(item, 'clickthrough', False)
    _set(item, 'layer', 10)
    label_comp = _text(
        item, 'label', label, 0, 0, width, height,
        13, C['text'], 'center',
    )
    _set(label_comp, 'clickthrough', True)
    hit = item.create(buttonCOMP, 'hit')
    _place(hit, 0, 0, width, height)
    _set(hit, 'buttontype', 'momentary')
    _set(hit, 'opacity', 0)
    _set(hit, 'bgalpha', 0)
    _set(hit, 'layer', 20)
    callback = hit.op('panelexec1')
    if callback is None:
        callback = hit.create(panelexecuteDAT, 'panelexec1')
    _set(callback, 'panels', '..')
    _set(callback, 'panelvalue', 'state')
    _set(callback, 'offtoon', True)
    _set(callback, 'valuechange', False)
    _set(callback, 'active', True)
    callback.text = (
        'def onOffToOn(panelValue):\n'
        '    try:\n'
        '        {}\n'
        '    except Exception as error:\n'
        "        op('{}').par.Lastaction = 'ERROR: {}'.format(error)\n"
        '        raise\n'
        '    return\n'
    ).format(code, SHOW_PATH, '{}')
    return item


def _style_tab(tab, page, active_color):
    """Give tabs a strong active colour and a quieter inactive surface."""
    for index, suffix in enumerate('rgb'):
        _expression(
            tab,
            'bgcolor' + suffix,
            "{} if op('{}').par.Activepage.eval() == {!r} else {}".format(
                active_color[index],
                SHOW_PATH,
                page,
                C['raised'][index],
            ),
        )
        for prefix in ('fontcolor', 'textcolor'):
            _expression(
                tab.op('label'),
                prefix + suffix,
                "{} if op('{}').par.Activepage.eval() == {!r} else {}".format(
                    C['canvas'][index],
                    SHOW_PATH,
                    page,
                    C['muted'][index],
                ),
            )


def _custom_page(show):
    page = next(
        (item for item in show.customPages if item.name == 'Operator'),
        None,
    )
    return page if page is not None else show.appendCustomPage('Operator')


def _ensure_parameters(show):
    page = _custom_page(show)
    if getattr(show.par, 'Activepage', None) is None:
        parameter = page.appendStr('Activepage', label='Active Page')[0]
        parameter.default = 'logic'
        parameter.val = 'logic'
        parameter.readOnly = True
    if getattr(show.par, 'Lastaction', None) is None:
        parameter = page.appendStr('Lastaction', label='Last Action')[0]
        parameter.default = 'READY'
        parameter.val = 'READY'
        parameter.readOnly = True
    if getattr(show.par, 'Selectedexecutor', None) is None:
        parameter = page.appendStr(
            'Selectedexecutor',
            label='Selected Executor',
        )[0]
        parameter.default = ''
        parameter.val = ''
    if getattr(show.par, 'Executorsfile', None) is None:
        parameter = page.appendFile(
            'Executorsfile',
            label='Executor Buttons JSON',
        )[0]
        parameter.default = 'config/executors.json'
        parameter.val = parameter.default
    if getattr(show.par, 'Reloadexecutors', None) is None:
        page.appendMomentary(
            'Reloadexecutors',
            label='Reload Executors',
        )


def _build_config_execute(show):
    execute = show.op('executorConfigExecute')
    if execute is None:
        execute = show.create(
            parameterexecuteDAT,
            'executorConfigExecute',
        )
    _set(execute, 'active', True)
    _set(execute, 'op', show.path)
    _set(execute, 'pars', 'Executorsfile Reloadexecutors')
    _set(execute, 'custom', True)
    _set(execute, 'builtin', False)
    _set(execute, 'valuechange', True)
    _set(execute, 'onpulse', True)
    execute.text = '''def _rebuild():
    run(
        "exec(open(project.folder + "
        "'/scripts/create_show_controller_ui.py').read())",
        delayFrames=1,
    )


def onValueChange(par, prev):
    if (
        par.name == 'Executorsfile'
        or (par.name == 'Reloadexecutors' and par.eval())
    ):
        _rebuild()
    return


def onPulse(par):
    if par.name == 'Reloadexecutors':
        _rebuild()
    return
'''
    execute.nodeX = -250
    execute.nodeY = 0
    return execute


def _executor_config(show):
    filename = show.par.Executorsfile.eval().strip()
    path = Path(filename)
    if not path.is_absolute():
        path = Path(project.folder) / path
    module_path = Path(project.folder) / 'scripts' / 'executor_model.py'
    name = 'logic_core_executor_ui_model'
    spec = importlib.util.spec_from_file_location(name, str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.ExecutorConfig.from_path(path)


def _connection_config(show):
    filename = show.par.Connectionsfile.eval().strip()
    path = Path(filename)
    if not path.is_absolute():
        path = Path(project.folder) / path
    module_path = Path(project.folder) / 'scripts' / 'connection_model.py'
    name = 'logic_core_connection_ui_model'
    spec = importlib.util.spec_from_file_location(name, str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.ConnectionConfig.from_path(path)


def _validate_clip_references(buttons):
    path = Path(project.folder) / 'config' / 'clips.json'
    clip_config = json.loads(path.read_text(encoding='utf-8'))
    clip_ids = {
        item['id'] for item in clip_config.get('clips', ())
        if item.get('enabled', True)
    }
    errors = {}
    for button in buttons:
        for action in button['actions']:
            clip_id = action.get('clipId')
            if clip_id is not None and clip_id not in clip_ids:
                errors.setdefault(button['id'], []).append(
                    'Unloaded clip: {}'.format(clip_id)
                )
    return {
        button_id: tuple(messages)
        for button_id, messages in errors.items()
    }


def _validate_connection_references(buttons, connections):
    connection_ids = {item['id'] for item in connections}
    for button in buttons:
        for action in button['actions']:
            connection_id = action.get('connectionId')
            if (
                connection_id is not None
                and connection_id not in connection_ids
            ):
                raise RuntimeError(
                    'Executor {} references unknown connection {}'.format(
                        button['id'], connection_id
                    )
                )


def build():
    project_comp = op('/project1')
    logic = op(LOGIC_PATH)
    if project_comp is None or logic is None:
        raise RuntimeError('logicCore must exist before showController')

    show = project_comp.op('showController')
    if show is None:
        show = project_comp.create(baseCOMP, 'showController')
    _ensure_parameters(show)
    _build_config_execute(show)

    console = project_comp.op('operatorConsole')
    panel = show.op('operatorUI')
    if panel is None:
        panel = show.create(containerCOMP, 'operatorUI')
    else:
        child_names = tuple(child.name for child in panel.children)
        for child_name in child_names:
            child = panel.op(child_name)
            if child is not None:
                child.destroy()
    operator_out = show.op('operatorOut')
    _place(panel, 0, 0, WIDTH, HEIGHT, C['canvas'])

    actions = show.op('executorActions')
    if actions is None:
        actions = show.create(fileinDAT, 'executorActions')
    _set(actions, 'file', 'scripts/show_controller_actions.py')
    _set(actions, 'converttable', False)
    _set(actions, 'language', 'python')
    actions.par.refreshpulse.pulse()
    action_path = SHOW_PATH + '/executorActions'
    executor_config_error = ''
    try:
        executor_config = _executor_config(show)
        executors = executor_config.buttons
    except Exception as error:
        executors = ()
        executor_config_error = str(error)
    try:
        clip_reference_errors = _validate_clip_references(executors)
    except Exception as error:
        clip_reference_errors = {}
        executor_config_error = (
            executor_config_error + ' / ' if executor_config_error else ''
        ) + str(error)
    connection_config = _connection_config(show)
    _validate_connection_references(
        executors,
        connection_config.connections,
    )

    logic_page = panel.create(containerCOMP, 'logicPage')
    _place(logic_page, 0, 0, WIDTH, HEIGHT, C['canvas'])
    logic_panel = logic_page.create(selectCOMP, 'logicPanel')
    _place(logic_panel, 0, 0, WIDTH, HEIGHT)
    _set(logic_panel, 'selectpanel', LOGIC_PATH + '/operatorUI')
    _set(logic_panel, 'matchsize', False)

    live_bank = logic_page.create(containerCOMP, 'liveExecutors')
    _place(live_bank, 590, 80, 670, 480, C['surface'])
    _set(live_bank, 'layer', 50)
    live_accent = live_bank.create(containerCOMP, 'accent')
    _place(live_accent, 0, 477, 670, 3, C['blue'])
    _text(
        live_bank, 'title', 'LIVE EXECUTORS',
        12, 444, 180, 22, 12, C['text']
    )
    _text(
        live_bank, 'hint',
        (
            'CONFIG ERROR: ' + executor_config_error
            if executor_config_error
            else 'Configure on EXECUTORS tab'
        ),
        12, 422, 640, 18, 9, C['muted']
    )
    for index, executor in enumerate(executors[:16]):
        column = index % 4
        row = index // 4
        reference_error = clip_reference_errors.get(executor['id'], ())
        callback_code = (
            "op('{}').par.Lastaction = {!r}".format(
                SHOW_PATH,
                'INVALID CLIP / EXECUTOR {}'.format(executor['id']),
            )
            if reference_error
            else "op('{}').module.execute_button({!r})".format(
                action_path,
                executor['id'],
            )
        )
        live_button = _button(
            live_bank,
            'liveExecutor{:02d}'.format(index),
            (
                executor['label'] + '\nINVALID CLIP'
                if reference_error else executor['label']
            ),
            12 + column * 163,
            318 - row * 100,
            151,
            90,
            C['red'] if reference_error else C[executor['color']],
            callback_code,
        )
        _set(live_button.op('label'), 'fontsize', 16)

    executor_page = panel.create(containerCOMP, 'executorPage')
    _place(executor_page, 0, 0, WIDTH, HEIGHT, C['canvas'])
    _set(executor_page, 'display', False)

    logo_image = executor_page.create(moviefileinTOP, 'brandLogoImage')
    _set(logo_image, 'file', 'ui/assets/pixel-formation-white.png')
    logo = executor_page.create(containerCOMP, 'brandLogo')
    _place(logo, 20, 660, 56, 44, C['canvas'])
    _set(logo, 'top', logo_image.path)
    _set(logo, 'topfill', 'best')
    _text(
        executor_page, 'product', 'showController.', 88, 665, 300, 34,
        23, C['cyan']
    )
    _text(
        executor_page, 'title', 'EXECUTOR SETUP', 440, 665, 400, 34,
        17, C['text'], 'center'
    )
    engine = PLAYBACK_PATH + '/control/engineStatus'
    engine_state = _text(
        executor_page, 'engineState', 'ENGINE —', 960, 665, 300, 34,
        13, C['yellow'], 'centerright'
    )
    _expression(
        engine_state,
        'text',
        "('ENGINE  ' + op('{}')['engineState', 1].val) "
        "if op('{}') is not None and op('{}').row('engineState') "
        "else 'ENGINE  OFFLINE'".format(engine, engine, engine),
    )
    header_line = executor_page.create(containerCOMP, 'headerLine')
    _place(header_line, 20, 654, 1240, 2, C['cyan'])

    config_bar = executor_page.create(containerCOMP, 'configBar')
    _place(config_bar, 20, 570, 1240, 64, C['surface'])
    _text(
        config_bar, 'title', 'EXECUTOR CONFIG JSON',
        14, 34, 170, 22, 11, C['muted']
    )
    config_name = _text(
        config_bar, 'configFile', '', 184, 34, 520, 22,
        10, C['text']
    )
    _expression(
        config_name,
        'text',
        "op('{}').par.Executorsfile.eval()".format(SHOW_PATH),
    )
    _button(
        config_bar, 'browseConfig', 'BROWSE', 744, 12, 140, 40, C['blue'],
        "op('{}').module.browse_executors()".format(action_path),
    )
    _button(
        config_bar, 'reloadConfig', 'RELOAD', 896, 12, 140, 40, C['raised'],
        "op('{}').module.reload_executors()".format(action_path),
    )
    _button(
        config_bar, 'editConfig', 'OPEN JSON', 1048, 12, 176, 40,
        C['green'],
        "op('{}').module.open_executor_config()".format(action_path),
    )
    _text(
        config_bar,
        'configError',
        executor_config_error,
        184,
        6,
        548,
        18,
        9,
        C['red'],
    )

    selector = executor_page.create(containerCOMP, 'executorSelector')
    _place(selector, 20, 20, 330, 530, C['surface'])
    selector_accent = selector.create(containerCOMP, 'accent')
    _place(selector_accent, 0, 527, 330, 3, C['blue'])
    _text(
        selector, 'title', 'EXECUTORS',
        14, 492, 300, 22, 13, C['muted']
    )
    if not executors:
        _text(
            selector, 'empty', 'NO VALID EXECUTOR CONFIGURATION',
            14, 430, 300, 40, 11, C['red'], 'center'
        )

    executor_ids = {item['id'] for item in executors}
    selected_executor = show.par.Selectedexecutor.eval()
    if selected_executor not in executor_ids:
        selected_executor = executors[0]['id'] if executors else ''
        show.par.Selectedexecutor = selected_executor

    for index, executor in enumerate(executors[:16]):
        column = index % 2
        row = index // 2
        button = _button(
            selector,
            'selectExecutor{:02d}'.format(index),
            executor['label'],
            14 + column * 153,
            424 - row * 58,
            145,
            48,
            C[executor['color']],
            "op('{}').module.select_executor({!r})".format(
                action_path,
                executor['id'],
            ),
        )
        for channel, suffix in enumerate('rgb'):
            _expression(
                button,
                'border' + 'a' + suffix,
                "{} if op('{}').par.Selectedexecutor.eval() == {!r} "
                "else {}".format(
                    C['text'][channel],
                    SHOW_PATH,
                    executor['id'],
                    C['border'][channel],
                ),
            )
        _set(button, 'borderaalpha', 1)
        for edge in (
            'leftborder', 'rightborder', 'topborder', 'bottomborder'
        ):
            _set(button, edge, 1)

    detail_host = executor_page.create(containerCOMP, 'executorDetail')
    _place(detail_host, 370, 20, 890, 530, C['surface'])
    detail_accent = detail_host.create(containerCOMP, 'accent')
    _place(detail_accent, 0, 527, 890, 3, C['green'])
    for index, executor in enumerate(executors[:16]):
        detail = detail_host.create(
            containerCOMP,
            'detail{:02d}'.format(index),
        )
        _place(detail, 0, 0, 890, 527, C['surface'])
        _expression(
            detail,
            'display',
            "op('{}').par.Selectedexecutor.eval() == {!r}".format(
                SHOW_PATH,
                executor['id'],
            ),
        )
        _text(
            detail, 'labelTitle', 'BUTTON LABEL',
            20, 482, 420, 20, 10, C['muted']
        )
        _field(
            detail, 'fieldLabel', executor['label'],
            20, 440, 420, 36,
        )
        _text(
            detail, 'colorTitle',
            'COLOR  /  raised cyan blue green lime red',
            460, 482, 300, 20, 10, C['muted']
        )
        _field(
            detail, 'fieldColor', executor['color'],
            460, 440, 100, 36,
        )
        _button(
            detail,
            'chooseColor',
            'CHOOSE v',
            568,
            440,
            96,
            36,
            C['blue'],
            "op('{}').module.choose_executor_color({!r})".format(
                action_path,
                executor['id'],
            ),
        )
        _text(
            detail, 'id', 'ID  {}'.format(executor['id']),
            670, 446, 200, 24, 10, C['muted'], 'centerright'
        )
        _text(
            detail, 'stackTitle',
            'ORDERED ACTION STACK / EDITABLE JSON / {} STEP{}'.format(
                len(executor['actions']),
                '' if len(executor['actions']) == 1 else 'S',
            ),
            20, 402, 620, 24, 12, C['text']
        )
        _button(
            detail,
            'addAction',
            'ADD ACTION v',
            704,
            394,
            166,
            34,
            C['blue'],
            "op('{}').module.add_executor_action({!r})".format(
                action_path,
                executor['id'],
            ),
        )
        reference_error = clip_reference_errors.get(executor['id'], ())
        _text(
            detail,
            'referenceError',
            ' / '.join(reference_error),
            20,
            376,
            850,
            22,
            10,
            C['red'],
        )
        _field(
            detail,
            'fieldActions',
            json.dumps(list(executor['actions']), indent=2),
            20,
            92,
            850,
            276,
            multiline=True,
        )
        _button(
            detail,
            'resetExecutor',
            'RESET SLOT',
            446,
            28,
            126,
            44,
            C['red'],
            "op('{}').module.reset_executor({!r})".format(
                action_path,
                executor['id'],
            ),
        )
        _button(
            detail,
            'revert',
            'REVERT',
            584,
            28,
            126,
            44,
            C['raised'],
            "op('{}').module.refresh()".format(action_path),
        )
        _button(
            detail,
            'saveExecutor',
            'SAVE + ASSIGN',
            714,
            28,
            156,
            44,
            C['green'],
            "op('{}').module.save_executor({!r})".format(
                action_path,
                executor['id'],
            ),
        )
        _text(
            detail, 'help',
            'Edit the slot, add actions, then SAVE + ASSIGN to update its '
            'live executor button.',
            20, 32, 540, 34, 10, C['muted']
        )

    connections_page = panel.create(containerCOMP, 'connectionsPage')
    _place(connections_page, 0, 0, WIDTH, HEIGHT, C['canvas'])
    _set(connections_page, 'display', False)

    connection_logo_image = connections_page.create(
        moviefileinTOP,
        'brandLogoImage',
    )
    _set(
        connection_logo_image,
        'file',
        'ui/assets/pixel-formation-white.png',
    )
    connection_logo = connections_page.create(
        containerCOMP,
        'brandLogo',
    )
    _place(connection_logo, 20, 660, 56, 44, C['canvas'])
    _set(connection_logo, 'top', connection_logo_image.path)
    _set(connection_logo, 'topfill', 'best')
    _text(
        connections_page,
        'product',
        'showController.',
        88,
        665,
        300,
        34,
        23,
        C['cyan'],
    )
    _text(
        connections_page,
        'title',
        'EXTERNAL CONNECTIONS',
        440,
        665,
        400,
        34,
        17,
        C['text'],
        'center',
    )
    connections_header = connections_page.create(
        containerCOMP,
        'headerLine',
    )
    _place(connections_header, 20, 654, 1240, 2, C['cyan'])

    connection_config_bar = connections_page.create(
        containerCOMP,
        'configBar',
    )
    _place(
        connection_config_bar,
        20,
        570,
        1240,
        64,
        C['surface'],
    )
    _text(
        connection_config_bar, 'title', 'CONNECTIONS JSON',
        14, 34, 150, 22, 11, C['muted']
    )
    connection_file = _text(
        connection_config_bar, 'file', '',
        166, 34, 540, 22, 10, C['text']
    )
    _expression(
        connection_file,
        'text',
        "op('{}').par.Connectionsfile.eval()".format(SHOW_PATH),
    )
    _button(
        connection_config_bar,
        'browse',
        'BROWSE',
        760,
        12,
        150,
        40,
        C['blue'],
        "op('{}').module.browse_connections()".format(action_path),
    )
    _button(
        connection_config_bar,
        'reload',
        'RELOAD',
        922,
        12,
        150,
        40,
        C['raised'],
        "op('{}').module.reload_connections()".format(action_path),
    )

    connection_bank = connections_page.create(
        containerCOMP,
        'connectionBank',
    )
    _place(connection_bank, 20, 100, 1240, 450, C['surface'])
    connection_accent = connection_bank.create(containerCOMP, 'accent')
    _place(connection_accent, 0, 447, 1240, 3, C['green'])
    _text(
        connection_bank, 'title', 'CONFIGURED ENDPOINTS',
        14, 410, 300, 24, 13, C['muted']
    )
    connection_status_path = SHOW_PATH + '/connections/status'
    connection_action_path = SHOW_PATH + '/connectionActions'
    for index, connection in enumerate(
        connection_config.connections[:8]
    ):
        column = index % 3
        row = index // 3
        x = 14 + column * 404
        y = 250 - row * 170
        card = connection_bank.create(
            containerCOMP,
            'connection{:02d}'.format(index),
        )
        _place(card, x, y, 390, 150, C['raised'])
        _text(
            card, 'label', connection['label'],
            12, 112, 250, 26, 13, C['text']
        )
        state_text = _text(
            card, 'state', 'UNKNOWN',
            270, 112, 108, 26, 11,
            C['green'] if connection['enabled'] else C['muted'],
            'centerright',
        )
        state_expression = (
            "op('{status}')[{id!r}, 'state'].val "
            "if op('{status}') is not None and "
            "op('{status}').row({id!r}) else 'UNKNOWN'"
        ).format(
            status=connection_status_path,
            id=connection['id'],
        )
        _expression(state_text, 'text', state_expression)
        endpoint = '{}  {}:{}'.format(
            connection['protocol'].upper(),
            connection['address'] or '*',
            connection['port'],
        )
        _text(
            card, 'endpoint', endpoint,
            12, 82, 366, 22, 11, C['cyan']
        )
        _text(
            card,
            'purpose',
            '{}  /  {}'.format(
                connection['direction'].upper(),
                connection['purpose'],
            ),
            12,
            56,
            366,
            20,
            10,
            C['muted'],
        )
        if connection['direction'] == 'send':
            _button(
                card, 'sendState', 'SEND STATE',
                12, 12, 170, 34, C['green'],
                "op('{}').module.send_logic_state({!r})".format(
                    connection_action_path,
                    connection['id'],
                ),
            )
            _button(
                card, 'sendTest', 'SEND TEST',
                194, 12, 184, 34, C['blue'],
                "op('{}').module.send_test({!r})".format(
                    connection_action_path,
                    connection['id'],
                ),
            )
        else:
            message = _text(
                card, 'lastMessage', 'WAITING FOR DATA',
                12, 12, 366, 34, 9, C['muted']
            )
            message_expression = (
                "op('{status}')[{id!r}, 'lastMessage'].val "
                "if op('{status}') is not None and "
                "op('{status}').row({id!r}) and "
                "op('{status}')[{id!r}, 'lastMessage'].val "
                "else 'WAITING FOR DATA'"
            ).format(
                status=connection_status_path,
                id=connection['id'],
            )
            _expression(message, 'text', message_expression)

    connection_footer = connections_page.create(
        containerCOMP,
        'footer',
    )
    _place(connection_footer, 20, 20, 1240, 60, C['surface'])
    _text(
        connection_footer,
        'hint',
        'Enable endpoints and configure destination addresses in the '
        'selected Connections JSON file.',
        14,
        18,
        1212,
        24,
        11,
        C['muted'],
    )

    tabs = panel.create(containerCOMP, 'navigation')
    _place(tabs, 0, 650, 1280, 70, C['surface'])
    _set(tabs, 'layer', 100)
    _set(tabs, 'borderover', True)
    _text(
        tabs, 'consoleTitle', 'OPERATOR CONSOLE',
        20, 18, 300, 34, 14, C['text']
    )
    logic_tab = _button(
        tabs, 'logic', 'GAME LOGIC', 690, 14, 180, 42, C['cyan'],
        "op('{}').module.set_page('logic')".format(action_path),
    )
    _style_tab(logic_tab, 'logic', C['cyan'])
    executor_tab = _button(
        tabs, 'executors', 'EXECUTORS', 882, 14, 180, 42, C['blue'],
        "op('{}').module.set_page('executors')".format(action_path),
    )
    _style_tab(executor_tab, 'executors', C['blue'])
    connections_tab = _button(
        tabs,
        'connections',
        'CONNECTIONS',
        1074,
        14,
        186,
        42,
        C['green'],
        "op('{}').module.set_page('connections')".format(action_path),
    )
    _style_tab(connections_tab, 'connections', C['green'])

    if operator_out is None:
        operator_out = show.create(opviewerTOP, 'operatorOut')
    _set(operator_out, 'opviewer', panel.path)
    _set(operator_out, 'allowpanel', True)
    _set(operator_out, 'outputresolution', 'custom')
    _set(operator_out, 'resolutionw', WIDTH)
    _set(operator_out, 'resolutionh', HEIGHT)
    _set(operator_out, 'resmult', False)

    # Provide one unmistakable project-level entry point for operators. The
    # selected logicCore panel remains reusable and host-independent, while
    # this Select COMP exposes the host-owned tabs and cross-core actions.
    if console is None:
        console = project_comp.create(selectCOMP, 'operatorConsole')
    _place(console, 0, 0, WIDTH, HEIGHT)
    _set(console, 'selectpanel', panel.path)
    _set(console, 'matchsize', False)

    active_page = show.par.Activepage.eval()
    if active_page == 'media':
        active_page = 'executors'
        show.par.Activepage = active_page
    if active_page not in ('logic', 'executors', 'connections'):
        active_page = 'logic'
        show.par.Activepage = active_page
    logic_page.par.display = active_page == 'logic'
    executor_page.par.display = active_page == 'executors'
    connections_page.par.display = active_page == 'connections'
    panel.nodeX, panel.nodeY = 0, 0
    operator_out.nodeX, operator_out.nodeY = 300, 0
    console.nodeX, console.nodeY = 900, -350
    show.nodeX, show.nodeY = 1200, -350
    panel.viewer = True
    console.viewer = True

    errors = (
        panel.errors(recurse=True)
        + operator_out.errors(recurse=True)
        + console.errors(recurse=True)
    )
    print('Created Show Controller operator UI at {}'.format(panel.path))
    print('Open the full console at {}'.format(console.path))
    print('Loaded executor buttons:', len(executors))
    if errors:
        print('Show Controller UI errors:')
        for error in errors:
            print(error)
    return panel


SHOW_CONTROLLER_UI = build()
