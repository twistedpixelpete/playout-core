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

## Media layout

```text
media/
├── video/
└── audio/
```

Clip records use nullable `videoFile` and `audioFile` fields. A video can use
its embedded audio when `audioFile` is null, while an audio-only clip has a
null `videoFile`. All paths remain relative to the corresponding root in
`config/clips.json`.

Audio-only playback uses four independent voices and does not alter program
deck state. Each clip targets a logical `audioBus`: `program`, `effects`,
`aux1`, or `aux2`. Playout Core exposes both a summed stereo `programAudio`
CHOP and an eight-channel `audioStems` CHOP. Hardware, ASIO, and Dante channel
mapping belongs to the host project.

## Video mapping

Playout Core separates playback sources, visual layer instances, logical
screen canvases, and physical feed outputs. Logical screens are defined in
`config/screens.json`. Each screen has an independent resolution, background,
master fade, and program-layer fit, position, scale, rotation, pivot, and
opacity. Named screen TOP outputs remain hardware-independent; Window COMPs,
display heads, LED processor canvases, NDI, and capture routing belong to the
host project.

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

Each deck should contain a Movie File In TOP, Audio Movie CHOP, Audio File In
CHOP, audio-source Switch CHOP, Info CHOP, video output, audio gain/output, and
a status DAT.

## Public command API

```python
op('playoutCore').Cue('1000000000000001')
op('playoutCore').Take('1000000000000001')
op('playoutCore').Take('3000000000000001', transition='cut')
op('playoutCore').Play()
op('playoutCore').Pause()
op('playoutCore').Stop()
op('playoutCore').Seek(seconds)
```

After changing playback scripts or clip configuration externally, reload the
library, promoted extension, and playback UI together:

```python
exec(open(project.folder + '/scripts/rebuild_playback_core.py').read())
```

The three runtime components rebuild independently:

```python
# logicCore only
exec(open(project.folder + '/scripts/create_logic_core.py').read())

# playbackCore only
exec(open(project.folder + '/scripts/rebuild_playback_core.py').read())

# Show Controller connections and UI only
exec(open(project.folder + '/scripts/rebuild_show_controller.py').read())
```

The Show Controller `EXECUTORS` tab edits slots `001`–`016` without opening
the source file. Select a slot, edit its label, color, or ordered action JSON,
then press `SAVE + ASSIGN`. The complete configuration is validated before an
atomic write to `config/executors.json`; `REVERT` discards unsaved edits.
`RESET SLOT` confirms before returning the selected fixed slot to an
unassigned state.

`ADD ACTION v` provides a Companion-style action chooser. Playback actions
open a second clip chooser showing human-readable clip names while storing the
immutable numeric clip ID. Actions are appended in execution order and remain
visible in the advanced JSON field before `SAVE + ASSIGN` is pressed. Saving
assigns the edited stack to the selected fixed live slot and refreshes its
operator button.

Executor sequences complete by default, including actions after a wait.
`executor.cancelPending` explicitly cancels delayed batches from older
executors when an override is required. Delayed actions execute through the
stable `/project1/showController/executorActions` DAT, outside the rebuildable
operator UI.

## System IDs

Clip IDs are immutable numeric strings. Adding media through the playbackCore
UI reserves the next ID from `config/id_registry.json`; reserved values are
never reused. The inspector displays the authoritative ID as `CURRENT ID`.
Operators edit the human-readable clip label, not the system ID.

Executor IDs are fixed console slots `001` through `016`. The media reference
is the nested action's numeric `clipId`. Keeping slot identity separate from
the clip label prevents a label edit from breaking executor references.

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
6. Wait for the Info CHOP to report the movie open with at least one decoded
   start frame. The configured pre-read cache may continue filling afterward.
7. Start the deck and transition it to program.
8. Stop and release the previous deck.
9. Publish the new program state.

Loads have a 15-second watchdog by default. Override it before rebuilding by
storing `movieLoadTimeoutSeconds` on playbackCore. A timeout or decoder/open
failure moves the engine to `ERROR`, cancels autoplay, and publishes the
decoder values in the deck status DAT. A later valid `Take()` recovers by
starting a fresh load.

The default start threshold is one decoded frame because some codecs never
fill the requested pre-read cache while paused. Store
`minimumMovieStartFrames` on playbackCore before rebuilding to raise this
threshold for unusually high-bitrate media.

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
