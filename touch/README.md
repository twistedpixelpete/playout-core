# Playout Core

Playout Core is a reusable TouchDesigner media playback engine. It owns media
loading, cueing, playback, transitions, audio, and diagnostics. It does not
contain game rules or operator-interface logic.

## Version 1 scope

- Two video/audio decks with program/standby roles
- Readiness-gated loading and cueing
- Cut and crossfade transitions
- Per-clip loop, speed, in, out, volume, and transition settings
- Relative media paths
- A latest-request-wins queue while a transition is active
- Program video, program audio, state, and diagnostic outputs
- Missing-file and decoder-error handling

## Component

The reusable component will be exported as `components/playoutCore.tox`.

Suggested internal network:

```text
/playoutCore
├── config
│   ├── clipLibrary
│   └── settings
├── control
│   ├── PlayoutCoreExt
│   ├── commandQueue
│   └── transitionTimer
├── decks
│   ├── deckA
│   └── deckB
├── mixer
│   ├── videoMix
│   └── audioMix
├── monitor
│   ├── deckAInfo
│   ├── deckBInfo
│   └── performance
└── output
    ├── programVideo
    ├── programAudio
    └── status
```

Each deck should contain a Movie File In TOP, Audio Movie CHOP, Info CHOP,
video output, audio gain/output, and a status DAT.

## Public command API

```python
op('playoutCore').Cue('clip_id')
op('playoutCore').Take('clip_id')
op('playoutCore').Play()
op('playoutCore').Pause()
op('playoutCore').Stop()
op('playoutCore').Seek(seconds)
```

The component must not depend on absolute operator paths outside itself.

## State model

Deck states:

```text
EMPTY -> LOADING -> CUED -> PLAYING -> FADING_OUT -> STOPPED
                    \-> ERROR
```

Engine states:

```text
IDLE
LOADING
READY
PLAYING
TRANSITIONING
PAUSED
ERROR
```

## Outputs

- TOP output 1: program video
- CHOP output 1: program audio
- DAT output 1: current engine and deck state
- CHOP output 2: numeric diagnostics

Status should include the requested clip, on-air clip, active deck, standby
deck, playback position, duration, loop state, readiness, and error message.

## Playback transaction

1. Resolve a clip ID from the clip library.
2. Validate the media file and settings.
3. Select the inactive deck.
4. Configure and load that deck.
5. Cue the in-point.
6. Wait for the file to report ready.
7. Start the deck and transition it to program.
8. Stop and release the previous deck.
9. Publish the new program state.

## Acceptance tests

- Take ten alternating clips without a black or stale frame.
- Reject an unknown clip ID without disturbing program output.
- Reject a missing file without disturbing program output.
- Loop a clip cleanly at its configured in/out range.
- Maintain audio/video synchronization.
- Cut with a zero-second transition.
- Crossfade using the clip's configured duration.
- Accept a new trigger during a transition using the request queue.
- Recover cleanly after a decoder-open failure.
- Maintain the target project frame rate during sustained playback.

