Files in this bundle
====================

1. waves2d_underwater_island_diffraction.ipynb
   Main notebook. It includes explanatory markdown, code cells, static figures,
   and embedded video outputs.

2. waves2d_underwater_island.py
   Supporting Python module containing the finite-difference operators,
   time-domain solver, frequency-domain solver, and animation helpers.

3. incoming_wave_diffraction.mp4
   Time-domain animation of a wavetrain arriving from the left and interacting
   with the underwater island.

4. steady_state_frequency_cycle.mp4
   2x2 comparison animation of monochromatic steady states for four incoming
   frequencies.

5. medium_panels.png, time_snapshots.png, steady_state_amplitudes.png,
   downstream_profiles.png
   Static figure assets used in the notebook.

Usage notes
===========

- Open the notebook in JupyterLab / Notebook in the same directory as the
  module and media files.
- The notebook is pre-populated with outputs, but the code cells are also
  provided so you can rerun or modify the experiments.
- The numerical model is a didactic shallow-water / variable-coefficient wave
  model intended for undergraduate exploration, not a production ocean model.
