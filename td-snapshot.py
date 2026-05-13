# td_patch_dump.py
# Dumps a structural and parametric summary of a TouchDesigner network to text.
#
# Outputs three sections:
#   WIRE EDGES      - operator wire connections with input slot indices
#   REFERENCE EDGES - parameter-driven dependencies (expressions + OP-typed values)
#   NODES           - per-operator block: input slots, outputs, changed parameters, refs
#
# A parameter is considered "changed" if its current value differs from its default,
# or if its mode is EXPRESSION, EXPORT, or BIND.
#
# OP-typed parameters set by value (e.g. Feedback TOP's "top" parameter) are also
# captured as reference edges, provided the target is within the dumped network.
#
# Usage: place in a Text DAT. Open Dialogs > Textport and DATs, then run:
#        op('/project1/text1').run()
#        Replace 'text1' with whatever you named the DAT.
#        Captures me.parent() by default; pass an explicit path to snapshot_patch('/some/path') to override.

import re

def op_display_type(o):
    # Use TD's built-in label (e.g. 'Keyboard In') combined with family (e.g. 'CHOP').
    return '{} {}'.format(o.label, o.family)

def op_label(o):
    # Format an operator as: /path/name [Display Type]
    return '{} [{}]'.format(o.path, op_display_type(o))

def snapshot_patch(root=None):
    if root is None:
        root_op = me.parent()
    else:
        root_op = op(root)
    ops = [root_op] + list(root_op.findChildren(depth=1, maxDepth=1, includeUtility=True))

    # Build a lookup from path -> op for type-tagging edges later.
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
        # outputs preserved in index order (not sorted)

        # Node block header includes operator type.
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

            # Expression ref discovery: scan the expression string for op() calls.
            if expr_text:
                for ref in op_refs_from_expr(expr_text, o):
                    local_refs.add((p.name, ref))
                    ref_edges.add((o.path, ref, p.name))
            elif mode == 'CONSTANT' and hasattr(cur, 'path'):
                # OP-typed value ref discovery: parameter holds an operator object directly
                # (e.g. Feedback TOP's "top" parameter pointing to comp1 by value, not expression).
                # Only record if the target is within the dumped network; filters out /sys/* etc.
                if cur.path == root_op.path or cur.path.startswith(root_op.path + '/'):
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
        # Format a wire edge. Output slot only shown when non-zero (multiple output case).
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
        # Format a reference edge with type tags on both ends.
        src_o = op_by_path.get(src_path)
        dst_o = op_by_path.get(dst_path)
        src_label = op_label(src_o) if src_o else src_path
        dst_label = op_label(dst_o) if dst_o else dst_path
        return '  {} -[{}]-> {}'.format(src_label, par_name, dst_label)

    # Section 1: all wire connections across the network, sorted for stable output.
    lines = []
    lines.append('WIRE EDGES')
    for src, dst, in_idx, out_idx in sorted(wire_edges):
        lines.append(fmt_wire(src, dst, in_idx, out_idx))
    if not wire_edges:
        lines.append('  (none)')

    lines.append('')
    # Section 2: parameter-driven dependencies (expressions and OP-typed values).
    lines.append('REFERENCE EDGES')
    for src, dst, par_name in sorted(ref_edges):
        lines.append(fmt_ref(src, dst, par_name))
    if not ref_edges:
        lines.append('  (none)')

    lines.append('')
    # Section 3: per-operator blocks with slots, outputs, changed params, and refs.
    lines.append('NODES')
    lines.append('')
    lines.extend(node_blocks)

    return '\n\n'.join(lines)

print(snapshot_patch())
