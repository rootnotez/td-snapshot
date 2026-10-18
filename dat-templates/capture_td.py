# Runs INSIDE TouchDesigner via the td-claude-bridge (/exec), driven by
# scripts/capture-dat-templates.sh, which prepends `START = n` and `END = m`.
#
# Creates each operator type in [START, END) in a scratch COMP, records the
# default text of the DATs it comes with, then destroys it. Prints one line:
# "@@DATTEMPLATES@@ <json>". The scratch COMP is removed when the last batch
# finishes (END >= number of types).
import json
import td

# Substrings of op type names never created here: hardware/device I/O, network
# listeners, file writers, window/engine processes. Creating them can grab a
# device or port, write files or open windows; their templates go unrecorded
# and the type is listed under "skipped".
SKIP = ['abletonlink', 'artnet', 'audiodevice', 'audiomovie', 'audiondi', 'audiorender',
        'audiostream', 'audiovst', 'audiowebrender', 'blacktrax', 'bodytrack', 'bullet',
        'cplusplus', 'directdisplay', 'directx', 'dmx', 'engine', 'etherdream', 'facetrack',
        'fileout', 'framework', 'freed', 'heliosdac', 'hokuyo', 'joystick', 'keyboardin',
        'kinect', 'laser', 'leap', 'leuzer', 'ltc', 'midi', 'monitors', 'mosys', 'mouse',
        'moviefileout', 'mpcdi', 'mqtt', 'ncam', 'ndi', 'nuitrack', 'nvidia', 'oak', 'oculus',
        'openvr', 'optitrack', 'orbbec', 'osc', 'ouster', 'pangolin', 'photoshop', 'pipe',
        'posistagenet', 'realsense', 'renderstream', 'scalabledisplay', 'screengrab', 'serial',
        'sharedmem', 'sick', 'socketio', 'st2110', 'stype', 'substance', 'syncin', 'syncout',
        'syphonspout', 'tablet', 'tcpip', 'touchin', 'touchout', 'udp', 'video', 'vio', 'web',
        'window', 'zed']

# Exceptions to SKIP: network and input DATs whose callbacks templates are among
# the most used. Creating them was checked safe on 2025.33230 (no dialog, no
# hang); each has `active` switched off straight after creation.
ALLOW = {'artnetDAT', 'bulletsolverCOMP', 'keyboardinDAT', 'mqttclientDAT', 'multitouchinDAT',
         'ndiDAT', 'oscinDAT', 'oscoutDAT', 'socketioDAT', 'tcpipDAT', 'touchinDAT',
         'touchoutDAT', 'udpinDAT', 'udpoutDAT', 'webclientDAT', 'webserverDAT', 'websocketDAT'}

TYPES = sorted(n for n in dir(td)
               if isinstance(getattr(td, n), type) and issubclass(getattr(td, n), td.OP)
               and getattr(td, n) is not td.OP and n not in ('ObjectCOMP', 'PanelCOMP')
               and n[0].islower())


def _is_code_dat(d):
    # Text and Execute-family DATs hold code; tables, Info DATs and device or
    # folder listings hold generated, machine-specific content, never a template.
    return d.OPType == 'textDAT' or d.OPType.endswith('executeDAT')


parent = op('/project1')
scratch = parent.op('dat_templates_capture') or parent.create(td.baseCOMP, 'dat_templates_capture')
try:
    _build = app.build
except NameError:
    _build = td.app.build
out = {'build': _build, 'types': len(TYPES), 'records': []}
for name in TYPES[START:END]:
    rec = {'op_type': name}
    if name not in ALLOW and any(s in name for s in SKIP):
        rec['skipped'] = True
        out['records'].append(rec)
        continue
    o = None
    try:
        # Named after its type so a docked DAT left behind by an earlier host
        # can't push this one's docked names to a numbered suffix.
        o = scratch.create(getattr(td, name), name)
        if name in ALLOW and getattr(o.par, 'active', None) is not None:
            o.par.active = False
        texts = []
        if o.family == 'DAT' and _is_code_dat(o) and o.text:
            texts.append(('text', o))
        for d in o.docked:
            if d.family == 'DAT' and _is_code_dat(d) and d.text:
                # Docked DATs are named <host>_<role>, e.g. scriptCHOP_callbacks.
                texts.append(('docked:' + d.name[len(o.name) + 1:], d))
        if o.isCOMP:
            for c in o.findChildren(type=td.DAT):
                if _is_code_dat(c) and c.text:
                    texts.append(('child:' + c.path[len(o.path) + 1:], c))
        rec['texts'] = [{'role': role, 'dat_type': d.OPType, 'text': d.text} for role, d in texts]
    except Exception as e:
        rec['failed'] = str(e)[:200]
    finally:
        if o is not None:
            try:
                o.destroy()
            except Exception:
                pass
    out['records'].append(rec)

if END >= len(TYPES):
    scratch.destroy()
print('@@DATTEMPLATES@@ ' + json.dumps(out))
