"""Promoted TouchDesigner Extension for /project1/logicCore."""

import importlib.util
import json
from pathlib import Path
import sys


def _load_module(filename, module_name):
    path = Path(project.folder) / 'scripts' / filename
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class LogicCoreExt:
    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self._module = _load_module('logic_model.py', 'logic_core_model')
        self._registry_module = _load_module(
            'game_registry.py',
            'logic_core_game_registry',
        )
        self._contestant_module = _load_module(
            'contestant_elimination_grid.py',
            'logic_core_contestant_elimination_grid',
        )
        config_path = Path(project.folder) / 'config' / 'logic.json'
        config = json.loads(config_path.read_text(encoding='utf-8'))
        if config.get('version') != 1:
            raise RuntimeError('Unsupported logic config version')
        self.gameId = config.get('gameId', 'generic')
        self._model = self._module.LogicModel(
            config['initialState'],
            config['allowedPhases'],
        )
        registry_path = (
            Path(project.folder) / 'config' / 'game_archetypes.json'
        )
        self._registry = self._registry_module.VariantRegistry.from_path(
            registry_path
        )
        self._activeGame = None
        self._runningGame = None
        self.ownerComp.store('logicConfig', config)
        self._publish()

    @staticmethod
    def _value(value):
        if isinstance(value, (dict, list, tuple, bool)) or value is None:
            return json.dumps(value, separators=(',', ':'))
        return value

    def _publish(self):
        state = self.ownerComp.op('control/state')
        snapshot = self._model.snapshot()
        state.clear()
        state.appendRows(
            [['key', 'value']]
            + [[key, self._value(value)] for key, value in snapshot.items()]
        )

        events = self.ownerComp.op('control/events')
        events.clear()
        events.appendRow(['sequence', 'revision', 'type', 'payload'])
        for event in self._model.events:
            events.appendRow([
                event.sequence,
                event.revision,
                event.event_type,
                json.dumps(event.payload, separators=(',', ':')),
            ])

        latest = self.ownerComp.op('control/latestEvent')
        latest.clear()
        latest.appendRow(['sequence', 'revision', 'type', 'payload'])
        if self._model.events:
            event = self._model.events[-1]
            latest.appendRow([
                event.sequence,
                event.revision,
                event.event_type,
                json.dumps(event.payload, separators=(',', ':')),
            ])

        status = self.ownerComp.op('control/status')
        status.clear()
        status.appendRows([
            ['key', 'value'],
            ['state', 'READY'],
            ['gameId', self.gameId],
            ['phase', snapshot['phase']],
            ['revision', self._model.revision],
            ['queuedEvents', len(self._model.events)],
            ['error', ''],
        ])

        variants = self.ownerComp.op('control/variants')
        if variants is not None:
            variants.clear()
            variants.appendRow(['id', 'modules', 'inspiredBy'])
            for variant in self._registry.list_variants():
                variants.appendRow([
                    variant['id'],
                    json.dumps(variant['modules'], separators=(',', ':')),
                    json.dumps(variant['inspiredBy'], separators=(',', ':')),
                ])

        active_game = self.ownerComp.op('control/activeGame')
        if active_game is not None:
            active_game.clear()
            active_game.appendRow(['key', 'value'])
            if self._activeGame is not None:
                for key, value in self._activeGame.snapshot().items():
                    active_game.appendRow([key, self._value(value)])

        summary = self.ownerComp.op('game/contestantEliminationGrid/summary')
        contestants = self.ownerComp.op(
            'game/contestantEliminationGrid/contestants'
        )
        if summary is not None:
            summary.clear()
            summary.appendRow(['key', 'value'])
        if contestants is not None:
            contestants.clear()
            contestants.appendRow([
                'number',
                'active',
                'freePass',
                'boughtOut',
                'boughtOutEndgame',
                'status',
                'column',
                'row',
            ])
        if self._runningGame is not None:
            game_summary = self._runningGame.summary()
            if summary is not None and game_summary is not None:
                for key, value in game_summary.items():
                    summary.appendRow([key, self._value(value)])
            if contestants is not None:
                for row in self._runningGame.contestant_rows():
                    contestants.appendRow([
                        row['number'],
                        int(row['active']),
                        int(row['freePass']),
                        int(row['boughtOut']),
                        int(row['boughtOutEndgame']),
                        row['status'],
                        row['column'],
                        row['row'],
                    ])

    def _run(self, command):
        try:
            result = command()
            self._publish()
            return result
        except Exception as exc:
            status = self.ownerComp.op('control/status')
            if status is not None:
                status['state', 1] = 'ERROR'
                status['error', 1] = str(exc)
            raise

    def Reset(self):
        return self._run(self._model.reset)

    def StartGame(self):
        return self._run(
            lambda: self._model.patch(
                {'phase': 'RUNNING'},
                'GAME_STARTED',
            )
        )

    def SetPhase(self, phase):
        return self._run(lambda: self._model.set_phase(phase))

    def SetState(self, key, value):
        return self._run(lambda: self._model.patch({key: value}))

    def PatchState(self, changes):
        return self._run(lambda: self._model.patch(changes))

    def Increment(self, key, amount=1):
        return self._run(lambda: self._model.increment(key, amount))

    def EmitEvent(self, event_type, payload=None):
        return self._run(lambda: self._model.emit(event_type, payload))

    def PeekEvents(self):
        return tuple(self._model.events)

    def PopEvents(self, count=None):
        return self._run(lambda: self._model.pop_events(count))

    def Snapshot(self):
        return self._model.snapshot()

    def ListVariants(self):
        return self._registry.list_variants()

    def CreateGame(self, game_id, variant_id, settings=None):
        def command():
            self._activeGame = self._registry.create(
                game_id,
                variant_id,
                settings,
            )
            self._runningGame = None
            if variant_id == 'contestantEliminationGrid':
                stake = (settings or {}).get('stake', 1000)
                self._runningGame = (
                    self._contestant_module.ContestantEliminationGrid(
                        stake=stake
                    )
                )
            snapshot = self._activeGame.snapshot()
            self._model.emit('GAME_CREATED', snapshot)
            return snapshot
        return self._run(command)

    def ConfigureGame(self, changes):
        def command():
            if self._activeGame is None:
                raise self._registry_module.RegistryError(
                    'No active game has been created'
                )
            snapshot = self._activeGame.configure(changes)
            self._model.emit('GAME_CONFIGURED', {
                'gameId': snapshot['gameId'],
                'variantId': snapshot['variantId'],
                'revision': snapshot['revision'],
                'changes': changes,
            })
            return snapshot
        return self._run(command)

    def ActiveGame(self):
        if self._activeGame is None:
            return None
        result = self._activeGame.snapshot()
        if self._runningGame is not None:
            result['session'] = self._runningGame.snapshot()
        return result

    def _require_contestant_game(self):
        if self._runningGame is None:
            raise self._contestant_module.ContestantGridError(
                'Create a contestantEliminationGrid game first'
            )
        return self._runningGame

    def _forward_game_events(self, events):
        for event in events:
            self._model.emit(event.event_type, {
                **event.payload,
                'gameRevision': event.revision,
                'gameSequence': event.sequence,
            })

    def LoadContestantSnapshot(self, snapshot):
        def command():
            game = self._require_contestant_game()
            events = game.load_snapshot(snapshot)
            self._forward_game_events(events)
            return game.snapshot()
        return self._run(command)

    def LoadContestantSnapshotFile(self, filename):
        path = Path(filename)
        if not path.is_absolute():
            path = Path(project.folder) / path
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        return self.LoadContestantSnapshot(snapshot)

    def ResetContestantEpisodeFile(self, filename):
        """Create a fresh session, then apply the designated start snapshot."""
        self.CreateGame(
            'episode',
            'contestantEliminationGrid',
            {'stake': 1000},
        )
        self.SetSnapshotVerification(
            bool(self.ownerComp.par.Verifysnapshots.eval())
        )
        result = self.LoadContestantSnapshotFile(filename)
        game = self.ownerComp.op('game')
        if (
            game is not None
            and game.par.Episodefile.eval().replace('\\', '/')
            != str(filename).replace('\\', '/')
        ):
            game.store('suppressEpisodeAutoLoad', True)
            game.par.Episodefile = filename
        return result

    def LoadContestantSnapshotText(self, text):
        try:
            snapshot = json.loads(text)
        except (TypeError, ValueError) as exc:
            raise self._contestant_module.ContestantGridError(
                'Snapshot input is not valid JSON'
            ) from exc
        return self.LoadContestantSnapshot(snapshot)

    def SetSnapshotVerification(self, enabled):
        game = self._require_contestant_game()
        return game.set_transition_verification(bool(enabled))

    def SnapshotVerification(self):
        game = self._require_contestant_game()
        return game.verify_transitions

    def CorrectContestantSnapshot(self, snapshot, reason):
        def command():
            game = self._require_contestant_game()
            event = game.apply_correction(snapshot, reason)
            self._forward_game_events((event,))
            return game.snapshot()
        return self._run(command)

    def ContestantSummary(self):
        game = self._require_contestant_game()
        return game.summary()

    def Contestants(self):
        game = self._require_contestant_game()
        return tuple(game.contestant_rows())
