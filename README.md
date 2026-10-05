# anim2real

Blender で作った「木の人形が動く動画」を、AI 動画生成（Seedance 2.5 / Atlas Cloud）で
**指定した人物が、指定した場所で、スマホで撮ったように動く実写風の動画**に変換するツールです。

```
① Blender（自動）              ② Atlas Cloud（Seedance 2.5）           ③ 完成
人体リグ ＋ 木の人形             人形 → 人物の画像の人に差し替え
＋ 空間の土台（床・壁・椅子）  →  背景 → 空間の画像の場所に差し替え   →  実写風の動画（mp4）
＋ モーション → 低画質の動画     撮り方 → スマホの手持ち風
```

- 動きは Blender で決めるので、毎回同じ動きになります。
- 人物・服装・場所は画像と設定ファイルで切り替えます。
- Blender のレンダは動きを伝えるためだけのものなので、画質は低くてかまいません（854x480、1本 1 分弱）。

---

## 1. 必要なもの

| もの | バージョン | 用途 |
|---|---|---|
| macOS / Linux | | Windows は未確認 |
| Python | 3.9 以上（追加のパッケージは不要） | |
| Blender | 5.1 以上 | リグ・人形・空間・モーション・レンダ |
| ffmpeg（ffprobe を含む） | | 動画の長さを測る・確認用のコマ画像を作る |
| curl | | アップロード・ダウンロード |
| Atlas Cloud のアカウントと API キー | | 動画生成（**有料**） |

macOS で ffmpeg を入れる場合: `brew install ffmpeg`

Blender が `/Applications/Blender.app` 以外にある場合は、環境変数でパスを指定します。
```bash
export BLENDER_BIN=/path/to/blender
```

## 2. セットアップ

```bash
cd anim2real
cp .env.example .env          # .env を開いて ATLASCLOUD_API_KEY= の後ろに自分のキーを書く
python3 -m unittest discover -s tests     # 処理テスト（通信なし・費用ゼロ・数秒）
```

`.env` は人に渡さないでください（API キーが入っています）。

## 3. 使い方

### いちばん簡単な流れ

```bash
# 1) 確認だけ（Blender も動かさず、お金もかからない）
python3 pipeline.py jobs/calf_stretch_studio.json

# 2) 本番（Blender で動きの動画を作る → Atlas Cloud で生成。約 $7 かかる）
python3 pipeline.py jobs/calf_stretch_studio.json --yes --open
```

`--yes` を付けたときだけ実際に生成され、料金がかかります。付けなければ、送る内容（プロンプト）と概算費用を表示するだけです。

完成した動画は `outputs/<ジョブ名>_<日時>/` に入ります。

| ファイル | 中身 |
|---|---|
| `<ジョブ名>.mp4` | 完成した動画 |
| `contact.jpg` | 2 秒ごとのコマを並べた確認用の画像 |
| `result.json` | **実際にかかった費用**（`price`、米ドル） |
| `request.json` / `job.json` | 送った内容（再現用） |

### Blender の部分だけ動かす

```bash
python3 blender/make.py build calf_stretch                 # 画面なしで動画を作る（約 45 秒）
python3 blender/make.py build calf_stretch --dry-run       # 手順だけ表示
python3 blender/make.py build calf_stretch --force         # 作り直す（既にあれば普段は再利用する）
```

できるもの: `blender/renders/calf_stretch__basic_room.mp4`（動きの動画）と
`blender/scenes/calf_stretch__basic_room.blend`（Blender で開いて中身を見られる）

### Blender の画面を見ながら動かす（任意）

途中経過を Blender の画面で見たいとき用です。同梱の MCP アドオンを使います。

```bash
python3 blender/make.py setup        # 同梱アドオンを Blender に入れる（最初の 1 回だけ）
blender/start.sh                     # Blender を起動（ポート 9878 で待ち受け）
python3 blender/make.py build calf_stretch --gui --force
```

ほかの Blender とぶつかる場合は、`BLENDER_MCP_PORT=9879 blender/start.sh` のように別のポートを使い、
`make.py` を動かすときにも同じ `BLENDER_MCP_PORT` を指定します。

## 4. ジョブ設定（`jobs/*.json`）

1 本の動画 = 1 つの設定ファイルです。既存のファイルを複製して書き換えるのが早いです。
**値は英語で書いてください**（Seedance は日本語の指示を正しく読まない恐れがあります）。

```json
{
 "name": "calf_stretch_studio",
 "motion": {"blender": "calf_stretch", "space": "basic_room"},
 "person": {
  "image": "assets/models/woman_beige_suit.png",
  "base": "a young Japanese woman in her late 20s",
  "outfit": "white blouse, beige tweed jacket and beige wide-leg trousers",
  "hair": "dark hair tied back in a low ponytail",
  "shoes": "white sneakers",
  "audience": "Japanese office workers in their 20s to 40s who sit at a desk all day"
 },
 "space_image": "assets/spaces/white_studio.png",
 "space_desc": "a plain off-white wall, light grey concrete-like floor with no mat or rug, ...",
 "action_desc": "she sits on the chair and does a gentle seated calf and hamstring stretch, ...",
 "camera": "smartphone_handheld",
 "resolution": "720p",
 "audio": "Quiet room tone only, no music, no speech."
}
```

| キー | 意味 |
|---|---|
| `motion` | 動きの元。`{"blender": モーション名, "space": 空間名}` なら Blender で自動で作る。既にある動画のパス（例 `"my_motion.mp4"`）も書ける（4〜30 秒、24fps 以上） |
| `motion.space_params` | 空間の土台の数値の上書き（例 `{"cam_yaw": 30, "chair": false}`）。項目は `blender/spaces/basic_room.py` の大文字の定数 |
| `person.image` | 人物の画像。**顔と人物像はこの画像から取る** |
| `person.base` | どんな人か（年代・性別など） |
| `person.outfit` / `hair` / `shoes` | 服装・髪型・靴。**書かなかった項目は画像のまま** |
| `person.audience` | 誰に見せる動画か。その人たちが身近に感じる見た目・雰囲気に寄せる |
| `space_image` | 場所の画像。**見た目（壁・床・家具の雰囲気）はこの画像で決まる**。写っている人物や再生ボタンなどは使わないよう指示している |
| `space_desc` | 場所の説明。置きたくない物は `no mat` のように明記する |
| `action_desc` | 動きの説明（動画の動きの補足） |
| `camera` | `smartphone_handheld`（スマホ手持ち、既定）/ `tripod_phone`（スマホを三脚に固定） |
| `resolution` | `720p` を推奨（費用を実測しているのはこれだけ） |
| `audio` | 音の指示。不要なら `"generate_audio": false` も書ける |
| `extra` | 追加の指示（任意） |

## 5. 新しい動き・空間を足す

### 動き（`blender/motions/<名前>.py`）

`calf_stretch.py` を複製して、`side()` のポーズの表（フレーム番号とポーズ）を書き換えます。

- 脚は IK（足首の位置と向き）、腕は手首の目標位置で動かします。
- 長さは `FRAMES`（24fps。480 = 20 秒）で決まります。Seedance に渡せるのは **4〜30 秒**です。
- 確認は `python3 blender/make.py build <名前> --force` で作り、動画を見るのが早いです。

### 空間の土台（`blender/spaces/<名前>.py`）

`basic_room.py` は**例**です。Blender の空間は「床・壁・椅子・カメラの位置」を Seedance に伝えるための最低限の形で、
**見た目はジョブの `space_image` で決まります**。
家具の配置やカメラの角度を変えたいときだけ、複製して作り替えてください（数値だけなら `space_params` で足ります）。

椅子の高さ（`SEAT_TOP`）とモーションの座る高さは対になっています。片方だけ変えると、お尻が浮いたり椅子にめり込んだりします。

## 6. 費用と注意

- **費用の実測**: 720p・約 20 秒で **$7.14／本**（約 $0.36／秒）。Atlas Cloud のモデル一覧に出る「$0.134」は最低単価で、実際の費用ではありません。
- **送った時点で課金されます。** 途中で止める方法（キャンセル API）は見つかっていません。必ず dry-run でプロンプトを確認してから `--yes` を付けてください。
- 残高が足りないと `HTTP 402: insufficient balance` で止まります（この場合は課金されません）。
- 出力の縦横比と長さは、元の動きの動画と同じになります（Seedance の編集モードの仕様）。縦長の動画がほしい場合は、Blender のレンダを縦長にする必要があります（現状は横長 854x480 だけ）。
- 人物の画像に実在の人を使う場合は、本人の許可を取ってください。
- 同じ画像・動画は 2 回目からアップロードしません（`outputs/.upload_cache.json`）。

## 7. Atlas Cloud を直接使う（`atlas.py`）

```bash
python3 atlas.py models seedance          # モデル一覧と基本価格
python3 atlas.py schema bytedance/seedance-2.5/reference-to-video   # 指定できるパラメータ
python3 atlas.py upload <ファイル>         # アップロードして URL を表示
python3 atlas.py status <prediction_id>   # 状態・実際の費用・出力の URL
```

Python から使う場合:
```python
from atlas import Atlas
a = Atlas()
pid = a.submit("bytedance/seedance-2.5/reference-to-video",
               {"prompt": "...", "reference_images": [a.upload("x.png")]})
s = a.wait(pid)
a.download(s["outputs"][0], "out.mp4")
```

## 8. テスト

```bash
python3 -m unittest discover -s tests -v                  # 通信なし・費用ゼロ（18 件、1 秒未満）
RUN_BLENDER=1 python3 -m unittest discover -s tests -v    # Blender で実際に動画を作るテストも（約 45 秒）
```

Atlas Cloud への送信はテストしていません（毎回料金がかかるため）。テストでは通信部分を差し替えています。

## 9. フォルダ構成

```
anim2real/
  pipeline.py            全体を実行（Blender → Atlas Cloud → 保存）
  atlas.py               Atlas Cloud のクライアント
  jobs/                  ジョブ設定（1 本 = 1 ファイル）
  assets/models/         人物の画像
  assets/spaces/         空間の画像
  blender/
    make.py              Blender 側の実行（画面なし / 画面あり）
    rig.py               人体リグ（Rigify）＋ 木の人形
    spaces/basic_room.py 空間の土台（例）
    motions/             モーション
    render.py            低画質レンダ
    addons/              同梱の MCP アドオン（GPL-3.0。詳細は addons/README.md）
    bl.py, start.sh      画面ありモード用
  tests/                 処理テスト
  outputs/               生成結果（人に渡さない）
```

## 10. うまくいかないとき

| 症状 | 対処 |
|---|---|
| `ATLASCLOUD_API_KEY が .env にも環境変数にもない` | `.env` にキーを書く |
| `HTTP 402: insufficient balance` | Atlas Cloud で残高をチャージする |
| `Blender が失敗した` | `BLENDER_BIN` が Blender 5.1 以上を指しているか確認する。`--dry-run` で手順を確認する |
| `--gui` で `Connection refused` | `blender/start.sh` で Blender を起動したか、ポートが合っているか確認する。`make.py setup` 済みか確認する |
| 人物の顔が画像と違う | `person.base` と画像の印象を揃える。顔が大きく写った画像を使う |
| 置いてほしくない物が出る | `space_desc` に `no ...` と書く。`space_image` に写っていないか確認する |
