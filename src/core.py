# core.py v1.2.0 | sha256:d32216054b79ff555e6dfdf18cefc0f42033aa05d38c4687d1c71cad5b1f325b
import re

def op_display_type(o):
    return '{} {}'.format(o.label, o.family)

def op_label(o):
    return '{} [{}]'.format(o.path, op_display_type(o))

def walk_patch(root=None):
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

            if changed:
                pars_out.append({
                    'name': p.name,
                    'current': cur,
                    'default': default,
                    'mode': mode,
                    'expr': expr_text,
                })

        nodes.append({
            'path': o.path,
            'label': op_label(o),
            'input_slots': input_slots,
            'outputs': outputs,
            'pars': pars_out,
            'refs': sorted(local_refs),
        })

    return nodes, wire_edges, ref_edges, op_by_path


def render_legacy(nodes, wire_edges, ref_edges, op_by_path):
    def fmt_wire(src_path, dst_path, in_idx, out_idx):
        src_o = op_by_path.get(src_path)
        dst_o = op_by_path.get(dst_path)
        src_label = op_label(src_o) if src_o else src_path
        dst_label = op_label(dst_o) if dst_o else dst_path
        if out_idx is not None and out_idx != 0:
            slot = 'out:{}, in:{}'.format(out_idx, in_idx)
        else:
            slot = 'in:{}'.format(in_idx)
        return '  {} -[{}]-> {}'.format(src_label, slot, dst_label)

    def fmt_ref(src_path, dst_path, par_name):
        src_o = op_by_path.get(src_path)
        dst_o = op_by_path.get(dst_path)
        src_label = op_label(src_o) if src_o else src_path
        dst_label = op_label(dst_o) if dst_o else dst_path
        return '  {} -[{}]-> {}'.format(src_label, par_name, dst_label)

    node_blocks = []
    for n in nodes:
        block = [n['label']]

        if n['input_slots']:
            block.append('  input_slots:')
            for idx, path in n['input_slots']:
                block.append('    [{}] {}'.format(idx, path))
        else:
            block.append('  input_slots: (none)')

        block.append('  outputs: ' + (', '.join(n['outputs']) if n['outputs'] else '(none)'))

        for par in n['pars']:
            line = '  par {}: current={!r}, default={!r}, mode={}'.format(
                par['name'], par['current'], par['default'], par['mode']
            )
            if par['expr']:
                line += ' | expr={!r}'.format(par['expr'])
            block.append(line)

        if n['refs']:
            block.append('  refs:')
            for par_name, ref_path in n['refs']:
                block.append('    {} -> {}'.format(par_name, ref_path))

        if not n['pars']:
            block.append('  par (no changed parameters found)')

        node_blocks.append('\n'.join(block))

    lines = []
    lines.append('WIRE EDGES')
    for src, dst, in_idx, out_idx in sorted(wire_edges):
        lines.append(fmt_wire(src, dst, in_idx, out_idx))
    if not wire_edges:
        lines.append('  (none)')

    lines.append('')
    lines.append('REFERENCE EDGES')
    for src, dst, par_name in sorted(ref_edges):
        lines.append(fmt_ref(src, dst, par_name))
    if not ref_edges:
        lines.append('  (none)')

    lines.append('')
    lines.append('NODES')
    lines.append('')
    lines.extend(node_blocks)

    return '\n\n'.join(lines)


def snapshot_patch(root=None):
    nodes, wire_edges, ref_edges, op_by_path = walk_patch(root)
    return render_legacy(nodes, wire_edges, ref_edges, op_by_path)
