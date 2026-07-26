"""TouchDesigner Extension for the /playoutCore public command API."""

import importlib.util
from pathlib import Path
import sys


def _load_external_module(filename, module_name):
    module_path = Path(project.folder) / 'scripts' / filename
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        raise RuntimeError('Unable to load {}'.format(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class PlayoutCoreExt:
    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self._engine_module = _load_external_module(
            'engine_model.py',
            'playout_core_engine_model',
        )
        self._readiness_module = _load_external_module(
            'take_readiness.py',
            'playout_core_take_readiness',
        )
        self._effects_module = _load_external_module(
            'effects_model.py',
            'playout_core_effects_model',
        )
        self._layer_module = _load_external_module(
            'layer_model.py',
            'playout_core_layer_model',
        )
        self._clip_module = _load_external_module(
            'clip_library.py',
            'playout_core_clip_library',
        )
        self._editor_module = _load_external_module(
            'library_editor.py',
            'playout_core_library_editor',
        )
        self._id_module = _load_external_module(
            'system_ids.py',
            'playout_core_system_ids',
        )
        self._library_cache = None
        self._model = self._engine_module.EngineModel()
        self._transition_started = None
        self._transition_duration = 0.0
        self._transition_from = 0.0
        self._transition_to = 0.0
        self._transition_override = None
        self._load_started = None
        self._load_generation = 0
        self._loading_clip = None
        self._loading_deck = None
        self._load_timeout_seconds = max(
            1.0,
            float(self.ownerComp.fetch('movieLoadTimeoutSeconds', 15.0)),
        )
        self._minimum_start_frames = max(
            1,
            int(self.ownerComp.fetch('minimumMovieStartFrames', 1)),
        )
        self._expected_play_deck = None
        self._play_reassertions = {'A': 0, 'B': 0}
        self._effects = self._effects_module.EffectsModel(
            self.ownerComp.fetch('audioVoiceCount', 4)
        )
        screen_config = self.ownerComp.fetch('screenConfig', None)
        self._screen_layers = {
            screen_id: self._layer_module.LayerTransform()
            for screen_id in (
                screen_config.screens if screen_config is not None else ()
            )
        }
        self._install_library(
            self._clip_module.load_clip_library(
                Path(project.folder) / 'config' / 'clips.json'
            )
        )
        self._publish()

    def _library(self):
        return self._library_cache

    @property
    def Library(self):
        """Current runtime library; deliberately excluded from OP storage."""
        return self._library_cache

    def _library_editor(self):
        source = Path(project.folder) / 'config' / 'clips.json'
        return self._editor_module.LibraryEditor(source, self._clip_module)

    def _id_allocator(self):
        source = Path(project.folder) / 'config' / 'id_registry.json'
        return self._id_module.SystemIdAllocator(source)

    def _install_library(self, library):
        # Dynamically loaded classes are not safe to pickle into a .toe.
        # Remove legacy storage and keep the parsed library on the Extension.
        self.ownerComp.unstore('clipLibrary')
        self.ownerComp.unstoreStartupValue('clipLibrary')
        self._library_cache = library
        table = self.ownerComp.op('config/clipLibrary')
        if table is not None:
            table.clear()
            table.appendRows(self._clip_module.clip_table_rows(library))
        status = self.ownerComp.op('config/libraryStatus')
        if status is not None:
            missing = sum(not clip.file_exists for clip in library.clips.values())
            status.clear()
            status.appendRows([
                ['key', 'value'],
                ['state', 'READY'],
                ['sourceFile', library.source_file],
                ['videoRoot', library.video_root],
                ['audioRoot', library.audio_root],
                ['audioBuses', ' '.join(library.audio_buses)],
                ['clipCount', len(library.clips)],
                ['missingFileCount', missing],
                ['error', ''],
            ])
        return library

    def ReloadLibrary(self):
        editor = self._library_editor()
        return self._install_library(
            self._clip_module.load_clip_library(editor.source)
        )

    def SaveLibrary(self):
        return self._install_library(self._library_editor().save())

    def AddClip(
        self,
        clip_id,
        video_file=None,
        audio_file=None,
        label=None,
        **settings
    ):
        library = self._library_editor().add(
            clip_id,
            video_file=video_file,
            audio_file=audio_file,
            label=label,
            **settings
        )
        return self._install_library(library).clips[clip_id]

    def AddClipAuto(
        self,
        video_file=None,
        audio_file=None,
        label=None,
        **settings
    ):
        clip_id = self._id_allocator().reserve()
        return self.AddClip(
            clip_id,
            video_file=video_file,
            audio_file=audio_file,
            label=label,
            **settings
        )

    def UpdateClip(self, clip_id, **changes):
        library = self._library_editor().update(clip_id, **changes)
        return self._install_library(library).clips[clip_id]

    def RenameClip(self, clip_id, new_id):
        raise RuntimeError(
            'System IDs are immutable; use UpdateClip(label=...)'
        )

    def DuplicateClip(self, clip_id, new_id, label=None):
        library = self._library_editor().duplicate(clip_id, new_id, label)
        return self._install_library(library).clips[new_id]

    def RemoveClip(self, clip_id):
        pending = self._model.pending_request
        in_use = {
            value for value in (
                self._model.on_air_clip,
                self._model.standby_clip,
                self._model.requested_clip,
                pending.clip_id if pending is not None else None,
            )
            if value
        }
        if clip_id in in_use:
            raise RuntimeError('Cannot remove a clip currently in use')
        library = self._library_editor().remove(clip_id)
        self._install_library(library)
        return True

    def _validated_clip(self, clip_id):
        if not isinstance(clip_id, str) or not clip_id.strip():
            raise ValueError('clip_id must be a non-empty string')

        library = self._library()
        if library is None:
            raise RuntimeError('Clip library is not loaded')

        clip = library.clips.get(clip_id)
        if clip is None:
            raise KeyError('Unknown clip id: {}'.format(clip_id))
        if not clip.enabled:
            raise ValueError('Clip is disabled: {}'.format(clip_id))
        if not clip.file_exists:
            raise FileNotFoundError(
                'Media file does not exist: {}'.format(
                    ', '.join(clip.missing_files)
                )
            )
        return clip

    def _validated_audio_clip(self, clip_id):
        clip = self._validated_clip(clip_id)
        if not clip.audio_file:
            raise ValueError(
                'Clip has no standalone audioFile: {}'.format(clip_id)
            )
        return clip

    def _validated_video_clip(self, clip_id):
        clip = self._validated_clip(clip_id)
        if not clip.video_file:
            raise ValueError('Clip has no videoFile: {}'.format(clip_id))
        return clip

    def _run(self, command):
        try:
            result = command()
            self._publish()
            return result
        except Exception as exc:
            # Validation failures must not change the authoritative model.
            self._publish_command_error(str(exc))
            raise

    def _status_table(self):
        return self.ownerComp.op('control/engineStatus')

    def _queue_table(self):
        return self.ownerComp.op('control/commandQueue')

    def _publish(self):
        status = self._status_table()
        if status is not None:
            snapshot = self._model.snapshot()
            snapshot.update({
                'expectedPlayDeck': self._expected_play_deck or '',
                'deckAPlay': self._movie_play_value('A'),
                'deckBPlay': self._movie_play_value('B'),
                'deckAPlayRetries': self._play_reassertions['A'],
                'deckBPlayRetries': self._play_reassertions['B'],
            })
            status.clear()
            status.appendRows(
                [['key', 'value']]
                + [[key, value] for key, value in snapshot.items()]
            )

        queue = self._queue_table()
        if queue is not None:
            request = self._model.pending_request
            queue.clear()
            queue.appendRows([
                ['command', 'clipId', 'transition'],
                [
                    request.command if request else '',
                    request.clip_id if request and request.clip_id else '',
                    (
                        request.transition
                        if request and request.transition
                        else ''
                    ),
                ],
            ])

    def _publish_command_error(self, message):
        status = self._status_table()
        if status is None:
            return
        row = status.row('commandError')
        if row:
            status['commandError', 1] = message
        else:
            status.appendRow(['commandError', message])

    def Cue(self, clip_id):
        def execute():
            clip = self._validated_video_clip(clip_id)
            result = self._model.cue(clip_id)
            if result == 'ACCEPTED':
                self._transition_override = None
                self._load_deck_safely(self._model.standby_deck, clip)
            return result
        return self._run(execute)

    def Take(self, clip_id, transition=None):
        def execute():
            clip = self._validated_video_clip(clip_id)
            if transition not in (None, 'cut', 'crossfade'):
                raise ValueError('transition must be cut, crossfade, or None')
            result = self._model.take(clip_id, transition=transition)
            if result in ('ACCEPTED', 'ALREADY_PENDING'):
                self._transition_override = transition
            if result == 'ACCEPTED':
                self._load_deck_safely(self._model.standby_deck, clip)
            return result
        return self._run(execute)

    def Play(self):
        def execute():
            if self._model.engine_state.value == 'READY':
                return self._begin_transition()
            result = self._model.play()
            if result == 'ACCEPTED' and self._model.active_deck:
                self._set_deck_play(self._model.active_deck, True)
            return result
        return self._run(execute)

    def Pause(self):
        def execute():
            result = self._model.pause()
            if result == 'ACCEPTED' and self._model.active_deck:
                self._set_deck_play(self._model.active_deck, False)
            return result
        return self._run(execute)

    def Stop(self):
        def execute():
            for deck_id in ('A', 'B'):
                movie = self._deck_movie(deck_id)
                self._set_par(movie, 'play', False)
            self._transition_started = None
            self._transition_override = None
            self._expected_play_deck = None
            self._play_reassertions = {'A': 0, 'B': 0}
            self._clear_load_tracking()
            return self._model.stop()
        return self._run(execute)

    def Seek(self, seconds):
        def execute():
            result = self._model.seek(seconds)
            deck_id = self._model.active_deck or self._model.standby_deck
            movie = self._deck_movie(deck_id)
            self._set_par(movie, 'cuepointunit', 'seconds')
            self._set_par(movie, 'cuepoint', float(seconds))
            pulse = getattr(movie.par, 'cuepulse', None)
            if pulse is not None:
                pulse.pulse()
            return result
        return self._run(execute)

    def _set_par(self, operator, name, value):
        if operator is None:
            return
        parameter = getattr(operator.par, name, None)
        if parameter is not None:
            parameter.val = value

    def _deck_component(self, deck_id):
        deck = self.ownerComp.op('decks/deck{}'.format(deck_id))
        if deck is None:
            raise RuntimeError('Missing deck {}'.format(deck_id))
        return deck

    def _deck_movie(self, deck_id):
        movie = self._deck_component(deck_id).op('movie')
        if movie is None:
            raise RuntimeError('Missing deck {} Movie File In TOP'.format(deck_id))
        return movie

    def _movie_play_value(self, deck_id):
        try:
            movie = self._deck_movie(deck_id)
            parameter = getattr(movie.par, 'play', None)
            return int(bool(parameter.eval())) if parameter is not None else -1
        except Exception:
            return -1

    def _set_deck_play(self, deck_id, enabled):
        movie = self._deck_movie(deck_id)
        parameter = getattr(movie.par, 'play', None)
        if parameter is None:
            raise RuntimeError(
                'Deck {} Movie File In TOP has no Play parameter'.format(
                    deck_id
                )
            )
        parameter.val = bool(enabled)
        if enabled:
            self._expected_play_deck = deck_id
        elif self._expected_play_deck == deck_id:
            self._expected_play_deck = None

    def _enforce_play_latch(self):
        state = self._model.engine_state.value
        if state == 'TRANSITIONING':
            expected = self._model.standby_deck
        elif state == 'PLAYING':
            expected = self._model.active_deck
        else:
            return
        if expected is None:
            self._model.set_error(
                '{} state has no selected playback deck'.format(state)
            )
            self._publish()
            return

        self._expected_play_deck = expected
        if self._movie_play_value(expected) == 1:
            return

        self._play_reassertions[expected] += 1
        self._set_deck_play(expected, True)
        if (
            self._movie_play_value(expected) != 1
            and self._play_reassertions[expected] >= 3
        ):
            message = (
                'Deck {} Play parameter did not remain enabled after '
                '{} attempts'
            ).format(expected, self._play_reassertions[expected])
            self._model.set_error(message, expected)
            self._publish_deck_status(
                expected,
                'ERROR',
                self._model.on_air_clip or self._model.standby_clip,
                message,
            )
        self._publish()

    def _load_deck(self, deck_id, clip):
        deck = self._deck_component(deck_id)
        movie = self._deck_movie(deck_id)
        audio_source = deck.op('audioSource')
        audio_gain = deck.op('audioGain')

        self._load_generation += 1
        self._load_started = absTime.seconds
        self._loading_clip = clip.id
        self._loading_deck = deck_id
        self._set_par(movie, 'play', False)
        self._set_par(movie, 'playmode', 'sequential')
        self._set_par(movie, 'file', clip.resolved_video_file)
        self._set_par(movie, 'speed', clip.speed)
        self._set_par(movie, 'repeat', clip.loop)
        self._set_par(movie, 'cuepointunit', 'seconds')
        self._set_par(movie, 'cuepoint', clip.in_seconds)
        self._set_par(movie, 'prereadframes', clip.pre_read_frames)
        self._set_par(movie, 'alwaysloadinitial', True)
        # Parameter naming has varied between TouchDesigner builds.
        self._set_par(movie, 'hardwaredecode', clip.hardware_decode)
        self._set_par(movie, 'hwdecode', clip.hardware_decode)
        self._set_par(audio_source, 'index', 0)
        self._set_par(audio_gain, 'gain', clip.volume if clip.audio_enabled else 0.0)

        reload_pulse = getattr(movie.par, 'reloadpulse', None)
        if reload_pulse is not None:
            reload_pulse.pulse()
        cue_pulse = getattr(movie.par, 'cuepulse', None)
        if cue_pulse is not None:
            cue_pulse.pulse()
        self._publish_deck_status(deck_id, 'LOADING', clip.id)

    def _load_deck_safely(self, deck_id, clip):
        try:
            self._load_deck(deck_id, clip)
        except Exception as exc:
            self._fail_load(
                deck_id,
                clip.id,
                'Unable to prepare deck {}: {}'.format(deck_id, exc),
            )
            raise

    def _clear_load_tracking(self):
        self._load_started = None
        self._loading_clip = None
        self._loading_deck = None

    def _fail_load(self, deck_id, clip_id, message):
        message = str(message)
        self._model.set_error(message, deck_id)
        self._transition_override = None
        self._clear_load_tracking()
        try:
            self._publish_deck_status(deck_id, 'ERROR', clip_id, message)
        except Exception as exc:
            debug('playbackCore deck error publishing failed:', exc)
        self._publish()

    @staticmethod
    def _channel_value(chop, name, default=0.0):
        if chop is None:
            return default
        channel = chop[name]
        return float(channel[0]) if channel is not None else default

    def _publish_deck_status(self, deck_id, state, clip_id='', error=''):
        table = self._deck_component(deck_id).op('status')
        if table is None:
            return
        info = self._deck_component(deck_id).op('movieInfo')
        table.clear()
        table.appendRows([
            ['key', 'value'],
            ['state', state],
            ['clipId', clip_id],
            ['open', self._channel_value(info, 'open')],
            ['opening', self._channel_value(info, 'opening')],
            ['fullyPreRead', self._channel_value(info, 'fully_pre_read')],
            ['numPreReadFrames', self._channel_value(info, 'num_pre_read_frames')],
            ['trueLength', self._channel_value(info, 'true_length')],
            ['decodeErrors', self._channel_value(info, 'has_decode_errors')],
            ['preReadFails', self._channel_value(info, 'pre_read_fails')],
            ['play', self._movie_play_value(deck_id)],
            ['playRetries', self._play_reassertions[deck_id]],
            ['loadGeneration', self._load_generation],
            ['error', error],
        ])

    def _begin_transition(self):
        if self._model.engine_state.value != 'READY':
            return 'IGNORED'
        self._model.validate_decks()
        standby = self._model.standby_deck
        clip = self._validated_video_clip(self._model.standby_clip)
        cross = self.ownerComp.op('mixer/video/cross')
        if cross is None:
            raise RuntimeError('Video mixer has not been created')
        standby_movie = self._deck_movie(standby)
        if not self._model.begin_transition():
            return 'IGNORED'

        self._set_deck_play(standby, True)
        self._transition_from = float(cross.par.cross.eval())
        self._transition_to = 0.0 if standby == 'A' else 1.0
        transition_type = self._transition_override or clip.transition_type
        self._transition_override = None
        self._transition_duration = (
            0.0
            if self._model.active_deck is None or transition_type == 'cut'
            else clip.transition_seconds
        )
        self._transition_started = absTime.seconds
        if self._transition_duration <= 0:
            cross.par.cross = self._transition_to
            self._complete_transition()
        else:
            self._publish()
        return 'ACCEPTED'

    def _complete_transition(self):
        old_active = self._model.active_deck
        incoming = self._model.standby_deck
        self._transition_started = None
        request = self._model.finish_transition()
        if self._model.active_deck != incoming:
            raise RuntimeError(
                'Transition completed on the wrong deck: expected {}, got {}'
                .format(incoming, self._model.active_deck)
            )
        if old_active is not None and old_active != incoming:
            self._set_deck_play(old_active, False)
            self._publish_deck_status(old_active, 'STOPPED')
        if self._model.active_deck:
            self._publish_deck_status(
                self._model.active_deck,
                'PLAYING',
                self._model.on_air_clip,
            )
        self._publish()
        if request is not None:
            if request.command == 'Take':
                self.Take(
                    request.clip_id,
                    transition=request.transition,
                )
            else:
                self.Cue(request.clip_id)

    def OnFrameStart(self):
        """Poll decoder readiness and advance an in-progress transition."""
        if self._model.engine_state.value == 'LOADING':
            deck_id = self._model.standby_deck
            clip_id = self._model.standby_clip
            if (
                self._loading_deck != deck_id
                or self._loading_clip != clip_id
                or self._load_started is None
            ):
                self._fail_load(
                    deck_id,
                    clip_id,
                    'Internal load tracking did not match the pending Take',
                )
                return
            deck = self._deck_component(deck_id)
            info = deck.op('movieInfo')
            movie = deck.op('movie')
            try:
                clip = self._validated_video_clip(clip_id)
            except Exception as exc:
                self._fail_load(
                    deck_id,
                    clip_id,
                    'Pending clip became unavailable: {}'.format(exc),
                )
                return
            elapsed = max(0.0, absTime.seconds - self._load_started)
            decision = self._readiness_module.assess_decoder_readiness(
                opened=self._channel_value(info, 'open') >= 1,
                opening=self._channel_value(info, 'opening') >= 1,
                open_failed=self._channel_value(info, 'open_failed') >= 1,
                decode_errors=(
                    self._channel_value(info, 'has_decode_errors') >= 1
                ),
                fully_pre_read=(
                    self._channel_value(info, 'fully_pre_read') >= 1
                ),
                num_pre_read_frames=self._channel_value(
                    info,
                    'num_pre_read_frames',
                ),
                requested_pre_read_frames=clip.pre_read_frames,
                movie_length_frames=self._channel_value(
                    info,
                    'true_length',
                ),
                minimum_start_frames=self._minimum_start_frames,
                elapsed_seconds=elapsed,
                timeout_seconds=self._load_timeout_seconds,
            )
            if decision.state == 'ERROR':
                errors = movie.errors() if movie is not None else ''
                message = (
                    str(errors)
                    if errors
                    else decision.reason
                )
                self._fail_load(deck_id, clip_id, message)
            elif decision.state == 'READY':
                autoplay = self._model.autoplay_when_ready
                if self.OnDeckReady():
                    self._publish_deck_status(deck_id, 'CUED', clip.id)
                    self._clear_load_tracking()
                    if autoplay:
                        self._begin_transition()

        if (
            self._model.engine_state.value == 'TRANSITIONING'
            and self._transition_started is not None
        ):
            elapsed = max(0.0, absTime.seconds - self._transition_started)
            amount = min(1.0, elapsed / self._transition_duration)
            value = (
                self._transition_from
                + (self._transition_to - self._transition_from) * amount
            )
            self.ownerComp.op('mixer/video/cross').par.cross = value
            if amount >= 1.0:
                self._complete_transition()

        self._enforce_play_latch()

        ui_actions = self.ownerComp.op('ui/uiActions')
        if ui_actions is not None:
            try:
                ui_actions.module.update_tallies()
            except Exception as exc:
                debug('playbackCore UI tally update failed:', exc)

    def _set_voice_route(self, voice_index, selected_bus):
        buses = self.ownerComp.fetch(
            'audioBuses',
            ('program', 'effects', 'aux1', 'aux2'),
        )
        for bus in buses:
            route = self.ownerComp.op(
                'mixer/audio/{}Voice{}'.format(bus, voice_index)
            )
            if route is not None:
                self._set_par(
                    route,
                    'gain',
                    1.0 if bus == selected_bus else 0.0,
                )

    def _publish_voice(self, voice_index, error=''):
        voice = self._effects.voices[voice_index]
        status = self.ownerComp.op(
            'audioOnly/voice{}Status'.format(voice_index)
        )
        if status is None:
            return
        status.clear()
        status.appendRows([
            ['key', 'value'],
            ['state', voice.state],
            ['clipId', voice.clip_id],
            ['audioBus', voice.audio_bus],
            ['error', error],
        ])

    def _stop_voice_operator(self, voice_index):
        source = self.ownerComp.op(
            'audioOnly/voice{}File'.format(voice_index)
        )
        if source is not None:
            self._set_par(source, 'play', False)
        self._set_voice_route(voice_index, None)

    def PlayAudio(self, clip_id):
        def execute():
            clip = self._validated_audio_clip(clip_id)
            voice_index, _ = self._effects.play(clip.id, clip.audio_bus)
            self._stop_voice_operator(voice_index)

            source = self.ownerComp.op(
                'audioOnly/voice{}File'.format(voice_index)
            )
            gain = self.ownerComp.op(
                'audioOnly/voice{}Gain'.format(voice_index)
            )
            if source is None or gain is None:
                self._effects.stop_voice(voice_index)
                raise RuntimeError(
                    'Audio routing network has not been created'
                )

            self._set_par(source, 'file', clip.resolved_audio_file)
            self._set_par(source, 'playmode', 'sequential')
            self._set_par(source, 'speed', clip.speed)
            self._set_par(source, 'repeat', clip.loop)
            self._set_par(source, 'cuepointunit', 'seconds')
            self._set_par(source, 'cuepoint', clip.in_seconds)
            self._set_par(source, 'volume', 1.0)
            self._set_par(gain, 'gain', clip.volume)
            if getattr(source.par, 'reloadpulse', None) is not None:
                source.par.reloadpulse.pulse()
            if getattr(source.par, 'cuepulse', None) is not None:
                source.par.cuepulse.pulse()
            self._set_voice_route(voice_index, clip.audio_bus)
            self._set_par(source, 'play', True)
            self._publish_voice(voice_index)
            return voice_index
        return self._run(execute)

    def StopAudio(self, clip_id):
        def execute():
            stopped = self._effects.stop_clip(clip_id)
            for voice_index in stopped:
                self._stop_voice_operator(voice_index)
                self._publish_voice(voice_index)
            return stopped
        return self._run(execute)

    def StopAllAudio(self):
        def execute():
            stopped = self._effects.stop_all()
            for voice_index in stopped:
                self._stop_voice_operator(voice_index)
                self._publish_voice(voice_index)
            return stopped
        return self._run(execute)

    def _screen_component(self, screen_id):
        if not isinstance(screen_id, str) or not screen_id:
            raise ValueError('screen_id must be a non-empty string')
        component = self.ownerComp.op('screens/{}'.format(screen_id))
        if component is None or screen_id not in self._screen_layers:
            raise KeyError('Unknown screen id: {}'.format(screen_id))
        return component

    @staticmethod
    def _pair(value, name):
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError('{} must contain two values'.format(name))
        if any(
            isinstance(item, bool) or not isinstance(item, (int, float))
            for item in value
        ):
            raise TypeError('{} values must be numeric'.format(name))
        return float(value[0]), float(value[1])

    def _publish_screen_layer(self, screen_id):
        transform = self._screen_layers[screen_id]
        component = self._screen_component(screen_id)
        fit = component.op('programFit')
        level = component.op('programLevel')

        self._set_par(
            fit,
            'fit',
            self._layer_module.FIT_MODES[transform.fit],
        )
        self._set_par(fit, 'tx', transform.position_x)
        self._set_par(fit, 'ty', transform.position_y)
        self._set_par(fit, 'sx', transform.scale_x)
        self._set_par(fit, 'sy', transform.scale_y)
        self._set_par(fit, 'r', transform.rotation)
        self._set_par(fit, 'px', transform.pivot_x)
        self._set_par(fit, 'py', transform.pivot_y)
        self._set_par(
            level,
            'opacity',
            transform.opacity if transform.enabled else 0.0,
        )

        table = component.op('layers')
        values = {
            'enabled': int(transform.enabled),
            'fit': transform.fit,
            'positionX': transform.position_x,
            'positionY': transform.position_y,
            'scaleX': transform.scale_x,
            'scaleY': transform.scale_y,
            'rotation': transform.rotation,
            'pivotX': transform.pivot_x,
            'pivotY': transform.pivot_y,
            'opacity': transform.opacity,
            'zOrder': transform.z_order,
        }
        if table is not None:
            for column, value in values.items():
                table['program', column] = value

    def SetScreenTransform(
        self,
        screen_id,
        *,
        fit=None,
        position=None,
        scale=None,
        rotation=None,
        pivot=None,
        opacity=None,
        enabled=None
    ):
        component = self._screen_component(screen_id)
        del component
        current = self._screen_layers[screen_id]
        changes = {}
        if fit is not None:
            changes['fit'] = fit
        if position is not None:
            changes['position_x'], changes['position_y'] = self._pair(
                position,
                'position',
            )
        if scale is not None:
            changes['scale_x'], changes['scale_y'] = self._pair(scale, 'scale')
        if rotation is not None:
            if isinstance(rotation, bool) or not isinstance(
                rotation,
                (int, float),
            ):
                raise TypeError('rotation must be numeric')
            changes['rotation'] = float(rotation)
        if pivot is not None:
            changes['pivot_x'], changes['pivot_y'] = self._pair(pivot, 'pivot')
        if opacity is not None:
            if isinstance(opacity, bool) or not isinstance(
                opacity,
                (int, float),
            ):
                raise TypeError('opacity must be numeric')
            changes['opacity'] = float(opacity)
        if enabled is not None:
            if not isinstance(enabled, bool):
                raise TypeError('enabled must be boolean')
            changes['enabled'] = enabled

        updated = current.updated(**changes)
        self._screen_layers[screen_id] = updated
        self._publish_screen_layer(screen_id)
        return updated

    def RouteProgram(self, screen_ids):
        if isinstance(screen_ids, str):
            screen_ids = [screen_ids]
        if not isinstance(screen_ids, (tuple, list, set)):
            raise TypeError('screen_ids must be a string or collection')
        selected = set(screen_ids)
        unknown = selected.difference(self._screen_layers)
        if unknown:
            raise KeyError(
                'Unknown screen id(s): {}'.format(', '.join(sorted(unknown)))
            )
        for screen_id, transform in tuple(self._screen_layers.items()):
            self._screen_layers[screen_id] = transform.updated(
                enabled=screen_id in selected
            )
            self._publish_screen_layer(screen_id)
        return tuple(
            screen_id for screen_id in self._screen_layers
            if screen_id in selected
        )

    def SetScreenFade(self, screen_id, fade):
        component = self._screen_component(screen_id)
        if isinstance(fade, bool) or not isinstance(fade, (int, float)):
            raise TypeError('fade must be numeric')
        fade = float(fade)
        if not 0 <= fade <= 1:
            raise ValueError('fade must be between 0 and 1')
        self._set_par(component.op('masterFade'), 'opacity', fade)
        status = component.op('status')
        if status is not None:
            status['masterFade', 1] = fade
        return fade

    @property
    def ScreenOutputs(self):
        return {
            screen_id: self.ownerComp.op(
                'screens/{}/screenOut'.format(screen_id)
            )
            for screen_id in self._screen_layers
        }

    def OnDeckReady(self):
        result = self._model.deck_ready()
        self._publish()
        return result

    def OnTransitionComplete(self):
        if self._model.engine_state.value != 'TRANSITIONING':
            return 'IGNORED'
        self._complete_transition()
        return 'ACCEPTED'
