# Film project: rules for workers

This repository makes one short film from one brief. Everything goes through `python3 tools/film.py`
(`--help` lists the commands). Do not call the image or video endpoints any other way, and never
print, copy or commit a key.

## If a person asks you for the film directly

They describe the film in plain words and expect you to run the stages below without being told
how. Put their words in `film/brief.md`, hand stage 1 to one LibraOS Engine worker (30 minute budget, check
`python3 tools/film.py check plan`), show them the keyframes and ask whether to make the film, and
when they agree hand stage 2 to a worker (check `python3 tools/film.py check final`). Never ask them
for stage names, budgets or commands.

## Stages

Work stops after stage 1 until a person says the keyframes are approved.

**Stage 1, plan (check: `python3 tools/film.py check plan`)**

1. `film/concept.md`: what the film shows and why, under 250 words, from `film/brief.md`.
2. `film/shots.json`: a list of 1 to 6 shots. Each shot:
   `{"name": "kebab-case", "seconds": 5, "prompt": "...", "first": "keyframes/NAME-first.png", "last": "keyframes/NAME-last.png", "seed": 1}`.
   The prompt says what is in the picture, how the camera moves from the first frame to the last, and
   "One continuous steady camera move, no cuts."
3. Keyframes: `python3 tools/film.py keyframe keyframes/NAME-first.png "prompt"`, then make the last
   frame from the first with `--ref keyframes/NAME-first.png` so the two frames show the same place,
   light and subject. Look at every keyframe you made before going on.
4. Commit, report the keyframes, and stop. Do not render.

**Stage 2, film (check: `python3 tools/film.py check final`)**, only after approval

5. `python3 tools/film.py render NAME` for each shot, one at a time. A 5 second clip takes about
   4 minutes at 896x512 and about 18 at 1344x768; the command waits and writes `clips/NAME.mp4` and `sheets/NAME.png`.
6. Look at each contact sheet. If the subject deforms or moves backwards, render once more with
   `--seed 2` and use the better take (rename it to `clips/NAME.mp4`). Say which take you used.
7. `film/scenes.json`: `{"scenes": [{"type": "card", "kicker": "", "title": "", "sub": "", "seconds": 3}, {"type": "clip", "name": "NAME"}, ...]}`.
   Open with a title card, end with a card.
8. Score: `python3 tools/film.py music` lists the team's instrumental scores. If there are any, pick
   the one that fits the brief, copy it with `python3 tools/film.py music NAME`, and add
   `"music": "film/music.flac"` (and `"music_start": seconds` to start later in the track) next to
   `"scenes"`. If there are none the film is silent; say so in the report.
9. `python3 tools/film.py build` writes `out/film.mp4` and `sheets/film.png`. Look at the sheet.
10. Commit everything, including clips, sheets and `out/film.mp4`.

## Picture rules

- One clip per continuous action. Never join two clips in the middle of a movement.
- Animals and people move forward, seen from behind or from the side; no close-up facing the camera.
- A pose that matters belongs in the keyframe, not only in the prompt.
- The last frame of a shot and the first frame of the next must agree on place and direction.
- Nothing in the picture that the brief did not ask for.
- No likeness of a real person, no brand names or logos in the picture.

## Words on screen

- English only, few words. No model or product names of other companies, no caveat labels.

## Report

Say what you made, which checks ran and their result, and what only a person can judge: you can
look at still frames, not at motion or sound.
