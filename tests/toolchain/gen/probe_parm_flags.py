# Errata probe for toeexpand/ERRATA.md E1 (.parm mode bit 0x1000) and E2
# (Phong MAT `texture4coordnterp` typo). Runs INSIDE TouchDesigner via
# td-claude-bridge; `tests/toolchain/gen/run.sh probe_parm_flags` prepends
# `OUT_DIR = r'...'` (default tests/toolchain/runs/probe_parm_flags-<build>/).
#
# For each op type below it creates four instances — default, changed
# (every probed par set to a non-default value), restored (changed, then
# `par.val = par.default`) and reset (changed, then `par.reset()`) — records
# TouchDesigner's own view of each probed par, and saves one .tox. Expand the
# .tox and read the `.parm` modes to see what the file side says:
#
#   toeexpand probe_parm_flags.tox
#   find probe_parm_flags.tox.dir -name '*.parm' \
#     -exec awk '$2 ~ /^[0-9]+$/ && int($2/4096)%2==1 {print FILENAME": "$0}' {} +
#
# Findings at 2025.33230 (2026-09-26): bit 0x1000 is set on every probed par
# in all four variants — a static per-parameter "always written" flag, not
# value state; TD's Python API reports those pars isDefault=True, CONSTANT.

import json

import td

PROBED = {
    'geometryCOMP': ['instancetexextendu', 'instancetexextendv', 'instancetexextendw',
                     'instancetexfilter', 'instancetexanisotropy'],
    'pbrMAT': ['basecolormapextendu', 'basecolormapextendv', 'basecolormapextendw',
               'basecolormapfilter', 'basecolormapanisotropy'],
    'noisePOP': ['overrideautoattr', 'attrtype', 'attrnumcomps',
                 'attrdefaultval0', 'attrdefaultval1', 'attrdefaultval2', 'attrdefaultval3'],
    'patternPOP': ['attrnumcomps'],
}
VARIANTS = ['default', 'changed', 'restored', 'reset']
ATTRS = ['val', 'default', 'isDefault', 'mode', 'expr', 'defaultExpr', 'defaultMode',
         'style', 'readOnly', 'enable', 'isCustom', 'sequence']


def describe(p):
    d = {}
    for a in ATTRS:
        try:
            v = getattr(p, a)
            d[a] = v if isinstance(v, (int, float, str, bool, type(None))) else repr(v)
        except Exception as e:
            d[a] = f'<{type(e).__name__}>'
    return d


def other_value(p):
    if p.isMenu:
        cur = p.eval()
        return next(n for n in p.menuNames if n != cur)
    if p.isToggle:
        return not p.eval()
    if p.isNumber:
        return p.eval() + 1
    return 'x'


try:
    OUT_DIR
except NameError:
    raise RuntimeError('OUT_DIR is not defined; run via tests/toolchain/gen/run.sh')

import os
os.makedirs(OUT_DIR, exist_ok=True)

report = {'app_build': td.app.build, 'ops': {}}
root = td.op('/project1').create(td.baseCOMP, 'tc_probe_parm_flags')
try:
    for i, (optype, pars) in enumerate(PROBED.items()):
        cls = getattr(td, optype)
        report['ops'][optype] = {}
        for j, variant in enumerate(VARIANTS):
            o = root.create(cls, f'{optype}_{variant}')
            o.nodeX, o.nodeY = j * 200, -i * 200
            info = {}
            for name in pars:
                p = getattr(o.par, name, None)
                if p is None:
                    info[name] = 'MISSING'
                    continue
                err = None
                try:
                    if variant != 'default':
                        p.val = other_value(p)
                    if variant == 'restored':
                        p.val = p.default
                    if variant == 'reset':
                        p.reset()
                except Exception as e:
                    err = f'{type(e).__name__}: {e}'
                info[name] = {'after': describe(p), 'error': err}
            report['ops'][optype][variant] = info

    # E2: Phong MAT texture slot 4 coordinate-interpolation par name.
    ph = root.create(td.phongMAT, 'phong_typo_probe')
    report['phong_texture_coordinterp_names'] = sorted(
        p.name for p in ph.pars() if p.name.startswith('texture') and 'coord' in p.name
        and p.name.endswith(('interp', 'nterp')))

    root.save(OUT_DIR + '/probe_parm_flags.tox')
    report['saved'] = OUT_DIR + '/probe_parm_flags.tox'
finally:
    root.destroy()

with open(OUT_DIR + '/probe_parm_flags.json', 'w') as f:
    json.dump(report, f, indent=1, sort_keys=True, default=repr)

print('build', report['app_build'])
print('phong coordinterp names:', report['phong_texture_coordinterp_names'])
print('saved', report.get('saved'))
