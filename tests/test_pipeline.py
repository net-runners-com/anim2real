"""処理テスト。Atlas Cloud にも Blender にも繋がない（費用ゼロ・数秒）。

  python3 -m unittest discover -s tests -v
  RUN_BLENDER=1 python3 -m unittest discover -s tests -v   # Blender で実際に動画を作るテストも（1〜2 分）
"""
import hashlib, io, json, os, py_compile, subprocess, sys, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "blender")]
import atlas, make, pipeline  # noqa: E402

PERSON = {"image": "assets/models/woman_beige_suit.png", "base": "a man in his 40s",
          "outfit": "navy polo shirt", "audience": "factory workers"}


class Prompt(unittest.TestCase):
    def test_specified_fields_are_used(self):
        p = pipeline.person_prompt(PERSON)
        self.assertIn("(a man in his 40s)", p)
        self.assertIn("Outfit: navy polo shirt.", p)
        self.assertIn("made for factory workers", p)

    def test_unspecified_fields_keep_image(self):
        p = pipeline.person_prompt(PERSON)
        self.assertIn("Keep the hairstyle from @Image1.", p)
        self.assertIn("Keep the shoes from @Image1.", p)

    def test_full_prompt_references_all_inputs(self):
        job = json.loads((ROOT / "jobs/calf_stretch_studio.json").read_text())
        p = pipeline.build_prompt(job)
        for ref in ("@Video1", "@Image1", "@Image2"):
            self.assertIn(ref, p)
        self.assertIn(pipeline.CAMERAS["smartphone_handheld"], p)

    def test_unknown_camera_fails(self):
        job = json.loads((ROOT / "jobs/calf_stretch_studio.json").read_text())
        job["camera"] = "drone"
        with self.assertRaises(KeyError):
            pipeline.build_prompt(job)


class Jobs(unittest.TestCase):
    def test_every_job_points_to_existing_files(self):
        for f in (ROOT / "jobs").glob("*.json"):
            with self.subTest(job=f.name):
                j = json.loads(f.read_text())
                self.assertTrue(pipeline.resolve(j["person"]["image"]).exists())
                self.assertTrue(pipeline.resolve(j["space_image"]).exists())
                m = j["motion"]
                if isinstance(m, dict):
                    self.assertTrue((ROOT / "blender/motions" / f"{m['blender']}.py").exists())
                    self.assertTrue((ROOT / "blender/spaces" / f"{m.get('space', 'basic_room')}.py").exists())
                pipeline.build_prompt(j)

    def test_dry_run_never_touches_atlas(self):
        job = ROOT / "jobs/calf_stretch_studio.json"
        with mock.patch.object(sys, "argv", ["pipeline.py", str(job)]), \
             mock.patch.object(pipeline, "Atlas", side_effect=AssertionError("Atlas を呼んだ")), \
             mock.patch.object(make, "run_headless", side_effect=AssertionError("Blender を呼んだ")), \
             redirect_stdout(io.StringIO()) as out:
            pipeline.main()
        self.assertIn("dry-run", out.getvalue())


class Blender(unittest.TestCase):
    def test_scripts_compile(self):
        for f in list((ROOT / "blender").rglob("*.py")):
            with self.subTest(f=f.name):
                py_compile.compile(str(f), doraise=True)

    def test_steps_order_and_params(self):
        s = make.steps("calf_stretch", "basic_room", {"cam_yaw": 30})
        self.assertEqual([n for n, _, _ in s], ["rig", "space", "motion", "save", "render"])
        self.assertEqual(s[1][2]["space_params"], {"cam_yaw": 30})
        self.assertTrue(s[-1][2]["out"].endswith("calf_stretch__basic_room.mp4"))

    def test_code_header_injects_params(self):
        code = make.code_of("result = PARAMS", {"a": 1, "s": "日本語"})
        g = {}
        exec(code, g)
        self.assertEqual(g["result"], {"a": 1, "s": "日本語"})

    def test_missing_motion_is_reported(self):
        with self.assertRaises(SystemExit):
            make.check("no_such_motion", "basic_room")

    def test_dry_run_does_not_launch_blender(self):
        with mock.patch.object(make, "run_headless", side_effect=AssertionError), \
             mock.patch.object(make, "run_gui", side_effect=AssertionError), \
             redirect_stdout(io.StringIO()):
            make.build("calf_stretch", dry_run=True, force=True)

    @unittest.skipUnless(os.environ.get("RUN_BLENDER"), "RUN_BLENDER=1 のときだけ")
    def test_headless_build_makes_video(self):
        mp4 = make.build("calf_stretch", force=True)
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height,nb_frames",
                              "-of", "csv=p=0", str(mp4)], capture_output=True, text=True).stdout.strip()
        w, h, n = map(int, out.split(","))
        self.assertGreaterEqual(w * h, 409_600)   # Seedance の最小画素数
        self.assertEqual(n, 480)


class Atlas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "cache.json"
        self.patch = mock.patch.object(atlas, "CACHE", self.cache)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_upload_cache_hit_skips_network(self):
        f = Path(self.tmp.name) / "a.png"
        f.write_bytes(b"x")
        self.cache.write_text(json.dumps({hashlib.sha256(b"x").hexdigest(): "https://cached"}))
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("通信した")):
            self.assertEqual(atlas.Atlas(key="k").upload(f), "https://cached")

    def test_upload_stores_new_url(self):
        f = Path(self.tmp.name) / "b.png"
        f.write_bytes(b"y")
        done = subprocess.CompletedProcess([], 0, stdout=json.dumps({"data": {"download_url": "https://new"}}))
        with mock.patch.object(subprocess, "run", return_value=done):
            self.assertEqual(atlas.Atlas(key="k").upload(f), "https://new")
        self.assertIn("https://new", self.cache.read_text())

    def test_upload_failure_raises(self):
        f = Path(self.tmp.name) / "c.png"
        f.write_bytes(b"z")
        with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout="null")):
            with self.assertRaises(atlas.AtlasError):
                atlas.Atlas(key="k").upload(f)

    def test_submit_insufficient_balance_raises(self):
        a = atlas.Atlas(key="k")
        with mock.patch.object(a, "api", return_value={"code": 402, "msg": "insufficient balance"}):
            with self.assertRaises(atlas.AtlasError):
                a.submit("m", {})

    def test_wait_returns_on_terminal_status(self):
        a = atlas.Atlas(key="k")
        seq = iter([{"status": "processing"}, {"status": "failed", "error": "x"}])
        with mock.patch.object(a, "status", side_effect=lambda _: next(seq)), mock.patch("time.sleep"):
            self.assertEqual(a.wait("id", log=lambda m: None)["status"], "failed")

    def test_missing_key_raises(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(atlas, "ROOT", Path(self.tmp.name)):
            with self.assertRaises(atlas.AtlasError):
                atlas.load_key()


if __name__ == "__main__":
    unittest.main()
