#!/usr/bin/env python3
"""完成した動画の長さに合わせて曲を作り（ACE-Step 1.5、ローカル・無料）、動画に入れる。

  python3 add_music.py outputs/xxx/calf_stretch_studio.mp4 --job jobs/calf_stretch_studio.json
  python3 add_music.py video.mp4 --caption "soft acoustic piano, calm" --bpm 80
  python3 add_music.py video.mp4 --wav 既存の曲.wav                 # 曲は作らず、手持ちの曲を合わせるだけ
  python3 add_music.py video.mp4 --dry-run                          # 何をするかだけ表示

出力: <動画名>_music.mp4（元の無音の動画は残す）と <動画名>_music.wav
pipeline.py は、ジョブに "music" があれば動画のあとに自動でこれを呼ぶ。
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ACE_ROOT = Path(os.environ.get("ACESTEP_ROOT", Path.home() / "ACE-Step-1.5"))

DEFAULT = {
    "caption": ("light acoustic piano with soft acoustic guitar, calm and positive wellness background music, "
                "gentle steady rhythm, warm, unobtrusive, no vocals"),
    "bpm": 80, "key": "C Major", "ts": "4", "seed": -1,
    "volume_db": -4.0,     # 曲の音量の調整（dB）
    "fade_in": 0.5, "fade_out": 2.5,
}
MARGIN = 4.0   # 曲は少し長めに作り、動画の長さで切ってフェードアウトする


class MusicError(RuntimeError):
    pass


def duration_of(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    if not out:
        raise MusicError(f"長さを測れない: {path}")
    return float(out)


def ace_available():
    return (ACE_ROOT / "acestep").is_dir() and (ACE_ROOT / "checkpoints").is_dir() and shutil.which("uv")


def generate(settings, seconds, wav):
    if not ace_available():
        raise MusicError(f"ACE-Step が見つからない（{ACE_ROOT}）。README の「曲を付ける」を見てセットアップするか、"
                         "ACESTEP_ROOT を設定する。手持ちの曲を使うなら --wav")
    cmd = ["uv", "run", "--project", str(ACE_ROOT), "python", str(ROOT / "music/gen_music.py"),
           "--duration", f"{seconds:.1f}", "--caption", settings["caption"], "--seed", str(settings["seed"]),
           "--out", str(wav)]
    for flag, key in (("--bpm", "bpm"), ("--key", "key"), ("--ts", "ts")):
        if settings.get(key) not in (None, ""):
            cmd += [flag, str(settings[key])]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if r.returncode or not wav.exists():
        raise MusicError(f"曲の生成に失敗:\n{(r.stderr or r.stdout)[-1500:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def mux_cmd(video, wav, out, dur, s):
    """曲を動画の長さで切り、頭と終わりをフェードして入れる。映像は再エンコードしない"""
    fo = min(s["fade_out"], dur / 2)
    af = (f"atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,afade=t=in:d={s['fade_in']},"
          f"afade=t=out:st={dur - fo:.3f}:d={fo},volume={s['volume_db']}dB")
    return ["ffmpeg", "-v", "error", "-i", str(video), "-i", str(wav), "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "192k", "-shortest", "-y", str(out)]


def add_music(video, settings=None, wav=None, dry_run=False, log=print):
    video = Path(video)
    s = {**DEFAULT, **(settings or {})}
    dur = duration_of(video)
    out = video.with_name(video.stem + "_music.mp4")
    music = Path(wav) if wav else video.with_name(video.stem + "_music.wav")
    log(f"動画 {dur:.1f}s → 曲 {dur + MARGIN:.1f}s を作って {dur:.1f}s に合わせる" if not wav else
        f"手持ちの曲 {music} を {dur:.1f}s に合わせる")
    if dry_run:
        log(json.dumps(s, ensure_ascii=False) + f"\n→ {out}")
        return out
    if not wav:
        info = generate(s, dur + MARGIN, music)
        log(f"曲: {music}（seed {info.get('seed')}、{info.get('sec')}s）")
    elif not music.exists():
        raise MusicError(f"見つからない: {music}")
    subprocess.run(mux_cmd(video, music, out, dur, s), check=True)
    log(f"saved {out}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--job", help="ジョブ設定の music を使う")
    ap.add_argument("--wav", help="曲を作らず、この曲を使う")
    ap.add_argument("--caption"); ap.add_argument("--bpm", type=int); ap.add_argument("--key")
    ap.add_argument("--ts"); ap.add_argument("--seed", type=int); ap.add_argument("--volume-db", type=float)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    s = dict(json.loads(Path(a.job).read_text()).get("music") or {}) if a.job else {}
    for k in ("caption", "bpm", "key", "ts", "seed", "volume_db"):
        if getattr(a, k) is not None:
            s[k] = getattr(a, k)
    try:
        out = add_music(a.video, s, a.wav, a.dry_run)
    except MusicError as e:
        sys.exit(str(e))
    if a.open and not a.dry_run:
        subprocess.run(["open", str(out)])


if __name__ == "__main__":
    main()
