"""Build a native Table COMP producer display for contestantEliminationGrid."""


ROOT_PATH = '/project1/logicCore'
WIDTH = 1280
HEIGHT = 720


def _set(operator, name, value):
    parameter = getattr(operator.par, name, None)
    if parameter is None:
        raise RuntimeError('{} has no parameter {}'.format(operator.path, name))
    parameter.val = value


def _menu(operator, name, label):
    parameter = getattr(operator.par, name, None)
    if parameter is None or label not in parameter.menuLabels:
        raise RuntimeError(
            '{}.{} cannot select {!r}; labels={}'.format(
                operator.path,
                name,
                label,
                tuple(parameter.menuLabels) if parameter else (),
            )
        )
    parameter.menuIndex = parameter.menuLabels.index(label)


def _panel(operator, x, y, width, height):
    for name, value in (
        ('x', x), ('y', y), ('w', width), ('h', height),
        ('display', True), ('enable', True),
    ):
        _set(operator, name, value)
    if getattr(operator.par, 'clickthrough', None) is not None:
        _set(operator, 'clickthrough', True)


def _color(operator, rgb, alpha=1):
    _set(operator, 'bgcolorr', rgb[0])
    _set(operator, 'bgcolorg', rgb[1])
    _set(operator, 'bgcolorb', rgb[2])
    _set(operator, 'bgalpha', alpha)


def _text(parent_op, name, text, x, y, width, height, size, color):
    item = parent_op.create(textCOMP, name)
    _panel(item, x, y, width, height)
    _set(item, 'text', text)
    _set(item, 'fontsize', size)
    _menu(item, 'fontsizeunits', 'P')
    _menu(item, 'alignx', 'Center')
    _menu(item, 'aligny', 'Center')
    _set(item, 'fontcolorr', color[0])
    _set(item, 'fontcolorg', color[1])
    _set(item, 'fontcolorb', color[2])
    _set(item, 'fontalpha', 1)
    _color(item, (0, 0, 0), 0)
    return item


def build():
    root = op(ROOT_PATH)
    if root is None:
        raise RuntimeError('Missing {}'.format(ROOT_PATH))
    old = root.op('producer')
    if old is not None:
        old.destroy()
    old_out = root.op('producerOut')
    if old_out is not None:
        old_out.destroy()

    producer = root.create(containerCOMP, 'producer')
    _panel(producer, 0, 0, WIDTH, HEIGHT)
    _color(producer, (0, 0, 0), 1)

    white = (0.92, 0.95, 1.0)
    muted = (0.52, 0.56, 0.64)
    lime = (0.60, 0.82, 0.24)
    green = (0.08, 0.66, 0.38)
    teal = (0.02, 0.58, 0.55)
    cyan = (0.02, 0.56, 0.78)
    blue = (0.02, 0.38, 0.66)
    slate = (0.16, 0.19, 0.23)
    pass_grey = (0.28, 0.32, 0.36)
    surface = (0.035, 0.04, 0.055)

    logo_source = producer.create(moviefileinTOP, 'brandLogo')
    _set(logo_source, 'file', 'ui/assets/pixel-formation-white.png')
    logo = producer.create(containerCOMP, 'logo')
    _panel(logo, 32, 657, 48, 48)
    _color(logo, (0, 0, 0), 1)
    _set(logo, 'top', logo_source.path)
    _menu(logo, 'topfill', 'Fill Best')

    _text(
        producer, 'title', 'CONTESTANT ELIMINATION GRID',
        96, 664, 636, 40, 22, white,
    )
    _text(
        producer, 'live', 'logicCore.  /  LIVE DATA',
        980, 670, 268, 28, 12, cyan,
    )

    cards = (
        ('prizePool', 'PRIZE POOL', 32, 292),
        ('question', 'QUESTION', 336, 190),
        ('remaining', 'REMAINING', 538, 190),
        ('eliminatedThisStage', 'OUT THIS STAGE', 740, 224),
        ('revision', 'REVISION', 976, 272),
    )
    card_accents = (lime, green, teal, cyan, blue)
    for index, (key, label, x, width) in enumerate(cards):
        card = producer.create(containerCOMP, 'card_' + key)
        _panel(card, x, 568, width, 78)
        _color(card, surface, 1)
        _text(card, 'label', label, 14, 43, width - 28, 24, 11, muted)
        _text(card, 'value', '--', 14, 8, width - 28, 34, 24, white)
        accent = card.create(containerCOMP, 'accent')
        _panel(accent, 0, 74, width, 4)
        _color(accent, card_accents[index], 1)

    board = producer.create(containerCOMP, 'board')
    _panel(board, 32, 40, 754, 500)
    _color(board, (0, 0, 0), 0)

    tile = board.create(containerCOMP, 'tile')
    _panel(tile, 0, 0, 68, 42)
    _set(tile, 'display', False)
    number = tile.create(textTOP, 'number')
    _set(number, 'text', '0')
    _menu(number, 'outputresolution', 'Custom Resolution')
    _set(number, 'resolutionw', 68)
    _set(number, 'resolutionh', 42)
    _set(number, 'resmult', False)
    _menu(number, 'positionunit', 'P')
    _menu(number, 'fontsizexunit', 'Px')
    _menu(number, 'fontsizeyunit', 'Px')
    _menu(number, 'alignx', 'Center')
    _menu(number, 'aligny', 'Center')
    _set(number, 'fontsizex', 19)
    _set(number, 'fontsizey', 19)
    _set(number, 'fontcolorr', white[0])
    _set(number, 'fontcolorg', white[1])
    _set(number, 'fontcolorb', white[2])
    _set(number, 'fontalpha', 1)
    _set(number, 'bgalpha', 1)
    _set(tile, 'top', './number')

    contestants = root.op('game/contestantEliminationGrid/contestants')
    row = "(me.digits or 1)"
    tile.par.x.expr = (
        "int(parent.LogicCore.op("
        "'game/contestantEliminationGrid/contestants'"
        ")[{}, 'column']) * 72".format(row)
    )
    tile.par.y.expr = (
        "(9 - int(parent.LogicCore.op("
        "'game/contestantEliminationGrid/contestants'"
        ")[{}, 'row'])) * 48".format(row)
    )
    number.par.text.expr = (
        "parent.LogicCore.op("
        "'game/contestantEliminationGrid/contestants'"
        ")[(parent().digits or 1), 'number']"
    )
    status = (
        "parent.LogicCore.op("
        "'game/contestantEliminationGrid/contestants'"
        ")[(parent().digits or 1), 'status'].val"
    )
    palette = {
        'ACTIVE': green,
        'ACTIVE_WITH_PASS': teal,
        'ELIMINATED': slate,
        'ELIMINATED_WITH_PASS': pass_grey,
        'BOUGHT_OUT': cyan,
        'BOUGHT_OUT_ENDGAME': lime,
    }
    for channel, name in enumerate(('bgcolorr', 'bgcolorg', 'bgcolorb')):
        getattr(number.par, name).expr = (
            "{}.get({}, (0.16, 0.19, 0.27))[{}]".format(
                repr(palette), status, channel
            )
        )
    text_palette = {
        'ACTIVE': white,
        'ACTIVE_WITH_PASS': white,
        'ELIMINATED': white,
        'ELIMINATED_WITH_PASS': white,
        'BOUGHT_OUT': white,
        'BOUGHT_OUT_ENDGAME': white,
    }
    for channel, name in enumerate(
        ('fontcolorr', 'fontcolorg', 'fontcolorb')
    ):
        getattr(number.par, name).expr = (
            "{}.get({}, (0.92, 0.95, 1.0))[{}]".format(
                repr(text_palette), status, channel
            )
        )

    rep_callbacks = board.create(textDAT, 'replicatorCallbacks')
    rep_callbacks.text = '''def onReplicate(
    comp, allOps, newOps, template, master
):
    for operator in newOps:
        operator.par.display = True
    return
'''
    replicator = board.create(replicatorCOMP, 'replicator')
    _set(replicator, 'template', contestants.path)
    _set(replicator, 'ignorefirstrow', True)
    _set(replicator, 'repsuffixstart', 1)
    _set(replicator, 'opprefix', 'item')
    _set(replicator, 'master', tile.path)
    _set(replicator, 'destination', board.path)
    _set(replicator, 'callbacks', rep_callbacks.path)
    _set(replicator, 'doincremental', False)
    replicator.par.recreateall.pulse()

    legend = (
        ('ACTIVE', green),
        ('FREE PASS', teal),
        ('ELIMINATED', slate),
        ('BOUGHT OUT', cyan),
        ('ENDGAME', lime),
    )
    for index, (label, color) in enumerate(legend):
        item = _text(
            producer, 'legend{}'.format(index + 1), label,
            834, 440 - index * 58, 300, 44, 16, white,
        )
        _color(item, color, 1)

    refresh = producer.create(textDAT, 'refresh')
    refresh.text = '''def refresh():
    owner = me.parent()
    logic = parent.LogicCore
    summary = logic.op('game/contestantEliminationGrid/summary')
    for key in (
        'prizePool', 'question', 'remaining',
        'eliminatedThisStage', 'revision',
    ):
        cell = summary[key, 1] if summary is not None else None
        value = cell.val if cell is not None else '--'
        if key == 'prizePool' and value != '--':
            value = '${:,.0f}'.format(float(value))
        owner.op('card_' + key + '/value').par.text = str(value)
'''

    callback = '''def onTableChange(dat, prevDAT, info):
    me.parent().op('refresh').module.refresh()
    return
'''
    for name, target in (
        (
            'summaryExecute',
            root.op(
                'game/contestantEliminationGrid/summary'
            ).path,
        ),
        (
            'contestantsExecute',
            root.op(
                'game/contestantEliminationGrid/contestants'
            ).path,
        ),
    ):
        execute = producer.create(datexecuteDAT, name)
        _set(execute, 'dat', target)
        _set(execute, 'active', True)
        _set(execute, 'tablechange', True)
        execute.text = callback

    producer_out = root.create(opviewerTOP, 'producerOut')
    _set(producer_out, 'opviewer', producer.path)
    _set(producer_out, 'allowpanel', True)
    _menu(producer_out, 'outputresolution', 'Custom Resolution')
    _set(producer_out, 'resolutionw', WIDTH)
    _set(producer_out, 'resolutionh', HEIGHT)
    _set(producer_out, 'resmult', False)

    for index, child in enumerate(producer.children):
        child.nodeX = (index % 6) * 180
        child.nodeY = -(index // 6) * 120
    producer.nodeX, producer.nodeY = 650, 0
    producer_out.nodeX, producer_out.nodeY = 900, 0
    refresh.module.refresh()

    errors = producer.errors(recurse=True) + producer_out.errors(recurse=True)
    print('Created replicated tile producer at {}'.format(producer.path))
    print('Producer TOP output:', producer_out.path)
    if errors:
        print('Producer screen errors:')
        for error in errors:
            print(error)
    return producer


CONTESTANT_PRODUCER = build()
