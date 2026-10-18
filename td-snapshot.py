# td-snapshot.py — BUILT FILE. Do not edit directly.
# Edit src/core.py, then run ./scripts/build.sh to regenerate.
#
# USAGE: Paste into a Text DAT, then RIGHT-CLICK the DAT > Run Script.
# Captures the network containing this DAT (me.parent()) by default.
# To target a different network: snapshot_patch('/project1/some/comp')

# core.py v3.1.0 | sha256:5ef5dd3561ccf006c40c4623ac1c871ee48becf6add929a71e48e03b526f356b
import re

# Snapshot script version, surfaced in the output preamble. Synced from the
# `core.py` entry in src/versions.txt by scripts/stamp.sh — do not edit by hand.
VERSION = '3.1.0'

def op_display_type(o):
    return '{} {}'.format(o.label, o.family)

def op_label(o):
    return '{} [{}]'.format(o.path, op_display_type(o))

# Display/Render exist as attributes on every OP, so hasattr() cannot tell whether
# a flag is meaningful. Per the TD docs (Display_Flag, Render_Flag, Flag; build
# 2025.33230): Display is on TOPs, CHOPs, SOPs, POPs and Object COMPs (Geometry,
# Camera, Light, Null, ...); Render is on SOPs, POPs and Object COMPs. Plain
# Container/Base COMPs, DATs and MATs have neither. Object COMPs are detected via
# op.isObject, not by family (their family is just 'COMP').
_DISPLAY_FAMILIES = ('TOP', 'CHOP', 'SOP', 'POP')
_RENDER_FAMILIES = ('SOP', 'POP')


def _flag_applies(o, families):
    try:
        return o.family in families or bool(o.isObject)
    except:
        return False


def walk_patch(root=None,
               include_comment=True,
               include_tags=True,
               include_storage=True,
               include_bypass=True,
               include_display=True,
               include_viewer=True,
               include_render=True,
               include_dat_text=True,
               dat_text_truncate=None):
    # `me` only exists when run from a DAT script; callers elsewhere (textport,
    # extensions, external exec) must pass a root and get no self-exclusion.
    try:
        self_op = me
    except NameError:
        self_op = None
    if root is None:
        if self_op is None:
            raise ValueError('walk_patch: no `me` available, pass a root path, e.g. snapshot_patch(\'/project1\')')
        root_op = self_op.parent()
    else:
        root_op = op(root)
    # A non-COMP root (e.g. a single MAT) has no children to walk.
    ops = [root_op] + (list(root_op.findChildren(includeUtility=True)) if root_op.isCOMP else [])

    # Exclude the component containing this script from the snapshot.
    # Walk up from me to find its direct child of root_op, then drop that subtree.
    while self_op is not None and self_op.parent() is not None and self_op.parent() != root_op:
        self_op = self_op.parent()
    if self_op is not None and self_op.parent() == root_op:
        exclude = {self_op.path}
        try:
            for child in self_op.findChildren(includeUtility=True):
                exclude.add(child.path)
        except:
            pass
        ops = [o for o in ops if o.path not in exclude]

    op_by_path = {o.path: o for o in ops}

    wire_edges = set()
    ref_edges = set()
    nodes = []

    # Regex-scan an expression string for op('name') patterns and resolve each
    # to a full operator path. TD evaluates a bare op('X') in a parameter
    # expression against the network containing the owner (its siblings), so
    # try the owner's parent first. A COMP owner's own children must not
    # shadow a sibling of the same name. owner.op() keeps '../x' style paths
    # resolving as before; op(raw) handles absolute paths and shortcuts.
    def op_refs_from_expr(expr, owner):
        refs = []
        for m in re.finditer(r"op\((['\"])(.*?)\1\)", expr):
            raw = m.group(2)
            par = owner.parent()
            target = (par.op(raw) if par is not None else None) or owner.op(raw) or op(raw)
            refs.append(target.path if target is not None else raw)
        return sorted(set(refs))

    for o in ops:
        input_slots = []
        outputs = []
        local_refs = set()
        pars_out = []

        # Collect incoming wire connections with their slot indices.
        # Slot order matters for operators like Composite TOP.
        try:
            for idx, src in enumerate(o.inputs):
                if src is not None:
                    input_slots.append((idx, src.path))
                    # Also record which output connector on the source this wire leaves from.
                    out_idx = None
                    try:
                        for oc_idx, oc in enumerate(src.outputConnectors):
                            for conn in oc.connections:
                                if conn.owner.path == o.path:
                                    out_idx = oc_idx
                                    break
                            if out_idx is not None:
                                break
                    except:
                        pass
                    wire_edges.add((src.path, o.path, idx, out_idx))
        except:
            pass

        try:
            for dst in o.outputs:
                if dst is not None:
                    outputs.append(op_label(dst))
        except:
            pass

        input_slots = sorted(set(input_slots), key=lambda x: (x[0], x[1]))

        for p in o.pars():
            if p.name == 'pageindex':
                continue

            try:
                mode = str(p.mode).split('.')[-1]
            except:
                mode = 'UNKNOWN'

            try:
                cur = p.eval()
            except:
                try:
                    cur = p.val
                except:
                    cur = '<unreadable>'

            try:
                default = p.default
            except:
                continue

            try:
                changed = not p.isDefault
            except:
                changed = (cur != default) or (mode in ('EXPRESSION', 'EXPORT', 'BIND'))

            if changed and mode == 'CONSTANT':
                def _empty(v): return v is None or v == ''
                if cur == default or (_empty(cur) and _empty(default)):
                    changed = False

            expr_text = None
            try:
                if mode == 'EXPRESSION' and p.expr:
                    expr_text = p.expr
            except:
                pass

            try:
                if hasattr(p, 'bindExpr') and p.bindExpr:
                    expr_text = p.bindExpr
            except:
                pass

            if expr_text:
                for ref in op_refs_from_expr(expr_text, o):
                    local_refs.add((p.name, ref))
                    ref_edges.add((o.path, ref, p.name))
            elif mode == 'CONSTANT' and hasattr(cur, 'path'):
                # OP-typed value ref: parameter holds an operator object directly
                # (e.g. Feedback TOP's "top" parameter pointing to a comp by value).
                local_refs.add((p.name, cur.path))
                ref_edges.add((o.path, cur.path, p.name))
            elif mode == 'CONSTANT' and isinstance(cur, (list, tuple)):
                # Multi-OP-valued parameter: list of OP references.
                # Composite TOP 'tops', Switch TOP, Select TOP 'chops', Merge CHOP
                # family, Cross TOP, etc. Each OP-typed element gets its own ref edge.
                for item in cur:
                    if hasattr(item, 'path'):
                        local_refs.add((p.name, item.path))
                        ref_edges.add((o.path, item.path, p.name))

            if changed:
                pars_out.append({
                    'name': p.name,
                    'current': cur,
                    'default': default,
                    'mode': mode,
                    'expr': expr_text,
                })

        node = {
            'path': o.path,
            'label': op_label(o),
            'input_slots': input_slots,
            'outputs': outputs,
            'pars': pars_out,
            'refs': sorted(local_refs),
        }

        if include_comment:
            try:
                if o.comment:
                    node['comment'] = o.comment
            except:
                pass

        if include_tags:
            try:
                tags = sorted(str(t) for t in o.tags)
                if tags:
                    node['tags'] = tags
            except:
                pass

        flags = {}
        # Each flag emits only when diverged from the type's default:
        # bypass/viewer default False (emit when True); display/render default True (emit when False).
        if include_bypass:
            try:
                if o.bypass:
                    flags['bypass'] = True
            except:
                pass
        if include_viewer:
            try:
                if o.viewer:
                    flags['viewer'] = True
            except:
                pass
        if include_display:
            try:
                if _flag_applies(o, _DISPLAY_FAMILIES) and o.display is False:
                    flags['display'] = False
            except:
                pass
        if include_render:
            try:
                if _flag_applies(o, _RENDER_FAMILIES) and o.render is False:
                    flags['render'] = False
            except:
                pass
        if flags:
            node['flags'] = flags

        if include_storage:
            try:
                st = o.storage
                if st:
                    node['storage'] = [(str(k), _storage_summary(st[k])) for k in sorted(st, key=str)]
            except:
                pass

        if include_dat_text:
            try:
                if o.family == 'DAT':
                    txt = o.text
                    if txt:
                        if dat_text_truncate is not None and len(txt) > dat_text_truncate:
                            node['dat_text'] = {
                                'text': txt[:dat_text_truncate],
                                'truncated': True,
                                'full_len': len(txt),
                            }
                        else:
                            node['dat_text'] = {'text': txt, 'truncated': False, 'full_len': len(txt)}
            except:
                pass

        nodes.append(node)

    return nodes, wire_edges, ref_edges, op_by_path


STORAGE_ITEM_MAX = 80
STORAGE_LINE_MAX = 300


def _unwrap_dependency(v):
    # tdu.Dependency wraps the real value, sometimes many layers deep.
    for _ in range(100):
        if type(v).__name__ != 'Dependency' or not hasattr(v, 'val'):
            break
        v = v.val
    return v


def _storage_scalar(v):
    """One short, deterministic text for a stored value; None for containers."""
    v = _unwrap_dependency(v)
    if hasattr(v, 'path') and hasattr(v, 'OPType'):
        return 'op({!r})'.format(v.path)
    if hasattr(v, 'items') or isinstance(v, (list, tuple, set, frozenset)):
        return None
    # Drop memory addresses so the same object prints the same way every run.
    s = re.sub(r' at 0x[0-9A-Fa-f]+', '', repr(v))
    return s if len(s) <= STORAGE_ITEM_MAX else s[:STORAGE_ITEM_MAX] + '…'


def _storage_count(v):
    v = _unwrap_dependency(v)
    try:
        n = len(v)
    except:
        return '{...}'
    text = '{} item{}'.format(n, '' if n == 1 else 's')
    return '{' + text + '}' if hasattr(v, 'items') else '[' + text + ']'


def _storage_summary(v):
    """A stored value in one line: mappings show their scalar fields and
    count nested containers; long text is cut, with its full length given."""
    v = _unwrap_dependency(v)
    one = _storage_scalar(v)
    if one is not None:
        return one
    if hasattr(v, 'items'):
        parts = []
        for k in sorted(v.keys(), key=str):
            item = _storage_scalar(v[k])
            parts.append('{}: {}'.format(k, item if item is not None else _storage_count(v[k])))
        s = '{' + ', '.join(parts) + '}'
    else:
        items = sorted(v, key=lambda x: str(_storage_scalar(x))) if isinstance(v, (set, frozenset)) else list(v)
        texts = [_storage_scalar(x) for x in items]
        if any(t is None for t in texts):
            return _storage_count(v)
        s = '[' + ', '.join(texts) + ']'
    if len(s) > STORAGE_LINE_MAX:
        s = '{}… ({} chars)'.format(s[:STORAGE_LINE_MAX], len(s))
    return s


def _fmt_flags(flags):
    return ', '.join('{}={}'.format(k, flags[k]) for k in sorted(flags))


def _fmt_dat_text_block(dat_text, indent='    '):
    lines = []
    for line in dat_text['text'].splitlines():
        lines.append(indent + line)
    if dat_text['truncated']:
        lines.append(indent + '(truncated, {} chars total)'.format(dat_text['full_len']))
    return lines


def _fmt_comment_block(comment, indent='    '):
    lines = comment.splitlines()
    if len(lines) <= 1:
        return ['  comment: {}'.format(comment)]
    out = ['  comment:']
    for line in lines:
        out.append(indent + line)
    return out


def _fmt_tags(tags):
    # Tags are comma-separated; a tag with whitespace, a comma or a quote is shown
    # as a Python repr so the list stays unambiguous. Plain tags stay bare.
    return ', '.join(t if t and not any(c.isspace() or c in ',\'"' for c in t) else repr(t)
                     for t in tags)


def render_blocks(nodes, wire_edges, ref_edges, op_by_path):
    # Per-node-block format. See project_per_node_block_format memory for design rationale.
    # Operators are named by their path relative to the root (the first block, which
    # keeps its absolute path), in headers, wires and refs alike. Positional IDs
    # (n1, n2, ...) renumbered every later block when one operator was added, so most
    # of a snapshot diff was renumbering; a path only changes when its operator moves.
    # An absolute path is the root or outside it; <unresolved X> is an op('X') in an
    # expression that resolved to no operator.

    root_path = nodes[0]['path'] if nodes else ''
    prefix = root_path.rstrip('/') + '/'
    in_network = {n['path'] for n in nodes}

    def name_for(path):
        if path != root_path and path in in_network and path.startswith(prefix):
            return path[len(prefix):]
        if path.startswith('/'):
            return path
        return '<unresolved {}>'.format(path)

    wires_by_dst = {}
    for src, dst, in_idx, out_idx in wire_edges:
        wires_by_dst.setdefault(dst, []).append((in_idx, src, out_idx))
    refs_by_src = {}
    for src, dst, par_name in ref_edges:
        refs_by_src.setdefault(src, []).append((par_name, dst))

    def fmt_par(par):
        s = '  {} = {!r} (default {!r}'.format(par['name'], par['current'], par['default'])
        if par['mode'] != 'CONSTANT':
            s += ', {}'.format(par['mode'])
        if par['expr']:
            s += ', expr={!r}'.format(par['expr'])
        return s + ')'

    lines = ['# td-snapshot v{} — each node block: "path [type]" (relative to the first block\'s path), changed pars, "in[N] <- src" for incoming wires, "ref par -> target" for parameter refs, "storage key = value" for op.store() data, "tags: a, b" for operator tags (a tag with spaces, commas or quotes is shown quoted).'.format(VERSION)]

    for n in nodes:
        lines.append('')
        lines.append(name_for(n['path']) + n['label'][len(n['path']):])
        if 'comment' in n:
            lines.extend(_fmt_comment_block(n['comment']))
        if n.get('tags'):
            lines.append('  tags: ' + _fmt_tags(n['tags']))
        if 'flags' in n:
            lines.append('  flags: ' + _fmt_flags(n['flags']))
        for key, summary in n.get('storage', []):
            lines.append('  storage {} = {}'.format(key, summary))
        for par in n['pars']:
            lines.append(fmt_par(par))
        for in_idx, src_path, out_idx in sorted(wires_by_dst.get(n['path'], []), key=lambda w: (w[0], w[1], w[2] or 0)):
            if out_idx is not None and out_idx != 0:
                lines.append('  in[{}] <- {} [out:{}]'.format(in_idx, name_for(src_path), out_idx))
            else:
                lines.append('  in[{}] <- {}'.format(in_idx, name_for(src_path)))
        for par_name, target_path in sorted(refs_by_src.get(n['path'], [])):
            lines.append('  ref {} -> {}'.format(par_name, name_for(target_path)))
        if 'dat_text' in n:
            lines.append('  dat_text:')
            lines.extend(_fmt_dat_text_block(n['dat_text']))

    return '\n'.join(lines)


def snapshot_patch(root=None,
                   include_comment=True,
                   include_tags=True,
                   include_storage=True,
                   include_bypass=True,
                   include_display=True,
                   include_viewer=True,
                   include_render=True,
                   include_dat_text=True,
                   dat_text_truncate=None):
    nodes, wire_edges, ref_edges, op_by_path = walk_patch(
        root,
        include_comment=include_comment,
        include_tags=include_tags,
        include_storage=include_storage,
        include_bypass=include_bypass,
        include_display=include_display,
        include_viewer=include_viewer,
        include_render=include_render,
        include_dat_text=include_dat_text,
        dat_text_truncate=dat_text_truncate,
    )
    return render_blocks(nodes, wire_edges, ref_edges, op_by_path)

# quickpaste_runner.py v1.0.0 | sha256:483271940e07bb28d1b4f896443f8b6034e5edea57ed352887f31bce7e04eb91
import datetime
result = snapshot_patch()
name = 'td_snapshot_' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
out = me.parent().create(textDAT, name)
out.text = result
out.openViewer(unique=True, borders=True)
