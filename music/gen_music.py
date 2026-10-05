#!/usr/bin/env python3
"""ACE-Step 1.5 でインスト曲を 1 曲作る（ACE-Step の環境の中で動く）。
直接は呼ばず、add_music.py から次の形で実行される:

    uv run --project $ACESTEP_ROOT python music/gen_music.py --duration 23 --caption "..." --out x.wav

ACE-Step 本体とモデル（約 9.4GB）はこのリポジトリに含まない。README の「曲を付ける」を参照。
"""
import argparse, json, os, shutil, sys, time
from pathlib import Path

ACE_ROOT = Path(os.environ.get("ACESTEP_ROOT", Path.home() / "ACE-Step-1.5"))
sys.path.insert(0, str(ACE_ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, required=True, help="秒（10〜600）")
    ap.add_argument("--caption", required=True)
    ap.add_argument("--bpm", type=int)
    ap.add_argument("--key", default="")
    ap.add_argument("--ts", default="", help="拍子: 2 / 3 / 4 / 6")
    ap.add_argument("--seed", type=int, default=-1)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler
    from acestep.inference import GenerationParams, GenerationConfig, generate_music

    t0 = time.time()
    dit = AceStepHandler()
    msg, ok = dit.initialize_service(project_root=str(ACE_ROOT), config_path="acestep-v15-turbo",
                                     device="auto", offload_to_cpu=False)
    if not ok:
        sys.exit(f"DiT の初期化に失敗: {msg}")
    llm = LLMHandler()
    msg, ok = llm.initialize(checkpoint_dir=str(ACE_ROOT / "checkpoints"),
                             lm_model_path=os.environ.get("ACESTEP_LM", "acestep-5Hz-lm-1.7B"),
                             backend=os.environ.get("ACESTEP_LM_BACKEND", "mlx"),
                             device="auto", offload_to_cpu=False, dtype=None)
    if not ok:
        sys.exit(f"LM の初期化に失敗: {msg}")

    duration = max(10.0, round(a.duration, 1))
    params = GenerationParams(
        task_type="text2music", caption=a.caption,
        lyrics="[Intro]\n[Instrumental]\n[Outro]", instrumental=True,
        bpm=a.bpm, keyscale=a.key, timesignature=a.ts, duration=duration,
        inference_steps=8, guidance_scale=1.0, shift=3.0,
        thinking=True,                       # 構成が安定しやすい
        use_cot_metas=False, use_cot_caption=False, use_cot_language=False,   # 指定した BPM・調を書き換えさせない
        seed=a.seed,
    )
    tmp = Path(a.out).with_suffix("")
    tmp.mkdir(parents=True, exist_ok=True)
    res = generate_music(dit, llm, params=params, config=GenerationConfig(batch_size=1, audio_format="wav"),
                         save_dir=str(tmp))
    if not res.success or not res.audios:
        sys.exit(f"生成に失敗: {res.status_message}")
    shutil.move(res.audios[0]["path"], a.out)
    shutil.rmtree(tmp, ignore_errors=True)
    seed = res.audios[0].get("params", {}).get("seed")
    print(json.dumps({"out": a.out, "seed": seed, "duration": duration, "sec": round(time.time() - t0, 1)}))


if __name__ == "__main__":
    main()
