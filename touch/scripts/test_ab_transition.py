"""Interactive A/B transition test for execution in TouchDesigner Textport."""


ROOT_PATH = '/project1/playoutCore'
GENERIC_ID = '1000000000000001'
GAMEPLAY_ID = '1000000000000002'
LOSE_ID = '1000000000000003'
WINNER_ID = '3000000000000001'


def status():
    core = op(ROOT_PATH)
    table = core.op('control/engineStatus')
    values = {
        str(table[row, 0]): str(table[row, 1])
        for row in range(1, table.numRows)
    }
    cross = core.op('mixer/video/cross')
    print(
        'state={engineState} active={activeDeck} standby={standbyDeck} '
        'onAir={onAirClip} pending={pendingCommand}:{pendingClip} '
        'expectedPlay={expectedPlayDeck} playA={deckAPlay} playB={deckBPlay} '
        'retriesA={deckAPlayRetries} retriesB={deckBPlayRetries} '
        'cross={cross}'.format(
            cross=round(float(cross.par.cross.eval()), 3),
            **values
        )
    )
    return values


def start():
    core = op(ROOT_PATH)
    core.Stop()
    result = core.Take(GENERIC_ID)
    print('Take generic:', result)
    print('Wait for PLAYING, then run: ab_next()')
    return result


def next_clip():
    core = op(ROOT_PATH)
    result = core.Take(GAMEPLAY_ID)
    print('Take gameplay:', result)
    print('During its crossfade, optionally run: ab_latest()')
    return result


def latest_wins():
    core = op(ROOT_PATH)
    first = core.Take(LOSE_ID)
    second = core.Take(WINNER_ID, transition='cut')
    print('Take lose:', first)
    print('Take win:', second)
    print('The pending request should be Take:{} (cut)'.format(WINNER_ID))
    return first, second


ab_status = status
ab_start = start
ab_next = next_clip
ab_latest = latest_wins

print('A/B test installed: ab_start(), ab_status(), ab_next(), ab_latest()')
