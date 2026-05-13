# td-snapshot

TouchDesigner networks are invisible to LLMs. This script captures your network as structured text — wiring, operator types, and every parameter that differs from its default — so you can paste it into a chat and get meaningful help debugging, refactoring, or explaining what a patch does.

It also works without LLMs: snapshot before and after a change and diff the output, or just audit what's actually non-default in a patch you inherited.

## What it captures

**WIRE EDGES** — every operator wire connection, annotated with input/output slot indices.

```
  /project1/blur1 [Blur TOP] -[in:0]-> /project1/out1 [Out TOP]
  /project1/noise1 [Noise TOP] -[out:1, in:0]-> /project1/comp1 [Composite TOP]
```

**REFERENCE EDGES** — parameter-driven dependencies: `op()` calls inside expressions, and OP-typed parameters set by value (e.g. a Feedback TOP's `top` parameter).

```
  /project1/feedback1 [Feedback TOP] -[top]-> /project1/render1 [Render TOP]
  /project1/math1 [Math CHOP] -[choppath]-> /project1/audioin1 [Audio In CHOP]
```

**NODES** — a per-operator block showing input slots, outputs, changed parameters, and local references.

```
/project1/blur1 [Blur TOP]
  input_slots:
    [0] /project1/noise1
  outputs: /project1/out1 [Out TOP]
  par blury: current=5.0, default=1.0, mode=CONSTANT
  par filter: current='gaussian', default='box', mode=CONSTANT
```

Only parameters that differ from their defaults are shown — or any parameter driven by an expression, export, or bind, regardless of value. Stock settings are omitted to keep the output readable.

## Setup

The script runs **inside TouchDesigner** — not as a standalone Python script. No packages or build steps needed.

1. Copy the contents of `td-snapshot.py` into a **Text DAT** inside your project.
2. Open **Dialogs > Textport and DATs**.
3. Run the DAT from the Textport:

```python
op('/project1/text1').run()
```

Replace `text1` with whatever you named the DAT. The output prints to the Textport — copy and paste it wherever you need it.

## Targeting a specific network

By default, the script captures the parent of the Text DAT (`me.parent()`). To target a different component, pass its path:

```python
# From the Textport:
snapshot_patch('/project1/mycomp')
```

Or edit the last line of the script before running:

```python
print(snapshot_patch('/project1/mycomp'))
```

## Scope

Only the **direct children** of the target network are captured — it does not recurse into sub-networks. To snapshot a nested component, pass its path directly.

OP-typed value refs are only recorded when the target operator lives within the captured network. References into `/sys/`, `/local/`, and other system paths are excluded.
