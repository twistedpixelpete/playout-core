"""In-place actions for the playbackCore UI. Never destroys the UI panel."""


ROOT_PATH = '/project1/playoutCore'


def _schedule_ui_rebuild():
    # playbackCore must never destroy or reconstruct Show Controller UI.
    run(
        "exec(open(project.folder + "
        "'/scripts/create_playback_ui.py').read())",
        delayFrames=1,
    )


def _set_text(path, value):
    target = op(path)
    if target is not None:
        parameter = getattr(target.par, 'text', None)
        if parameter is None:
            raise RuntimeError(
                '{} has no Text parameter'.format(target.path)
            )
        parameter.val = value


def _set_button_border(button, color):
    if button is None:
        return
    for suffix, value in zip('rgb', color):
        parameter = getattr(button.par, 'bordera' + suffix, None)
        if parameter is not None:
            parameter.val = value
    border_alpha = getattr(button.par, 'borderaalpha', None)
    if border_alpha is not None:
        border_alpha.val = 1.0
    for name in ('leftborder', 'rightborder', 'topborder', 'bottomborder'):
        parameter = getattr(button.par, name, None)
        if parameter is not None:
            parameter.val = 1


def _set_panel_color(panel, color):
    if panel is None:
        return
    for suffix, value in zip('rgb', color):
        parameter = getattr(panel.par, 'bgcolor' + suffix, None)
        if parameter is not None:
            parameter.val = value


def _set_button_label(button, value):
    if button is None:
        return
    for name in ('text', 'label', 'buttonofflabel'):
        parameter = getattr(button.par, name, None)
        if parameter is not None:
            parameter.val = value
    text_child = button.op('text')
    if text_child is not None:
        parameter = getattr(text_child.par, 'text', None)
        if parameter is not None:
            parameter.val = value


def select_clip(clip_id):
    core = op(ROOT_PATH)
    library = core.Library
    if library is None or clip_id not in library.clips:
        raise KeyError('Unknown clip id: {}'.format(clip_id))

    core.store('uiSelectedClip', clip_id)
    clip = library.clips[clip_id]
    _set_text(ROOT_PATH + '/ui/inspector/field_label', clip.label)
    _set_text(
        ROOT_PATH + '/ui/inspector/currentClipId',
        'CURRENT ID  {}'.format(clip.id),
    )
    values = {
        'id': clip.id,
        'type': clip.media_type.upper(),
        'file': clip.video_file or clip.audio_file,
        'playback': 'Loop {}  |  Speed {}'.format(
            'ON' if clip.loop else 'OFF', clip.speed
        ),
        'trim': 'In {}s  |  Out {}'.format(
            clip.in_seconds,
            clip.out_seconds if clip.out_seconds is not None else 'END',
        ),
        'audio': 'Volume {}  |  Bus {}'.format(clip.volume, clip.audio_bus),
        'transition': '{}  |  {}s'.format(
            clip.transition_type.upper(), clip.transition_seconds
        ),
        'decoder': 'Pre-read {}  |  Hardware {}'.format(
            clip.pre_read_frames,
            'ON' if clip.hardware_decode else 'OFF',
        ),
        'status': 'READY' if clip.file_exists else 'MISSING',
    }
    for key, value in values.items():
        _set_text(
            ROOT_PATH + '/ui/inspector/value_' + key,
            value,
        )
    update_tallies()
    return clip_id


def _field(name):
    field = op(ROOT_PATH + '/ui/inspector/field_' + name)
    if field is None:
        raise RuntimeError('Missing property field: {}'.format(name))
    return str(field.par.text.eval()).strip()


def _boolean(value, name):
    lowered = value.lower()
    if lowered in ('true', '1', 'yes', 'on'):
        return True
    if lowered in ('false', '0', 'no', 'off'):
        return False
    raise ValueError('{} must be true or false'.format(name))


def save_properties():
    core = op(ROOT_PATH)
    clip_id = core.fetch('uiSelectedClip', '')
    if not clip_id:
        raise RuntimeError('Select a clip before saving')
    raw_out = _field('out_seconds')
    try:
        clip = core.UpdateClip(
            clip_id,
            label=_field('label'),
            loop=_boolean(_field('loop'), 'Loop'),
            speed=float(_field('speed')),
            in_seconds=float(_field('in_seconds')),
            out_seconds=float(raw_out) if raw_out else None,
            volume=float(_field('volume')),
            audio_bus=_field('audio_bus'),
            transition_type=_field('transition_type').lower(),
            transition_seconds=float(_field('transition_seconds')),
            pre_read_frames=int(_field('pre_read_frames')),
            hardware_decode=_boolean(
                _field('hardware_decode'), 'Hardware Decode'
            ),
        )
        _set_text(ROOT_PATH + '/ui/inspector/saveStatus', 'SAVED')
        select_clip(clip_id)
        return clip
    except Exception as exc:
        _set_text(
            ROOT_PATH + '/ui/inspector/saveStatus',
            'ERROR: {}'.format(exc),
        )
        raise


def save_label():
    core = op(ROOT_PATH)
    clip_id = core.fetch('uiSelectedClip', '')
    if not clip_id:
        raise RuntimeError('Select a clip before saving its name')
    try:
        clip = core.UpdateClip(clip_id, label=_field('label'))
        core.store(
            'uiLibraryMessage',
            'SAVED NAME / SYSTEM ID {}'.format(clip.id),
        )
        _set_button_label(
            core.op('ui/clips/clip_' + _slug(clip.id)),
            clip.label,
        )
        select_clip(clip.id)
        _set_text(
            ROOT_PATH + '/ui/inspector/renameStatus',
            core.fetch('uiLibraryMessage', ''),
        )
        return clip
    except Exception as exc:
        _set_text(
            ROOT_PATH + '/ui/inspector/renameStatus',
            'ERROR: {}'.format(exc),
        )
        raise


def copy_clip_id():
    core = op(ROOT_PATH)
    clip_id = core.fetch('uiSelectedClip', '')
    library = core.Library
    if not clip_id or library is None or clip_id not in library.clips:
        raise RuntimeError('Select a clip before copying its system ID')
    ui.clipboard = clip_id
    message = 'COPIED SYSTEM ID {}'.format(clip_id)
    core.store('uiLibraryMessage', message)
    _set_text(ROOT_PATH + '/ui/inspector/renameStatus', message)
    return clip_id


def reload_library():
    core = op(ROOT_PATH)
    library = core.ReloadLibrary()
    selected = core.fetch('uiSelectedClip', '')
    if selected in library.clips:
        select_clip(selected)
    _schedule_ui_rebuild()
    return library


def add_video():
    from pathlib import Path

    path = ui.chooseFile(
        start=str(Path(project.folder) / 'media' / 'video'),
        fileTypes=['mp4', 'mov', 'm4v', 'avi', 'wmv'],
        title='Add Video Clip',
    )
    if not path:
        return ''
    core = op(ROOT_PATH)
    try:
        clip = core.AddClipAuto(
            video_file=path,
            label=Path(path).stem,
        )
        core.store('uiSelectedClip', clip.id)
        core.store(
            'uiLibraryMessage',
            'ADDED {} / SYSTEM ID {}'.format(clip.label, clip.id),
        )
        _schedule_ui_rebuild()
        return clip.id
    except Exception as exc:
        _set_text(
            ROOT_PATH + '/ui/inspector/renameStatus',
            'ERROR: {}'.format(exc),
        )
        raise


def remove_clip():
    import json
    from pathlib import Path

    core = op(ROOT_PATH)
    clip_id = core.fetch('uiSelectedClip', '')
    library = core.Library
    if not clip_id or library is None or clip_id not in library.clips:
        raise RuntimeError('Select a clip before removing it')

    clip = library.clips[clip_id]
    referenced_by = []
    reference_check_error = ''
    executor_file = Path(project.folder) / 'config' / 'executors.json'
    if executor_file.is_file():
        try:
            raw = json.loads(executor_file.read_text(encoding='utf-8'))
            for button in raw.get('buttons', []):
                if any(
                    action.get('clipId') == clip_id
                    for action in button.get('actions', [])
                ):
                    referenced_by.append(button.get('id', '?'))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            reference_check_error = str(exc)

    message = (
        'Remove "{}" from playbackCore?\n\n'
        'System ID: {}\n'
        'The media file will remain on disk.'
    ).format(clip.label, clip.id)
    if referenced_by:
        message += (
            '\n\nWarning: executor slot(s) {} reference this clip '
            'and will become invalid.'
        ).format(', '.join(referenced_by))
    if reference_check_error:
        message += (
            '\n\nWarning: executor references could not be checked: {}'
        ).format(reference_check_error)

    choice = ui.messageBox(
        'Remove Clip',
        message,
        buttons=['Cancel', 'Remove'],
    )
    if choice != 1:
        return False

    try:
        core.RemoveClip(clip_id)
        core.store('uiSelectedClip', '')
        core.store(
            'uiLibraryMessage',
            'REMOVED {} / MEDIA FILE KEPT'.format(clip.id),
        )
        _schedule_ui_rebuild()
        return True
    except Exception as exc:
        _set_text(
            ROOT_PATH + '/ui/inspector/renameStatus',
            'ERROR: {}'.format(exc),
        )
        raise


def update_tallies():
    core = op(ROOT_PATH)
    library = core.Library
    status = core.op('control/engineStatus')
    if library is None or status is None:
        return
    on_air = str(status['onAirClip', 1])
    standby = str(status['standbyClip', 1])
    engine_state = str(status['engineState', 1])
    on_air_clip = library.clips.get(on_air)
    standby_clip = library.clips.get(standby)
    on_air_name = on_air_clip.label if on_air_clip is not None else ''
    standby_name = standby_clip.label if standby_clip is not None else ''
    selected = core.fetch('uiSelectedClip', '')
    signature = (
        on_air,
        standby,
        engine_state,
        on_air_name,
        standby_name,
        selected,
    )
    ui_panel = core.op('ui')
    if ui_panel is None or ui_panel.fetch('tallySignature', None) == signature:
        return
    ui_panel.store('tallySignature', signature)

    border = (0.16, 0.21, 0.25)
    idle = (0.070, 0.096, 0.118)
    preview = (0.22, 0.79, 0.57)
    program = (0.94, 0.36, 0.40)
    for clip in library.clips.values():
        tally = core.op('ui/clips/tally_' + _slug(clip.id))
        button = core.op('ui/clips/clip_' + _slug(clip.id))
        border_color = (
            (1.0, 1.0, 1.0) if clip.id == selected
            else border
        )
        button_color = (
            program if clip.id == on_air
            else preview if clip.id == standby
            else idle
        )
        _set_panel_color(tally, border_color)
        _set_panel_color(button, button_color)

    _set_text(
        ROOT_PATH + '/ui/previewMonitor/title',
        'PREVIEW / STANDBY' + (
            '   ' + standby_name if standby_name else ''
        ),
    )
    _set_text(
        ROOT_PATH + '/ui/programMonitor/title',
        'PROGRAM / ON AIR' + (
            '   ' + on_air_name if on_air_name else ''
        ),
    )


def _slug(value):
    return ''.join(
        character if character.isalnum() else '_'
        for character in value
    ).strip('_') or 'clip'
