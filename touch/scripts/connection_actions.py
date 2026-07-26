"""Runtime receive/send actions for Show Controller connections."""

import json


SHOW_PATH = '/project1/showController'
LOGIC_PATH = '/project1/logicCore'


def _show():
    return op(SHOW_PATH)


def _status():
    return _show().op('connections/status')


def _set_status(connection_id, **changes):
    table = _status()
    if table is None or table.row(connection_id) is None:
        return
    for key, value in changes.items():
        if table.col(key) is not None:
            table[connection_id, key] = str(value)


def receive(connection_id, message, peer_address='', peer_port=''):
    table = _status()
    purpose = table[connection_id, 'purpose'].val
    _set_status(
        connection_id,
        state='RECEIVED',
        lastMessage=str(message)[:160],
        peer='{}:{}'.format(peer_address, peer_port).strip(':'),
        error='',
    )
    try:
        if purpose == 'contestantSnapshot':
            logic = op(LOGIC_PATH)
            active = logic.ActiveGame()
            if active is None:
                logic.CreateGame(
                    'episode',
                    'contestantEliminationGrid',
                    {'stake': 1000},
                )
            logic.SetSnapshotVerification(
                bool(logic.par.Verifysnapshots.eval())
            )
            result = logic.LoadContestantSnapshotText(message)
        elif purpose == 'executorTrigger':
            payload = json.loads(message)
            if not isinstance(payload, dict):
                raise ValueError('executor trigger must be a JSON object')
            button_id = payload.get('buttonId')
            if not isinstance(button_id, str) or not button_id:
                raise ValueError('executor trigger requires buttonId')
            result = _show().op(
                'operatorUI/actions'
            ).module.execute_button(button_id)
        else:
            raise ValueError(
                'Unsupported receive purpose: {}'.format(purpose)
            )
    except Exception as error:
        _set_status(
            connection_id,
            state='ERROR',
            error=str(error),
        )
        raise
    _set_status(connection_id, state='ACTIVE', error='')
    return result


def send(connection_id, payload):
    endpoint = _show().op('connections/' + connection_id)
    table = _status()
    if endpoint is None or table is None or table.row(connection_id) is None:
        raise RuntimeError('Unknown send connection: {}'.format(
            connection_id
        ))
    if table[connection_id, 'direction'].val != 'send':
        raise RuntimeError('{} is not a send connection'.format(
            connection_id
        ))
    message = (
        payload if isinstance(payload, str)
        else json.dumps(payload, separators=(',', ':'), allow_nan=False)
    )
    try:
        endpoint.send(message, terminator='')
    except Exception as error:
        _set_status(connection_id, state='ERROR', error=str(error))
        raise
    _set_status(
        connection_id,
        state='SENT',
        lastMessage=message[:160],
        error='',
    )
    return message


def send_logic_state(connection_id):
    logic = op(LOGIC_PATH)
    payload = {
        'type': 'logicState',
        'state': logic.Snapshot(),
        'game': logic.ActiveGame(),
        'summary': (
            logic.ContestantSummary()
            if logic.ActiveGame() is not None
            else None
        ),
    }
    return send(connection_id, payload)


def send_test(connection_id):
    return send(connection_id, {
        'type': 'connectionTest',
        'source': 'pixel.formation showController',
    })
