"""Create the independent /project1/logicCore Base COMP."""


ROOT_PATH = '/project1/logicCore'


def _ensure(parent_op, op_class, name):
    existing = parent_op.op(name)
    if existing is not None:
        if not isinstance(existing, op_class):
            raise TypeError('{} has the wrong operator type'.format(existing.path))
        return existing
    return parent_op.create(op_class, name)


def _set(operator, name, value):
    parameter = getattr(operator.par, name, None)
    if parameter is None:
        raise RuntimeError('{} has no parameter {}'.format(operator.path, name))
    parameter.val = value


def _connect(source, destination):
    for connector in destination.inputConnectors:
        connector.disconnect()
    source.outputConnectors[0].connect(destination.inputConnectors[0])


def _ensure_toggle(comp, page_name, name, label, default):
    parameter = getattr(comp.par, name, None)
    if parameter is None:
        page = next(
            (
                item for item in comp.customPages
                if item.name == page_name
            ),
            None,
        )
        if page is None:
            page = comp.appendCustomPage(page_name)
        group = page.appendToggle(name, label=label)
        parameter = group[0]
        parameter.default = default
        parameter.val = default
    return parameter


def _custom_page(comp, name):
    page = next(
        (item for item in comp.customPages if item.name == name),
        None,
    )
    return page if page is not None else comp.appendCustomPage(name)


def _build_episode_loader(game, contestant_grid):
    old_loader = contestant_grid.op('episodeLoader')
    if old_loader is not None:
        old_loader.destroy()
    old_page = next(
        (
            item for item in contestant_grid.customPages
            if item.name == 'Episode'
        ),
        None,
    )
    if old_page is not None:
        old_page.destroy()

    page = _custom_page(game, 'Episode')
    if getattr(game.par, 'Episodefile', None) is None:
        page.appendFile('Episodefile', label='Episode JSON')
    if getattr(game.par, 'Loadepisode', None) is None:
        page.appendMomentary('Loadepisode', label='Load Episode')
    if getattr(game.par, 'Loadstatus', None) is None:
        status = page.appendStr('Loadstatus', label='Load Status')[0]
        status.default = 'NO FILE LOADED'
        status.val = status.default
        status.readOnly = True

    execute = _ensure(
        game,
        parameterexecuteDAT,
        'episodeLoadExecute',
    )
    _set(execute, 'active', True)
    _set(execute, 'op', game.path)
    _set(execute, 'pars', 'Episodefile Loadepisode')
    _set(execute, 'custom', True)
    _set(execute, 'builtin', False)
    _set(execute, 'valuechange', True)
    _set(execute, 'onpulse', True)
    execute.text = '''def _load():
    game = me.parent()
    if game.fetch('suppressEpisodeAutoLoad', False):
        game.store('suppressEpisodeAutoLoad', False)
        return
    filename = game.par.Episodefile.eval().strip()
    if not filename:
        game.par.Loadstatus = 'CHOOSE A JSON FILE'
        return
    logic = parent.LogicCore
    try:
        active = logic.ActiveGame()
        is_start = (
            filename.replace(chr(92), '/').split('/')[-1].lower()
            == '00 start.json'
        )
        if active is None or is_start:
            logic.CreateGame(
                'episode',
                'contestantEliminationGrid',
                {'stake': 1000},
            )
        elif active['variantId'] != 'contestantEliminationGrid':
            raise RuntimeError(
                'Active game is not contestantEliminationGrid'
            )
        logic.SetSnapshotVerification(
            bool(logic.par.Verifysnapshots.eval())
        )
        logic.LoadContestantSnapshotFile(filename)
        producer_refresh = logic.op('producer/refresh')
        if producer_refresh is not None:
            producer_refresh.module.refresh()
    except Exception as error:
        game.par.Loadstatus = 'ERROR: {}'.format(error)
        raise
    game.par.Loadstatus = 'LOADED: {}'.format(filename)
    print('Loaded episode JSON: {}'.format(filename))
    return


def onValueChange(par, prev):
    if par.name == 'Episodefile':
        _load()
    return


def onPulse(par):
    if par.name == 'Loadepisode':
        _load()
    return
'''
    execute.nodeX = 0
    execute.nodeY = 200
    return game


def build():
    project_comp = op('/project1')
    if project_comp is None:
        raise RuntimeError('Missing /project1')
    root = _ensure(project_comp, baseCOMP, 'logicCore')
    _set(root, 'parentshortcut', 'LogicCore')
    _ensure_toggle(
        root,
        'Testing',
        'Verifysnapshots',
        'Verify Snapshot Transitions',
        True,
    )
    control = _ensure(root, baseCOMP, 'control')
    game = _ensure(root, baseCOMP, 'game')
    contestant_grid = _ensure(
        game,
        baseCOMP,
        'contestantEliminationGrid',
    )

    extension = _ensure(control, fileinDAT, 'LogicCoreExt')
    state = _ensure(control, tableDAT, 'state')
    events = _ensure(control, tableDAT, 'events')
    latest = _ensure(control, tableDAT, 'latestEvent')
    status = _ensure(control, tableDAT, 'status')
    variants = _ensure(control, tableDAT, 'variants')
    active_game = _ensure(control, tableDAT, 'activeGame')
    summary = _ensure(contestant_grid, tableDAT, 'summary')
    contestants = _ensure(contestant_grid, tableDAT, 'contestants')
    snapshot_file = _ensure(contestant_grid, fileinDAT, 'snapshotFile')
    snapshot_execute = _ensure(
        contestant_grid,
        datexecuteDAT,
        'snapshotExecute',
    )
    episode_loader = _build_episode_loader(game, contestant_grid)
    state_out = _ensure(root, outDAT, 'stateOut')
    events_out = _ensure(root, outDAT, 'eventsOut')
    game_out = _ensure(root, outDAT, 'gameOut')
    summary_out = _ensure(root, outDAT, 'summaryOut')
    contestants_out = _ensure(root, outDAT, 'contestantsOut')

    _set(extension, 'file', 'scripts/logic_core_ext.py')
    _set(extension, 'converttable', False)
    _set(extension, 'language', 'python')
    extension.par.refreshpulse.pulse()
    _connect(state, state_out)
    _connect(events, events_out)
    _connect(active_game, game_out)
    _connect(summary, summary_out)
    _connect(contestants, contestants_out)

    _set(snapshot_file, 'converttable', False)
    _set(snapshot_file, 'language', 'json')
    _set(snapshot_execute, 'dat', 'snapshotFile')
    _set(snapshot_execute, 'active', True)
    _set(snapshot_execute, 'tablechange', True)
    snapshot_execute.text = '''def onTableChange(dat, prevDAT, info):
    if not dat.text.strip():
        return
    logic = dat.parent().parent().parent()
    active = logic.ActiveGame()
    if active is None:
        logic.CreateGame(
            'episode',
            'contestantEliminationGrid',
            {'stake': 1000},
        )
    elif active['variantId'] != 'contestantEliminationGrid':
        raise RuntimeError(
            'Active game is not contestantEliminationGrid'
        )
    logic.SetSnapshotVerification(
        bool(logic.par.Verifysnapshots.eval())
    )
    logic.LoadContestantSnapshotText(dat.text)
    background = logic.op('producer/background')
    text_spec = logic.op('producer/textSpec')
    if text_spec is not None:
        text_spec.cook(force=True)
    if background is not None:
        background.cook(force=True)
    print(
        'Loaded contestant snapshot from {}'.format(
            dat.par.file.eval() or dat.path
        )
    )
    return
'''

    _set(
        root,
        'ext0object',
        "op('./control/LogicCoreExt').module.LogicCoreExt(me)",
    )
    _set(root, 'ext0name', 'LogicCore')
    _set(root, 'ext0promote', True)
    _set(root, 'initextonstart', True)
    root.par.reinitextensions.pulse()

    control.nodeX, control.nodeY = 0, 0
    state_out.nodeX, state_out.nodeY = 300, 100
    events_out.nodeX, events_out.nodeY = 300, -100
    game_out.nodeX, game_out.nodeY = 300, -300
    summary_out.nodeX, summary_out.nodeY = 500, -100
    contestants_out.nodeX, contestants_out.nodeY = 500, -300
    for index, item in enumerate((
        extension,
        state,
        events,
        latest,
        status,
        variants,
        active_game,
    )):
        item.nodeX = index * 180
        item.nodeY = 0

    game.nodeX, game.nodeY = 0, -350
    contestant_grid.nodeX, contestant_grid.nodeY = 0, 0
    snapshot_file.nodeX, snapshot_file.nodeY = 0, 100
    snapshot_execute.nodeX, snapshot_execute.nodeY = 200, 100
    summary.nodeX, summary.nodeY = 0, -100
    contestants.nodeX, contestants.nodeY = 200, -100

    print('Created independent logicCore at {}'.format(root.path))
    print('Initial state:', root.Snapshot())
    return root


LOGIC_CORE = build()

exec(open(
    project.folder + '/scripts/create_contestant_table_producer.py'
).read())

exec(open(
    project.folder + '/scripts/create_logic_operator_ui.py'
).read())

# Rehydrate the selected episode after extension reinitialization. Rebuilding
# logicCore resets the in-memory model, but custom parameter values persist.
GAME_COMPONENT = LOGIC_CORE.op('game')
EPISODE_FILE = GAME_COMPONENT.par.Episodefile.eval().strip()
if EPISODE_FILE:
    try:
        ACTIVE_GAME = LOGIC_CORE.ActiveGame()
        if ACTIVE_GAME is None:
            LOGIC_CORE.CreateGame(
                'episode',
                'contestantEliminationGrid',
                {'stake': 1000},
            )
        LOGIC_CORE.SetSnapshotVerification(
            bool(LOGIC_CORE.par.Verifysnapshots.eval())
        )
        LOGIC_CORE.LoadContestantSnapshotFile(EPISODE_FILE)
        PRODUCER_REFRESH = LOGIC_CORE.op('producer/refresh')
        if PRODUCER_REFRESH is not None:
            PRODUCER_REFRESH.module.refresh()
        GAME_COMPONENT.par.Loadstatus = 'LOADED: {}'.format(
            EPISODE_FILE
        )
        print('Rehydrated episode JSON: {}'.format(EPISODE_FILE))
    except Exception as ERROR:
        GAME_COMPONENT.par.Loadstatus = 'ERROR: {}'.format(ERROR)
        raise
