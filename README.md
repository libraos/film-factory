# Film Factory

The film-production Skill for LibraOS Next. Describe a film in your own words; the agent plans it,
shows you the keyframes, and after your one approval hands the rendering to LibraOS Engine workers
and delivers a finished film with title cards and an optional score.

## Contents

| Path | What it is |
| --- | --- |
| [`skills/film-production`](skills/film-production) | The Skill: `SKILL.md`, the worker rules, and `scripts/film.py`, the one script that calls the image and video models and builds the film |
| [`examples/pier-nine`](examples/pier-nine) | A 20 second test run at the fast size: the brief, plan, keyframes and contact sheets |
| [`examples/tidal-city`](examples/tidal-city) | A 30 second run at 1344x768 with a score |

## Install

In LibraOS Next, open Skills and install **Film Production** from Recommended. Or copy
`skills/film-production` into your agent's Skills folder (`~/.claude/skills/` or `~/.agents/skills/`).

## Setup, once per machine

`film.py` needs Python 3, ffmpeg, Chrome (for title cards), and two OpenAI-shaped endpoints: one serving `/v1/videos`
and one serving `/v1/images`. Copy `skills/film-production/assets/env.example` to
`~/.config/film-kit/env`, fill in the endpoints and models, and put the key in a file outside any
repository. Then run `python3 tools/film.py doctor` in a film project. Workers need network access
for the endpoints: `libraos-core config set dispatch.codex_network true`.

The script sends your prompts and keyframes only to the endpoints you configure. When an image
endpoint answers with a link instead of the image, the script downloads that link without the key.
The key never leaves the configured host, even on a redirect. Endpoints must use `https://`
(plain `http://` only on loopback, or with `FILM_ALLOW_HTTP=1`). The script never prints or stores a key.

## Tests

    cd skills/film-production && python3 -m unittest discover -s tests

## Licence

MIT. See [LICENSE](LICENSE).
