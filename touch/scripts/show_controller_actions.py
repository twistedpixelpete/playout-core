"""Host-level execution of configured multi-action operator buttons."""

import importlib.util
import json
from pathlib import Path
import sys


SHOW_PATH = '/project1/showController'
LOGIC_PATH = '/project1/logicCore'
PLAYBACK_PATH = '/project1/playoutCore'
START_SNAPSHOT = 'components/logicCore/data/ep02/00 Start.json'
EXECUTOR_COLORS = ('raised', 'cyan', 'blue', 'green', 'lime', 'red')
ACTION_CHOICES = (
    ('CANCEL PENDING EXECUTORS', 'executor.cancelPending'),
    ('TAKE CLIP', 'playback.take'),
    ('CUE CLIP', 'playback.cue'),
    ('PLAY AUDIO CLIP', 'playback.playAudio'),
    ('PLAY', 'playback.play'),
    ('PAUSE', 'playback.pause'),
    ('STOP', 'playback.stop'),
    ('WAIT', 'wait'),
    ('RESET EPISODE', 'logic.resetEpisode'),
    ('EMIT LOGIC EVENT', 'logic.emitEvent'),
    ('SEND LOGIC STATE', 'connection.sendState'),
    ('SEND CONNECTION DATA', 'connection.send'),
)


def _show():
    show = op(SHOW_PATH)
    if show is None:
        raise RuntimeError('Missing {}'.format(SHOW_PATH))
    return show


def _logic():
    logic = op(LOGIC_PATH)
    if logic is None:
        raise RuntimeError('Missing {}'.format(LOGIC_PATH))
    return logic


def _playback():
    playback = op(PLAYBACK_PATH)
    if playback is None:
        raise RuntimeError('Missing {}'.format(PLAYBACK_PATH))
    return playback


def _load_executor_module():
    name = 'logic_core_executor_model'
    path = Path(project.folder) / 'scripts' / 'executor_model.py'
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _executor_config():
    filename = _show().par.Executorsfile.eval().strip()
    if not filename:
        raise RuntimeError('Choose an executor JSON file')
    path = Path(filename)
    if not path.is_absolute():
        path = Path(project.folder) / path
    return _load_executor_module().ExecutorConfig.from_path(path)


def _executor_source():
    filename = _show().par.Executorsfile.eval().strip()
    if not filename:
        raise RuntimeError('Choose an executor JSON file')
    path = Path(filename)
    if not path.is_absolute():
        path = Path(project.folder) / path
    return path.resolve()


def _load_executor_editor_module():
    name = 'logic_core_executor_editor'
    path = Path(project.folder) / 'scripts' / 'executor_editor.py'
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _executor_detail(button_id):
    buttons = _executor_config().buttons
    index = next(
        (
            item_index
            for item_index, button in enumerate(buttons)
            if button['id'] == button_id
        ),
        None,
    )
    if index is None:
        raise RuntimeError('Unknown executor ID: {}'.format(button_id))
    detail = _show().op(
        'operatorUI/executorPage/executorDetail/detail{:02d}'.format(index)
    )
    if detail is None:
        raise RuntimeError('Missing executor editor for {}'.format(button_id))
    return detail


def _detail_field(detail, name):
    control = detail.op(name)
    if control is None:
        raise RuntimeError('Missing executor field: {}'.format(name))
    return str(control.par.text.eval()).strip()


def _set_detail_field(detail, name, value):
    control = detail.op(name)
    if control is None:
        raise RuntimeError('Missing executor field: {}'.format(name))
    control.par.text = str(value)


def set_page(page):
    if page not in ('logic', 'executors', 'connections'):
        raise ValueError('Unknown operator page: {}'.format(page))
    ui_panel = _show().op('operatorUI')
    ui_panel.op('logicPage').par.display = page == 'logic'
    ui_panel.op('executorPage').par.display = page == 'executors'
    ui_panel.op('connectionsPage').par.display = page == 'connections'
    _show().par.Activepage = page
    return page


def _reset_episode():
    result = _logic().ResetContestantEpisodeFile(START_SNAPSHOT)
    game = _logic().op('game')
    if game is not None:
        game.par.Loadstatus = 'EPISODE RESET: 00 Start.json'
    return result


def _execute_action(action):
    action_type = action['type']
    if action_type == 'executor.cancelPending':
        return _cancel_pending_executor_runs()
    if action_type == 'logic.resetEpisode':
        return _reset_episode()
    if action_type == 'logic.emitEvent':
        return _logic().EmitEvent(
            action['eventType'],
            action['payload'],
        )
    if action_type == 'playback.cue':
        return _playback().Cue(action['clipId'])
    if action_type == 'playback.take':
        if action.get('transition'):
            return _playback().Take(
                action['clipId'],
                transition=action['transition'],
            )
        return _playback().Take(action['clipId'])
    if action_type == 'playback.playAudio':
        return _playback().PlayAudio(action['clipId'])
    if action_type == 'playback.play':
        return _playback().Play()
    if action_type == 'playback.pause':
        return _playback().Pause()
    if action_type == 'playback.stop':
        return _playback().Stop()
    if action_type == 'connection.sendState':
        return _show().op(
            'connectionActions'
        ).module.send_logic_state(action['connectionId'])
    if action_type == 'connection.send':
        return _show().op('connectionActions').module.send(
            action['connectionId'],
            action['payload'],
        )
    raise RuntimeError('Unsupported executor action: {}'.format(action_type))


def execute_scheduled(token, button_id, label, actions, final_batch):
    failed = set(_show().fetch('executorFailedTokens', ()))
    if token in failed:
        return None
    try:
        for action in actions:
            _execute_action(action)
    except Exception as error:
        failed.add(token)
        _show().store('executorFailedTokens', tuple(failed))
        _show().par.Lastaction = 'ERROR {}: {}'.format(label, error)
        raise
    if final_batch:
        _show().par.Lastaction = 'COMPLETE: {}'.format(label)
    else:
        _show().par.Lastaction = 'RUNNING: {}'.format(label)
    return button_id


def _cancel_pending_executor_runs():
    cancelled = 0
    for pending in list(runs):
        try:
            group = str(pending.group)
        except Exception:
            continue
        if group.startswith('logicCoreExecutor'):
            pending.kill()
            cancelled += 1
    return cancelled


def execute_button(button_id):
    config = _executor_config()
    button = config.button(button_id)
    batches = config.plan(button_id)
    token = int(_show().fetch('executorToken', 0)) + 1
    _show().store('executorToken', token)
    _show().par.Lastaction = 'TRIGGERED: {}'.format(button['label'])

    action_dat = _show().op('executorActions')
    if action_dat is None:
        raise RuntimeError('Missing stable Show Controller executorActions DAT')
    for index, batch in enumerate(batches):
        final_batch = index == len(batches) - 1
        arguments = (
            token,
            button_id,
            button['label'],
            batch.actions,
            final_batch,
        )
        if batch.at_ms == 0:
            execute_scheduled(*arguments)
        else:
            run(
                'args[0].module.execute_scheduled(*args[1:])',
                action_dat,
                *arguments,
                delayMilliSeconds=batch.at_ms,
                wallTime=True,
                delayRef=op.TDResources,
                group='logicCoreExecutor{}'.format(token),
            )
    return tuple(batches)


def play():
    result = _playback().Play()
    _show().par.Lastaction = 'PLAY'
    return result


def pause():
    result = _playback().Pause()
    _show().par.Lastaction = 'PAUSE'
    return result


def stop():
    result = _playback().Stop()
    _show().par.Lastaction = 'STOP'
    return result


def refresh():
    run(
        "exec(open(project.folder + "
        "'/scripts/create_show_controller_ui.py').read())",
        delayFrames=1,
    )


def browse_executors():
    selected = ui.chooseFile(
        start=str(Path(project.folder) / 'config'),
        fileTypes=['json'],
        title='Select Executor Buttons JSON',
    )
    if selected:
        _show().par.Executorsfile = str(selected)
    return selected


def reload_executors():
    # Reload is a UI action, so rebuild directly on the next frame. The
    # custom parameter is Momentary rather than Pulse and must not rely on
    # Parameter Execute's onPulse callback.
    refresh()


def select_executor(button_id):
    config = _executor_config()
    config.button(button_id)
    _show().par.Selectedexecutor = button_id
    return button_id


def save_executor(button_id):
    detail = _executor_detail(button_id)

    try:
        actions = json.loads(_detail_field(detail, 'fieldActions'))
    except json.JSONDecodeError as exc:
        _show().par.Lastaction = 'EXECUTOR JSON ERROR: {}'.format(exc)
        raise ValueError('Actions must be a valid JSON array: {}'.format(
            exc
        )) from exc
    if not isinstance(actions, list):
        raise ValueError('Actions must be a JSON array')

    editor = _load_executor_editor_module().ExecutorEditor(
        _executor_source(),
        _load_executor_module(),
    )
    saved = editor.update(
        button_id,
        _detail_field(detail, 'fieldLabel'),
        _detail_field(detail, 'fieldColor').lower(),
        actions,
    )
    _show().par.Selectedexecutor = button_id
    _show().par.Lastaction = 'ASSIGNED EXECUTOR {}: {}'.format(
        saved['id'],
        saved['label'],
    )
    refresh()
    return saved


def choose_executor_color(button_id):
    detail = _executor_detail(button_id)
    choice = ui.messageBox(
        'Executor Color',
        'Choose the button color:',
        buttons=['Cancel'] + list(EXECUTOR_COLORS),
    )
    if choice <= 0:
        return ''
    color = EXECUTOR_COLORS[choice - 1]
    _set_detail_field(detail, 'fieldColor', color)
    _show().par.Lastaction = 'EDITING {} / COLOR {}'.format(
        button_id,
        color.upper(),
    )
    return color


def _choose_clip():
    source = Path(project.folder) / 'config' / 'clips.json'
    try:
        raw = json.loads(source.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            'Unable to read playback clip configuration: {}'.format(exc)
        ) from exc
    clips = [
        item for item in raw.get('clips', ())
        if (
            isinstance(item, dict)
            and item.get('enabled', True)
            and isinstance(item.get('id'), str)
            and item['id']
        )
    ]
    if not clips:
        raise RuntimeError('No enabled clips exist in config/clips.json')
    choice = ui.messageBox(
        'Choose Playback Clip',
        'Choose the clip for this action:',
        buttons=['Cancel'] + [
            '{}  [{}]'.format(clip.get('label', clip['id']), clip['id'])
            for clip in clips
        ],
    )
    return None if choice <= 0 else clips[choice - 1]


def _default_action(action_type):
    if action_type in (
        'playback.take',
        'playback.cue',
        'playback.playAudio',
    ):
        clip = _choose_clip()
        if clip is None:
            return None
        return {'type': action_type, 'clipId': clip['id']}
    if action_type == 'wait':
        return {'type': 'wait', 'durationMs': 1000}
    if action_type == 'logic.resetEpisode':
        return {'type': action_type}
    if action_type == 'logic.emitEvent':
        return {
            'type': action_type,
            'eventType': 'CUSTOM_EVENT',
            'payload': {},
        }
    if action_type == 'connection.sendState':
        return {
            'type': action_type,
            'connectionId': 'logicStateOutput',
        }
    if action_type == 'connection.send':
        return {
            'type': action_type,
            'connectionId': 'logicStateOutput',
            'payload': {},
        }
    return {'type': action_type}


def add_executor_action(button_id):
    detail = _executor_detail(button_id)
    choice = ui.messageBox(
        'Add Executor Action',
        'Choose an action to add to the bottom of the ordered stack:',
        buttons=['Cancel'] + [label for label, _ in ACTION_CHOICES],
    )
    if choice <= 0:
        return None
    label, action_type = ACTION_CHOICES[choice - 1]
    action = _default_action(action_type)
    if action is None:
        return None
    try:
        actions = json.loads(_detail_field(detail, 'fieldActions'))
    except json.JSONDecodeError as exc:
        raise ValueError(
            'Fix the current action JSON before adding: {}'.format(exc)
        ) from exc
    if not isinstance(actions, list):
        raise ValueError('Actions must be a JSON array')
    if (
        len(actions) == 1
        and actions[0].get('type') == 'logic.emitEvent'
        and actions[0].get('eventType') == 'EXECUTOR_UNASSIGNED'
    ):
        actions = []
    actions.append(action)
    _set_detail_field(
        detail,
        'fieldActions',
        json.dumps(actions, indent=2),
    )
    _show().par.Lastaction = 'EDITING {} / ADDED {}'.format(
        button_id,
        label,
    )
    return action


def reset_executor(button_id):
    config = _executor_config()
    button = config.button(button_id)
    choice = ui.messageBox(
        'Reset Executor Slot',
        (
            'Reset executor {} ({}) to UNASSIGNED?\n\n'
            'The fixed slot ID will be preserved.'
        ).format(button_id, button['label']),
        buttons=['Cancel', 'Reset Slot'],
    )
    if choice != 1:
        return False
    editor = _load_executor_editor_module().ExecutorEditor(
        _executor_source(),
        _load_executor_module(),
    )
    reset = editor.reset(button_id)
    _show().par.Lastaction = 'RESET EXECUTOR {}'.format(button_id)
    refresh()
    return reset


def open_executor_config():
    filename = _show().par.Executorsfile.eval().strip()
    if not filename:
        raise RuntimeError('Choose an executor JSON file')
    path = Path(filename)
    if not path.is_absolute():
        path = Path(project.folder) / path
    ui.viewFile(str(path))
    return str(path)


def browse_connections():
    selected = ui.chooseFile(
        start=str(Path(project.folder) / 'config'),
        fileTypes=['json'],
        title='Select Connections JSON',
    )
    if selected:
        _show().par.Connectionsfile = str(selected)
    return selected


def reload_connections():
    run(
        "exec(open(project.folder + "
        "'/scripts/create_connections.py').read()); "
        "exec(open(project.folder + "
        "'/scripts/create_show_controller_ui.py').read())",
        delayFrames=1,
    )
