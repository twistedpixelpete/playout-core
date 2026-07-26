"""Per-frame callback bridge for the Playout Core Extension."""


def onFrameStart(frame):
    parent().OnFrameStart()


def onStart():
    return


def onCreate():
    return


def onExit():
    return


def onFrameEnd(frame):
    return


def onPlayStateChange(state):
    return


def onDeviceChange():
    return
