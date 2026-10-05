#!/usr/bin/env python3
"""Blender 側: リグ（ボーン）と人形 → 空間の土台 → モーション → 低品質レンダ → motion 動画。

  python3 blender/make.py setup                         # 同梱 MCP アドオンを Blender に入れる（GUI モード用）
  python3 blender/make.py build calf_stretch            # 画面なし（blender -b）で動画まで作る
  python3 blender/make.py build calf_stretch --gui      # 起動中の Blender（blender/start.sh）に送って作る。途中を目で見られる
  python3 blender/make.py build calf_stretch --space basic_room --dry-run   # 実行せず手順だけ表示

出力: blender/renders/<motion>__<space>.mp4 と blender/scenes/<motion>__<space>.blend
"""
import argparse, json, os, shutil, subprocess, sys, textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLENDER = os.environ.get("BLENDER_BIN") or shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"
ADDON_ZIP = HERE / "addons" / "blender_mcp-1.0.0.zip"


def outputs(motion, space):
    stem = f"{motion}__{space}"
    return HERE / "renders" / f"{stem}.mp4", HERE / "scenes" / f"{stem}.blend"


def steps(motion, space, space_params=None):
    """Blender 内で順に実行するスクリプトと、その先頭に差し込む PARAMS"""
    mp4, blend = outputs(motion, space)
    common = {"space_params": space_params or {}}
    save = textwrap.dedent(f"""
        import bpy, os
        os.makedirs({str(blend.parent)!r}, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath={str(blend)!r}, copy=True)
        result = {{'saved': {str(blend)!r}}}
    """)
    return [
        ("rig", HERE / "rig.py", common),
        ("space", HERE / "spaces" / f"{space}.py", common),
        ("motion", HERE / "motions" / f"{motion}.py", common),
        ("save", save, common),
        ("render", HERE / "render.py", {**common, "out": str(mp4)}),
    ]


def code_of(src, params):
    body = src.read_text() if isinstance(src, Path) else src
    head = f"import sys\nsys.path.insert(0, {str(HERE)!r})\nPARAMS = {json.dumps(params)!r}\nimport json as _j\nPARAMS = _j.loads(PARAMS)\n"
    return head + body


def check(motion, space):
    missing = [str(p) for _, p, _ in steps(motion, space) if isinstance(p, Path) and not p.exists()]
    if missing:
        sys.exit("見つからない:\n  " + "\n  ".join(missing))


def run_headless(motion, space, space_params):
    """1 回の blender -b で全工程を流す（-y: Rigify のドライバーを動かすため自動実行を許可）"""
    script = "\n".join(
        f"# ---- {name} ----\nexec(compile({code_of(src, p)!r}, {name!r}, 'exec'), {{'__name__': '__main__'}})"
        for name, src, p in steps(motion, space, space_params))
    tmp = HERE / "renders" / ".headless_run.py"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(script)
    r = subprocess.run([BLENDER, "-b", "-y", "--factory-startup", "--python-exit-code", "1", "--python", str(tmp)])
    if r.returncode:
        sys.exit(f"Blender が失敗した (exit {r.returncode})")


def run_gui(motion, space, space_params):
    sys.path.insert(0, str(HERE))
    from bl import send
    for name, src, p in steps(motion, space, space_params):
        print(f"[{name}]", flush=True)
        r = send(code_of(src, p))
        if r.get("status") != "ok":
            sys.exit(f"{name} で失敗: {r.get('message')}\n{r.get('stderr', '')}")
        if r.get("result") is not None:
            print(" ", json.dumps(r["result"], ensure_ascii=False, default=repr)[:300])


def setup():
    if not ADDON_ZIP.exists():
        sys.exit(f"見つからない: {ADDON_ZIP}")
    r = subprocess.run([BLENDER, "--command", "extension", "install-file", "-r", "user_default", "-e", str(ADDON_ZIP)])
    sys.exit(r.returncode)


def build(motion, space="basic_room", gui=False, space_params=None, dry_run=False, force=False):
    """pipeline.py からも呼ぶ。できた mp4 のパスを返す"""
    check(motion, space)
    mp4, blend = outputs(motion, space)
    if mp4.exists() and not force:
        print(f"既にある（作り直すなら --force）: {mp4}")
        return mp4
    if dry_run:
        print(f"Blender: {BLENDER}\nmode: {'GUI (MCP 9878)' if gui else 'headless (blender -b)'}")
        for name, src, p in steps(motion, space, space_params):
            print(f"  {name:7} {src if isinstance(src, Path) else '(inline)'}  PARAMS={json.dumps(p, ensure_ascii=False)}")
        print(f"  → {mp4}\n  → {blend}")
        return mp4
    (run_gui if gui else run_headless)(motion, space, space_params)
    if not mp4.exists():
        sys.exit(f"動画ができていない: {mp4}")
    return mp4


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["setup", "build"])
    ap.add_argument("motion", nargs="?")
    ap.add_argument("--space", default="basic_room")
    ap.add_argument("--gui", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.cmd == "setup":
        setup()
    if not a.motion:
        ap.error("motion を指定する（blender/motions/*.py のファイル名）")
    print(build(a.motion, a.space, a.gui, dry_run=a.dry_run, force=a.force))


if __name__ == "__main__":
    main()
