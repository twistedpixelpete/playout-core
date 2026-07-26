"""Operator actions for the logicCore contestant-elimination UI."""

from pathlib import Path


ROOT_PATH = '/project1/logicCore'
EPISODE_DIRECTORY = 'components/logicCore/data/ep02'
START_SNAPSHOT = '00 Start.json'


def _logic():
    logic = op(ROOT_PATH)
    if logic is None:
        raise RuntimeError('Missing {}'.format(ROOT_PATH))
    return logic


def _game():
    game = _logic().op('game')
    if game is None:
        raise RuntimeError('Missing {}/game'.format(ROOT_PATH))
    return game


def _episode_files():
    directory = Path(project.folder) / EPISODE_DIRECTORY
    return tuple(sorted(directory.glob('*.json')))


def _portable_path(path):
    return path.relative_to(Path(project.folder)).as_posix()


def select_episode(filename):
    """Select an episode file; reload explicitly if it is already selected."""
    files = {path.name: path for path in _episode_files()}
    path = files.get(filename)
    game = _game()
    if path is None:
        game.par.Loadstatus = 'ERROR: Episode file not found: {}'.format(
            filename
        )
        raise FileNotFoundError(filename)

    portable = _portable_path(path)
    current = game.par.Episodefile.eval().replace('\\', '/')
    if current == portable:
        game.par.Loadepisode.pulse()
    else:
        game.par.Episodefile = portable
    return portable


def browse_episode():
    """Open a JSON chooser and pass the selection to the game loader."""
    start = str(Path(project.folder) / EPISODE_DIRECTORY)
    selected = ui.chooseFile(
        start=start,
        fileTypes=['json'],
        title='Select logicCore Episode JSON',
    )
    if selected:
        game = _game()
        selected = str(selected)
        current = game.par.Episodefile.eval()
        if current == selected:
            game.par.Loadepisode.pulse()
        else:
            game.par.Episodefile = selected
    return selected


def reload_episode():
    game = _game()
    if not game.par.Episodefile.eval().strip():
        game.par.Loadstatus = 'CHOOSE A JSON FILE'
        return None
    game.par.Loadepisode.pulse()
    return game.par.Episodefile.eval()


def reset_episode():
    """Reset the running session from the designated start snapshot."""
    path = Path(project.folder) / EPISODE_DIRECTORY / START_SNAPSHOT
    portable = _portable_path(path)
    result = _logic().ResetContestantEpisodeFile(portable)
    _game().par.Loadstatus = 'EPISODE RESET: {}'.format(START_SNAPSHOT)
    return result


def step_episode(offset):
    """Move through the sorted episode snapshots by one position."""
    files = _episode_files()
    if not files:
        raise RuntimeError('No episode JSON files found')
    current_name = Path(_game().par.Episodefile.eval()).name
    names = [path.name for path in files]
    try:
        current_index = names.index(current_name)
    except ValueError:
        current_index = 0 if offset >= 0 else len(names) - 1
    target_index = max(0, min(len(names) - 1, current_index + offset))
    return select_episode(names[target_index])


def toggle_verification():
    """Toggle ordered-transition checks without disabling schema validation."""
    logic = _logic()
    enabled = not bool(logic.par.Verifysnapshots.eval())
    logic.par.Verifysnapshots = enabled
    active = logic.ActiveGame()
    if (
        active is not None
        and active.get('variantId') == 'contestantEliminationGrid'
    ):
        logic.SetSnapshotVerification(enabled)
    return enabled
