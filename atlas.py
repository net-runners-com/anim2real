#!/usr/bin/env python3
"""Atlas Cloud API クライアント（標準ライブラリのみ）

ライブラリ:
  from atlas import Atlas
  a = Atlas()                         # .env の ATLASCLOUD_API_KEY を読む
  url = a.upload(Path("x.png"))       # sha256 キャッシュ付き
  pid = a.submit("bytedance/seedance-2.5/reference-to-video", body)
  s = a.wait(pid)                     # completed / failed / timeout まで待つ
  a.download(s["outputs"][0], Path("out.mp4"))

CLI:
  python3 atlas.py models [絞り込み語]       モデル一覧と基本価格
  python3 atlas.py schema <model>           パラメータ一覧
  python3 atlas.py upload <file>            アップロードして URL を表示
  python3 atlas.py status <prediction_id>   状態・費用・出力 URL
"""
import hashlib, json, os, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = "https://api.atlascloud.ai/api/v1"
CACHE = ROOT / "outputs/.upload_cache.json"
UA = "curl/8.7.1"  # 既定の Python UA だと弾かれることがある


class AtlasError(RuntimeError):
    pass


def _http(url, key=None, body=None, timeout=120):
    headers = {"User-Agent": UA}
    if key:
        headers["Authorization"] = "Bearer " + key
    if body is not None:
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                               method="POST" if body is not None else "GET", headers=headers)
    try:
        return json.load(urllib.request.urlopen(r, timeout=timeout))
    except urllib.error.HTTPError as e:
        raise AtlasError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:400]}") from None


def load_key():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))
    key = os.environ.get("ATLASCLOUD_API_KEY")
    if not key:
        raise AtlasError("ATLASCLOUD_API_KEY が .env にも環境変数にもない")
    return key


class Atlas:
    def __init__(self, key=None):
        self.key = key or load_key()

    def api(self, path, body=None):
        return _http(BASE + path, self.key, body)

    # --- media -------------------------------------------------------------
    def upload(self, path):
        """同じ内容のファイルは再アップロードしない"""
        path = Path(path)
        cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        if h in cache:
            return cache[h]
        # multipart は curl に任せる（標準ライブラリだけだと冗長になる）
        out = subprocess.run(["curl", "-s", "-X", "POST", BASE + "/model/uploadMedia",
                              "-H", "Authorization: Bearer " + self.key, "-H", "User-Agent: " + UA,
                              "-F", f"file=@{path}"], capture_output=True, text=True, check=True).stdout
        try:
            url = ((json.loads(out) or {}).get("data") or {}).get("download_url")
        except json.JSONDecodeError:
            url = None
        if not url:
            raise AtlasError(f"upload 失敗 {path}: {out[:300]}")
        cache[h] = url
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1))
        return url

    @staticmethod
    def download(url, dest):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-sL", "-o", str(dest), url], check=True)
        return dest

    # --- predictions -------------------------------------------------------
    def submit(self, model, body, endpoint="/model/generateVideo"):
        """送信した時点で課金される。キャンセル API は確認できていない"""
        r = self.api(endpoint, {"model": model, **body})
        if r.get("code") not in (200, None) or not r.get("data"):
            raise AtlasError(f"submit 失敗: {json.dumps(r)[:400]}")
        return r["data"]["id"]

    def status(self, pid):
        return self.api(f"/model/prediction/{pid}")["data"]

    def wait(self, pid, interval=10, timeout=1800, log=print):
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(interval)
            s = self.status(pid)
            if s.get("status") in ("completed", "failed", "timeout"):
                return s
            log(f"  {int(time.time() - t0)}s {s.get('status')}")
        raise AtlasError(f"timeout ({timeout}s) {pid}")

    # --- catalog (認証不要) ----------------------------------------------------
    @staticmethod
    def models(query=""):
        data = _http(BASE + "/models").get("data", [])
        return [m for m in data if query.lower() in m.get("model", "").lower()]

    @staticmethod
    def schema(model):
        m = next((m for m in Atlas.models(model) if m["model"] == model), None)
        if not m:
            raise AtlasError(f"モデルが見つからない: {model}")
        return _http(m["schema"])


def _schema_props(o, out):
    if isinstance(o, dict):
        if "properties" in o and "prompt" in o["properties"]:
            out.update(o["properties"])
        for v in o.values():
            _schema_props(v, out)
    elif isinstance(o, list):
        for v in o:
            _schema_props(v, out)
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "models":
        for m in Atlas.models(args[0] if args else ""):
            print(f"{m['model']:60} ${((m.get('price') or {}).get('actual') or {}).get('base_price', '?')}")
    elif cmd == "schema":
        for k, v in _schema_props(Atlas.schema(args[0]), {}).items():
            extra = f" enum={v['enum']}" if v.get("enum") else ""
            print(f"{k:28} {v.get('type', ''):8} default={v.get('default')}{extra}")
    elif cmd == "upload":
        print(Atlas().upload(args[0]))
    elif cmd == "status":
        s = Atlas().status(args[0])
        print(json.dumps({k: s.get(k) for k in ("status", "error", "price", "total_tokens", "outputs")},
                         ensure_ascii=False, indent=1))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    try:
        main()
    except AtlasError as e:
        sys.exit(str(e))
