"""Build the pixel.formation playbackCore operator interface."""

from pathlib import Path


ROOT_PATH = '/project1/playoutCore'
WIDTH, HEIGHT = 1600, 900

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
    'yellow': (0.97, 0.85, 0.15),
    'red': (0.94, 0.36, 0.40),
    'black': (0.0, 0.0, 0.0),
}


def _set(operator, name, value):
    parameter = getattr(operator.par, name, None)
    if parameter is None:
        return
    try:
        parameter.val = value
    except Exception:
        debug('Skipped UI parameter {}.{}={!r}'.format(
            operator.path, name, value
        ))


def _set_expression(operator, name, expression):
    parameter = getattr(operator.par, name, None)
    if parameter is not None:
        parameter.expr = expression


def _place(operator, x, y, width, height, color=None):
    for name, value in (
        ('x', x), ('y', y), ('w', width), ('h', height),
        ('width', width), ('height', height),
    ):
        _set(operator, name, value)
    if color:
        for suffix, value in zip('rgb', color):
            _set(operator, 'bgcolor' + suffix, value)
        _set(operator, 'bgalpha', 1.0)


def _text(parent_op, name, text, x, y, width, height, size, color, justify='centerleft'):
    item = parent_op.create(textCOMP, name)
    _place(item, x, y, width, height)
    _set(item, 'text', text)
    _set(item, 'fontsize', size)
    _set(item, 'scaletofit', 'onlyshrink')
    _set(item, 'textpaddingl', 4)
    _set(item, 'textpaddingr', 4)
    _set(item, 'justify', justify)
    for prefix in ('fontcolor', 'textcolor'):
        for suffix, value in zip('rgb', color):
            _set(item, prefix + suffix, value)
    return item


def _field(parent_op, name, value, x, y, width, height):
    # Field COMP is deprecated; Text COMP is the supported editable control.
    item = parent_op.create(textCOMP, name)
    item.name = name
    _place(item, x, y, width, height, C['canvas'])
    _set(item, 'text', str(value))
    _set(item, 'type', 'string')
    _set(item, 'editmode', 'editable')
    _set(item, 'fontsize', 14)
    _set(item, 'justify', 'centerleft')
    _set(item, 'textpaddingl', 8)
    _set(item, 'textpaddingr', 8)
    for suffix, component in zip('rgb', C['text']):
        _set(item, 'fontcolor' + suffix, component)
        _set(item, 'textcolor' + suffix, component)
    return item


def _button(parent_op, name, label, x, y, width, height, color, code):
    item = parent_op.create(buttonCOMP, name)
    item.name = name
    _place(item, x, y, width, height, color)
    for parameter in ('text', 'label', 'buttonofflabel'):
        _set(item, parameter, label)
    _set(item, 'buttontype', 'momentary')
    _set(item, 'fontsize', 15)
    for suffix, value in zip('rgb', C['border']):
        _set(item, 'bordera' + suffix, value)
    _set(item, 'borderaalpha', 1.0)
    for edge in ('leftborder', 'rightborder', 'topborder', 'bottomborder'):
        _set(item, edge, 1)
    button_text = item.op('text')
    if button_text is not None:
        _set(button_text, 'scaletofit', 'onlyshrink')
        _set(button_text, 'fontsize', 14)
        _set(button_text, 'textpaddingl', 10)
        _set(button_text, 'textpaddingr', 10)
        _set(button_text, 'textpaddingt', 6)
        _set(button_text, 'textpaddingb', 6)

    callback = item.op('panelexec1')
    if callback is None:
        callback = item.create(panelexecuteDAT, 'panelexec1')
    _set(callback, 'panels', '..')
    _set(callback, 'panelvalue', 'state')
    _set(callback, 'offtoon', True)
    _set(callback, 'valuechange', False)
    _set(callback, 'active', True)
    callback.text = (
        'def onOffToOn(panelValue):\n'
        '    {}\n'
        '    return\n'
    ).format(code)
    return item


def _media_tile(parent_op, name, label, x, y, width, height, color, code):
    """Create a reliably colorable tile with a transparent click target."""
    item = parent_op.create(containerCOMP, name)
    item.name = name
    _place(item, x, y, width, height, color)
    _set(item, 'clickthrough', False)
    _set(item, 'layer', 1)

    text = _text(
        item,
        'text',
        label,
        0,
        0,
        width,
        height,
        14,
        C['text'],
        'center',
    )
    _set(text, 'clickthrough', True)
    _set(text, 'layer', 1)

    hit = item.create(buttonCOMP, 'hit')
    _place(hit, 0, 0, width, height)
    _set(hit, 'buttontype', 'momentary')
    _set(hit, 'opacity', 0)
    _set(hit, 'bgalpha', 0)
    _set(hit, 'layer', 2)
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
        '    {}\n'
        '    return\n'
    ).format(code)
    return item


def _monitor(
    parent_op, name, title, top_path, x, y, tally_color,
    width=590, height=300, progress_expression=None
):
    frame = parent_op.create(containerCOMP, name)
    _place(frame, x, y, width, height, C['surface'])
    _text(
        frame, 'title', title, 12, height - 34, width - 24, 24,
        15, tally_color,
    )

    viewer = frame.create(containerCOMP, 'viewer')
    _place(viewer, 12, 22, width - 24, height - 64, C['black'])
    _set(viewer, 'top', top_path)
    _set(viewer, 'topfill', 'best')
    _set(viewer, 'topsmoothness', 'linear')
    for suffix, value in zip('rgb', tally_color):
        _set(viewer, 'bordera' + suffix, value)
    _set(viewer, 'borderaalpha', 1.0)
    for edge in ('leftborder', 'rightborder', 'topborder', 'bottomborder'):
        _set(viewer, edge, 1)
    track = frame.create(containerCOMP, 'progressTrack')
    _place(track, 12, 10, width - 24, 5, C['raised'])
    fill = frame.create(containerCOMP, 'progressFill')
    _place(fill, 12, 10, 0, 5, tally_color)
    _set(fill, 'layer', 1)
    if progress_expression:
        _set_expression(fill, 'w', progress_expression)
    return frame


def _monitor_proxy(parent_op, name, source_path, width, height):
    source = parent_op.create(selectTOP, name + 'Source')
    _set(source, 'top', source_path)
    proxy = parent_op.create(resolutionTOP, name + 'Proxy')
    _set(proxy, 'outputresolution', 'custom')
    _set(proxy, 'resolutionw', width)
    _set(proxy, 'resolutionh', height)
    source.outputConnectors[0].connect(proxy.inputConnectors[0])
    source.nodeX, source.nodeY = -400, -200
    proxy.nodeX, proxy.nodeY = -200, -200
    return proxy


def _slug(value):
    return ''.join(
        character if character.isalnum() else '_'
        for character in value
    ).strip('_') or 'clip'


def build():
    core = op(ROOT_PATH)
    if core is None:
        raise RuntimeError('Missing {}'.format(ROOT_PATH))
    library = core.ReloadLibrary()

    panel = core.op('ui')
    if panel is None:
        panel = core.create(containerCOMP, 'ui')
    elif not isinstance(panel, containerCOMP):
        raise TypeError(
            '{} must be a Container COMP'.format(panel.path)
        )
    else:
        # Preserve the root COMP so an open playbackCore UI window remains
        # attached while its generated contents are refreshed. Cache names,
        # not OP objects: destroying one TouchDesigner operator can invalidate
        # other cached Python OP wrappers.
        child_names = tuple(child.name for child in panel.children)
        for child_name in child_names:
            child = panel.op(child_name)
            if child is not None:
                child.destroy()
    _place(panel, 0, 0, WIDTH, HEIGHT, C['canvas'])
    panel.nodeX, panel.nodeY = 1450, 500

    actions = panel.create(fileinDAT, 'uiActions')
    _set(actions, 'file', 'scripts/playback_ui_actions.py')
    _set(actions, 'converttable', False)
    _set(actions, 'language', 'python')
    actions.par.refreshpulse.pulse()

    logo_image = panel.create(moviefileinTOP, 'brandLogoImage')
    _set(
        logo_image,
        'file',
        str(Path(project.folder) / 'ui' / 'assets' / 'pixel-formation-white.png'),
    )
    _set(logo_image, 'play', False)
    logo_image.nodeX, logo_image.nodeY = -600, -400
    logo = panel.create(containerCOMP, 'brandLogo')
    _place(logo, 20, 838, 78, 48, C['black'])
    _set(logo, 'top', logo_image.path)
    _set(logo, 'topfill', 'best')
    _text(panel, 'product', 'playbackCore', 108, 846, 260, 34, 22, C['cyan'])
    state = _text(
        panel, 'engineState', '', 1280, 850, 300, 32, 14, C['yellow'],
        'centerright',
    )
    _set_expression(
        state,
        'text',
        "'ENGINE  ' + str(op('../control/engineStatus')['engineState', 1])",
    )
    header_accent = panel.create(containerCOMP, 'headerAccent')
    _place(header_accent, 20, 830, 1560, 2, C['cyan'])

    preview_source = panel.create(selectTOP, 'uiPreviewSource')
    _set_expression(
        preview_source,
        'top',
        "\"../decks/deck{}/videoOut\".format("
        "str(op('../control/engineStatus')['standbyDeck', 1]))",
    )
    preview_source.nodeX, preview_source.nodeY = -600, -200
    preview_proxy = panel.create(resolutionTOP, 'previewProxy')
    _set(preview_proxy, 'outputresolution', 'custom')
    _set(preview_proxy, 'resolutionw', 640)
    _set(preview_proxy, 'resolutionh', 360)
    preview_source.outputConnectors[0].connect(
        preview_proxy.inputConnectors[0]
    )
    program_proxy = _monitor_proxy(
        panel, 'program', '../mixer/video/program', 640, 360
    )

    preview_progress = (
        "int(476 * float(op('{root}/decks/deck' + "
        "str(op('{root}/control/engineStatus')['standbyDeck', 1]) + "
        "'/movieInfo')['index_fraction'][0]))"
    ).format(root=ROOT_PATH)
    program_progress = (
        "int(476 * float(op('{root}/decks/deck' + "
        "str(op('{root}/control/engineStatus')['activeDeck', 1]) + "
        "'/movieInfo')['index_fraction'][0])) "
        "if str(op('{root}/control/engineStatus')['activeDeck', 1]) else 0"
    ).format(root=ROOT_PATH)

    # Broadcast-style Preview / Program row using lightweight UI proxies.
    _monitor(
        panel, 'previewMonitor', 'PREVIEW / STANDBY',
        preview_proxy.path, 20, 585, C['green'], width=500, height=245,
        progress_expression=preview_progress,
    )
    _monitor(
        panel, 'programMonitor', 'PROGRAM / ON AIR',
        program_proxy.path, 540, 585, C['red'], width=500, height=245,
        progress_expression=program_progress,
    )

    aux = panel.create(containerCOMP, 'auxMultiview')
    _place(aux, 1060, 585, 520, 245, C['surface'])
    _text(aux, 'title', 'OUTPUT MULTIVIEW', 12, 211, 496, 24, 13, C['muted'])
    screen_config = core.fetch('screenConfig', None)
    screen_ids = tuple(screen_config.screens) if screen_config else ()
    for index, screen_id in enumerate(screen_ids[:4]):
        column, row = index % 2, index // 2
        screen_proxy = _monitor_proxy(
            panel,
            'screen' + str(index),
            '../screen_' + screen_id,
            320,
            180,
        )
        _monitor(
            aux,
            'screen_' + _slug(screen_id),
            screen_id.upper(),
            screen_proxy.path,
            12 + column * 250,
            109 - row * 99,
            C['cyan'],
            width=238,
            height=90,
        )

    transport = panel.create(containerCOMP, 'transport')
    _place(transport, 20, 510, 1560, 58, C['surface'])
    transport_accent = transport.create(containerCOMP, 'accent')
    _place(transport_accent, 0, 55, 1560, 3, C['yellow'])
    selected_expression = "op('{}').fetch('uiSelectedClip', '')".format(ROOT_PATH)
    _button(
        transport, 'cue', 'CUE TO PREVIEW', 12, 8, 190, 42, C['blue'],
        "clip_id={}; clip_id and op('{}').Cue(clip_id)".format(
            selected_expression, ROOT_PATH
        ),
    )
    _button(
        transport, 'take', 'TAKE / AUTO', 216, 8, 190, 42, C['green'],
        "clip_id={}; clip_id and op('{}').Take(clip_id)".format(
            selected_expression, ROOT_PATH
        ),
    )
    _button(
        transport, 'cut', 'CUT', 420, 8, 110, 42, C['yellow'],
        "clip_id={}; clip_id and op('{}').Take("
        "clip_id, transition='cut')".format(
            selected_expression, ROOT_PATH
        ),
    )
    _button(
        transport, 'pause', 'PAUSE', 1192, 8, 100, 42, C['raised'],
        "op('{}').Pause()".format(ROOT_PATH),
    )
    _button(
        transport, 'play', 'PLAY', 1304, 8, 100, 42, C['raised'],
        "op('{}').Play()".format(ROOT_PATH),
    )
    _button(
        transport, 'stop', 'STOP', 1416, 8, 130, 42, C['red'],
        "op('{}').Stop()".format(ROOT_PATH),
    )

    # Clip bin, inspired by Resolume/vMix input rows.
    clips = panel.create(containerCOMP, 'clips')
    _place(clips, 20, 20, 800, 472, C['surface'])
    clips_accent = clips.create(containerCOMP, 'accent')
    _place(clips_accent, 0, 469, 800, 3, C['cyan'])
    _text(clips, 'title', 'MEDIA BIN', 14, 432, 200, 26, 14, C['muted'])
    selected = core.fetch('uiSelectedClip', '')
    if selected not in library.clips:
        selected = next(iter(library.clips), '')
        core.store('uiSelectedClip', selected)
    engine_status = core.op('control/engineStatus')
    on_air_clip = (
        str(engine_status['onAirClip', 1]) if engine_status is not None else ''
    )
    standby_clip = (
        str(engine_status['standbyClip', 1]) if engine_status is not None else ''
    )
    for index, clip in enumerate(library.clips.values()):
        column = index % 5
        row = index // 5
        x = 14 + column * 154
        y = 266 - row * 154
        if y < 70:
            break
        color = (
            C['red'] if clip.id == on_air_clip
            else C['green'] if clip.id == standby_clip
            else C['raised']
        )
        callback = (
            "op('{root}/ui/uiActions').module.select_clip({clip!r})"
        ).format(root=ROOT_PATH, clip=clip.id)
        tally_border = (
            (1.0, 1.0, 1.0) if clip.id == selected
            else C['border']
        )
        tally = clips.create(containerCOMP, 'tally_' + _slug(clip.id))
        _place(tally, x, y, 142, 142, tally_border)
        _set(tally, 'layer', 0)
        _media_tile(
            clips, 'clip_' + _slug(clip.id),
            clip.label,
            x + 3, y + 3, 136, 136, color, callback,
        )
        clip_button = clips.op('clip_' + _slug(clip.id))
        _set(clip_button, 'layer', 1)

    add_code = (
        "op('{root}/ui/uiActions').module.add_video()"
    ).format(root=ROOT_PATH)
    _button(clips, 'addVideo', '+ ADD VIDEO', 14, 14, 160, 42, C['cyan'], add_code)
    _button(
        clips, 'refresh', 'REFRESH', 186, 14, 120, 42, C['raised'],
        "op('{}').op('ui/uiActions').module.reload_library()".format(
            ROOT_PATH
        ),
    )
    _button(
        clips,
        'removeSelected',
        'REMOVE SELECTED',
        318,
        14,
        170,
        42,
        C['red'],
        "op('{}/ui/uiActions').module.remove_clip()".format(ROOT_PATH),
    )

    inspector = panel.create(containerCOMP, 'inspector')
    _place(inspector, 840, 20, 400, 472, C['surface'])
    inspector_accent = inspector.create(containerCOMP, 'accent')
    _place(inspector_accent, 0, 469, 400, 3, C['green'])
    _text(
        inspector, 'title', 'PLAYBACK CLIP PROPERTIES',
        14, 432, 372, 26, 13, C['muted'],
    )
    selected_clip = library.clips.get(selected)
    _field(
        inspector,
        'field_label',
        selected_clip.label if selected_clip else '',
        14,
        390,
        280,
        30,
    )
    _button(
        inspector,
        'saveLabel',
        'SAVE NAME',
        302,
        390,
        84,
        30,
        C['blue'],
        "op('{}/ui/uiActions').module.save_label()".format(ROOT_PATH),
    )
    _text(
        inspector,
        'currentClipId',
        (
            'CURRENT ID  ' + selected_clip.id
            if selected_clip else 'CURRENT ID  -'
        ),
        14,
        370,
        276,
        18,
        10,
        C['cyan'],
    )
    _button(
        inspector,
        'copyClipId',
        'COPY ID',
        302,
        366,
        84,
        24,
        C['raised'],
        "op('{}/ui/uiActions').module.copy_clip_id()".format(ROOT_PATH),
    )
    property_values = {
        'id': selected_clip.id if selected_clip else '',
        'type': selected_clip.media_type.upper() if selected_clip else '',
        'file': (
            selected_clip.video_file or selected_clip.audio_file
            if selected_clip else ''
        ),
        'playback': (
            'Loop {}  |  Speed {}'.format(
                'ON' if selected_clip.loop else 'OFF', selected_clip.speed
            ) if selected_clip else ''
        ),
        'trim': (
            'In {}s  |  Out {}'.format(
                selected_clip.in_seconds,
                selected_clip.out_seconds
                if selected_clip.out_seconds is not None else 'END',
            ) if selected_clip else ''
        ),
        'audio': (
            'Volume {}  |  Bus {}'.format(
                selected_clip.volume, selected_clip.audio_bus
            ) if selected_clip else ''
        ),
        'transition': (
            '{}  |  {}s'.format(
                selected_clip.transition_type.upper(),
                selected_clip.transition_seconds,
            ) if selected_clip else ''
        ),
        'decoder': (
            'Pre-read {}  |  Hardware {}'.format(
                selected_clip.pre_read_frames,
                'ON' if selected_clip.hardware_decode else 'OFF',
            ) if selected_clip else ''
        ),
        'status': (
            'READY' if selected_clip and selected_clip.file_exists
            else 'MISSING' if selected_clip else ''
        ),
    }
    property_labels = {
        'id': 'SYSTEM ID', 'type': 'MEDIA TYPE', 'file': 'SOURCE',
        'playback': 'PLAYBACK', 'trim': 'IN / OUT', 'audio': 'AUDIO',
        'transition': 'TRANSITION', 'decoder': 'DECODER',
        'status': 'FILE STATUS',
    }
    for index, key in enumerate(property_labels):
        y = 348 - index * 36
        _text(
            inspector, 'label_' + key, property_labels[key],
            14, y, 104, 24, 11, C['muted'],
        )
        _text(
            inspector, 'value_' + key, property_values[key],
            124, y, 262, 24, 12,
            C['red'] if key == 'status' and property_values[key] == 'MISSING'
            else C['text'],
        )
    _text(
        inspector,
        'renameStatus',
        core.fetch('uiLibraryMessage', ''),
        14,
        18,
        372,
        24,
        9,
        C['cyan'],
    )

    diagnostics = panel.create(containerCOMP, 'diagnostics')
    _place(diagnostics, 1260, 252, 320, 240, C['surface'])
    diagnostics_accent = diagnostics.create(containerCOMP, 'accent')
    _place(diagnostics_accent, 0, 237, 320, 3, C['yellow'])
    _text(
        diagnostics, 'title', 'ENGINE / OUTPUT STATUS',
        14, 202, 292, 26, 12, C['muted'],
    )
    status_table = core.op('control/engineStatus')
    status_keys = (
        'engineState', 'deckAState', 'deckBState', 'activeDeck',
        'standbyDeck', 'onAirClip', 'standbyClip', 'pendingCommand', 'error',
    )
    for index, key in enumerate(status_keys):
        y = 168 - index * 19
        value = (
            str(status_table[key, 1]) or '-'
            if status_table is not None and status_table.row(key) else '-'
        )
        _text(
            diagnostics, 'label_' + key, key.upper(),
            14, y, 130, 18, 9, C['muted'],
        )
        _text(
            diagnostics, 'value_' + key, value,
            148, y, 158, 18, 10,
            C['red'] if key == 'error' and value != '-' else C['text'],
        )

    audio_panel = panel.create(containerCOMP, 'audioOnly')
    _place(audio_panel, 1260, 20, 320, 214, C['surface'])
    audio_accent = audio_panel.create(containerCOMP, 'accent')
    _place(audio_accent, 0, 211, 320, 3, C['blue'])
    _text(
        audio_panel, 'title', 'AUDIO-ONLY / SFX',
        14, 178, 220, 24, 12, C['muted'],
    )
    audio_clips = [
        clip for clip in library.clips.values()
        if clip.media_type == 'audio'
    ]
    if audio_clips:
        for index, clip in enumerate(audio_clips[:3]):
            _button(
                audio_panel,
                'sfx_' + _slug(clip.id),
                'PLAY  ' + clip.label,
                14, 132 - index * 40, 220, 34, C['raised'],
                "op('{}').PlayAudio({!r})".format(ROOT_PATH, clip.id),
            )
    else:
        _text(
            audio_panel, 'empty', 'No audio-only clips in the library.',
            14, 132, 200, 34, 11, C['muted'],
        )
    _button(
        audio_panel, 'stopAll', 'STOP ALL', 224, 132, 82, 34, C['red'],
        "op('{}').StopAllAudio()".format(ROOT_PATH),
    )
    _text(
        audio_panel, 'voicesTitle', 'VOICE POOL',
        14, 96, 120, 20, 10, C['muted'],
    )
    for voice_index in range(1, 5):
        voice_status = core.op(
            'audioOnly/voice{}Status'.format(voice_index)
        )
        voice_state = (
            str(voice_status['state', 1])
            if voice_status is not None and voice_status.row('state')
            else 'IDLE'
        )
        voice_clip = (
            str(voice_status['clipId', 1])
            if voice_status is not None and voice_status.row('clipId')
            else ''
        )
        _text(
            audio_panel, 'voice{}'.format(voice_index),
            'VOICE {}    {:<10}    {}'.format(
                voice_index, voice_state, voice_clip
            ),
            14, 72 - (voice_index - 1) * 20, 292, 18, 10, C['text'],
        )

    panel.viewer = True
    print('Created playbackCore operator UI with {} clips'.format(
        len(library.clips)
    ))
    return panel


PLAYBACK_UI = build()
