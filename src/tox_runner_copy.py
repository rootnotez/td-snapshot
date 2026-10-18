# tox_runner_copy.py v1.1.0 | sha256:586c76ee733c52a5aa290bc43e16338d70a086ddc1a61c850f6ac20c58d47547
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
    ui.clipboard = result

def onValueChange(panelValue):
    pass

def onOnToOff(panelValue):
    pass

def onWhileOn(panelValue):
    pass

def onWhileOff(panelValue):
    pass
