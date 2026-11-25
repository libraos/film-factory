#!/usr/bin/env python3
"""Film kit: keyframes, renders, contact sheets and the final cut, from one command.

  film.py doctor                                   check the settings and the two endpoints
  film.py keyframe OUT.png "prompt" [--ref IN.png] still from the image model, cropped to the film size
  film.py render NAME [--seed N] [--resume JOB]    render or resume shot NAME, then make its contact sheet
  film.py sheet CLIP.mp4 OUT.png                   contact sheet of any clip
  film.py music [NAME]                             list the score library, or copy one score into the project
  film.py build                                    cards + clips from film/scenes.json -> out/film.mp4
                                                   (scenes.json "size": the film's frame size, default 1920x1080)
  film.py check plan|final                         are the deliverables of that stage there and well formed

Settings come from the environment, or from KEY=VALUE lines in $FILM_ENV (default ~/.config/film-kit/env):
  FILM_VIDEO_BASE_URL, FILM_IMAGE_BASE_URL   OpenAI-shaped bases ending in /v1 (the team gateway for both)
  FILM_VIDEO_KEY / _KEY_FILE / _KEY_CMD      bearer key, a file holding it, or a command that prints it
  FILM_IMAGE_KEY / _KEY_FILE / _KEY_CMD      same for images (falls back to the video key)
  FILM_VIDEO_MODEL, FILM_IMAGE_MODEL, FILM_SIZE (default 896x512), FILM_FFMPEG, FILM_CHROME
  FILM_ALLOW_HTTP=1                          allow plain http:// bases on a host other than loopback (key unencrypted)
Standard library only. Keys are never printed or written to disk, and never sent to a host other than the
configured endpoint (a redirect to another host goes without the key). Paths must stay inside the project.
"""
import argparse, base64, html, ipaddress, json, mimetypes, os, re, shutil, subprocess, sys, time, urllib.error, urllib.parse, urllib.request, uuid
from tempfile import TemporaryDirectory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = {}
SHOT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RENDER_LIMIT = 2 * 3600       # seconds a render may poll before giving up
IMAGE_CAP = 64 * 1024 * 1024  # largest image result fetched from a url


def load_conf():
    path = os.environ.get("FILM_ENV") or os.path.expanduser("~/.config/film-kit/env")
    if os.path.exists(path):
        with open(path) as settings:
            for line in settings:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    v = v.strip()
                    if len(v) > 1 and v[0] == v[-1] and v[0] in "\"'":
                        v = v[1:-1]
                    CONF[k.strip()] = v
    CONF.update({k: v for k, v in os.environ.items() if k.startswith("FILM_")})


def conf(name, default=None):
    return CONF.get(name, default)


def need(name):
    if not conf(name):
        sys.exit("missing setting %s (see tools/film.py --help)" % name)
    return conf(name)


def key(kind):
    for k in (kind, "VIDEO"):
        p = "FILM_%s_KEY" % k
        if conf(p):
            return conf(p)
        if conf(p + "_FILE"):
            return open(os.path.expanduser(conf(p + "_FILE"))).read().strip()
        if conf(p + "_CMD"):
            r = subprocess.run(conf(p + "_CMD"), shell=True, capture_output=True, text=True, timeout=60)
            if r.returncode or not r.stdout.strip():
                sys.exit("%s_CMD failed (exit %d)" % (p, r.returncode))
            return r.stdout.strip()
    sys.exit("missing key for %s: set FILM_%s_KEY, _KEY_FILE or _KEY_CMD" % (kind.lower(), kind))


def size():
    w, h = need_size().split("x")
    return int(w), int(h)


def need_size():
    return conf("FILM_SIZE", "896x512")


def ffmpeg():
    f = conf("FILM_FFMPEG") or shutil.which("ffmpeg")
    if not f:
        sys.exit("ffmpeg not found: set FILM_FFMPEG")
    return f


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("command failed: %s\n%s" % (" ".join(cmd[:4]), r.stderr[-600:]))
    return r


def is_loopback(host):
    host = (host or "").strip("[]").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def url_problem(url):
    """Why this url may not be used, or None: https always, http only on loopback or with FILM_ALLOW_HTTP=1."""
    u = urllib.parse.urlsplit(url)
    if u.scheme == "https" and u.hostname:
        return None
    if u.scheme == "http" and u.hostname:
        if is_loopback(u.hostname) or conf("FILM_ALLOW_HTTP") == "1":
            return None
        return ("plain http:// to %s would send data and the key unencrypted; use https://, "
                "or set FILM_ALLOW_HTTP=1 to allow it" % u.hostname)
    return "only https:// urls are used (got %s)" % (u.scheme + "://" if u.scheme else repr(url[:80]))


def need_url(name):
    url = need(name)
    problem = url_problem(url)
    if problem:
        sys.exit("%s: %s" % (name, problem))
    return url


def origin(url):
    u = urllib.parse.urlsplit(url)
    return u.scheme.lower(), (u.hostname or "").lower(), u.port or {"http": 80, "https": 443}.get(u.scheme.lower())


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to an allowed url, and drops the key when scheme, host or port changes."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        newurl = urllib.parse.urljoin(req.full_url, newurl)
        problem = url_problem(newurl)
        if problem:
            raise urllib.error.HTTPError(req.full_url, code, "redirect refused: " + problem, headers, fp)
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and origin(newurl) != origin(req.full_url):
            for h in [h for h in new.headers if h.lower() == "authorization"]:
                del new.headers[h]
            for h in [h for h in new.unredirected_hdrs if h.lower() == "authorization"]:
                del new.unredirected_hdrs[h]
        return new


OPENER = urllib.request.build_opener(SafeRedirect)


def http(method, url, token, body=None, ctype=None, to=None, timeout=600, soft=False):
    req = urllib.request.Request(url, body, method=method)
    req.add_header("Authorization", "Bearer " + token)
    if ctype:
        req.add_header("Content-Type", ctype)
    try:
        with OPENER.open(req, timeout=timeout) as r:
            if to:
                with open(to, "wb") as f:
                    shutil.copyfileobj(r, f)
                return None
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        msg = "%s %s -> HTTP %d: %s" % (method, url.split("/v1")[-1], e.code, e.read().decode("utf-8", "replace")[:300])
    except Exception as e:  # network refused, timeout, DNS
        msg = "%s %s -> %s" % (method, url.split("/v1")[-1], e)
    if soft:
        return {"_error": msg}
    sys.exit(msg)


def multipart(fields, files):
    b = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (b, k, v)).encode())
    for k, p in files.items():
        mime = mimetypes.guess_type(p)[0] or "application/octet-stream"
        head = '--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\nContent-Type: %s\r\n\r\n' % (b, k, os.path.basename(p), mime)
        parts.append(head.encode() + open(p, "rb").read() + b"\r\n")
    parts.append(("--%s--\r\n" % b).encode())
    return b"".join(parts), "multipart/form-data; boundary=" + b


def fetch(url, to, timeout=120, cap=IMAGE_CAP):
    """Download a url the endpoint returned: allowed urls only, no key, a timeout and a size cap."""
    problem = url_problem(url)
    if problem:
        sys.exit("image result url refused: " + problem)
    try:
        with OPENER.open(urllib.request.Request(url), timeout=timeout) as r, open(to, "wb") as f:
            got = 0
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                got += len(chunk)
                if got > cap:
                    raise ValueError("larger than %d MiB" % (cap >> 20))
                f.write(chunk)
        return
    except urllib.error.HTTPError as e:
        msg = "HTTP %d %s" % (e.code, e.reason)
    except Exception as e:  # network refused, timeout, DNS, too large
        msg = str(e)
    if os.path.exists(to):
        os.remove(to)
    sys.exit("image result download from %s failed: %s" % (urllib.parse.urlsplit(url).hostname, msg))


def rel(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def path_problem(p):
    """Why path p (relative to the project, or absolute) is not inside the project, or None."""
    root = os.path.realpath(ROOT)
    full = os.path.realpath(rel(p))
    if full != root and os.path.commonpath([root, full]) == root:
        return None
    return "%s is outside the project (%s); use a path inside it" % (p, root)


def inside(p, what):
    """rel(p), after checking that it stays inside the project."""
    problem = path_problem(p)
    if problem:
        sys.exit("%s: %s" % (what, problem))
    return rel(p)


def shot_name(name, what="shot"):
    if not isinstance(name, str) or not SHOT_NAME.match(name):
        sys.exit("%s name %r: use lowercase letters, digits and dashes, starting with a letter or digit" % (what, name))
    return name


# ---- keyframe ----
def keyframe(a):
    base, tok, model = need_url("FILM_IMAGE_BASE_URL").rstrip("/"), key("IMAGE"), need("FILM_IMAGE_MODEL")
    out = inside(a.out, "keyframe OUT")
    ref = inside(a.ref, "--ref") if a.ref else None
    w, h = size()
    src = "1536x1024" if w >= h else "1024x1536"
    if a.ref:
        body, ctype = multipart({"model": model, "size": src, "prompt": a.prompt}, {"image": ref})
        d = http("POST", base + "/images/edits", tok, body, ctype)
    else:
        d = http("POST", base + "/images/generations", tok, json.dumps({"model": model, "size": src, "prompt": a.prompt}).encode(), "application/json")
    item = d["data"][0]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    raw = out + ".raw.png"
    if item.get("b64_json"):
        open(raw, "wb").write(base64.b64decode(item["b64_json"]))
    else:
        fetch(item["url"], raw)
    run([ffmpeg(), "-v", "error", "-y", "-i", raw, "-vf", "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (w, h, w, h), out])
    os.remove(raw)
    print("keyframe %s (%dx%d)" % (a.out, w, h))


# ---- render ----
def shots():
    return json.load(open(rel("film/shots.json")))


def sheet(clip, out):
    seconds = duration(clip)
    if seconds <= 0:
        sys.exit("could not read the duration of %s" % clip)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    # Sample 24 tiles across the entire running time, including the final scene.
    # -reinit_filter 0 keeps the tiles gathered so far when a cut changes the input's colour metadata
    filters = "fps=%.12g,scale=320:-2,tile=6x4" % (24 / seconds)
    run([ffmpeg(), "-v", "error", "-y", "-reinit_filter", "0", "-i", clip, "-vf", filters, "-frames:v", "1", "-vsync", "0", out])


def conform_duration(clip, seconds):
    actual = duration(clip)
    if actual == seconds:
        return
    if actual <= 0:
        sys.exit("could not read the duration of %s" % clip)
    # Retain the entire move when the video service rounds the requested duration.
    video = "setpts=%.9f*PTS,fps=24,tpad=stop_mode=clone:stop=1" % (seconds / actual)
    audio = "atempo=%.9f,apad" % (actual / seconds)
    with TemporaryDirectory(dir=os.path.dirname(clip)) as work:
        conformed = os.path.join(work, "conformed.mp4")
        run([ffmpeg(), "-v", "error", "-i", clip, "-vf", video, "-af", audio, "-t", str(seconds),
             "-c:v", "libx264", "-crf", "15", "-c:a", "aac", "-b:a", "128k", conformed])
        os.replace(conformed, clip)


def render(a):
    shot_name(a.name)
    shot = next((s for s in shots() if s["name"] == a.name), None)
    if not shot:
        sys.exit("no shot named %s in film/shots.json" % a.name)
    files = {n: inside(shot[k], "shot %s %s" % (a.name, k)) for n, k in (("input_reference", "first"), ("last_frame", "last")) if shot.get(k)}
    base, tok = need_url("FILM_VIDEO_BASE_URL").rstrip("/"), key("VIDEO")
    seed = a.seed if a.seed is not None else shot.get("seed", 1)
    if a.resume:
        status_url = base + "/videos/" + urllib.parse.quote(a.resume, safe="")
        job = http("GET", status_url, tok, timeout=60)
        print("resumed %s as %s (seed %s)" % (a.name, a.resume, seed), flush=True)
    else:
        fields = {"model": need("FILM_VIDEO_MODEL"), "prompt": shot["prompt"], "seconds": str(shot.get("seconds", 5)), "size": need_size(), "seed": str(seed)}
        body, ctype = multipart(fields, files)
        job = http("POST", base + "/videos", tok, body, ctype)
        status_url = base + "/videos/" + urllib.parse.quote(job["id"], safe="")
        print("submitted %s as %s (seed %s)" % (a.name, job["id"], seed), flush=True)
    last, t0 = None, time.time()
    while job.get("status") not in ("completed", "failed", "cancelled"):
        if time.time() - t0 > RENDER_LIMIT:
            sys.exit("render %s: no result after %d minutes (last status %s); try later with: render %s --resume %s"
                     % (a.name, RENDER_LIMIT // 60, job.get("status"), a.name, status_url.rsplit("/", 1)[-1]))
        line = "%s %s%%" % (job.get("status"), job.get("progress", 0))
        if line != last:
            print("  %4ds %s" % (time.time() - t0, line), flush=True)
            last = line
        time.sleep(15)
        nxt = http("GET", status_url, tok, timeout=60, soft=True)
        if "_error" not in nxt:
            job = nxt
    if job["status"] != "completed":
        sys.exit("render %s %s: %s" % (a.name, job["status"], json.dumps(job.get("error"))))
    tag = a.name if a.seed is None else "%s.seed%s" % (a.name, seed)
    clip, sh = rel("clips/%s.mp4" % tag), rel("sheets/%s.png" % tag)
    os.makedirs(os.path.dirname(clip), exist_ok=True)
    http("GET", status_url + "/content", tok, to=clip)
    conform_duration(clip, float(shot.get("seconds", 5)))
    sheet(clip, sh)
    print("clip clips/%s.mp4, contact sheet sheets/%s.png (%ds)" % (tag, tag, time.time() - t0))


# ---- build ----
CSS = """*{margin:0;box-sizing:border-box}html,body{width:1920px;height:1080px;overflow:hidden;font-family:"DejaVu Sans",Arial,sans-serif;color:#14171f;
background:radial-gradient(1300px 800px at 28% 18%,#fff 0,#f3f5f9 70%)}
.c{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:0 160px}
.k{font-size:28px;font-weight:700;letter-spacing:5px;color:#2f6bff;margin-bottom:26px}
h1{font-size:104px;font-weight:800;line-height:1.08}h2{font-size:46px;font-weight:400;color:#465066;line-height:1.35;margin-top:30px}"""


def card(scene, out):
    chrome = conf("FILM_CHROME") or shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        sys.exit("Chrome not found: set FILM_CHROME")
    e = lambda k: html.escape(scene.get(k, ""))
    page = out + ".html"
    with open(page, "w") as page_file:
        page_file.write("<meta charset=utf-8><style>%s</style><div class=c><div class=k>%s</div><h1>%s</h1><h2>%s</h2></div>" % (CSS, e("kicker"), e("title"), e("sub")))
    with TemporaryDirectory(prefix="film-chrome-") as profile:
        # Chrome refuses to start as root with its sandbox on; anywhere else keep the sandbox.
        sandbox = ["--no-sandbox"] if hasattr(os, "geteuid") and os.geteuid() == 0 else []
        run([chrome, "--headless=new"] + sandbox + ["--disable-gpu", "--hide-scrollbars",
             "--user-data-dir=" + profile, "--window-size=1920,1080", "--screenshot=" + out, "file://" + page])
    os.remove(page)


def build(a):
    with open(rel("film/scenes.json")) as scenes_file:
        plan = json.load(scenes_file)
    width, height = map(int, plan.get("size", "1920x1080").split("x"))
    canvas = "scale=%d:%d:force_original_aspect_ratio=increase:flags=lanczos,crop=%d:%d,setsar=1" % (width, height, width, height)
    work = rel("out/work")
    os.makedirs(work, exist_ok=True)
    enc = ["-r", "24", "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-an"]
    segs = []
    for i, s in enumerate(plan["scenes"]):
        seg = os.path.join(work, "seg%02d.mp4" % i)
        if s["type"] == "card":
            png = os.path.join(work, "card%02d.png" % i)
            card(s, png)
            d = float(s.get("seconds", 3))
            run([ffmpeg(), "-v", "error", "-y", "-loop", "1", "-framerate", "24", "-t", str(d), "-i", png, "-vf",
                 "%s,fade=t=in:st=0:d=0.3:color=white,fade=t=out:st=%.2f:d=0.3:color=white" % (canvas, d - 0.3)] + enc + [seg])
        elif s["type"] == "clip":
            shot_name(s.get("name"), "scene %d clip" % i)
            clip = rel("clips/%s.mp4" % s["name"])
            if not os.path.exists(clip):
                sys.exit("scene %d: clips/%s.mp4 is missing; render it first" % (i, s["name"]))
            cmd = [ffmpeg(), "-v", "error", "-y", "-ss", str(s.get("start", 0))]
            if s.get("seconds"):
                cmd += ["-t", str(s["seconds"])]
            run(cmd + ["-i", clip, "-vf", "fps=24," + canvas] + enc + [seg])
        else:
            sys.exit("scene %d: unknown type %s" % (i, s["type"]))
        segs.append(seg)
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as concat_list:
        concat_list.writelines("file '%s'\n" % s for s in segs)
    out = rel("out/film.mp4")
    silent = os.path.join(work, "video.mp4")
    run([ffmpeg(), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent])
    music = plan.get("music")
    if music:
        d = duration(silent)
        run([ffmpeg(), "-v", "error", "-y", "-i", silent, "-ss", str(plan.get("music_start", 0)), "-i", inside(music, "film/scenes.json music"), "-filter_complex",
             "[1:a]afade=t=in:st=0:d=1,afade=t=out:st=%.2f:d=2[a]" % (d - 2), "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-t", str(d), out])
    else:
        shutil.copy(silent, out)
    final_duration = duration(out)
    sheet(out, rel("sheets/film.png"))
    print("film out/film.mp4 (%.1f s), contact sheet sheets/film.png" % final_duration)


def music(a):
    """List the scores in FILM_MUSIC_DIR, or copy one into the project as film/music.EXT."""
    lib = os.path.expanduser(conf("FILM_MUSIC_DIR") or "")
    tracks = sorted(f for f in os.listdir(lib) if f.lower().endswith((".flac", ".wav", ".mp3", ".m4a"))) if os.path.isdir(lib) else []
    if not tracks:
        print("no score library (FILM_MUSIC_DIR); the film will be silent")
        return
    if not a.name:
        for t in tracks:
            note = os.path.join(lib, os.path.splitext(t)[0] + ".txt")
            print("%s  %.0f s  %s" % (t, duration(os.path.join(lib, t)), open(note).read().strip() if os.path.exists(note) else ""))
        return
    if a.name not in tracks:
        sys.exit("no such score: %s" % a.name)
    out = "film/music" + os.path.splitext(a.name)[1].lower()
    shutil.copy(os.path.join(lib, a.name), rel(out))
    print('score copied to %s; add "music": "%s" to film/scenes.json' % (out, out))


def duration(path):
    r = subprocess.run([ffmpeg(), "-i", path], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


# ---- check ----
def check(a):
    bad = []
    ok = lambda cond, msg: bad.append(msg) if not cond else None
    ex = lambda p: os.path.exists(rel(p)) and os.path.getsize(rel(p)) > 0
    ok(ex("film/concept.md"), "film/concept.md is missing")
    sl = []
    try:
        sl = shots()
    except Exception as e:
        ok(False, "film/shots.json: %s" % e)
    ok(1 <= len(sl) <= 6, "film/shots.json needs 1 to 6 shots")
    w, h = size()
    for s in sl:
        n = s.get("name", "?")
        ok(isinstance(n, str) and SHOT_NAME.match(n), "shot name %r: use lowercase letters, digits and dashes" % (n,))
        ok(all(s.get(k) for k in ("name", "prompt", "first", "last")), "shot %s needs name, prompt, first and last" % n)
        ok(5 <= float(s.get("seconds", 5)) <= 15, "shot %s: seconds must be 5 to 15" % n)
        ok(len(s.get("prompt", "")) >= 120, "shot %s: prompt is too short to steer the model" % n)
        for k in ("first", "last"):
            if s.get(k):
                ok(not path_problem(s[k]), "shot %s: keyframe %s" % (n, path_problem(s[k])))
                ok(ex(s[k]), "shot %s: keyframe %s is missing" % (n, s[k]))
        if a.stage == "final" and isinstance(n, str) and SHOT_NAME.match(n):
            ok(ex("clips/%s.mp4" % n), "clips/%s.mp4 is missing" % n)
            ok(ex("sheets/%s.png" % n), "sheets/%s.png is missing" % n)
    if a.stage == "final":
        ok(ex("film/scenes.json"), "film/scenes.json is missing")
        ok(ex("out/film.mp4"), "out/film.mp4 is missing")
        if ex("out/film.mp4"):
            d = duration(rel("out/film.mp4"))
            ok(d >= 8, "out/film.mp4 is only %.1f s" % d)
        if ex("film/scenes.json"):
            sc = json.load(open(rel("film/scenes.json")))["scenes"]
            ok(sc and sc[-1]["type"] == "card", "the film must end on a card")
            lib = os.path.expanduser(conf("FILM_MUSIC_DIR") or "")
            if os.path.isdir(lib) and os.listdir(lib):
                plan = json.load(open(rel("film/scenes.json")))
                ok(plan.get("music") and ex(plan["music"]), "a score library is set but film/scenes.json has no music")
    if bad:
        print("\n".join("FAIL " + b for b in bad))
        sys.exit(1)
    print("check %s: ok (%d shots, %dx%d)" % (a.stage, len(sl), w, h))


def doctor(a):
    print("size %s, ffmpeg %s" % (need_size(), "found" if (conf("FILM_FFMPEG") or shutil.which("ffmpeg")) else "MISSING"))
    for kind in ("VIDEO", "IMAGE"):
        base = need_url("FILM_%s_BASE_URL" % kind).rstrip("/")
        d = http("GET", base + "/models", key(kind), timeout=30, soft=True)
        ids = [m.get("id") for m in d.get("data", [])] if "_error" not in d else []
        want = conf("FILM_%s_MODEL" % kind)
        state = d["_error"] if "_error" in d else ("model %s %s" % (want, "listed" if want in ids else "NOT listed (%d models)" % len(ids)))
        print("%s endpoint: %s" % (kind.lower(), state))


def main():
    load_conf()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(f=doctor)
    p = sub.add_parser("keyframe"); p.add_argument("out"); p.add_argument("prompt"); p.add_argument("--ref"); p.set_defaults(f=keyframe)
    p = sub.add_parser("render"); p.add_argument("name"); p.add_argument("--seed", type=int); p.add_argument("--resume", metavar="JOB", help="resume this shot's existing job using its original seed"); p.set_defaults(f=render)
    p = sub.add_parser("sheet"); p.add_argument("clip"); p.add_argument("out"); p.set_defaults(f=lambda a: sheet(rel(a.clip), rel(a.out)))
    p = sub.add_parser("music"); p.add_argument("name", nargs="?"); p.set_defaults(f=music)
    sub.add_parser("build").set_defaults(f=build)
    p = sub.add_parser("check"); p.add_argument("stage", choices=("plan", "final")); p.set_defaults(f=check)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
