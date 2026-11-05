import turtle, math

W, H, CELL = 96, 54, 8            
FOCAL = H * 0.95
NEAR = 0.1
BG = (32, 24, 42)
LIGHT = (0.4, 0.85, 0.5)
_l = math.sqrt(sum(v * v for v in LIGHT))
LIGHT = tuple(v / _l for v in LIGHT)

import os
HERE = os.path.dirname(os.path.abspath(__file__))
OBJ_PATH = os.path.join(HERE, "warehouse.obj")          

def load_obj(path):
    verts, mats, static, fork = [], {}, [], []
    cur_col, cur_obj = (180, 180, 180), ""
    mtl = None
    with open(path) as f:
        lines = f.read().splitlines()
    for ln in lines:                                    
        if ln.startswith("mtllib"):
            mtl = os.path.join(os.path.dirname(path), ln.split(None, 1)[1].strip())
    if mtl and os.path.exists(mtl):
        name = None
        for ln in open(mtl):
            t = ln.split()
            if t and t[0] == "newmtl": name = t[1]
            elif t and t[0] == "Kd" and name:
                mats[name] = tuple(min(255, int(float(v) * 255)) for v in t[1:4])
    for ln in lines:
        t = ln.split()
        if not t: continue
        if t[0] == "v":
            verts.append((float(t[1]), float(t[2]), float(t[3])))
        elif t[0] == "o":
            cur_obj = t[1]
        elif t[0] == "usemtl":
            cur_col = mats.get(t[1], (180, 180, 180))
        elif t[0] == "f":
            idx = [int(x.split("/")[0]) - 1 for x in t[1:]]
            for i in range(1, len(idx) - 1):             
                p0, p1, p2 = verts[idx[0]], verts[idx[i]], verts[idx[i + 1]]
                e1 = [p1[k] - p0[k] for k in range(3)]; e2 = [p2[k] - p0[k] for k in range(3)]
                n = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
                L = math.sqrt(sum(v * v for v in n)) or 1.0
                tri = (p0, p1, p2, tuple(v / L for v in n), cur_col)
                (fork if cur_obj.startswith("Forklift") else static).append(tri)
    return static, fork

if not os.path.exists(OBJ_PATH):
    raise SystemExit("warehouse.obj not found - run blender_build_warehouse.py in Blender first.")
STATIC, FORK = load_obj(OBJ_PATH)
print("Loaded", len(STATIC), "static +", len(FORK), "forklift triangles from Blender OBJ")

def forklift(t):
    dx = 14 * math.sin(t * 0.5)
    return [(tuple((p[0] + dx, p[1], p[2]) for p in (p0,))[0], (p1[0] + dx, p1[1], p1[2]),
             (p2[0] + dx, p2[1], p2[2]), n, c) for (p0, p1, p2, n, c) in FORK]

S = dict(yaw=0.5, pitch=0.45, dist=34.0, zbuf=True, depth=False, cull=True, anim=True, time=0.0)
stats = dict(tris=0, tested=0, rejected=0)

def raster(A, B, C, color, fb, zb, use_z, depth_view):
    minx = max(0, int(min(A[0], B[0], C[0])));  maxx = min(W - 1, int(max(A[0], B[0], C[0])) + 1)
    miny = max(0, int(min(A[1], B[1], C[1])));  maxy = min(H - 1, int(max(A[1], B[1], C[1])) + 1)
    area = (B[0] - A[0]) * (C[1] - A[1]) - (B[1] - A[1]) * (C[0] - A[0])
    if abs(area) < 1e-9:
        return
    inv = 1.0 / area
    for y in range(miny, maxy + 1):
        py = y + 0.5
        for x in range(minx, maxx + 1):
            px = x + 0.5
            w0 = ((B[0] - px) * (C[1] - py) - (B[1] - py) * (C[0] - px)) * inv
            w1 = ((C[0] - px) * (A[1] - py) - (C[1] - py) * (A[0] - px)) * inv
            w2 = 1.0 - w0 - w1
            if w0 < 0 or w1 < 0 or w2 < 0:
                continue                                  
            iz = w0 * A[2] + w1 * B[2] + w2 * C[2]        
            i = y * W + x
            stats['tested'] += 1
            if use_z:
                if iz <= zb[i]:                           
                    stats['rejected'] += 1
                    continue
                zb[i] = iz                               
            if depth_view:
                g = max(0, int(255 * (1 - (1 / iz) / 48)))
                fb[i] = (g, g, g)
            else:
                fb[i] = color                             

def render_buffer():
    fb = [BG] * (W * H)
    zb = [0.0] * (W * H)                                  
    stats.update(tris=0, tested=0, rejected=0)
    cp = (S['dist'] * math.cos(S['pitch']) * math.sin(S['yaw']),
          2 + S['dist'] * math.sin(S['pitch']),
          S['dist'] * math.cos(S['pitch']) * math.cos(S['yaw']))
    F = (-cp[0], 2 - cp[1], -cp[2]); fl = math.sqrt(sum(v * v for v in F)); F = tuple(v / fl for v in F)
    R = (-F[2], 0, F[0]); rl = math.hypot(R[0], R[2]); R = tuple(v / rl for v in R)
    U = (R[1] * F[2] - R[2] * F[1], R[2] * F[0] - R[0] * F[2], R[0] * F[1] - R[1] * F[0])

    for (p0, p1, p2, n, col) in STATIC + forklift(S['time']):
        if S['cull'] and sum((cp[k] - p0[k]) * n[k] for k in range(3)) <= 0:
            continue                                      # back-face culling
        sh = 0.3 + 0.7 * max(0.0, sum(n[k] * LIGHT[k] for k in range(3)))
        color = tuple(int(c * sh) for c in col)
        pts = []                                          
        for p in (p0, p1, p2):
            d = (p[0] - cp[0], p[1] - cp[1], p[2] - cp[2])
            pts.append((sum(d[k] * R[k] for k in range(3)),
                        sum(d[k] * U[k] for k in range(3)),
                        sum(d[k] * F[k] for k in range(3))))
        poly = []                                        
        for i in range(3):
            a, b = pts[i], pts[(i + 1) % 3]
            ina, inb = a[2] >= NEAR, b[2] >= NEAR
            if ina:
                poly.append(a)
            if ina != inb:
                t = (NEAR - a[2]) / (b[2] - a[2])
                poly.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), NEAR))
        if len(poly) < 3:
            continue
        sp = [(W / 2 + v[0] / v[2] * FOCAL, H / 2 - v[1] / v[2] * FOCAL, 1 / v[2]) for v in poly]
        stats['tris'] += 1
        for i in range(1, len(sp) - 1):
            raster(sp[0], sp[i], sp[i + 1], color, fb, zb, S['zbuf'], S['depth'])
    return fb

screen = turtle.Screen()
screen.setup(W * CELL + 20, H * CELL + 70)
screen.title("Real-Time 3D Warehouse Visibility System - Z-Buffer")
screen.bgcolor("black"); screen.colormode(255); screen.tracer(0)

pen = turtle.Turtle(); pen.shape("square"); pen.penup(); pen.hideturtle()
hud = turtle.Turtle(); hud.hideturtle(); hud.penup(); hud.color("white")

def paint(fb):
    """Run-length merge each row, then stamp one stretched square per run."""
    pen.clearstamps()
    for y in range(H):
        row, x = y * W, 0
        while x < W:
            c, x0 = fb[row + x], x
            while x < W and fb[row + x] == c:
                x += 1
            n = x - x0
            pen.shapesize(CELL / 20, CELL * n / 20, 0)
            pen.color(c)
            pen.goto(-W * CELL / 2 + (x0 + n / 2) * CELL, H * CELL / 2 - (y + 0.5) * CELL + 20)
            pen.stamp()
    hud.clear(); hud.goto(-W * CELL / 2 + 5, -H * CELL / 2 - 12)
    hidden = 100 * stats['rejected'] / stats['tested'] if stats['tested'] else 0
    hud.write(f"Z-buffer:{'ON' if S['zbuf'] else 'OFF'}  Depth:{'ON' if S['depth'] else 'OFF'}  "
              f"Cull:{'ON' if S['cull'] else 'OFF'} | tris {stats['tris']}  tested {stats['tested']}  "
              f"rejected {stats['rejected']} ({hidden:.1f}% hidden)", font=("Consolas", 10, "normal"))
    screen.update()

def loop():
    if S['anim']:
        S['time'] += 0.08
    paint(render_buffer())
    screen.ontimer(loop, 10)

def key(name, fn):
    screen.onkeypress(fn, name)

def orbit(dy, dp):
    def f():
        S['yaw'] += dy
        S['pitch'] = max(0.05, min(1.5, S['pitch'] + dp))
    return f
def zoom(k):
    def f(): S['dist'] = max(4, min(60, S['dist'] * k))
    return f
def toggle(name):
    def f(): S[name] = not S[name]
    return f

key("Left", orbit(0.08, 0)); key("Right", orbit(-0.08, 0))
key("Up", orbit(0, -0.06));  key("Down", orbit(0, 0.06))
key("w", zoom(0.92)); key("s", zoom(1.08))
key("z", toggle('zbuf')); key("d", toggle('depth'))
key("c", toggle('cull')); key("space", toggle('anim'))
screen.listen()
loop()
screen.mainloop()
