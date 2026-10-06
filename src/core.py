# core.py v2.2.0 | sha256:36a6452640c5aec04a9745aba3df18fe87327f6221c524e94ae45352e6cbd1ff
import re

# Snapshot script version, surfaced in the output preamble. Synced from the
# `core.py` entry in src/versions.txt by scripts/stamp.sh — do not edit by hand.
VERSION = '2.2.0'

def op_display_type(o):
    return '{} {}'.format(o.label, o.family)

def op_label(o):
    return '{} [{}]'.format(o.path, op_display_type(o))

def walk_patch(root=None,
               include_comment=True,
               include_storage=True,
               include_bypass=True,
               include_display=True,
               include_viewer=True,
               include_render=True,
               include_dat_text=True,
               dat_text_truncate=None):
    if root is None:
        root_op = me.parent()
    else:
        root_op = op(root)
    ops = [root_op] + list(root_op.findChildren(includeUtility=True))

    # Exclude the component containing this script from the snapshot.
    # Walk up from me to find its direct child of root_op, then drop that subtree.
    self_op = me
    while self_op.parent() is not None and self_op.parent() != root_op:
        self_op = self_op.parent()
    if self_op.parent() == root_op:
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
    # to a full operator path. Tries owner-relative, then absolute resolution.
    def op_refs_from_expr(expr, owner):
        refs = []
        for m in re.finditer(r"op\((['\"])(.*?)\1\)", expr):
            raw = m.group(2)
            target = op(owner.path + '/' + raw) or owner.op(raw) or op(raw)
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
                if hasattr(o, 'display') and o.display is False:
                    flags['display'] = False
            except:
                pass
        if include_render:
            try:
                if hasattr(o, 'render') and o.render is False:
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


def render_blocks(nodes, wire_edges, ref_edges, op_by_path):
    # Per-node-block format. See project_per_node_block_format memory for design rationale.
    # Sequential IDs (n1, n2, ...) assigned in walk order; out-of-network ref/wire targets
    # get IDs continuing past in-network nodes, declared as bare lines at the bottom.

    id_by_path = {n['path']: 'n{}'.format(i + 1) for i, n in enumerate(nodes)}

    in_network = set(id_by_path)
    extra_paths = set()
    for src, dst, _, _ in wire_edges:
        if src not in in_network: extra_paths.add(src)
        if dst not in in_network: extra_paths.add(dst)
    for src, dst, _ in ref_edges:
        if src not in in_network: extra_paths.add(src)
        if dst not in in_network: extra_paths.add(dst)
    extra_sorted = sorted(extra_paths)
    for i, p in enumerate(extra_sorted):
        id_by_path[p] = 'n{}'.format(len(nodes) + 1 + i)

    wires_by_dst = {}
    for src, dst, in_idx, out_idx in wire_edges:
        wires_by_dst.setdefault(dst, []).append((in_idx, src, out_idx))
    refs_by_src = {}
    for src, dst, par_name in ref_edges:
        refs_by_src.setdefault(src, []).append((par_name, dst))

    def label_for(path):
        o = op_by_path.get(path)
        return op_label(o) if o else path

    def fmt_par(par):
        s = '  {} = {!r} (default {!r}'.format(par['name'], par['current'], par['default'])
        if par['mode'] != 'CONSTANT':
            s += ', {}'.format(par['mode'])
        if par['expr']:
            s += ', expr={!r}'.format(par['expr'])
        return s + ')'

    lines = ['# td-snapshot v{} — each node block: changed pars, "in[N] <- src" for incoming wires, "ref par -> target" for parameter refs, "storage key = value" for op.store() data.'.format(VERSION)]

    for n in nodes:
        nid = id_by_path[n['path']]
        lines.append('')
        lines.append('{} = {}'.format(nid, n['label']))
        if 'comment' in n:
            lines.extend(_fmt_comment_block(n['comment']))
        if 'flags' in n:
            lines.append('  flags: ' + _fmt_flags(n['flags']))
        for key, summary in n.get('storage', []):
            lines.append('  storage {} = {}'.format(key, summary))
        for par in n['pars']:
            lines.append(fmt_par(par))
        for in_idx, src_path, out_idx in sorted(wires_by_dst.get(n['path'], [])):
            src_id = id_by_path.get(src_path, src_path)
            if out_idx is not None and out_idx != 0:
                lines.append('  in[{}] <- {} [out:{}]'.format(in_idx, src_id, out_idx))
            else:
                lines.append('  in[{}] <- {}'.format(in_idx, src_id))
        for par_name, target_path in sorted(refs_by_src.get(n['path'], [])):
            target_id = id_by_path.get(target_path, target_path)
            lines.append('  ref {} -> {}'.format(par_name, target_id))
        if 'dat_text' in n:
            lines.append('  dat_text:')
            lines.extend(_fmt_dat_text_block(n['dat_text']))

    for p in extra_sorted:
        lines.append('')
        lines.append('{} = {}'.format(id_by_path[p], label_for(p)))

    return '\n'.join(lines)


def snapshot_patch(root=None,
                   include_comment=True,
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
        include_storage=include_storage,
        include_bypass=include_bypass,
        include_display=include_display,
        include_viewer=include_viewer,
        include_render=include_render,
        include_dat_text=include_dat_text,
        dat_text_truncate=dat_text_truncate,
    )
    return render_blocks(nodes, wire_edges, ref_edges, op_by_path)
