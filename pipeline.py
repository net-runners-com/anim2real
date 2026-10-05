#!/usr/bin/env python3
"""anim2real: anim のマネキン動画 → 実写風動画 (Seedance 2.5 / Atlas Cloud)

  python3 pipeline.py jobs/calf_stretch_studio.json          # dry-run (プロンプトと概算費用だけ表示)
  python3 pipeline.py jobs/calf_stretch_studio.json --yes    # 実行 (課金される)
"""
import json, subprocess, sys, time
from pathlib import Path

from atlas import Atlas, AtlasError

ROOT = Path(__file__).resolve().parent
MODEL = "bytedance/seedance-2.5/reference-to-video"
# 実測: 720p / 19.7s = $7.136 (2026-10-05)。他解像度は未計測
USD_PER_SEC = {"720p": 7.136064 / 19.712}

CAMERAS = {
    "smartphone_handheld": (
        "Shot on a smartphone held by someone standing nearby: real handheld footage, subtle natural hand shake "
        "and micro reframing, slight auto-exposure and white balance drift, mild sensor noise, phone lens look "
        "with deep focus, no cinematic lighting, no color grading, no slow motion."),
    "tripod_phone": (
        "Shot on a smartphone on a small tripod: static framing, natural phone exposure, mild sensor noise, "
        "deep focus, no cinematic lighting, no color grading."),
}


def resolve(p):
    p = Path(p).expanduser()
    return p if p.is_absolute() else (ROOT / p).resolve()


PERSON_FIELDS = (("outfit", "outfit"), ("hair", "hairstyle"), ("shoes", "shoes"))


def person_prompt(p):
    """person: base / outfit / hair / shoes / audience。未指定の項目は @Image1 のまま"""
    s = f"Replace the wooden mannequin in @Video1 with the person from @Image1"
    s += f" ({p['base']})." if p.get("base") else "."
    s += " Keep the face and identity from @Image1."
    for key, label in PERSON_FIELDS:
        s += f" {label.capitalize()}: {p[key]}." if p.get(key) else f" Keep the {label} from @Image1."
    if p.get("audience"):
        s += (f" This video is made for {p['audience']}: the person should look like a relatable peer of that audience, "
              "with natural, approachable body language and grooming that fits them.")
    return s


def build_prompt(job):
    parts = [
        person_prompt(job["person"]),
        f"Follow the exact body motion and timing of @Video1: {job['action_desc']}",
        "Set the scene in the space from @Image2 (use only the room itself, not any people, props or UI in that image): "
        f"{job['space_desc']}",
        CAMERAS[job.get("camera", "smartphone_handheld")],
        "Photorealistic, natural skin texture, realistic fabric wrinkles.",
        job.get("audio", "Quiet room tone only, no music, no speech."),
    ]
    if job.get("extra"):
        parts.append(job["extra"])
    return " ".join(parts)


def duration_of(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    job_file = Path(sys.argv[1])
    go = "--yes" in sys.argv
    job = json.loads(job_file.read_text())
    name = job.get("name", job_file.stem)
    motion, model_img, space_img = resolve(job["motion"]), resolve(job["person"]["image"]), resolve(job["space_image"])
    for p in (motion, model_img, space_img):
        if not p.exists():
            sys.exit(f"見つからない: {p}")

    res = job.get("resolution", "720p")
    dur = duration_of(motion)
    rate = USD_PER_SEC.get(res)
    est = f"${dur * rate:.2f} (推定)" if rate else "不明 (この解像度は未計測)"
    prompt = build_prompt(job)
    print(f"job: {name}\nmotion: {motion} ({dur:.1f}s)\nmodel: {model_img}\nspace: {space_img}\n"
          f"resolution: {res}  概算費用: {est}\n\nprompt:\n{prompt}\n")
    if not go:
        print("dry-run。実行するには --yes を付ける")
        return

    atlas = Atlas()
    body = {
        "prompt": prompt,
        "reference_videos": [atlas.upload(motion)],
        "reference_images": [atlas.upload(model_img), atlas.upload(space_img)],
        "omni_reference_task_type": "edit", "duration": -1, "ratio": "adaptive",
        "resolution": res, "generate_audio": job.get("generate_audio", True), "watermark": False,
    }
    outdir = ROOT / "outputs" / f"{name}_{time.strftime('%Y%m%d_%H%M%S')}"
    outdir.mkdir(parents=True)
    (outdir / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=1))
    (outdir / "request.json").write_text(json.dumps({"model": MODEL, **body}, ensure_ascii=False, indent=1))

    pid = atlas.submit(MODEL, body)
    print("submitted", pid, "→", outdir, flush=True)
    s = atlas.wait(pid, log=lambda m: print(m, flush=True))
    meta = {k: s.get(k) for k in ("id", "status", "error", "price", "total_tokens", "created_at", "completed_at")}
    (outdir / "result.json").write_text(json.dumps(meta, indent=1))
    if s["status"] != "completed":
        sys.exit(f"失敗: {meta}")

    mp4 = atlas.download(s["outputs"][0], outdir / f"{name}.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vf", "fps=0.5,scale=320:-1,tile=5x2",
                    "-frames:v", "1", "-y", str(outdir / "contact.jpg")], check=False)
    print(f"saved {mp4}  price ${meta['price']}")
    if "--open" in sys.argv:
        subprocess.run(["open", str(mp4)])

if __name__ == "__main__":
    try:
        main()
    except AtlasError as e:
        sys.exit(str(e))
