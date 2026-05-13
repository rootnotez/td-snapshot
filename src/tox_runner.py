# Panel Execute DAT content for the td-snapshot TOX.
# Attach this DAT to the button's panel. It fires when the button is pressed,
# captures the network containing the TOX, and writes output to the 'output' Text DAT.

def onOffToOn(panelValue):
    result = mod(op('core')).snapshot_patch(me.parent().parent())
    op('output').text = result

def onValueChange(panelValue):
    pass

def onOnToOff(panelValue):
    pass

def onWhileOn(panelValue):
    pass

def onWhileOff(panelValue):
    pass
