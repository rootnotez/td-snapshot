# tox_runner_inspect.py v1.0.0 | sha256:19467831a364093deb7c6f338b5d3632155036b457b09ae64649b1ed681eb662
def onOffToOn(panelValue):
    result = mod(op('core')).snapshot_patch(me.parent().parent().path)
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
