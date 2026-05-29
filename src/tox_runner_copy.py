# tox_runner_copy.py v1.0.1 | sha256:0b5137746c322ce135b0af0544d7b452a9a3aaadeb356c5abab90c43f3d9c4af
def onOffToOn(panelValue):
    result = mod(op('core')).snapshot_patch(me.parent().parent().path)
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
