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

---

## Option 1: Quick paste

The fastest way to use it. No TOX required.

1. Copy `td-snapshot.py` into a **Text DAT** in your project.
2. Open **Dialogs > Textport and DATs**.
3. Run it:

```python
op('/project1/text1').run()
```

The output prints to the Textport — copy and paste it wherever you need it.

To target a specific network instead of the Text DAT's parent:

```python
snapshot_patch('/project1/mycomp')
```

---

## Option 2: TOX component (reusable, button-triggered)

A Container COMP saved as a `.tox` that you can drop into any project. Click a button, read the output from a Text DAT inside the component — no Textport needed.

### TOX structure

Build the component with these operators inside a Container COMP:

| Operator | Type | Name | Contents |
|---|---|---|---|
| Script | Text DAT | `core` | `src/core.py` |
| Script | Text DAT | `runner` | `src/tox_runner.py` |
| Output | Text DAT | `output` | *(leave empty)* |
| Trigger | Button COMP | `button` | *(any label)* |
| Events | Panel Execute DAT | `panel_exec` | *(see below)* |

### Wiring the button

1. Create a **Panel Execute DAT** inside the Container COMP.
2. In its **Panel** parameter, point it at `button`.
3. Paste the contents of `src/tox_runner.py` into it (or set its DAT parameter to `runner`).

When clicked, the button fires `onOffToOn`, which calls `snapshot_patch` on the network containing the TOX (`me.parent().parent()`) and writes the result to the `output` Text DAT.

### Saving and reusing

Right-click the Container COMP > **Save Component** to save it as a `.tox`. Drop that file into any future project from the palette or filesystem.

---

## Scope

Only the **direct children** of the target network are captured — it does not recurse into sub-networks. To snapshot a nested component, pass its path directly to `snapshot_patch()`.

OP-typed value refs are only recorded when the target operator lives within the captured network. References into `/sys/`, `/local/`, and other system paths are excluded.

---

## Repo structure

```
src/
  core.py              ← edit this — snapshot_patch() lives here
  quickpaste_runner.py ← one-liner entry point for the quick paste build
  tox_runner.py        ← Panel Execute DAT content for the TOX button
td-snapshot.py         ← BUILT — do not edit directly
build.sh               ← rebuilds td-snapshot.py from src/
```

After editing `src/core.py`, run `./build.sh` to regenerate `td-snapshot.py`. The TOX's `core` DAT reads `src/core.py` directly so it stays in sync automatically.
