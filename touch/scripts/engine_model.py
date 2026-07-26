"""TouchDesigner-independent Playout Core state and command model."""

from dataclasses import dataclass
from enum import Enum


class DeckState(str, Enum):
    EMPTY = 'EMPTY'
    LOADING = 'LOADING'
    CUED = 'CUED'
    PLAYING = 'PLAYING'
    FADING_OUT = 'FADING_OUT'
    STOPPED = 'STOPPED'
    ERROR = 'ERROR'


class EngineState(str, Enum):
    IDLE = 'IDLE'
    LOADING = 'LOADING'
    READY = 'READY'
    PLAYING = 'PLAYING'
    TRANSITIONING = 'TRANSITIONING'
    PAUSED = 'PAUSED'
    ERROR = 'ERROR'


@dataclass(frozen=True)
class Request:
    command: str
    clip_id: str | None = None
    transition: str | None = None


class EngineModel:
    """State-only model. TouchDesigner operator changes live in the Extension."""

    def __init__(self):
        self.engine_state = EngineState.IDLE
        self.deck_states = {
            'A': DeckState.EMPTY,
            'B': DeckState.EMPTY,
        }
        self.active_deck = None
        self.standby_deck = 'A'
        self.requested_clip = None
        self.on_air_clip = None
        self.standby_clip = None
        self.pending_request = None
        self.autoplay_when_ready = False
        self.position_seconds = 0.0
        self.error = ''

    def _queue_latest(self, command, clip_id=None, transition=None):
        self.pending_request = Request(command, clip_id, transition)
        return 'QUEUED'

    def validate_decks(self):
        if self.standby_deck not in self.deck_states:
            raise RuntimeError('Invalid standby deck: {}'.format(
                self.standby_deck
            ))
        if (
            self.active_deck is not None
            and self.active_deck not in self.deck_states
        ):
            raise RuntimeError('Invalid active deck: {}'.format(
                self.active_deck
            ))
        if (
            self.active_deck is not None
            and self.active_deck == self.standby_deck
        ):
            raise RuntimeError('Active and standby decks must be different')
        return True

    def cue(self, clip_id):
        self.validate_decks()
        if self.engine_state == EngineState.TRANSITIONING:
            return self._queue_latest('Cue', clip_id)
        if (
            self.engine_state == EngineState.LOADING
            and self.standby_clip == clip_id
        ):
            return 'ALREADY_PENDING'
        self.requested_clip = clip_id
        self.standby_clip = clip_id
        self.deck_states[self.standby_deck] = DeckState.LOADING
        self.engine_state = EngineState.LOADING
        self.autoplay_when_ready = False
        self.error = ''
        return 'ACCEPTED'

    def take(self, clip_id, transition=None):
        if self.engine_state == EngineState.TRANSITIONING:
            return self._queue_latest('Take', clip_id, transition)
        result = self.cue(clip_id)
        self.autoplay_when_ready = True
        return result

    def deck_ready(self):
        if self.engine_state != EngineState.LOADING:
            return False
        self.deck_states[self.standby_deck] = DeckState.CUED
        self.engine_state = EngineState.READY
        return True

    def begin_transition(self):
        self.validate_decks()
        if self.engine_state != EngineState.READY:
            return False
        self.engine_state = EngineState.TRANSITIONING
        self.deck_states[self.standby_deck] = DeckState.PLAYING
        if self.active_deck is not None:
            self.deck_states[self.active_deck] = DeckState.FADING_OUT
        return True

    def finish_transition(self):
        self.validate_decks()
        if self.engine_state != EngineState.TRANSITIONING:
            return None

        old_active = self.active_deck
        self.active_deck = self.standby_deck
        self.standby_deck = 'B' if self.active_deck == 'A' else 'A'
        self.on_air_clip = self.standby_clip
        self.standby_clip = None
        self.deck_states[self.active_deck] = DeckState.PLAYING
        if old_active is not None:
            self.deck_states[old_active] = DeckState.STOPPED
        self.engine_state = EngineState.PLAYING
        self.validate_decks()

        request = self.pending_request
        self.pending_request = None
        return request

    def play(self):
        if self.engine_state == EngineState.READY:
            self.deck_states[self.standby_deck] = DeckState.PLAYING
            self.engine_state = EngineState.PLAYING
            return 'ACCEPTED'
        if self.engine_state == EngineState.PAUSED and self.active_deck:
            self.deck_states[self.active_deck] = DeckState.PLAYING
            self.engine_state = EngineState.PLAYING
            return 'ACCEPTED'
        return 'IGNORED'

    def pause(self):
        if self.engine_state != EngineState.PLAYING:
            return 'IGNORED'
        if self.active_deck:
            self.deck_states[self.active_deck] = DeckState.CUED
        self.engine_state = EngineState.PAUSED
        return 'ACCEPTED'

    def stop(self):
        for deck in self.deck_states:
            if self.deck_states[deck] != DeckState.EMPTY:
                self.deck_states[deck] = DeckState.STOPPED
        self.engine_state = EngineState.IDLE
        self.active_deck = None
        self.standby_deck = 'A'
        self.requested_clip = None
        self.on_air_clip = None
        self.standby_clip = None
        self.pending_request = None
        self.autoplay_when_ready = False
        self.position_seconds = 0.0
        self.error = ''
        return 'ACCEPTED'

    def seek(self, seconds):
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
            raise TypeError('Seek position must be numeric')
        if seconds < 0:
            raise ValueError('Seek position must be at least 0')
        self.position_seconds = float(seconds)
        return 'ACCEPTED'

    def set_error(self, message, deck=None):
        self.error = str(message)
        self.engine_state = EngineState.ERROR
        self.autoplay_when_ready = False
        if deck in self.deck_states:
            self.deck_states[deck] = DeckState.ERROR

    def snapshot(self):
        request = self.pending_request
        return {
            'engineState': self.engine_state.value,
            'deckAState': self.deck_states['A'].value,
            'deckBState': self.deck_states['B'].value,
            'activeDeck': self.active_deck or '',
            'standbyDeck': self.standby_deck,
            'requestedClip': self.requested_clip or '',
            'onAirClip': self.on_air_clip or '',
            'standbyClip': self.standby_clip or '',
            'pendingCommand': request.command if request else '',
            'pendingClip': request.clip_id if request and request.clip_id else '',
            'pendingTransition': (
                request.transition if request and request.transition else ''
            ),
            'positionSeconds': self.position_seconds,
            'error': self.error,
        }
