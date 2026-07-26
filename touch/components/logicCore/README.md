# logicCore

Temporary package boundary for the reusable pixel.formation game-logic
component.

The currently active implementation remains in `touch/config`,
`touch/scripts`, and `touch/tests` until its game format and public contract
are stable. Moving those files here is a later migration step and should be
done together with updating TouchDesigner paths and test discovery.

Planned contents:

- `config/`: versioned game configuration and schemas
- `scripts/`: TouchDesigner-independent model and component adapter
- `tests/`: pure-model and component-contract tests
- `logicCore.tox`: exported reusable component (not yet created)

logicCore must not reference playbackCore or operator paths outside its own
component.

## Game archetype foundation

The active development implementation currently exposes reusable pure-Python
mechanics from `touch/scripts/game_archetypes.py`. Preset compositions are
listed in `touch/config/game_archetypes.json`.

The presets are mechanics-oriented rather than branded copies:

| Preset | Example format | Reusable mechanics |
| --- | --- | --- |
| `massEliminationLadder` | The 1% Club | simultaneous answers, locked submissions, passes, eliminations, shared prize pool |
| `counterDropElimination` | Tipping Point | question-earned counters, externally reported drops, scores, eliminations, jackpot objective |
| `teamPursuitQuiz` | The Chase | cash builder, offer selection, pursuit track, team bank, timed final |
| `hiddenValueOffer` | Deal or No Deal | sealed values, staged reveals, banker offers, accept/reject decision |
| `territoryTimedDuel` | The Floor | grid adjacency, opponent selection, alternating clocks, territory transfer |
| `specialistRoundElimination` | Hard Quiz | specialist categories, positive/negative scoring, round eliminations, head-to-head final |
| `wagerableClueBoard` | Jeopardy! | category/value board, control, buzzer lockout, hidden wagers, final wager |

Exact question counts, timing, prize schedules, scoring values, offer
algorithms, tie-breaks, and regional format variations belong in project
configuration or project-specific rules.

The archetype classes remain independent of TouchDesigner. A later
`LogicCoreExt` integration will translate their snapshots into output DATs and
their domain events into the ordered logicCore event queue.

## Variant factory API

After rebuilding logicCore, available variants and the active project can be
managed through the promoted extension:

```python
logic = op('/project1/logicCore')

logic.ListVariants()
logic.CreateGame(
    'new_show',
    'territoryTimedDuel',
    {
        'board': {'width': 10, 'height': 10},
        'duelSeconds': 45,
    },
)
logic.ConfigureGame({'duelSeconds': 50})
logic.ActiveGame()
```

`CreateGame()` emits `GAME_CREATED`, while `ConfigureGame()` emits
`GAME_CONFIGURED`. Both events use the existing ordered logicCore queue.

Additional DATs:

- `control/variants`: available preset IDs, modules, and research references
- `control/activeGame`: active project definition and configuration
- `gameOut`: active project readout outside logicCore

The factory creates project definitions and module compositions. Running
session support is currently implemented for `contestantEliminationGrid`;
the remaining presets are still reusable research primitives.

## contestantEliminationGrid

The first running variant accepts ordered episode snapshots using the external
JSON contract:

```python
logic.CreateGame(
    'episode',
    'contestantEliminationGrid',
    {'stake': 1000},
)
logic.LoadContestantSnapshotFile(
    'components/logicCore/data/ep02/00 Start.json'
)
logic.LoadContestantSnapshot(snapshot)
logic.CorrectContestantSnapshot(snapshot, 'Operator correction reason')
```

Published readouts:

- `game/contestantEliminationGrid/summary`
- `game/contestantEliminationGrid/contestants`
- `summaryOut`
- `contestantsOut`

The variant validates player identity, active totals, stage eliminations,
sticky pass/buyout flags, forward question movement, and prize-pool changes.
Normal invalid transitions are rejected atomically. Corrections require an
explicit operator reason.

The generated `producer` Container COMP provides a 1280-by-720 high-contrast
producer screen with summary cards, a 10×10 contestant grid, semantic state
colours, and a legend. It is driven entirely by the published DATs.

### TouchDesigner JSON input

The generated `/project1/logicCore/game` component has an `Episode` custom
parameter page. Choose a JSON file with `Episode JSON`, or pulse `Load Episode`
to reload the currently selected file.

`game/contestantEliminationGrid/snapshotFile` is the single JSON File In DAT.
Set its File parameter to a portable episode path such as:

```text
components/logicCore/data/ep02/00 Start.json
```

Its `snapshotExecute` DAT watches for content changes. When a valid file is
loaded or refreshed, it creates the running variant if necessary, applies the
snapshot through the authoritative model, and republishes every DAT and
producer-screen value. Invalid snapshots leave the previous state unchanged
and put the validation message in logicCore's status DAT.

## Operator interfaces

The construction script creates two 1280-by-720 panels:

- `/project1/logicCore/operatorUI` contains the contestant board confidence
  monitor and episode controls. It deliberately shows only the board, not the
  full producer monitor.
- `/project1/showController/operatorUI` is the host console. Its `GAME LOGIC`
  page selects the logicCore panel and adds a permanently visible live
  executor dock. `EXECUTORS` is the setup view: select an executor on the left
  and inspect its ordered command stack on the right. `CONNECTIONS` displays
  the configured external endpoints from `config/connections.json`.

Open `/project1/showController/operatorUI` to use the full three-tab console.
Opening `/project1/logicCore/operatorUI` directly shows only the embedded game
panel, so the Show Controller tabs are intentionally absent there.

`BROWSE / LOAD JSON` on the Game Logic page opens TouchDesigner's file chooser
and sends the selected JSON file through the authoritative episode loader.
`RESET EPISODE` always starts a new session from
`components/logicCore/data/ep02/00 Start.json`.

The episode controls are intentionally compact. Episode totals share the
feedback panel, leaving the right side of the main operating page available
for a 4-by-4 executor dock. The first 16 configured executors are available
without leaving the Game Logic page. Executor setup provides Browse, Reload
and Open JSON controls for the selected configuration file.

The playback commands are implemented by the sibling Show Controller. No
runtime operator inside logicCore references playbackCore.

Stage snapshots are not presented as manual operator buttons because normal
progression is owned by the external data source. `RESET EPISODE` is the one
deliberate exception: it creates a fresh running session and applies
`components/logicCore/data/ep02/00 Start.json`.

Executor buttons contain ordered action stacks. Supported actions currently
include episode reset, logic event emission, playback cue/take, audio playback,
transport controls, and explicit waits. A `wait` action splits the stack into
delayed batches using TouchDesigner's delayed `run()` command. The executor
configuration is selected with the `Executor Buttons JSON` custom parameter on
`/project1/showController`.

## External connections

The initial connection transport is native TouchDesigner UDP messaging. All
sample endpoints are disabled by default so rebuilding logicCore cannot claim
a network port unexpectedly. Configure them in `touch/config/connections.json`,
or choose another connection file using the `Connections JSON` custom
parameter or the controls on the `CONNECTIONS` tab.

The supplied receiver purposes are:

- `contestantSnapshot`: accepts the same raw JSON object as the episode file
  loader and publishes it through logicCore.
- `executorTrigger`: accepts `{"buttonId":"start_show"}` and triggers the
  matching configured executor.

The supplied `logicState` sender emits a compact JSON object containing the
current generic state, active game and contestant summary. The Connections tab
shows endpoint state, bind/destination address, latest peer, latest message and
errors. Send endpoints also provide `SEND STATE` and `SEND TEST` controls.

Executor action stacks may send through configured endpoints:

```json
{
  "type": "connection.sendState",
  "connectionId": "logicStateOutput"
}
```

or:

```json
{
  "type": "connection.send",
  "connectionId": "logicStateOutput",
  "payload": {"type": "customMessage"}
}
```

UDP is the first transport foundation. Reliable TCP/WebSocket protocols and
protocol-specific adapters should be added as separate connection types rather
than placing network behavior inside logicCore.
