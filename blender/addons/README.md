# 同梱アドオン

| ファイル | 内容 | ライセンス |
|---|---|---|
| `blender_mcp-1.0.0.zip` | Blender Lab 公式の MCP アドオン（https://www.blender.org/lab/mcp-server/）。Blender の画面を開いたまま、外部から bpy コードを送れるようにする。GUI モード（`make.py --gui`）を使うときだけ必要 | GPL-3.0-or-later（作者: Blender Lab。中身は改変していない。全文は `COPYING-GPL-3.0.txt`） |

Rigify（人体リグ）は Blender に最初から入っているので、同梱していない。

インストールは `python3 blender/make.py setup`。手動で入れる場合は、Blender → 編集 → プリファレンス → Get Extensions → 右上の ▾ → 「ディスクからインストール」でこの zip を選ぶ。
