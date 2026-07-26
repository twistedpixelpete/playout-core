"""Build the efficient contestantEliminationGrid producer renderer."""


ROOT_PATH = '/project1/logicCore'
# Free/non-commercial TouchDesigner output.
WIDTH = 1280
HEIGHT = 720


def _ensure(parent_op, op_class, name):
    existing = parent_op.op(name)
    if existing is not None:
        if not isinstance(existing, op_class):
            raise TypeError('{} has the wrong operator type'.format(
                existing.path
            ))
        return existing
    return parent_op.create(op_class, name)


def _set(operator, name, value):
    parameter = getattr(operator.par, name, None)
    if parameter is None:
        raise RuntimeError('{} has no parameter {}'.format(
            operator.path, name
        ))
    parameter.val = value


def _set_menu_label(operator, name, label):
    parameter = getattr(operator.par, name, None)
    if parameter is None:
        raise RuntimeError('{} has no parameter {}'.format(
            operator.path, name
        ))
    if label not in parameter.menuLabels:
        raise RuntimeError(
            '{}.{} has no menu label {!r}; available labels: {}'.format(
                operator.path,
                name,
                label,
                tuple(parameter.menuLabels),
            )
        )
    parameter.menuIndex = parameter.menuLabels.index(label)


def _custom_page(comp, name):
    page = next(
        (item for item in comp.customPages if item.name == name),
        None,
    )
    return page if page is not None else comp.appendCustomPage(name)


def _ensure_float(comp, page, name, label, default, minimum=None):
    parameter = getattr(comp.par, name, None)
    if parameter is None:
        group = page.appendFloat(name, label=label)
        parameter = group[0]
        parameter.val = default
    parameter.default = default
    if minimum is not None:
        parameter.min = minimum
        parameter.clampMin = True
    return parameter


def _add_layout_parameters(producer):
    page = _custom_page(producer, 'Layout')
    definitions = (
        ('Titlex', 'Title X', 35, 0),
        ('Titley', 'Title Y', 683, 0),
        ('Titlesize', 'Title Size', 18, 1),
        ('Statusx', 'Status X', 1240, 0),
        ('Statusy', 'Status Y', 683, 0),
        ('Statussize', 'Status Size', 10, 1),
        ('Metriclabelsize', 'Metric Label Size', 10, 1),
        ('Metricvaluesize', 'Metric Value Size', 24, 1),
        ('Metric1x', 'Prize Pool X', 47, 0),
        ('Metric2x', 'Question X', 345, 0),
        ('Metric3x', 'Remaining X', 557, 0),
        ('Metric4x', 'Out This Stage X', 769, 0),
        ('Metric5x', 'Revision X', 1015, 0),
        ('Metriclabely', 'Metric Label Y', 631, 0),
        ('Metricvaluey', 'Metric Value Y', 596, 0),
        ('Gridx', 'Grid X', 35, 0),
        ('Gridy', 'Grid Y', 44, 0),
        ('Gridpitchx', 'Grid Pitch X', 72, 1),
        ('Gridpitchy', 'Grid Pitch Y', 51, 1),
        ('Tilewidth', 'Tile Width', 64, 1),
        ('Tileheight', 'Tile Height', 43, 1),
        ('Gridtextsize', 'Grid Text Size', 18, 1),
        ('Gridtextoffsetx', 'Grid Text Offset X', 0, None),
        ('Gridtextoffsety', 'Grid Text Offset Y', 0, None),
        ('Legendx', 'Legend X', 793, 0),
        ('Legendy', 'Legend Y', 493, 0),
        ('Legendpitch', 'Legend Pitch', 52, 1),
        ('Legendwidth', 'Legend Width', 200, 1),
        ('Legendheight', 'Legend Height', 39, 1),
        ('Legendtextsize', 'Legend Text Size', 12, 1),
    )
    for name, label, default, minimum in definitions:
        _ensure_float(
            producer,
            page,
            name,
            label,
            default,
            minimum,
        )
    if getattr(producer.par, 'Resetlayout', None) is None:
        page.appendMomentary(
            'Resetlayout',
            label='Reset Pixel Layout',
        )


def _connect_input(source, destination, index):
    connector = destination.inputConnectors[index]
    connector.disconnect()
    source.outputConnectors[0].connect(connector)


def _remove_legacy_nodes(producer):
    names = [
        'showTitle',
        'systemStatus',
        'prizePool',
        'question',
        'remaining',
        'eliminated',
        'revision',
    ]
    names.extend('legend{}'.format(index) for index in range(1, 6))
    names.extend('player{}'.format(index) for index in range(1, 101))
    for name in names:
        operator = producer.op(name)
        if operator is not None:
            operator.destroy()


BACKGROUND_CALLBACKS = r'''"""Render the producer background in one Script TOP cook."""

import numpy as np

WIDTH = __OUTPUT_WIDTH__
HEIGHT = __OUTPUT_HEIGHT__

COLORS = {
    'background': (5, 8, 15, 255),
    'surface': (9, 14, 23, 255),
    'raised': (14, 21, 31, 255),
    'accent': (0, 209, 199, 255),
    'ACTIVE': (14, 140, 110, 255),
    'ACTIVE_WITH_PASS': (31, 97, 224, 255),
    'ELIMINATED': (41, 48, 64, 255),
    'ELIMINATED_WITH_PASS': (56, 69, 97, 255),
    'BOUGHT_OUT': (235, 135, 26, 255),
    'BOUGHT_OUT_ENDGAME': (148, 77, 209, 255),
}


def _rect(canvas, x, y, width, height, color):
    x0 = max(0, round(x))
    x1 = min(WIDTH, round(x + width))
    y0 = max(0, round(y))
    y1 = min(HEIGHT, round(y + height))
    if x1 > x0 and y1 > y0:
        canvas[y0:y1, x0:x1] = color


def onCook(scriptOp):
    layout = parent().par
    canvas = np.empty((HEIGHT, WIDTH, 4), dtype=np.uint8)
    canvas[:] = COLORS['background']

    # Header rule and five summary cards.
    _rect(canvas, 35, 655, 1205, 2, COLORS['accent'])
    cards = (
        (35, 572, 287, 79),
        (333, 572, 200, 79),
        (545, 572, 200, 79),
        (757, 572, 233, 79),
        (1003, 572, 237, 79),
    )
    for x, y, width, height in cards:
        _rect(canvas, x, y, width, height, COLORS['raised'])
        _rect(canvas, x, y + height - 4, width, 4, COLORS['accent'])

    contestants = parent.LogicCore.op(
        'game/contestantEliminationGrid/contestants'
    )
    grid_x = layout.Gridx.eval()
    grid_y = layout.Gridy.eval()
    pitch_x = layout.Gridpitchx.eval()
    pitch_y = layout.Gridpitchy.eval()
    tile_w = layout.Tilewidth.eval()
    tile_h = layout.Tileheight.eval()
    for number in range(1, 101):
        column = (number - 1) % 10
        row = (number - 1) // 10
        status = 'ELIMINATED'
        if contestants is not None and contestants.numRows > number:
            status = contestants[number, 'status'].val
        color = COLORS.get(status, COLORS['ELIMINATED'])
        x = grid_x + column * pitch_x
        y = grid_y + (9 - row) * pitch_y
        _rect(canvas, x, y, tile_w, tile_h, color)
        _rect(
            canvas,
            x,
            y + tile_h - 2,
            tile_w,
            2,
            COLORS['accent'],
        )

    legend_x = layout.Legendx.eval()
    legend_y = layout.Legendy.eval()
    legend_pitch = layout.Legendpitch.eval()
    legend_width = layout.Legendwidth.eval()
    legend_height = layout.Legendheight.eval()
    legend = (
        ('ACTIVE', 'ACTIVE'),
        ('FREE PASS', 'ACTIVE_WITH_PASS'),
        ('ELIMINATED', 'ELIMINATED'),
        ('BOUGHT OUT', 'BOUGHT_OUT'),
        ('ENDGAME', 'BOUGHT_OUT_ENDGAME'),
    )
    for index, (_, status) in enumerate(legend):
        _rect(
            canvas,
            legend_x,
            legend_y - index * legend_pitch,
            legend_width,
            legend_height,
            COLORS[status],
        )

    scriptOp.copyNumpyArray(canvas)
    return


def onSetupParameters(scriptOp):
    return


def onPulse(par):
    return


def onGetCookLevel(scriptOp):
    return CookLevel.AUTOMATIC
'''


TEXT_SPEC_CALLBACKS = r'''"""Build one Specification DAT for all producer text."""


WIDTH = __OUTPUT_WIDTH__
HEIGHT = __OUTPUT_HEIGHT__


def _value(table, key, default='--'):
    if table is None:
        return default
    cell = table[key, 1]
    return cell.val if cell is not None else default


def _row_pixels(
    scriptOp,
    x,
    y,
    text,
    size,
    color=(0.92, 0.96, 1.0),
    alignx='left',
    aligny='center',
):
    scriptOp.appendRow([
        x,
        y,
        text,
        size,
        size,
        color[0],
        color[1],
        color[2],
        1,
        alignx,
        aligny,
        'bbox',
        'bbox',
    ])


def onCook(scriptOp):
    layout = parent().par
    scriptOp.clear()
    scriptOp.appendRow([
        'x',
        'y',
        'text',
        'fontsizex',
        'fontsizey',
        'fontcolorr',
        'fontcolorg',
        'fontcolorb',
        'fontalpha',
        'alignx',
        'aligny',
        'alignxmode',
        'alignymode',
    ])

    white = (0.92, 0.96, 1.0)
    muted = (0.47, 0.58, 0.68)
    accent = (0.0, 0.82, 0.78)
    summary = parent.LogicCore.op(
        'game/contestantEliminationGrid/summary'
    )

    _row_pixels(
        scriptOp,
        layout.Titlex.eval(),
        layout.Titley.eval(),
        'CONTESTANT ELIMINATION GRID',
        layout.Titlesize.eval(),
        white,
    )
    _row_pixels(
        scriptOp,
        layout.Statusx.eval(),
        layout.Statusy.eval(),
        'LOGICCORE  /  LIVE DATA',
        layout.Statussize.eval(),
        accent,
        'right',
    )

    metrics = (
        (layout.Metric1x.eval(), 'PRIZE POOL', 'prizePool', True),
        (layout.Metric2x.eval(), 'QUESTION', 'question', False),
        (layout.Metric3x.eval(), 'REMAINING', 'remaining', False),
        (
            layout.Metric4x.eval(),
            'OUT THIS STAGE',
            'eliminatedThisStage',
            False,
        ),
        (layout.Metric5x.eval(), 'REVISION', 'revision', False),
    )
    for x, title, key, money in metrics:
        raw = _value(summary, key)
        if money and raw != '--':
            value = '${:,.0f}'.format(float(raw))
        else:
            value = str(raw)
        _row_pixels(
            scriptOp,
            x,
            layout.Metriclabely.eval(),
            title,
            layout.Metriclabelsize.eval(),
            muted,
        )
        _row_pixels(
            scriptOp,
            x,
            layout.Metricvaluey.eval(),
            value,
            layout.Metricvaluesize.eval(),
            white,
        )

    grid_x = layout.Gridx.eval()
    grid_y = layout.Gridy.eval()
    pitch_x = layout.Gridpitchx.eval()
    pitch_y = layout.Gridpitchy.eval()
    tile_w = layout.Tilewidth.eval()
    tile_h = layout.Tileheight.eval()
    for number in range(1, 101):
        column = (number - 1) % 10
        row = (number - 1) // 10
        _row_pixels(
            scriptOp,
            (
                grid_x + column * pitch_x + tile_w / 2
                + layout.Gridtextoffsetx.eval()
            ),
            (
                grid_y + (9 - row) * pitch_y + tile_h / 2
                + layout.Gridtextoffsety.eval()
            ),
            str(number),
            layout.Gridtextsize.eval(),
            white,
            'center',
        )

    legend = (
        'ACTIVE',
        'FREE PASS',
        'ELIMINATED',
        'BOUGHT OUT',
        'ENDGAME',
    )
    legend_x = layout.Legendx.eval()
    legend_y = layout.Legendy.eval()
    legend_pitch = layout.Legendpitch.eval()
    legend_width = layout.Legendwidth.eval()
    legend_height = layout.Legendheight.eval()
    for index, label in enumerate(legend):
        _row_pixels(
            scriptOp,
            legend_x + legend_width / 2,
            (
                legend_y - index * legend_pitch
                + legend_height / 2
            ),
            label,
            layout.Legendtextsize.eval(),
            white,
            'center',
        )
    return


def onSetupParameters(scriptOp):
    return


def onPulse(par):
    return


def onGetCookLevel(scriptOp):
    return CookLevel.AUTOMATIC
'''


def build():
    root = op(ROOT_PATH)
    if root is None:
        raise RuntimeError('Missing {}'.format(ROOT_PATH))

    existing = root.op('producer')
    if existing is not None:
        existing.destroy()
    producer = root.create(containerCOMP, 'producer')
    _add_layout_parameters(producer)
    _set(producer, 'w', WIDTH)
    _set(producer, 'h', HEIGHT)
    _set(producer, 'display', True)

    background_callbacks = _ensure(
        producer,
        textDAT,
        'backgroundCallbacks',
    )
    background_callbacks.text = (
        BACKGROUND_CALLBACKS
        .replace('__OUTPUT_WIDTH__', str(WIDTH))
        .replace('__OUTPUT_HEIGHT__', str(HEIGHT))
    )

    background = _ensure(producer, scriptTOP, 'background')
    _set(background, 'callbacks', 'backgroundCallbacks')
    _set(background, 'format', 'rgba8fixed')

    text_callbacks = _ensure(producer, textDAT, 'textSpecCallbacks')
    text_callbacks.text = (
        TEXT_SPEC_CALLBACKS
        .replace('__OUTPUT_WIDTH__', str(WIDTH))
        .replace('__OUTPUT_HEIGHT__', str(HEIGHT))
    )

    text_spec = _ensure(producer, scriptDAT, 'textSpec')
    _set(text_spec, 'callbacks', 'textSpecCallbacks')

    layout_execute = _ensure(
        producer,
        parameterexecuteDAT,
        'layoutExecute',
    )
    _set(layout_execute, 'active', True)
    _set(layout_execute, 'op', producer.path)
    _set(layout_execute, 'pars', '*')
    _set(layout_execute, 'custom', True)
    _set(layout_execute, 'builtin', False)
    _set(layout_execute, 'valuechange', True)
    _set(layout_execute, 'onpulse', True)
    layout_execute.text = '''def _refresh():
    text_spec = me.parent().op('textSpec')
    background = me.parent().op('background')
    if text_spec is not None:
        text_spec.cook(force=True)
    if background is not None:
        background.cook(force=True)


def onValueChange(par, prev):
    _refresh()
    return


def onPulse(par):
    if par.name == 'Resetlayout':
        me.parent().customPages['Layout'].resetPars()
    _refresh()
    return
'''

    labels = _ensure(producer, textTOP, 'labels')
    _set(labels, 'specdat', 'textSpec')
    _set_menu_label(
        labels,
        'outputresolution',
        'Custom Resolution',
    )
    _set(labels, 'resolutionw', WIDTH)
    _set(labels, 'resolutionh', HEIGHT)
    _set(labels, 'resmult', False)
    _set(labels, 'bgalpha', 0)
    _set_menu_label(labels, 'dispmethod', 'Polygon')
    _set_menu_label(labels, 'positionunit', 'P')
    _set_menu_label(labels, 'fontsizexunit', 'Px')
    _set_menu_label(labels, 'fontsizeyunit', 'Px')

    composite = _ensure(producer, compositeTOP, 'composite')
    _set(composite, 'operand', 'over')
    _set_menu_label(
        composite,
        'outputresolution',
        'Custom Resolution',
    )
    _set(composite, 'resolutionw', WIDTH)
    _set(composite, 'resolutionh', HEIGHT)
    # Composite TOP's Over operation places Input 1 over Input 2.
    _connect_input(labels, composite, 0)
    _connect_input(background, composite, 1)

    output = _ensure(producer, nullTOP, 'out')
    _connect_input(composite, output, 0)
    _set(producer, 'top', './out')

    background_callbacks.nodeX = 0
    background_callbacks.nodeY = 150
    background.nodeX = 0
    background.nodeY = 0
    text_callbacks.nodeX = 220
    text_callbacks.nodeY = 300
    text_spec.nodeX = 220
    text_spec.nodeY = 150
    layout_execute.nodeX = 440
    layout_execute.nodeY = 300
    labels.nodeX = 220
    labels.nodeY = 0
    composite.nodeX = 440
    composite.nodeY = 0
    output.nodeX = 660
    output.nodeY = 0
    producer.nodeX = 650
    producer.nodeY = 0

    print('Created efficient producer renderer at {}'.format(producer.path))
    print('Producer child operators:', len(producer.children))
    errors = producer.errors(recurse=True)
    if errors:
        print('Producer screen errors:')
        for error in errors:
            print(error)
    return producer


CONTESTANT_PRODUCER = build()
