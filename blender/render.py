"""低品質レンダ（Seedance に動きを渡すためだけなので画質は要らない）。
PARAMS = {'out': path, 'still': bool}  ← make.py が先頭に差し込む。
動画: 854x480（Seedance の最小 W*H 409,600 を満たす）・Eevee 4 サンプル（1 だと壁がザラつく）・H.264 低ビットレート。
still: 空間の参照画像。人形を隠して 1280x720 で frame 1 を PNG に。"""
import bpy, os

P = globals().get('PARAMS', {})
OUT = P['out']
scn = bpy.context.scene
r = scn.render
try: r.engine = 'BLENDER_EEVEE_NEXT'
except TypeError: r.engine = 'BLENDER_EEVEE'
ee = scn.eevee
for k, v in (('use_raytracing', False), ('use_shadows', True), ('taa_render_samples', 4 if not P.get('still') else 16)):
    if hasattr(ee, k): setattr(ee, k, v)
scn.view_settings.view_transform = 'AgX'
r.fps = 24; r.resolution_percentage = 100
os.makedirs(os.path.dirname(OUT), exist_ok=True)

figure = [o for o in bpy.data.objects if o.parent and o.parent.name == 'rig']
if P.get('still'):
    r.resolution_x, r.resolution_y = 1280, 720
    for o in figure: o.hide_render = True
    r.image_settings.media_type = 'IMAGE'; r.image_settings.file_format = 'PNG'
    scn.frame_set(1); r.filepath = OUT
    bpy.ops.render.render(write_still=True)
    for o in figure: o.hide_render = False
else:
    r.resolution_x, r.resolution_y = 854, 480
    r.image_settings.media_type = 'VIDEO'; r.image_settings.file_format = 'FFMPEG'
    r.ffmpeg.format = 'MPEG4'; r.ffmpeg.codec = 'H264'; r.ffmpeg.constant_rate_factor = 'LOW'; r.ffmpeg.gopsize = 12
    r.filepath = OUT; r.use_file_extension = False
    bpy.ops.render.render(animation=True)

result = {'out': OUT, 'frames': (scn.frame_start, scn.frame_end), 'bytes': os.path.getsize(OUT) if os.path.exists(OUT) else None}
