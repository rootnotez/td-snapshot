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
