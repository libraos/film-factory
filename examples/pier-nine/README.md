# Pier Nine: the test run (2026-11-25)

A 20 second film (title card, two 7 second shots, closing card, with a score) made in
LibraOS Next 0.3.1 in a new, empty project from two plain messages. The screen recording of the
run is cut down to `libraos_next_pier_nine_desk.mp4` and the film is `libraos_next_pier_nine_film.mp4`
(not in this repository).

**Message 1** (14:25)

> Make a 20 second opening film for Pier Nine, a small floating sauna on a quiet fjord. It's a dark
> timber cabin on a pontoon with one big window facing the water, and it opens in June. Two shots:
> gliding over still water at dawn toward the cabin, then inside with the warm timber benches,
> looking out through the window. Start with a title card that says Pier Nine and end with one that
> says Opens in June. Calm and bright, no people.

The agent picked up the film-production skill, set the project up and wrote the brief, then handed
stage 1 to a LibraOS Engine worker, which wrote the concept and the shot list, made four keyframes
and passed the plan check in 3 minutes. The agent showed the keyframes and asked "Shall I make the
20-second film from these?" (5 minutes 21 seconds after message 1).

**Message 2** (14:30)

> These look good. Go ahead and make the film.

The agent handed stage 2 to one worker, which:

- rendered the exterior shot at 1344x768 (about 20 minutes), found a double image near its end on
  the contact sheet and decided to retry it;
- rendered the interior shot at 1344x768 (about 20 minutes) and kept it;
- rendered the exterior again with seed 2 at 896x512 to leave time for review (about 7 minutes)
  and kept that take;
- took the opening of the one instrumental score in the team library, built the film and passed
  the final check.

The film was delivered 48 minutes 27 seconds after message 2 (15:19), within the worker's
65 minute budget.

What is here: the brief, `concept.md`, `shots.json`, `scenes.json`, the four keyframes and the
contact sheets (as JPEG copies to keep the repository small). Clips and the film are not committed.

Notes from the run:

- The agent reported one limitation: a slight shift of the exterior shoreline remains. Motion,
  pacing and sound are for a person to judge.
- The two shots are at different render sizes (exterior 896x512, interior 1344x768); the build
  scales both to the film size. `shots.json` still lists seed 1 for the exterior; the kept take
  was seed 2.
- `skills/film-production/scripts/film.py` needed no changes in this run.
- Workers need network access for the image and video endpoints
  (`libraos-core config set dispatch.codex_network true`, once per machine).
- Endpoints in this run: video straight to the render machine's `/v1/videos` adapter, images through
  a local OpenAI-shaped proxy. The gateway route was not tested.
