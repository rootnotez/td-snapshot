# td-snapshot.py — BUILT FILE. Do not edit directly.
# Edit src/core.py, then run ./build.sh to regenerate.
#
# USAGE: Paste into a Text DAT, then RIGHT-CLICK the DAT > Run Script.
# Captures the network containing this DAT (me.parent()) by default.
# To target a different network: snapshot_patch('/project1/some/comp')

import re

def op_display_type(o):
    return '{} {}'.format(o.label, o.family)

def op_label(o):
    return '{} [{}]'.format(o.path, op_display_type(o))

def snapshot_patch(root=None):
    if root is None:
        root_op = me.parent()
    else:
        root_op = op(root)
    ops = [root_op] + list(root_op.findChildren(includeUtility=True))

    op_by_path = {o.path: o for o in ops}

    wire_edges = set()
    ref_edges = set()
    node_blocks = []

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

        block = [op_label(o)]

        if input_slots:
            block.append('  input_slots:')
            for idx, path in input_slots:
                block.append('    [{}] {}'.format(idx, path))
        else:
            block.append('  input_slots: (none)')

        block.append('  outputs: ' + (', '.join(outputs) if outputs else '(none)'))

        found_any = False

        for p in o.pars():
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

            # A parameter is "changed" if its evaluated value differs from the default,
            # or if it is driven by an expression, export, or bind (regardless of value).
            changed = (cur != default) or (mode in ('EXPRESSION', 'EXPORT', 'BIND'))

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
                # Only record if the target is within the captured network.
                local_refs.add((p.name, cur.path))
                ref_edges.add((o.path, cur.path, p.name))

            if changed:
                found_any = True
                block.append(
                    '  par {}: current={!r}, default={!r}, mode={}'.format(
                        p.name, cur, default, mode
                    ) + (' | expr={!r}'.format(expr_text) if expr_text else '')
                )

        if local_refs:
            block.append('  refs:')
            for par_name, ref_path in sorted(local_refs):
                block.append('    {} -> {}'.format(par_name, ref_path))

        if not found_any:
            block.append('  par (no changed parameters found)')

        node_blocks.append('\n'.join(block))

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

import datetime
result = snapshot_patch()
name = 'td_snapshot_' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
out = me.parent().create(textDAT, name)
out.text = result
out.openViewer(unique=True, borders=True)
