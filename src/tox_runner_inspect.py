# tox_runner_inspect.py v1.1.0 | sha256:f808762beabefaf78f5bb0933fd03bbf5cd21a0543698a10f23e349427fb9a1d
def _root_path():
    # Rootpath on the component picks what to snapshot. Empty means the network
    # containing the component; a relative path resolves from that network.
    base = me.parent().parent()
    path = me.parent().par.Rootpath.eval().strip()
    target = base.op(path) if path else base
    if target is None:
        raise ValueError('td-snapshot: no operator at Rootpath {!r}'.format(path))
    return target.path

def onOffToOn(panelValue):
    result = mod(op('core')).snapshot_patch(_root_path())
    op('output').text = result
    op('output').openViewer(unique=True, borders=True)

def onValueChange(panelValue):
    pass

def onOnToOff(panelValue):
    pass

def onWhileOn(panelValue):
    pass

def onWhileOff(panelValue):
    pass
