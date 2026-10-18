"""Host-side helpers for the dat-templates/ record (see dat-templates/README.md).

    assemble OUT.json BATCH...   merge capture_td.py batch outputs into one per-build record
    gen-core                     regenerate the _DAT_TEMPLATES table in src/core.py from
                                 every dat-templates/<build>.json
    check                        exit 1 if src/core.py's table is out of date

Run with: uv run --no-project python scripts/dat_templates.py <command> ...
"""

import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RECORD_DIR = REPO / 'dat-templates'
CORE = REPO / 'src' / 'core.py'
MARKER = '@@DATTEMPLATES@@ '
BEGIN = '# BEGIN GENERATED DAT TEMPLATES'
END = '# END GENERATED DAT TEMPLATES'


def text_hash(text):
    # Must match _dat_template_hash in src/core.py.
    return hashlib.sha256(text.replace('\r\n', '\n').encode('utf-8')).hexdigest()


def label(op_type, role):
    if role == 'text':
        return op_type
    kind, _, rest = role.partition(':')
    return '{} {}'.format(op_type, rest) if kind == 'docked' else '{}/{}'.format(op_type, rest)


def assemble(out_path, batch_paths):
    build, types, templates, skipped, failed = None, None, [], [], {}
    for p in batch_paths:
        line = next(l for l in Path(p).read_text().splitlines() if l.startswith(MARKER))
        batch = json.loads(line[len(MARKER):])
        build, types = batch['build'], batch['types']
        for rec in batch['records']:
            if rec.get('skipped'):
                skipped.append(rec['op_type'])
            elif 'failed' in rec:
                failed[rec['op_type']] = rec['failed']
            for t in rec.get('texts', []):
                templates.append({'op_type': rec['op_type'], 'role': t['role'],
                                  'dat_type': t['dat_type'], 'sha256': text_hash(t['text']),
                                  'chars': len(t['text']), 'text': t['text']})
    record = {
        'build': build,
        'captured': datetime.date.today().isoformat(),
        'op_types': types,
        'distinct_texts': len({t['sha256'] for t in templates}),
        'templates': sorted(templates, key=lambda t: (t['op_type'], t['role'])),
        'skipped': sorted(skipped),
        'failed': dict(sorted(failed.items())),
    }
    Path(out_path).write_text(json.dumps(record, indent=1, ensure_ascii=False) + '\n')
    print('{}: build {}, {} templates ({} distinct), {} skipped, {} failed'.format(
        out_path, build, len(templates), record['distinct_texts'], len(skipped), len(failed)))


def core_block():
    labels = {}
    builds = []
    for p in sorted(RECORD_DIR.glob('*.json')):
        record = json.loads(p.read_text())
        builds.append(record['build'])
        for t in record['templates']:
            labels.setdefault(t['sha256'][:16], set()).add(label(t['op_type'], t['role']))
    lines = [BEGIN,
             '# Default DAT texts TouchDesigner creates, keyed by the first 16 hex chars of',
             '# the sha256 of the text (\\r\\n normalised to \\n). Builds: {}.'.format(', '.join(builds)),
             '# Generated from dat-templates/*.json by scripts/dat_templates.py gen-core.',
             '_DAT_TEMPLATES = {']
    for h in sorted(labels):
        lines.append("    '{}': {!r},".format(h, ' or '.join(sorted(labels[h]))))
    lines += ['}', END]
    return '\n'.join(lines)


def _current_block(src):
    m = re.search(re.escape(BEGIN) + r'.*?' + re.escape(END), src, re.S)
    if m is None:
        sys.exit('{}: no {} ... {} block'.format(CORE, BEGIN, END))
    return m


def gen_core():
    src = CORE.read_text()
    m = _current_block(src)
    CORE.write_text(src[:m.start()] + core_block() + src[m.end():])
    print('Regenerated _DAT_TEMPLATES in src/core.py')


def check():
    if _current_block(CORE.read_text()).group(0) != core_block():
        sys.exit('src/core.py _DAT_TEMPLATES is stale: run scripts/dat_templates.py gen-core')


if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'assemble':
        assemble(args[0], args[1:])
    elif cmd == 'gen-core':
        gen_core()
    elif cmd == 'check':
        check()
    else:
        sys.exit(__doc__)
