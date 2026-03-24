# Legend style dialog behavior

This note documents the legend right-click editor introduced in `figure_legend.py`.

## Interaction model

The legend style editor now behaves like a conventional modal dialog:

- Right-clicking a legend marker opens the dialog for that plot.
- **OK** applies the pending edits and closes the dialog.
- **Cancel**, the close icon, **Escape**, and clicking the backdrop dismiss the dialog without applying pending edits.

The dialog keeps its edits local until confirmation. This avoids rewriting unrelated plot style fields while the user is still editing.

## Color control

The previous free-form text field has been replaced with a graphical `ColorPicker`, which delegates to the browser's native color chooser.

Internally the dialog normalizes the plot's current color to `#rrggbb` for the picker while preserving untouched plot fields exactly as-is.

## Frontend bridge responsibilities

`_LegendInteractionBridge` owns the browser-only behavior that Python widgets cannot observe directly:

- intercepting right-clicks inside the figure root
- wiring Escape and backdrop dismissal
- focus entry / focus return for the modal dialog
- ARIA labels for the dialog and its controls

This keeps `LegendPanelManager` focused on plot state and widget synchronization.

## Plot-id transport

Legend rows encode plot ids into reversible, class-safe tokens before sending them through DOM class names. This avoids failures for plot ids containing spaces or punctuation.

## Regression coverage

The repository now includes focused tests for:

- encoded plot-id round-tripping for context-menu open requests
- OK-only application of pending edits
- Escape-driven dismissal without side effects
- color normalization for the graphical picker
