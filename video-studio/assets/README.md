# Assets

This directory is intentionally provider-neutral.

The renderer automatically uses files named `scene_01` through `scene_15` when present:

- `scene_XX.mp4`, `.mov`, `.webm` -> real B-roll / footage
- `scene_XX.jpg`, `.jpeg`, `.png`, `.webp` -> documentary still / generated academic visual
- `music.mp3` -> optional background score

If a scene has no external asset, the renderer creates a clean academic motion card from `project.json`, so production never stops because an asset is missing.

Primary footage sources for this project: Pexels and Pixabay, selected only when their license allows the intended use. Visuals generated specifically for the project can also be placed here.
