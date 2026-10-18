# core.py v3.2.0 | sha256:908c0cf6bf3e6b4118a2158f40b74c8c2717eb3d6c169a45b959a3d6c0c9cc6f
import hashlib
import re

# Snapshot script version, surfaced in the output preamble. Synced from the
# `core.py` entry in src/versions.txt by scripts/stamp.sh — do not edit by hand.
VERSION = '3.2.0'

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


# BEGIN GENERATED DAT TEMPLATES
# Default DAT texts TouchDesigner creates, keyed by the first 16 hex chars of
# the sha256 of the text (\r\n normalised to \n). Builds: 2025.33230.
# Generated from dat-templates/*.json by scripts/dat_templates.py gen-core.
_DAT_TEMPLATES = {
    '048965a931724b49': 'tcpipDAT callbacks',
    '08af9bf3bb043ba2': 'annotateCOMP/annotation/title/dragger/help',
    '0f6a4187266b806a': 'scriptTOP callbacks',
    '1165c7f6bab54649': 'webclientDAT callbacks',
    '14fd60afdc8d14f2': 'udpinDAT callbacks',
    '16f93718b2691cd3': 'oscinDAT callbacks',
    '1b8e965b5d5f1859': 'listCOMP callbacks',
    '2190983ebc7eb440': 'multitouchinDAT callbacks',
    '22fa94db72627f2e': 'bindCHOP callbacks',
    '232b9898e47e1920': 'glslCOMP pixel',
    '28468dd8f6c98ef2': 'buttonCOMP/parexec1',
    '28be8b0e5ef903b8': 'glslMAT pixel',
    '2977ebaad7fce510': 'glslTOP pixel or glslmultiTOP pixel',
    '29ef464313f2d50a': 'glslPOP compute',
    '2beb69cdd0ad0371': 'errorDAT callbacks',
    '2fed1a31ddf5ce49': 'usdCOMP callbacks',
    '306c2ff6e3b7a34a': 'artnetDAT callbacks',
    '3316734c1dd8995c': 'socketioDAT callbacks',
    '3376ef27d863fa3c': 'tuioinDAT callbacks',
    '358ac709021be29b': 'datexecuteDAT',
    '3cd4906b485996c4': 'bulletsolverCOMP callbacks',
    '3d0f0322e167cffe': 'folderDAT callbacks',
    '492380a939fc24c3': 'annotateCOMP/annotation/parexec1',
    '4c4ce3f41a44d2d3': 'timerCHOP callbacks',
    '545f517e56ea0566': 'scriptDAT callbacks',
    '5d520bdc200332c7': 'glslMAT vertex',
    '6916addd111d5bfc': 'scriptCHOP callbacks',
    '6942ad520c6ad42e': 'pargroupexecuteDAT',
    '759db7ee5c662e49': 'sliderCOMP/panelexec1',
    '8c98ec01bb4c94d4': 'opfindDAT callbacks',
    '8ca100258ec66e93': 'fbxCOMP callbacks',
    '9296b0d8ee312141': 'textCOMP callbacks',
    '9414eba391561cf7': 'renderpickCHOP callbacks',
    '979eb764f0fb785d': 'eventCHOP callbacks',
    'a4d2852d52bea3a4': 'blobtrackTOP callbacks',
    'a7aefd001170e0f5': 'glslTOP compute or glslmultiTOP compute',
    'a998dbb5b960826b': 'scriptSOP callbacks',
    'ad37af1f2347512a': 'annotateCOMP/annotation/title/titleText_callbacks',
    'b05115595e920e70': 'mqttclientDAT callbacks',
    'b3e4f3311c5c86bb': 'chopexecuteDAT',
    'b3e54a6759e37d62': 'websocketDAT callbacks',
    'b4c362529b3996ad': 'scriptPOP callbacks',
    'bf42c8039655af5a': 'glslcopyPOP ptCompute',
    'c0075fe5b7c1c613': 'buttonCOMP/panelexec1',
    'c85a1b89ce96ca5d': 'performDAT callbacks',
    'c9d07fd774d28fde': 'webserverDAT callbacks',
    'ce091c4ed0553904': 'ndiDAT callbacks',
    'd6dcdc48156b3310': 'keyboardinDAT callbacks',
    'd8a953673ac6b2bd': 'renderpickDAT callbacks',
    'd9db560ea1f01da4': 'glslcopyPOP primCompute',
    'da1091e23e691441': 'glslcopyPOP vertCompute',
    'e19644fa6814f860': 'gltfinCOMP callbacks',
    'e20357cd44efc512': 'lsystemSOP rules',
    'e482945cf4ff25c0': 'glsladvancedPOP compute',
    'e58d677cbc1ca00e': 'annotateCOMP/annotation/panelexec1',
    'e9cb5330c992259f': 'replicatorCOMP callbacks',
    'ea7c2148e863cbd5': 'executeDAT',
    'ee926991d760920d': 'panelexecuteDAT',
    'f02c7d8495121ec7': 'annotateCOMP/annotation/title/buttons/text1_callbacks',
    'f10d23e0629180cc': 'fifoDAT callbacks',
    'f1338b72138e4780': 'parameterexecuteDAT',
    'f4c1503a2b84f7d4': 'opexecuteDAT',
}
# END GENERATED DAT TEMPLATES


def _dat_template_hash(text):
    # Must match text_hash in scripts/dat_templates.py.
    return hashlib.sha256(text.replace('\r\n', '\n').encode('utf-8')).hexdigest()[:16]


def walk_patch(root=None,
               include_comment=True,
               include_tags=True,
               include_storage=True,
               include_bypass=True,
               include_display=True,
               include_viewer=True,
               include_render=True,
               include_dat_text=True,
               dat_text_truncate=None,
               collapse_dat_templates=True):
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
                    template = _DAT_TEMPLATES.get(_dat_template_hash(txt)) if txt and collapse_dat_templates else None
                    if template:
                        # Unchanged default text: name it instead of repeating it.
                        # The full text is in dat-templates/<build>.json.
                        node['dat_text'] = {'template': template, 'full_len': len(txt)}
                    elif txt:
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

    lines = ['# td-snapshot v{} — each node block: "path [type]" (relative to the first block\'s path), changed pars, "in[N] <- src" for incoming wires, "ref par -> target" for parameter refs, "storage key = value" for op.store() data, "tags: a, b" for operator tags (a tag with spaces, commas or quotes is shown quoted), "dat_text: (unchanged X template, N chars)" for DAT text identical to the default TouchDesigner gives X (texts listed in dat-templates/ in the td-snapshot repo).'.format(VERSION)]

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
        if 'dat_text' in n and 'template' in n['dat_text']:
            lines.append('  dat_text: (unchanged {} template, {} chars)'.format(
                n['dat_text']['template'], n['dat_text']['full_len']))
        elif 'dat_text' in n:
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
                   dat_text_truncate=None,
                   collapse_dat_templates=True):
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
        collapse_dat_templates=collapse_dat_templates,
    )
    return render_blocks(nodes, wire_edges, ref_edges, op_by_path)
