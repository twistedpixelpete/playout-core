"""Rebuild only Show Controller connections and operator UI.

Run from the TouchDesigner Textport:
exec(open(project.folder + '/scripts/rebuild_show_controller.py').read())
"""


def _execute(filename):
    source = project.folder + '/scripts/' + filename
    exec(open(source, encoding='utf-8').read(), globals())


def rebuild():
    _execute('create_connections.py')
    _execute('create_show_controller_ui.py')
    show = op('/project1/showController')
    if show is None or show.op('operatorUI') is None:
        raise RuntimeError('Show Controller UI was not created')
    print('Rebuilt Show Controller independently')
    return show


SHOW_CONTROLLER = rebuild()
