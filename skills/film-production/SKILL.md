---
name: film-production
description: Make a short film or video from a plain description, with LibraOS Engine workers, an image model and a video model. Use whenever a person asks for a film, video, clip, trailer or animation of something they describe (a product film, a launch clip, an opening film). The person only describes the film; this skill supplies the stages, the worker handoffs, the checks and the one approval.
---

# Film production

A person describes a film in their own words. You turn that into a concept, a shot list, keyframes,
rendered clips and a finished film, with one stop for their approval. Never ask the person for stage
names, budgets, commands or file names: those are yours to supply from this page.

All model calls go through one script, `tools/film.py`. It reads its endpoints and key from settings
outside the repository and never prints or stores a key.

## When a person asks for a film

1. **Project.** If the repository has no `tools/film.py`, set it up from this skill's folder:
   `scripts/film.py` to `tools/film.py`; `assets/project/AGENTS.md` to `AGENTS.md` and `CLAUDE.md`;
   `assets/project/gitignore` to `.gitignore`. If `AGENTS.md`, `CLAUDE.md` or `.gitignore` already
   exists, keep the person's content and append this skill's section to the end instead of
   overwriting (skip lines already there). Write the person's request, in their words, into
   `film/brief.md`. Commit.
2. **Ready?** Run `python3 tools/film.py doctor`. If a model is not listed or a setting is missing,
   tell the person in one or two plain sentences what is missing (see "Once per machine") and stop.
3. **Plan.** Hand stage 1 of `AGENTS.md` to one LibraOS Engine worker: goal = the concept, the shot list and
   the keyframes for the brief, then stop; budget 30 minutes; check
   `python3 tools/film.py check plan`. If no worker can be started, do stage 1 yourself.
4. **Show and ask.** When the plan check passes, look at the keyframes yourself, then show them to the
   person with one line per shot saying what it shows and how the camera moves. Ask whether to make
   the film from these. Stop here. Do not render.
5. **Changes.** If the person wants something different, redo only those keyframes (and the shot
   list), show them again, and ask again.
6. **Film.** When the person agrees, in whatever words, hand stage 2 of `AGENTS.md` to one LibraOS Engine
   worker on the same branch: render the shots, check the contact sheets, write the scenes, add a score, build;
   budget 15 minutes plus 6 per shot at 896x512, or 15 plus 25 per shot at 1344x768; check
   `python3 tools/film.py check final`. If no worker can be started, do stage 2 of `AGENTS.md`
   yourself, on the same branch, with the same check.
7. **Deliver.** Link `out/film.mp4` and `sheets/film.png`. Say what was checked and what only a
   person can judge: motion, pacing and sound. Say if a worker reported a fault it could not fix.

If a worker stops because it has no network, say so plainly and name the fix under "Once per machine".

## Once per machine

1. Settings: copy `assets/env.example` to `~/.config/film-kit/env` and fill it in. Both base URLs are
   normally the team gateway and the key is the one from LibraOS Next.
2. Worker network: Codex workers have no network by default and cannot reach the endpoints. The
   owner turns it on at their own terminal: `libraos-core config set dispatch.codex_network true`.
3. `ffmpeg` and Chrome (for title cards) installed, or named in `FILM_FFMPEG` / `FILM_CHROME`.

## What the stages produce

| Stage | Files | Check |
|---|---|---|
| 1 plan | `film/concept.md`, `film/shots.json`, `keyframes/*.png` | `tools/film.py check plan` |
| 2 film | `clips/*.mp4`, `sheets/*.png`, `film/scenes.json`, `out/film.mp4` | `tools/film.py check final` |

A 5 second clip takes about 4 minutes at 896x512 and about 18 at 1344x768, one clip at a time.
The picture and wording rules workers follow are in the project's `AGENTS.md`.

## Settings

| Name | Meaning |
|---|---|
| `FILM_VIDEO_BASE_URL`, `FILM_IMAGE_BASE_URL` | bases ending in `/v1`; `https://`, or `http://` only on loopback |
| `FILM_VIDEO_KEY`, `_KEY_FILE` or `_KEY_CMD` | bearer key, a file holding it, or a command that prints it; `FILM_IMAGE_*` likewise, falling back to the video key |
| `FILM_VIDEO_MODEL`, `FILM_IMAGE_MODEL` | model names as the endpoint lists them |
| `FILM_SIZE` | `896x512` (fast) or `1344x768` (final) |
| `FILM_MUSIC_DIR` | folder of instrumental scores the team may use (optional; without it films are silent) |
| `FILM_FFMPEG`, `FILM_CHROME` | paths, if not on `PATH` |
| `FILM_ALLOW_HTTP` | `1` allows a plain `http://` base on a host other than loopback, which sends the key unencrypted (optional; off by default) |
