# Project 057 / Phase 003 runtime probes on the original repo

These notes capture a few direct runtime checks run against the original repository to confirm that the structural findings in the Phase 003 blueprint also show up in behavior.

## Probe 1: two views, two plots, one legend surface
A figure was created with two views and one plot assigned to each view.

Observed results:

- global plot registrations: `p1 -> ('main',)`, `p2 -> ('second',)`
- layout section ids still exposed only one `legend`, one `parameters`, and one `info` surface
- the legend contained rows for the active view only
- switching from `main` to `second` changed visible legend rows from `['p1']` to `['p2']`

Interpretation:

The legend is one global presentation filtered by active view. It is not an independently mountable filtered presentation over the global plot set.

## Probe 2: two info cards, one shared info box
A figure was created and two simple info cards were added with different `view=` values.

Observed results:

- both info cards were appended into the same `InfoPanelManager._layout_box.children`
- switching the active view only changed each card’s `layout.display`
- one card became `block/none` while the other became `none/block`

Interpretation:

Info content is still modeled as children of one global box, with active view acting as the visibility gate.

## Probe 3: shell surfaces remain singleton even when plot membership differs
The same figure layout snapshot still reported singleton shell surfaces for legend, parameters, and info even though plot membership differed across views.

Interpretation:

The shell is still organized around singleton panel categories, while plot membership differences are handled later by active-view filtering inside legend/info behavior.
