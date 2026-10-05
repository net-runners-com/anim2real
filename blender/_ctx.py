"""オペレーターを VIEW_3D コンテキストで実行する。
GUI（MCP タイマー経由）では override が必要。バックグラウンド（blender -b）ではそのまま呼ぶ。"""
import bpy


def view3d_override():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                region = next(r for r in area.regions if r.type == 'WINDOW')
                return dict(window=win, screen=win.screen, area=area, region=region,
                            scene=win.scene, view_layer=win.view_layer)
    return None


def run(fn):
    ov = None if bpy.app.background else view3d_override()
    if ov is None:
        return fn()
    with bpy.context.temp_override(**ov):
        return fn()
