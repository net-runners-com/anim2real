"""椅子に座ったふくらはぎストレッチ 20 秒（480f @24fps）を Rigify リグにポーズ・トゥ・ポーズで打つ。
右脚 → 左脚: 脚を前へ伸ばす → かかと接地 → つま先を手前に引く（背屈）→ 股関節から前傾して手を膝へ → 2 回深める → 戻す。
脚は IK（foot_ik の world 位置・回転）、腕は肩→手先ターゲットの 2 ボーン解析 IK で FK 方向を出して aim する。
rig は原点・無回転前提。anim/scripts/81_calf_stretch.py から移植。
`python3 blender/make.py calf_stretch` から実行される。"""
import bpy, math
from mathutils import Vector, Matrix
import _ctx

ACTION = "calf_stretch"
FPS, FRAMES = 24, 480
SPEED = 1.5                        # 1.0 = 1 脚 234f。速くした分は R→L→R… と繰り返して 20 秒を埋める
X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
CTRL = ['torso', 'hips', 'chest', 'head', 'upper_arm_fk.L', 'forearm_fk.L', 'hand_fk.L',
        'upper_arm_fk.R', 'forearm_fk.R', 'hand_fk.R', 'foot_ik.L', 'foot_ik.R']

SIT_Z = -0.532                     # torso drop: hip joint 1.072 → 0.54 (thigh horizontal, shin vertical)
FOOT_SIT = (0, -0.50, 0)           # ankle under the knee
FOOT_MID = (0, -0.70, 0.10)        # leg on its way out
FOOT_EXT = (0, -0.856, 0.012)      # heel on the floor, knee almost straight

def R(axis, deg): return Matrix.Rotation(math.radians(deg), 3, axis)
def rot_xyz(rx, ry, rz): return R(Z, rz) @ R(Y, ry) @ R(X, rx)

def aim(rig, name, d):
    pb = rig.pose.bones[name]
    rest = pb.bone.matrix_local.to_3x3()
    rest_dir = (rest @ Y).normalized(); d = Vector(d).normalized()
    M = (rest_dir.rotation_difference(d).to_matrix() @ rest).to_4x4(); M.translation = pb.matrix.translation
    pb.matrix = M
    bpy.context.view_layer.update()

def wrot(rig, name, rx=0, ry=0, rz=0):
    pb = rig.pose.bones[name]; M = pb.bone.matrix_local.to_3x3()
    pb.rotation_quaternion = (M.inverted() @ rot_xyz(rx, ry, rz) @ M).to_quaternion()

def wloc(rig, name, off):
    pb = rig.pose.bones[name]; M = pb.bone.matrix_local.to_3x3()
    pb.location = M.inverted() @ Vector(off)

def arm_to(rig, s, target, pole):
    """2-bone analytic IK: shoulder → hand target, elbow toward `pole` (world dir)."""
    ua, fa = rig.pose.bones[f'upper_arm_fk.{s}'], rig.pose.bones[f'forearm_fk.{s}']
    a, b = ua.bone.length, fa.bone.length
    S = ua.matrix.translation.copy(); T = Vector(target)
    d = min((T - S).length, a + b - 1e-3); u = (T - S).normalized()
    x = (a * a - b * b + d * d) / (2 * d); h = math.sqrt(max(a * a - x * x, 0.0))
    p = Vector(pole); p = (p - p.dot(u) * u).normalized()
    E = S + u * x + p * h; W = S + u * d
    aim(rig, f'upper_arm_fk.{s}', E - S); aim(rig, f'forearm_fk.{s}', W - E)
    aim(rig, f'hand_fk.{s}', (W - E).normalized() + Vector((0, 0, -0.35)))

def mx(v): return (-v[0], v[1], v[2])

# ---- poses ------------------------------------------------------------------------------
# hands: world-space wrist targets. On the thighs while sitting; on the knee of the working leg when leaning.
HAND_THIGH = (0.17, -0.25, 0.62)
REST = {'lean': 0, 'chest': 0, 'head': 0, 'footL': FOOT_SIT, 'footR': FOOT_SIT, 'toeL': 0, 'toeR': 0,
        'handL': HAND_THIGH, 'handR': mx(HAND_THIGH)}

def apply(rig, pose):
    p = {**REST, **pose}
    wloc(rig, 'torso', (0, 0, SIT_Z)); wrot(rig, 'torso', p['lean'], 0, 0)
    wrot(rig, 'chest', p['chest'], 0, 0); wrot(rig, 'head', p['head'], 0, 0); wrot(rig, 'hips', 0, 0, 0)
    for s in 'LR':
        wloc(rig, f'foot_ik.{s}', p['foot' + s]); wrot(rig, f'foot_ik.{s}', -p['toe' + s], 0, 0)  # +toe = toes up
    bpy.context.view_layer.update()
    for s, sx in (('L', 1), ('R', -1)):
        arm_to(rig, s, p['hand' + s], (sx * 1.0, 0.6, -0.2))

def side(s):
    """Key list (frame offset, pose) for one leg. s = 'L' or 'R' (working leg)."""
    sx = 1 if s == 'L' else -1
    foot, toe = 'foot' + s, 'toe' + s
    knee = (sx * 0.098, -0.42, 0.47)                     # top of the working knee
    hl, hr = (knee[0] + 0.07, knee[1], knee[2]), (knee[0] - 0.07, knee[1], knee[2])
    reach = {'handL': hl, 'handR': hr}
    shin = {'handL': (hl[0], -0.52, 0.40), 'handR': (hr[0], -0.52, 0.40)}
    def hold(t, lean, chest, head, hands=reach):
        return {foot: FOOT_EXT, toe: t, 'lean': lean, 'chest': chest, 'head': head, **hands}
    return [
        (0, {}),
        (16, {foot: (0, -0.56, 0.06), toe: 5}),
        (30, {foot: FOOT_MID, toe: 10}),
        (44, {foot: FOOT_EXT, toe: 0}),                  # heel lands
        (64, hold(32, 6, 4, 4, {})),                     # pull toes up
        (92, hold(36, 24, 10, 12)),                      # hinge forward, hands to knee
        (120, hold(44, 30, 12, 14, shin)),               # deepen
        (146, hold(36, 24, 10, 12)),                     # ease (breath)
        (172, hold(45, 31, 13, 15, shin)),               # deepen again
        (194, hold(40, 28, 11, 13, shin)),
        (212, hold(8, 4, 2, 2, {})),                     # sit up, relax toes
        (222, {foot: FOOT_MID, toe: 8}),
        (234, {}),
    ]

def build():
    rig = bpy.data.objects['rig']; scn = bpy.context.scene
    if bpy.context.object and bpy.context.object.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
    ad = rig.animation_data or rig.animation_data_create()
    for t in ad.nla_tracks: t.mute = True
    ad.action = None
    if ACTION in bpy.data.actions: bpy.data.actions.remove(bpy.data.actions[ACTION])
    rig.location = (0, 0, 0); rig.rotation_euler = (0, 0, 0)
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.rotation_euler = (0, 0, 0); pb.scale = (1, 1, 1)
    for n in CTRL: rig.pose.bones[n].rotation_mode = 'QUATERNION'
    for s in 'LR':
        rig.pose.bones[f'upper_arm_parent.{s}']['IK_FK'] = 1.0; rig.pose.bones[f'thigh_parent.{s}']['IK_FK'] = 0.0
    bpy.context.view_layer.update()

    keys, t, legs = [(1, {})], 13, 'RL'
    span = round(234 / SPEED)
    i = 0
    while t + span <= FRAMES + 1:
        keys += [(min(t + round(f / SPEED), FRAMES), p) for f, p in side(legs[i % 2])]
        t += span; i += 1
    if keys[-1][0] < FRAMES: keys.append((FRAMES, {}))
    for f, pose in keys:
        scn.frame_set(f); apply(rig, pose)
        for n in CTRL:
            pb = rig.pose.bones[n]; pb.keyframe_insert('location', frame=f); pb.keyframe_insert('rotation_quaternion', frame=f)
    ad.action.name = ACTION
    scn.render.fps = FPS; scn.frame_start, scn.frame_end = 1, FRAMES

    # QA: seat contact and floor penetration at a few frames
    qa = {}
    for f in (1, 13 + 120, 13 + 234 + 172):
        scn.frame_set(f); dg = bpy.context.evaluated_depsgraph_get()
        def minz(name):
            o = bpy.data.objects[name].evaluated_get(dg)
            return round(min((o.matrix_world @ Vector(c)).z for c in o.bound_box), 3)
        qa[f] = {n: minz(n) for n in ('Pelvis', 'Thigh.L', 'Thigh.R', 'Foot.L', 'Foot.R', 'Toe.L', 'Toe.R', 'Hand.L', 'Hand.R')}
    scn.frame_set(1)
    return {'frames': FRAMES, 'keys': len(keys), 'qa_minz': qa}

result = _ctx.run(build)
