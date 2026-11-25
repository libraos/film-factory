# Tidal City: the showcase run (2026-11-25)

A 30 second film at 1344x768 with a score (title card, four shots of 6, 6, 7 and 5 seconds, closing
card), made in LibraOS Next 0.3.1 in a new, empty project from two plain messages. The screen
recording of the run is cut down to `libraos_next_tidal_city_desk.mp4` and the film is
`libraos_next_tidal_city_film.mp4` (not in this repository).

**Message 1** (15:47)

> Make a 30 second opening film for Tidal City, the first city built on the open ocean, opening in
> 2040. Four shots: dive through sunrise clouds to reveal a city of white towers and hanging gardens
> rising out of the sea; race low over the water as a fleet of tall sailing ships streams into the
> harbour; climb the tallest tower past gardens and waterfalls all the way to the top; then pull
> back at dusk as the whole city lights up. Open with a title card that says Tidal City and close
> with one that says The ocean is open. 2040. Make it big, bright and awe-inspiring, with music.

The agent picked up the film-production skill, set the project up, wrote the brief, the concept and
four shots, chose the score from the team library, made eight keyframes itself (no worker for this
stage), showed them as a storyboard with both title cards and asked "Shall I render the 30-second
film from these keyframes, with music and your exact title cards?" (about 6 minutes).

**Message 2** (15:56)

> Wow, these look great. Go ahead and make the film.

The agent handed stage 2 to one LibraOS Engine worker with a 115 minute budget. The worker rendered
the four shots one at a time at 1344x768 and checked each contact sheet:

| Shot | Length | Render | Worker's note |
| --- | --- | --- | --- |
| sunrise-dive | 6 s | about 14 min | coherent cloud reveal toward the harbour |
| harbour-race | 6 s | about 15 min | fleet heads inward; possible ship shape artifacts in close passes (second take kept) |
| tower-climb | 7 s | about 21 min | reaches the summit; brief change in spire shape at the crest (second take kept) |
| dusk-pullback | 5 s | about 12 min | usable, brief crop of the crown |

It built the film with both cards and the score, decoded all 720 frames, checked that the score
spans the 30 seconds, and committed a first cut that passed the final check 64 minutes after
message 2 (17:00). It then rendered second takes of the two flagged shots, tower (about 20 min)
and harbour (about 15 min), compared the sheets, kept both second takes with the first sunrise and
dusk takes, rebuilt the film and passed the final check again. The final cut was ready 99 minutes
after message 2 (17:35), within the budget; the agent reported it to the person at 17:37.

What is here: the brief, `concept.md`, `shots.json`, `scenes.json`, the eight keyframes and the
contact sheets (as JPEG copies to keep the repository small).

Notes from the run:

- The worker extended `skills/film-production/scripts/film.py`, and the change is now in the skill (with a test in
  `skills/film-production/tests/test_film.py`): contact sheets sample 24 tiles across the whole clip, so the last scene is
  always on the film's sheet; `scenes.json` may give the film's frame size (`"size": "1344x768"`;
  default 1920x1080); the score is cut to the exact film length.
- `shots.json` still lists seed 1 for every shot; the kept harbour and tower takes are seed 2.
- Motion, pacing and sound are for a person to judge.
- The score came from `FILM_MUSIC_DIR`, a folder of instrumental tracks the team may use; there is
  no score generation in the kit.
- Endpoints in this run: video straight to the render machine's `/v1/videos` adapter, images through
  a local OpenAI-shaped proxy. The gateway route was not tested.
