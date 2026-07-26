"""Build the pixel.formation logicCore operator interface."""


ROOT_PATH = '/project1/logicCore'
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
    parameter = getattr(operator.par, name, None)
    if parameter is None:
        return
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
    for suffix, value in zip('rgb', C['border']):
        _set(item, 'bordera' + suffix, value)
    _set(item, 'borderaalpha', 1)
    for edge in ('leftborder', 'rightborder', 'topborder', 'bottomborder'):
        _set(item, edge, 1)

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
        "        op('{}').op('game').par.Loadstatus = "
        "'ERROR: {}'.format(error)\n"
        '        raise\n'
        '    return\n'
    ).format(code, ROOT_PATH, '{}')
    return item


def _card(parent_op, name, label, x, width, accent, value_expression):
    card = parent_op.create(containerCOMP, 'card_' + name)
    _place(card, x, 580, width, 64, C['surface'])
    accent_bar = card.create(containerCOMP, 'accent')
    _place(accent_bar, 0, 61, width, 3, accent)
    _text(card, 'label', label, 10, 34, width - 20, 20, 10, C['muted'])
    value = _text(
        card, 'value', '--', 10, 6, width - 20, 28, 19, C['text']
    )
    _expression(value, 'text', value_expression)
    return card


def _summary_expression(key, formatter=None):
    table = "{}/game/contestantEliminationGrid/summary".format(ROOT_PATH)
    value = "op('{}')[{!r}, 1].val".format(table, key)
    condition = "op('{}') is not None and op('{}').row({!r})".format(
        table, table, key
    )
    if formatter:
        value = formatter.format(value=value)
    return "{} if {} else '--'".format(value, condition)


def build():
    logic = op(ROOT_PATH)
    if logic is None:
        raise RuntimeError('Missing {}'.format(ROOT_PATH))

    old = logic.op('operatorUI')
    if old is not None:
        old.destroy()
    old_out = logic.op('operatorOut')
    if old_out is not None:
        old_out.destroy()

    panel = logic.create(containerCOMP, 'operatorUI')
    _place(panel, 0, 0, WIDTH, HEIGHT, C['canvas'])

    actions = panel.create(fileinDAT, 'actions')
    _set(actions, 'file', 'scripts/logic_operator_ui_actions.py')
    _set(actions, 'converttable', False)
    _set(actions, 'language', 'python')
    actions.par.refreshpulse.pulse()

    logo_image = panel.create(moviefileinTOP, 'brandLogoImage')
    _set(logo_image, 'file', 'ui/assets/pixel-formation-white.png')
    _set(logo_image, 'play', False)
    logo = panel.create(containerCOMP, 'brandLogo')
    _place(logo, 20, 660, 56, 44, C['canvas'])
    _set(logo, 'top', logo_image.path)
    _set(logo, 'topfill', 'best')

    _text(
        panel, 'product', 'logicCore.', 88, 665, 260, 34, 23, C['cyan']
    )
    _text(
        panel,
        'screenTitle',
        'CONTESTANT ELIMINATION / OPERATOR',
        360,
        665,
        570,
        34,
        16,
        C['text'],
        'center',
    )
    verification_header = _text(
        panel,
        'verificationHeader',
        '',
        980,
        665,
        280,
        34,
        13,
        C['yellow'],
        'centerright',
    )
    _expression(
        verification_header,
        'text',
        "'VERIFICATION  ' + ('ON' if op('{}').par.Verifysnapshots "
        "else 'OFF / TESTING')".format(ROOT_PATH),
    )
    header_line = panel.create(containerCOMP, 'headerLine')
    _place(header_line, 20, 654, 1240, 2, C['cyan'])

    _card(
        panel,
        'prizePool',
        'PRIZE POOL',
        20,
        226,
        C['lime'],
        _summary_expression(
            'prizePool',
            "'$' + format(float({value}), ',.0f')",
        ),
    )
    _card(
        panel,
        'question',
        'QUESTION',
        258,
        170,
        C['green'],
        _summary_expression('question'),
    )
    _card(
        panel,
        'remaining',
        'REMAINING',
        440,
        190,
        C['green'],
        _summary_expression('remaining'),
    )
    _card(
        panel,
        'eliminated',
        'OUT THIS STAGE',
        642,
        206,
        C['cyan'],
        _summary_expression('eliminatedThisStage'),
    )
    _card(
        panel,
        'revision',
        'REVISION',
        860,
        176,
        C['blue'],
        _summary_expression('revision'),
    )
    _card(
        panel,
        'passes',
        'FREE PASSES',
        1048,
        212,
        C['yellow'],
        _summary_expression('totalFreePass'),
    )

    controls = panel.create(containerCOMP, 'episodeControls')
    _place(controls, 340, 420, 230, 140, C['surface'])
    accent = controls.create(containerCOMP, 'accent')
    _place(accent, 0, 137, 230, 3, C['cyan'])
    _text(
        controls, 'title', 'EPISODE CONTROL',
        10, 108, 210, 20, 11, C['muted']
    )
    source_label = _text(
        controls,
        'sourceLabel',
        'EXTERNAL SNAPSHOT INPUT',
        14,
        462,
        382,
        24,
        11,
        C['cyan'],
    )
    _set(source_label, 'display', False)
    source_help = _text(
        controls,
        'sourceHelp',
        'Stage progression is controlled by the incoming data source. '
        'A JSON file can still be loaded manually for testing.',
        14,
        426,
        382,
        34,
        10,
        C['muted'],
    )
    _set(source_help, 'display', False)
    current_file = _text(
        controls, 'currentFile', 'NO MANUAL FILE SELECTED',
        10, 84, 210, 18, 9, C['text'], 'center'
    )
    _expression(
        current_file,
        'text',
        "op('{}/game').par.Episodefile.eval().replace('\\\\', '/')."
        "split('/')[-1] or 'NO MANUAL FILE SELECTED'".format(ROOT_PATH),
    )

    action_path = ROOT_PATH + '/operatorUI/actions'
    _button(
        controls,
        'browseJson',
        'BROWSE / LOAD JSON',
        10,
        44,
        100,
        32,
        C['blue'],
        "op('{}').module.browse_episode()".format(action_path),
    )
    _button(
        controls,
        'resetEpisode',
        'RESET EPISODE',
        120,
        44,
        100,
        32,
        C['red'],
        "op('{}').module.reset_episode()".format(action_path),
    )
    reset_help = _text(
        controls,
        'resetHelp',
        'Creates a fresh authoritative session and applies 00 Start.json.',
        14,
        312,
        382,
        20,
        9,
        C['muted'],
    )
    _set(reset_help, 'display', False)

    verify_button = _button(
        controls,
        'verification',
        'VERIFICATION',
        10,
        8,
        210,
        28,
        C['raised'],
        "op('{}').module.toggle_verification()".format(action_path),
    )
    _expression(
        verify_button.op('label'),
        'text',
        "'VERIFICATION ON — ORDERED DATA' if op('{}').par.Verifysnapshots "
        "else 'VERIFICATION OFF — FREE TESTING'".format(ROOT_PATH),
    )

    old_episode_title = _text(
        controls, 'episodeTitle', 'EPISODE TOTALS',
        14, 226, 200, 20, 10, C['muted']
    )
    _set(old_episode_title, 'display', False)
    totals = (
        ('totalContestants', 'TOTAL CONTESTANTS', C['cyan']),
        ('totalEliminated', 'TOTAL ELIMINATED', C['muted']),
        ('totalBoughtOut', 'BOUGHT OUT', C['blue']),
        ('totalBoughtOutEndgame', 'ENDGAME BUYOUT', C['lime']),
    )
    for index, (key, label, color) in enumerate(totals):
        y = 184 - index * 43
        old_label = _text(
            controls, 'label_' + key, label,
            14, y, 250, 28, 10, C['muted']
        )
        old_value = _text(
            controls, 'value_' + key, '--',
            280, y, 116, 28, 15, color, 'centerright'
        )
        _set(old_label, 'display', False)
        _set(old_value, 'display', False)

    preview = panel.create(containerCOMP, 'producerPreview')
    _place(preview, 20, 110, 300, 340, C['surface'])
    preview_accent = preview.create(containerCOMP, 'accent')
    _place(preview_accent, 0, 337, 300, 3, C['green'])
    _text(
        preview, 'title', 'CONTESTANT BOARD / CONFIDENCE MONITOR',
        14, 306, 272, 22, 10, C['muted']
    )
    board_source = preview.create(opviewerTOP, 'boardSource')
    _set(
        board_source,
        'opviewer',
        logic.op('producer/board').path,
    )
    _set(board_source, 'allowpanel', False)
    _set(board_source, 'outputresolution', 'custom')
    _set(board_source, 'resolutionw', 754)
    _set(board_source, 'resolutionh', 500)
    _set(board_source, 'resmult', False)
    monitor = preview.create(containerCOMP, 'monitor')
    _place(monitor, 14, 14, 272, 284, C['canvas'])
    _set(monitor, 'top', board_source.path)
    _set(monitor, 'topfill', 'best')

    diagnostics = panel.create(containerCOMP, 'diagnostics')
    _place(diagnostics, 340, 80, 230, 320, C['surface'])
    diagnostics_accent = diagnostics.create(containerCOMP, 'accent')
    _place(diagnostics_accent, 0, 317, 230, 3, C['yellow'])
    _text(
        diagnostics, 'title', 'FEEDBACK / TOTALS',
        10, 288, 210, 20, 11, C['muted']
    )
    load_status = _text(
        diagnostics, 'loadStatus', 'NO FILE LOADED',
        10, 258, 210, 24, 9, C['text'], 'center'
    )
    _expression(
        load_status,
        'text',
        "op('{}/game').par.Loadstatus.eval()".format(ROOT_PATH),
    )

    latest = "{}/control/latestEvent".format(ROOT_PATH)
    latest_type = _text(
        diagnostics, 'latestType', 'NO EVENT',
        10, 230, 210, 20, 9, C['cyan'], 'center'
    )
    _expression(
        latest_type,
        'text',
        "('LATEST EVENT  ' + op('{}')[1, 'type'].val) "
        "if op('{}') is not None and op('{}').numRows > 1 "
        "else 'LATEST EVENT  —'".format(latest, latest, latest),
    )
    latest_payload = _text(
        diagnostics, 'latestPayload', '',
        14, 50, 782, 32, 10, C['muted']
    )
    _expression(
        latest_payload,
        'text',
        "op('{}')[1, 'payload'].val "
        "if op('{}') is not None and op('{}').numRows > 1 else ''".format(
            latest, latest, latest
        ),
    )
    _set(latest_payload, 'display', False)
    hint = _text(
        diagnostics,
        'hint',
        'Verification checks ordered game transitions. Turn it off only '
        'when freely testing snapshots.',
        14,
        14,
        782,
        24,
        10,
        C['muted'],
    )
    _set(hint, 'display', False)

    _text(
        diagnostics, 'totalsTitle', 'EPISODE TOTALS',
        10, 198, 210, 20, 9, C['muted']
    )
    for index, (key, label, color) in enumerate(totals):
        y = 158 - index * 36
        _text(
            diagnostics, 'totalLabel_' + key, label,
            10, y, 150, 24, 8, C['muted']
        )
        value = _text(
            diagnostics, 'totalValue_' + key, '--',
            160, y, 60, 24, 11, color, 'centerright'
        )
        _expression(value, 'text', _summary_expression(key))

    operator_out = logic.create(opviewerTOP, 'operatorOut')
    _set(operator_out, 'opviewer', panel.path)
    _set(operator_out, 'allowpanel', True)
    _set(operator_out, 'outputresolution', 'custom')
    _set(operator_out, 'resolutionw', WIDTH)
    _set(operator_out, 'resolutionh', HEIGHT)
    _set(operator_out, 'resmult', False)

    for index, child in enumerate(panel.children):
        child.nodeX = (index % 6) * 180
        child.nodeY = -(index // 6) * 120
    panel.nodeX, panel.nodeY = 650, -450
    operator_out.nodeX, operator_out.nodeY = 900, -450
    panel.viewer = True

    errors = panel.errors(recurse=True) + operator_out.errors(recurse=True)
    print('Created logicCore operator UI at {}'.format(panel.path))
    print('Operator TOP output:', operator_out.path)
    if errors:
        print('Operator UI errors:')
        for error in errors:
            print(error)
    return panel


LOGIC_OPERATOR_UI = build()
