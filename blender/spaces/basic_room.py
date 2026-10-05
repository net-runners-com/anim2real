"""空間の土台（例）: 床・奥の壁・左手の壁（窓の開口）・椅子・照明・カメラ。
見た目（壁の色・床の素材・置物など）はジョブの `space_image` の画像で Seedance が決める。
ここで作るのは、動きと構図を Seedance に伝えるための最低限の形だけ。
別の空間がほしいときは、このファイルを複製して形（家具の配置・カメラ）を変える。
ジョブの `blender.space_params` で下の大文字の定数を上書きできる（make.py が PARAMS として渡す）。
カメラ位置と椅子の高さは calf_stretch のモーションに合わせてある（SEAT_TOP はモーションの SIT_Z と対）。"""
import bpy, bmesh, math
from mathutils import Vector
import _ctx

SPACE = "basic_room"
CAM_YAW = 58.0          # deg: 0 = 正面(-Y から見る)、90 = 真横(+X から見る)
CAM_DIST, CAM_H, CAM_LENS = 3.9, 1.0, 45
AIM = Vector((0.0, -0.38, 0.62))
SEAT_TOP = 0.43
WALL_C, FLOOR_C = (0.82, 0.80, 0.76), (0.55, 0.55, 0.54)
CHAIR, WINDOW = True, True

for _k, _v in globals().get('PARAMS', {}).get('space_params', {}).items():   # ジョブからの上書き
    globals()[_k.upper()] = Vector(_v) if _k.upper() == 'AIM' else _v


def wipe():
    rig = bpy.data.objects['rig']
    keep = {rig} | set(rig.children) | {bpy.data.objects.get('metarig')}
    for o in list(bpy.data.objects):
        if o not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras, bpy.data.materials):
        for d in list(coll):
            if d.users == 0: coll.remove(d)
    col = bpy.data.collections.get('Space') or bpy.data.collections.new('Space')
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    return col


def mat(name, rgb, rough=0.6, spec=0.3, noise=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Roughness'].default_value = rough
    if 'Specular IOR Level' in b.inputs: b.inputs['Specular IOR Level'].default_value = spec
    if noise:   # コンクリート風のムラ
        tx = nt.nodes.new('ShaderNodeTexNoise'); tx.inputs['Scale'].default_value = 6.0; tx.inputs['Detail'].default_value = 8.0
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color = (*[c * (1 - noise) for c in rgb], 1)
        ramp.color_ramp.elements[1].color = (*[min(1, c * (1 + noise)) for c in rgb], 1)
        nt.links.new(tx.outputs['Fac'], ramp.inputs['Fac']); nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    else:
        b.inputs['Base Color'].default_value = (*rgb, 1)
    m.diffuse_color = (*rgb, 1)
    return m


def obj(col, name, me, loc=(0, 0, 0), material=None):
    o = bpy.data.objects.new(name, me); col.objects.link(o); o.location = loc
    if material: me.materials.append(material)
    for p in me.polygons: p.use_smooth = True
    return o


def box(col, name, size, loc, material, bevel=0.0):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0); bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bm.to_mesh(me); bm.free()
    o = obj(col, name, me, loc, material)
    if bevel:
        m = o.modifiers.new('bevel', 'BEVEL'); m.width = bevel; m.segments = 3
    return o


def cyl(col, name, r, h, loc, material):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=r, radius2=r, depth=h)
    bm.to_mesh(me); bm.free()
    return obj(col, name, me, loc, material)


def room(col, yaw):
    """床と、カメラの反対側の壁（被写体から 2.6m 奥）・左手の壁（窓付き）"""
    floor = mat('Floor_concrete', FLOOR_C, rough=0.85, spec=0.15, noise=0.08)
    wall = mat('Wall_white', WALL_C, rough=0.9, spec=0.05)
    box(col, 'Floor', (14, 14, 0.02), (0, 0, -0.01), floor)
    to_cam = Vector((math.sin(yaw), -math.cos(yaw), 0)); side = Vector((math.cos(yaw), math.sin(yaw), 0))
    c = AIM.to_2d().to_3d() - to_cam * 2.6
    back = box(col, 'Wall_back', (10, 0.1, 4), c + Vector((0, 0, 2)), wall); back.rotation_euler = (0, 0, yaw)
    # 左手（カメラから見て）の壁。窓の開口は 3 枚の板で囲って作る
    lc = AIM.to_2d().to_3d() - side * 3.0 + to_cam * 1.0
    if not WINDOW:
        box(col, 'Wall_left', (0.1, 6, 4), lc + Vector((0, 0, 2)), wall).rotation_euler = (0, 0, yaw)
        return to_cam, side, lc
    for n, (w, h, dz, dx) in {'low': (6, 0.8, 0.4, 0), 'high': (6, 1.0, 3.5, 0),
                              'a': (2.2, 2.2, 1.9, -1.9), 'b': (2.2, 2.2, 1.9, 1.9)}.items():
        p = box(col, f'Wall_left_{n}', (0.1, w if n in ('low', 'high') else 1.6, h),
                lc + to_cam * dx + Vector((0, 0, dz)), wall)
        p.rotation_euler = (0, 0, yaw)
    return to_cam, side, lc


def chair(col):
    shell = mat('Chair_shell', (0.92, 0.92, 0.9), rough=0.45, spec=0.4)
    metal = mat('Chair_metal', (0.85, 0.85, 0.85), rough=0.3, spec=0.6)
    box(col, 'Chair_seat', (0.50, 0.46, 0.05), (0.0, -0.02, SEAT_TOP - 0.025), shell, bevel=0.02)
    box(col, 'Chair_back', (0.48, 0.04, 0.40), (0.0, 0.23, SEAT_TOP + 0.33), shell, bevel=0.018)
    for i, (x, y) in enumerate(((0.21, -0.21), (-0.21, -0.21), (0.21, 0.18), (-0.21, 0.18))):
        cyl(col, f'Chair_leg.{i}', 0.014, SEAT_TOP - 0.05, (x, y, (SEAT_TOP - 0.05) / 2), metal)
    for i, x in enumerate((0.21, -0.21)):
        cyl(col, f'Chair_post.{i}', 0.012, 0.34, (x, 0.22, SEAT_TOP + 0.12), metal)


def lights(col, to_cam, side, window):
    def area(name, size, energy, loc, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, 'AREA'); ld.size = size; ld.energy = energy; ld.color = color
        o = bpy.data.objects.new(name, ld); col.objects.link(o); o.location = loc
        o.rotation_euler = (AIM - Vector(loc)).normalized().to_track_quat('-Z', 'Y').to_euler()
    area('Window', 2.2, 1400, window - side * 0.3 + Vector((0, 0, 1.9)), (1.0, 0.98, 0.95))   # 窓からの自然光
    area('Fill', 4.0, 260, AIM + to_cam * 2.5 + side * 2.0 + Vector((0, 0, 1.5)))
    area('Top', 4.0, 200, AIM + Vector((0, 0, 3.5)))
    world = bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (0.9, 0.9, 0.9, 1); bg.inputs['Strength'].default_value = 0.5


def camera(col, to_cam):
    cd = bpy.data.cameras.new('Cam'); cd.lens = CAM_LENS
    cam = bpy.data.objects.new('Cam', cd); col.objects.link(cam)
    cam.location = AIM + to_cam * CAM_DIST + Vector((0, 0, CAM_H - AIM.z))
    cam.rotation_euler = (AIM - cam.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam
    return cam


def build():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
    col = wipe()
    yaw = math.radians(CAM_YAW)
    to_cam, side, window = room(col, yaw)
    if CHAIR: chair(col)
    lights(col, to_cam, side, window)
    cam = camera(col, to_cam)
    bpy.context.scene['space'] = SPACE
    return {'space': SPACE, 'objects': len(col.objects), 'camera': tuple(round(v, 2) for v in cam.location)}


result = _ctx.run(build)
