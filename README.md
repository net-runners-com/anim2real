# anim2real

`anim` で作ったマネキンのモーション動画を、Seedance 2.5（Atlas Cloud）で「指定した人物 × 指定した空間 × スマホ撮影風」の実写動画に変換する。

## 入力（ジョブ設定 `jobs/*.json`）

| キー | 内容 |
|---|---|
| `motion` | マネキン（Tポーズのリグ）でレンダした動画。例 `../anim/renders/calf_stretch_v2.mp4`。4〜30秒・24fps 以上 |
| `person.image` | 人物モデルの画像（顔と人物像はこの画像から取る） |
| `person.base` | 人物の基本像（例: `a young Japanese woman in her late 20s`） |
| `person.outfit` / `person.hair` / `person.shoes` | 服装・髪型・靴。書かなかった項目は画像のまま |
| `person.audience` | どんな人に見せる動画か。その人たちが身近に感じる人物像・雰囲気に寄せる |
| `space_image` / `space_desc` | 空間の画像と英文説明（置きたくない物は "no mat" のように明記） |
| `action_desc` | 動きの説明（動画の動きを補足する） |
| `camera` | `smartphone_handheld`（デフォルト）/ `tripod_phone` |
| `resolution` | `720p` 推奨（費用を実測済みなのはこれだけ） |
| `audio` | 環境音の指示 |

設定の値は英語で書く（Seedance は日本語の指示を正しく読まない恐れがあるため）。

## 実行

```bash
python3 pipeline.py jobs/calf_stretch_studio.json           # dry-run：プロンプトと概算費用だけ表示
python3 pipeline.py jobs/calf_stretch_studio.json --yes --open
```

出力は `outputs/<name>_<日時>/` に、`<name>.mp4`・`contact.jpg`（2秒ごとのコマ）・`request.json`・`result.json`（実際の費用）を保存する。
同じ内容のファイルは再アップロードしない（`outputs/.upload_cache.json`）。

## 費用

- 実測：720p・19.7秒で **$7.14**（約 $0.36/秒）。表示されている "$0.134" は最低単価であって、実際の費用ではない。
- 編集モードでは、出力の縦横比と長さが入力動画と同じになる。縦長にしたいときは、`anim` 側で 9:16 にレンダし直す。
- 送信した時点で課金される。キャンセル用の API は見つかっていない。

## Atlas Cloud クライアント（`atlas.py`）

`pipeline.py` からも使い、単体でも動く。依存は標準ライブラリと curl だけ。

```bash
python3 atlas.py models seedance        # モデル一覧と基本価格
python3 atlas.py schema bytedance/seedance-2.5/reference-to-video
python3 atlas.py upload assets/spaces/white_studio.png
python3 atlas.py status <prediction_id> # 状態・実際の費用・出力 URL
```

```python
from atlas import Atlas
a = Atlas()
pid = a.submit("bytedance/seedance-2.5/reference-to-video", {"prompt": "...", "reference_images": [a.upload("x.png")]})
s = a.wait(pid); a.download(s["outputs"][0], "out.mp4")
```

APIキーは `.env` の `ATLASCLOUD_API_KEY` から読む（git の管理対象外）。

## anim との連携

1. `anim/scripts/8x_*.py` でモーションを作り、`anim/renders/*.mp4` にレンダする
2. `jobs/` に設定を作り、`motion` にそのパスを書く
3. `pipeline.py` で dry-run してプロンプトを確認してから `--yes` で実行する
