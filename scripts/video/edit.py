"""Cut one live take into the < 3 min submission video.

    python3 edit.py --take ~/tmp/mbvideo/take-XXXX --narration ~/tmp/mbvideo/narration --out motherbrain-demo.mp4

Only waiting is compressed. Calm scenes are trimmed to their narration. Live agent
scenes play at real speed unless the whole cut would exceed the limit. Dream plays
at real time when it is short (no label; narration already says it is live).
"""
import argparse
import json
import os
import subprocess
from pathlib import Path

LIMIT = 172.0  # seconds, leaves margin under 3:00
FONT = next((f for f in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
                         "/Library/Fonts/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if os.path.exists(f)), None)

def _has_drawtext():
    try:
        out = subprocess.check_output(["ffmpeg", "-hide_banner", "-filters"], stderr=subprocess.STDOUT, text=True)
        return "drawtext" in out
    except Exception:
        return False

HAS_DRAWTEXT = _has_drawtext()

# (segment, from-mark, to-mark, narration, kind)
PLAN = [
    ("hero", "hero", "stages", "hero", "calm"),
    ("stages", "stages", "thoughts_wait", "stages", "calm"),
    ("scout", "thoughts_wait", "soul", "scout", "live"),
    ("soul", "soul", "ops_wait", "soul", "calm"),
    ("ops", "ops_wait", "before_after", "ops", "live"),
    ("before_after", "before_after", "dream", "before_after", "calm"),
    ("dream", "dream", "dream_done", "dream", "fast"),
    ("dream_tail", "dream_done", "refusal", None, "calm"),
    ("refusal", "refusal", "ledger", "refusal", "live"),
    ("ledger", "ledger", "plans", None, "calm"),
    ("plans", "plans", "connect", "plans", "calm"),
    ("connect", "connect", "end", "connect", "calm"),
]


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--take", required=True)
    a.add_argument("--narration", required=True)
    a.add_argument("--out", default="motherbrain-demo.mp4")
    a = a.parse_args()
    take, nar = Path(a.take).expanduser(), Path(a.narration).expanduser()
    meta = json.loads((take / "marks.json").read_text())
    m = {x["name"]: x["t"] for x in meta["marks"]}
    video = take / meta["video"]

    segs = []
    for name, f, t, n, kind in PLAN:
        start, end = m[f], m[t]
        nd = dur(nar / f"{n}.wav") if n else 0.0
        segs.append({"name": name, "start": start, "end": end, "raw": end - start, "narr": n, "nd": nd, "kind": kind, "speed": 1.0})

    def shape(live_speed):
        for s in segs:
            need = s["nd"] + 0.7 if s["nd"] else 0
            if s["kind"] == "calm":
                s["speed"] = 1.0
                s["end_used"] = s["start"] + min(s["raw"], max(need, 3.0))
            elif s["kind"] == "fast":
                s["end_used"] = s["end"]
                s["speed"] = max(1.0, s["raw"] / max(need, 12.0)) if s["raw"] > 20 else 1.0
            else:
                s["end_used"] = s["end"]
                s["speed"] = live_speed
            s["out"] = max((s["end_used"] - s["start"]) / s["speed"], need)
        return sum(s["out"] for s in segs)

    live_speed = 1.0
    total = shape(live_speed)
    while total > LIMIT and live_speed < 2.0:
        live_speed = round(live_speed + 0.1, 2)
        total = shape(live_speed)
    print(f"total {total:.1f}s, live speed {live_speed}x")

    fc, vlabels, alabels, t = [], [], [], 0.0
    for i, s in enumerate(segs):
        clip = (s["end_used"] - s["start"]) / s["speed"]
        pad = max(0.0, s["out"] - clip)
        f = (f"[0:v]trim=start={s['start']:.3f}:end={s['end_used']:.3f},setpts=(PTS-STARTPTS)/{s['speed']:.4f},"
             f"fps=30,tpad=stop_mode=clone:stop_duration={pad:.3f}")
        label = None
        if s["speed"] > 1.05:
            label = f"sped up {s['speed']:.1f}x" if s["kind"] != "fast" else f"dream running on the strong model - sped up {s['speed']:.0f}x"
        if label and FONT and HAS_DRAWTEXT:
            f += (f",drawtext=fontfile='{FONT}':text='{label}':x=w-tw-24:y=h-th-22:fontsize=22:fontcolor=white:"
                  f"box=1:boxcolor=0xe5192f@0.85:boxborderw=10")
        fc.append(f + f"[v{i}]")
        vlabels.append(f"[v{i}]")
        if s["narr"]:
            ms = int((t + 0.3) * 1000)
            fc.append(f"[{len(alabels) + 1}:a]adelay={ms}|{ms},aformat=channel_layouts=stereo[a{len(alabels)}]")
            alabels.append((s["narr"], f"[a{len(alabels)}]"))
        s["at"] = t
        t += s["out"]
    fc.append("".join(vlabels) + f"concat=n={len(vlabels)}:v=1:a=0[vout]")
    fc.append("".join(l for _, l in alabels) + f"amix=inputs={len(alabels)}:normalize=0,volume=1.0[aout]")
    cmd = ["ffmpeg", "-y", "-i", str(video)]
    for n, _ in alabels:
        cmd += ["-i", str(nar / f"{n}.wav")]
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]", "-t", f"{t:.2f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    (Path(a.out).with_suffix(".cut.json")).write_text(json.dumps({"total": t, "live_speed": live_speed, "segments": segs}, indent=1))
    print(f"wrote {a.out} ({t:.1f}s)")


if __name__ == "__main__":
    main()
