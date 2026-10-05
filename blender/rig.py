"""人体リグ + 木製デッサン人形を作る（シーンを空にしてから）。
1) Rigify human メタリグ → 2) Rigify 生成（rig）→ 3) 剛体パーツを ORG ボーンに親付け（スキン不要）。
anim/scripts/01_metarig.py・03_generate_rig.py・20_mannequin_wood.py から移植。"""
import bpy, math, addon_utils
from mathutils import Vector, Matrix
import _ctx

COL_NAME = "Mannequin"
L = {}  # name -> (head, tail) in rig space

def bone(n):
    rig = bpy.data.objects['rig']; b = rig.data.bones[n]
    return rig.matrix_world @ b.head_local, rig.matrix_world @ b.tail_local   # world space

def wood_material():
    m = bpy.data.materials.get("WoodBeech") or bpy.data.materials.new("WoodBeech")
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs['Scale'].default_value = (1.0, 1.0, 0.12)        # stretch grain along the part axis (local Z)
    wave = nt.nodes.new("ShaderNodeTexWave"); wave.wave_type = 'BANDS'; wave.bands_direction = 'X'
    wave.inputs['Scale'].default_value = 16.0; wave.inputs['Distortion'].default_value = 3.0
    wave.inputs['Detail'].default_value = 3.0; wave.inputs['Detail Scale'].default_value = 1.5
    noise = nt.nodes.new("ShaderNodeTexNoise"); noise.inputs['Scale'].default_value = 3.0; noise.inputs['Detail'].default_value = 4.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.64, 0.46, 0.26, 1); ramp.color_ramp.elements[0].position = 0.1
    ramp.color_ramp.elements[1].color = (0.76, 0.59, 0.38, 1); ramp.color_ramp.elements[1].position = 0.9
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion"); ao.inputs['Distance'].default_value = 0.06
    mixc = nt.nodes.new("ShaderNodeMix"); mixc.data_type = 'RGBA'; mixc.blend_type = 'MULTIPLY'; mixc.inputs['Factor'].default_value = 0.35
    rough = nt.nodes.new("ShaderNodeMath"); rough.operation = 'MULTIPLY_ADD'; rough.inputs[1].default_value = 0.15; rough.inputs[2].default_value = 0.32
    ln = nt.links.new
    ln(tc.outputs['Object'], mp.inputs['Vector']); ln(mp.outputs['Vector'], wave.inputs['Vector'])
    ln(tc.outputs['Object'], noise.inputs['Vector']); ln(noise.outputs['Fac'], wave.inputs['Phase Offset'])
    ln(wave.outputs['Fac'], ramp.inputs['Fac'])
    ln(ramp.outputs['Color'], mixc.inputs['A']); ln(ao.outputs['Color'], mixc.inputs['B'])
    ln(mixc.outputs['Result'], bsdf.inputs['Base Color'])
    ln(noise.outputs['Fac'], rough.inputs[0]); ln(rough.outputs['Value'], bsdf.inputs['Roughness'])
    bsdf.inputs['Coat Weight'].default_value = 0.35; bsdf.inputs['Coat Roughness'].default_value = 0.2
    ln(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return m

def finish(obj, name, parent_bone, mat, bevel=0.006):
    obj.name = name
    col = bpy.data.collections[COL_NAME]
    for c in obj.users_collection: c.objects.unlink(obj)
    col.objects.link(obj)
    if bevel:
        b = obj.modifiers.new("Bevel", 'BEVEL'); b.width = bevel; b.segments = 3; b.limit_method = 'ANGLE'
    obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
    rig = bpy.data.objects['rig']
    M = obj.matrix_world.copy()
    obj.parent = rig; obj.parent_type = 'BONE'; obj.parent_bone = parent_bone
    bpy.context.view_layer.update()
    obj.matrix_world = M
    return obj

def taper(name, bone_name, r1, r2, gap0, gap1, parent=None, mat=None):
    h, t = bone(bone_name); d = t - h; n = d.normalized()
    a = h + n * gap0; b = t - n * gap1; c = (a + b) / 2
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=r1, radius2=r2, depth=(b - a).length, location=c, end_fill_type='NGON')
    o = bpy.context.active_object; o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = d.to_track_quat('Z', 'Y')
    bpy.ops.object.transform_apply(rotation=True)
    return finish(o, name, parent or bone_name, mat)

def ball(name, pos, r, parent, mat, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=r, location=pos)
    o = bpy.context.active_object; o.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    return finish(o, name, parent, mat, bevel=0)

def build_mannequin():
    rig = bpy.data.objects['rig']
    if bpy.context.object and bpy.context.object.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
    # clean previous
    if 'Mannequin' in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects['Mannequin'], do_unlink=True)
    col = bpy.data.collections.get(COL_NAME)
    if col:
        for o in list(col.objects): bpy.data.objects.remove(o, do_unlink=True)
    else:
        col = bpy.data.collections.new(COL_NAME); bpy.context.scene.collection.children.link(col)
    bpy.context.scene.frame_set(1)   # root-motion action moves the rig object; build at its start
    rig.data.pose_position = 'REST'; bpy.context.view_layer.update()
    mat = wood_material()
    parts = []
    # --- torso ---
    h, t = bone('ORG-spine.006'); c = (h + t) / 2 + Vector((0, 0.005, 0.012))
    parts.append(ball('Head', c, 0.105, 'ORG-spine.006', mat, scale=(0.88, 1.0, 1.22)))
    parts.append(taper('Neck', 'ORG-spine.005', 0.036, 0.034, -0.05, -0.01, mat=mat))
    h, t = bone('ORG-spine.002'); h3, t3 = bone('ORG-spine.003')
    parts.append(ball('Chest', (h + t3) / 2 + Vector((0, 0.0, 0.01)), 0.17, 'ORG-spine.003', mat, scale=(1.0, 0.66, 1.12)))
    h, t = bone('ORG-spine.001')
    parts.append(ball('Waist', t + Vector((0, 0.005, -0.02)), 0.085, 'ORG-spine.001', mat))
    h, t = bone('ORG-spine')
    parts.append(ball('Pelvis', h + Vector((0, -0.01, 0.07)), 0.15, 'ORG-spine', mat, scale=(1.0, 0.68, 0.78)))
    # --- limbs ---
    for s in 'LR':
        ua_h, ua_t = bone(f'ORG-upper_arm.{s}'); fa_h, fa_t = bone(f'ORG-forearm.{s}'); hd_h, hd_t = bone(f'ORG-hand.{s}')
        parts.append(ball(f'Shoulder.{s}', ua_h, 0.052, f'ORG-shoulder.{s}', mat))
        parts.append(taper(f'UpperArm.{s}', f'ORG-upper_arm.{s}', 0.042, 0.036, 0.05, 0.035, mat=mat))
        parts.append(ball(f'Elbow.{s}', fa_h, 0.037, f'ORG-upper_arm.{s}', mat))
        parts.append(taper(f'Forearm.{s}', f'ORG-forearm.{s}', 0.034, 0.028, 0.035, 0.03, mat=mat))
        parts.append(ball(f'Wrist.{s}', hd_h, 0.028, f'ORG-forearm.{s}', mat))
        n = (hd_t - hd_h).normalized()
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1.0, location=hd_h + n * 0.095)
        o = bpy.context.active_object; o.scale = (0.042, 0.016, 0.085)
        o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = n.to_track_quat('Z', 'Y')
        bpy.ops.object.transform_apply(rotation=True, scale=True)
        parts.append(finish(o, f'Hand.{s}', f'ORG-hand.{s}', mat, bevel=0))
        th_h, th_t = bone(f'ORG-thigh.{s}'); sh_h, sh_t = bone(f'ORG-shin.{s}'); ft_h, ft_t = bone(f'ORG-foot.{s}'); to_h, to_t = bone(f'ORG-toe.{s}')
        parts.append(ball(f'Hip.{s}', th_h, 0.058, 'ORG-spine', mat))
        parts.append(taper(f'Thigh.{s}', f'ORG-thigh.{s}', 0.064, 0.05, 0.055, 0.045, mat=mat))
        parts.append(ball(f'Knee.{s}', sh_h, 0.05, f'ORG-thigh.{s}', mat))
        parts.append(taper(f'Shin.{s}', f'ORG-shin.{s}', 0.046, 0.036, 0.045, 0.035, mat=mat))
        parts.append(ball(f'Ankle.{s}', ft_h, 0.036, f'ORG-shin.{s}', mat))
        c = (ft_h + ft_t) / 2 + Vector((0, 0.0, -0.02))
        parts.append(ball(f'Foot.{s}', c, 1.0, f'ORG-foot.{s}', mat, scale=(0.042, 0.085, 0.03)))
        c = (to_h + to_t) / 2 + Vector((0, 0.0, 0.003))
        parts.append(ball(f'Toe.{s}', c, 1.0, f'ORG-toe.{s}', mat, scale=(0.04, 0.05, 0.02)))
    rig.data.pose_position = 'POSE'; bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    return {'parts': len(parts), 'names': [p.name for p in parts][:12]}



def clear_scene():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions, bpy.data.materials,
                 bpy.data.cameras, bpy.data.lights, bpy.data.collections):
        for d in list(coll):
            if d.users == 0 or coll is bpy.data.collections:
                coll.remove(d)


def build_rig():
    addon_utils.enable('rigify', default_set=True, persistent=True)
    scn = bpy.context.scene
    scn.render.fps = 24; scn.frame_start = 1
    bpy.ops.object.armature_human_metarig_add()
    meta = bpy.context.active_object; meta.name = 'metarig'
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.pose.rigify_generate()
    rig = bpy.data.objects['rig']
    meta.hide_set(True); meta.hide_render = True
    return rig


def build():
    clear_scene()
    rig = build_rig()
    m = build_mannequin()
    ctrl = [b.name for b in rig.pose.bones if not b.name.startswith(('DEF-', 'MCH-', 'ORG-', 'VIS_'))]
    return {'rig_bones': len(rig.pose.bones), 'control_bones': len(ctrl), **m}


result = _ctx.run(build)
