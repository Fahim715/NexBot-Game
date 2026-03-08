from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
import random
import time
import collections

# =============================================================================
# CONFIGURATION
# =============================================================================
WINDOW_WIDTH, WINDOW_HEIGHT = 800, 600
MAZE_SIZE = 16 
CELL_SIZE = 10.0
WALL_HEIGHT = 10.0

# Physics Constants
GRAVITY = -35.0          
BOUNCE_FACTOR = 0.7      
FRICTION = 0.98          

# Player Settings
WALK_SPEED = 15.0
RUN_SPEED = 28.0
TURN_SPEED = 5.0 
PLAYER_RADIUS = 2.0
PLAYER_HEIGHT = 5.0
MAX_STAMINA = 100.0
STAMINA_DRAIN = 30.0
STAMINA_REGEN = 10.0

# Camera
THIRD_PERSON_DIST = 25.0 
THIRD_PERSON_HEIGHT = 20.0 

# Nextbot Settings
NEXTBOT_SPEED = 17.5 
NEXTBOT_SIZE = 8.0

# Colors 
COLOR_WALL = (0.8, 0.7, 0.4) 
COLOR_FLOOR = (0.6, 0.5, 0.3)
COLOR_CEILING = (0.9, 0.9, 0.8)
COLOR_PLAYER = (0.2, 0.8, 0.2)
COLOR_BALL = (1.0, 0.2, 0.2)
COLOR_LIGHT_BULB = (1.0, 1.0, 0.8) # Yellowish white

# =============================================================================
# PHYSICS CLASSES
# =============================================================================
class Projectile:
    def __init__(self, x, y, z, angle):
        self.x = x
        self.y = y
        self.z = z
        self.radius = 0.8
        self.active = True
        
        throw_force = 45.0 
        self.vx = math.cos(angle) * throw_force
        self.vy = math.sin(angle) * throw_force
        self.vz = 10.0 
        
    def update(self, dt):
        self.vz += GRAVITY * dt
        next_x = self.x + self.vx * dt
        next_y = self.y + self.vy * dt
        self.z += self.vz * dt
        self.vx *= FRICTION
        self.vy *= FRICTION
        
        # Floor Collision
        if self.z - self.radius < 0:
            self.z = self.radius
            self.vz = -self.vz * BOUNCE_FACTOR
            if abs(self.vz) < 1.0: self.vz = 0
            self.vx *= 0.9
            self.vy *= 0.9

        # Wall Collision
        if check_wall_collision(next_x, self.y, self.radius):
            self.vx = -self.vx * BOUNCE_FACTOR 
        else:
            self.x = next_x
            
        if check_wall_collision(self.x, next_y, self.radius):
            self.vy = -self.vy * BOUNCE_FACTOR
        else:
            self.y = next_y
            
        if self.z < -10 or (abs(self.vx) < 0.1 and abs(self.vy) < 0.1 and abs(self.vz) < 0.1):
            self.active = False

# =============================================================================
# TEXTURE & MAZE GEN
# =============================================================================
def create_nextbot_texture():
    width, height = 64, 64
    data = bytearray(width * height * 3)
    for y in range(height):
        for x in range(width):
            r = random.randint(200, 255); g = random.randint(200, 255); b = random.randint(200, 255)
            dx_l = x - 20; dy_l = y - 40
            dx_r = x - 44; dy_r = y - 40
            dx_m = x - 32; dy_m = y - 15
            if (dx_l**2 + dy_l**2 < 30) or (dx_r**2 + dy_r**2 < 30): r,g,b = 0,0,0
            if (dx_m**2 * 0.5 + dy_m**2 < 60): r,g,b = 0,0,0
            if x < 2 or x > 62 or y < 2 or y > 62: r,g,b = 0,0,0
            idx = (y * width + x) * 3
            data[idx] = r; data[idx+1] = g; data[idx+2] = b
    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE, bytes(data))
    return tex_id

def generate_maze(w, h):
    grid = [[1 for _ in range(w)] for _ in range(h)]
    def carve(cx, cy):
        grid[cy][cx] = 0
        directions = [(0, 2), (0, -2), (2, 0), (-2, 0)]
        random.shuffle(directions)
        for dx, dy in directions:
            nx, ny = cx + dx, cy + dy
            if 0 < nx < w-1 and 0 < ny < h-1 and grid[ny][nx] == 1:
                grid[cy + dy//2][cx + dx//2] = 0
                carve(nx, ny)
    carve(1, 1)
    for _ in range(int(w*h*0.1)):
        rx = random.randint(1, w-2); ry = random.randint(1, h-2)
        if grid[ry][rx] == 1: grid[ry][rx] = 0
    return grid

# =============================================================================
# GAME STATE
# =============================================================================
maze = []
maze_w, maze_h = 0, 0
nextbot_tex = None
quadric = None
ceiling_lights = [] 

# Player
px, py = 0, 0
p_angle = 0
stamina = MAX_STAMINA
is_third_person = False
is_torch_on = False 
is_ghost_light_on = False 

# Autopilot State
is_autopilot = False
shoot_cooldown = 0.0

# Entities
ghosts = [] 
projectiles = []

total_hits = 0
jumpscare_active = False
survival_time = 0
start_time = 0
last_frame_time = 0
keys = {}
special_keys_state = {}

# =============================================================================
# LOGIC & AI
# =============================================================================
def check_wall_collision(x, y, radius):
    min_gx = int((x - radius) / CELL_SIZE)
    max_gx = int((x + radius) / CELL_SIZE)
    min_gy = int((y - radius) / CELL_SIZE)
    max_gy = int((y + radius) / CELL_SIZE)
    
    for gy in range(min_gy, max_gy + 1):
        for gx in range(min_gx, max_gx + 1):
            if 0 <= gx < maze_w and 0 <= gy < maze_h:
                if maze[gy][gx] == 1:
                    wall_x1 = gx * CELL_SIZE
                    wall_x2 = wall_x1 + CELL_SIZE
                    wall_y1 = gy * CELL_SIZE
                    wall_y2 = wall_y1 + CELL_SIZE
                    cx = max(wall_x1, min(x, wall_x2))
                    cy = max(wall_y1, min(y, wall_y2))
                    dist_sq = (x - cx)**2 + (y - cy)**2
                    if dist_sq < radius**2:
                        return True
    return False

def check_line_of_sight(x1, y1, x2, y2):
    dist = math.sqrt((x2-x1)**2 + (y2-y1)**2)
    if dist == 0: return True
    steps = int(dist / 2.0)
    dx = (x2 - x1) / steps
    dy = (y2 - y1) / steps
    cx, cy = x1, y1
    for i in range(steps):
        if check_wall_collision(cx, cy, 0.5): return False
        cx += dx
        cy += dy
    return True

def get_next_step_to_ghost():
    start_gx = int(px / CELL_SIZE)
    start_gy = int(py / CELL_SIZE)
    queue = collections.deque([(start_gx, start_gy, [])])
    visited = set([(start_gx, start_gy)])
    
    ghost_cells = []
    for g in ghosts:
        gx = int(g['x'] / CELL_SIZE)
        gy = int(g['y'] / CELL_SIZE)
        ghost_cells.append((gx, gy))

    while queue:
        cx, cy, path = queue.popleft()
        if (cx, cy) in ghost_cells:
            if not path: return None
            return path[0] 

        moves = [(0,1), (0,-1), (1,0), (-1,0)]
        for dx, dy in moves:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < maze_w and 0 <= ny < maze_h:
                if maze[ny][nx] == 0 and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    new_path = list(path)
                    new_path.append((nx, ny))
                    queue.append((nx, ny, new_path))
    return None

def update_autopilot(dt):
    global px, py, p_angle, shoot_cooldown
    shoot_cooldown -= dt
    target_ghost = None
    min_dist = 99999
    
    for g in ghosts:
        dist = math.sqrt((px - g['x'])**2 + (py - g['y'])**2)
        if check_line_of_sight(px, py, g['x'], g['y']):
            if dist < min_dist:
                min_dist = dist
                target_ghost = g

    dx, dy = 0, 0
    if target_ghost:
        dx = target_ghost['x'] - px
        dy = target_ghost['y'] - py
        wanted_angle = math.atan2(dy, dx)
        p_angle = wanted_angle 
        if shoot_cooldown <= 0:
            projectiles.append(Projectile(px, py, PLAYER_HEIGHT, p_angle))
            shoot_cooldown = 0.4 
    else:
        next_cell = get_next_step_to_ghost()
        if next_cell:
            target_x = next_cell[0] * CELL_SIZE + CELL_SIZE/2
            target_y = next_cell[1] * CELL_SIZE + CELL_SIZE/2
            dx = target_x - px; dy = target_y - py
            dist = math.sqrt(dx*dx + dy*dy)
            if dist > 1.0:
                wanted_angle = math.atan2(dy, dx)
                p_angle = wanted_angle
                move_speed = RUN_SPEED
                mx = math.cos(p_angle) * move_speed * dt
                my = math.sin(p_angle) * move_speed * dt
                if not check_wall_collision(px + mx, py, PLAYER_RADIUS): px += mx
                if not check_wall_collision(px, py + my, PLAYER_RADIUS): py += my

def get_random_empty_spot():
    empty_spots = []
    for y in range(maze_h):
        for x in range(maze_w):
            if maze[y][x] == 0:
                empty_spots.append((x * CELL_SIZE + CELL_SIZE/2, y * CELL_SIZE + CELL_SIZE/2))
    return random.choice(empty_spots)

def spawn_entities():
    global px, py, ghosts, total_hits
    px, py = get_random_empty_spot()
    ghosts = []
    total_hits = 0
    add_new_ghost() 

def add_new_ghost():
    gx, gy = get_random_empty_spot()
    while (gx-px)**2 + (gy-py)**2 < 100*100:
        gx, gy = get_random_empty_spot()
    ghosts.append({'x': gx, 'y': gy, 'color': (1.0, 1.0, 1.0) })

def relocate_ghost(ghost_index):
    global total_hits
    gx, gy = get_random_empty_spot()
    ghosts[ghost_index]['x'] = gx
    ghosts[ghost_index]['y'] = gy
    ghosts[ghost_index]['color'] = (random.random(), random.random(), random.random())
    total_hits += 1
    if total_hits > 0 and total_hits % 3 == 0:
        add_new_ghost()

def reset_game():
    global stamina, jumpscare_active, start_time, keys, projectiles
    spawn_entities()
    stamina = MAX_STAMINA
    jumpscare_active = False
    projectiles = []
    start_time = time.time()
    keys = {}

def update(dt):
    global px, py, p_angle, stamina, jumpscare_active, survival_time
    
    if jumpscare_active: return
    survival_time = time.time() - start_time

    if is_autopilot:
        update_autopilot(dt)
        stamina = MAX_STAMINA
    else:
        speed = WALK_SPEED
        is_sprinting = False
        if b'shift' in keys and keys[b'shift']: is_sprinting = True
        
        if is_sprinting and stamina > 0:
            speed = RUN_SPEED
            stamina -= STAMINA_DRAIN * dt
        else:
            stamina = min(MAX_STAMINA, stamina + STAMINA_REGEN * dt)

        if GLUT_KEY_LEFT in special_keys_state and special_keys_state[GLUT_KEY_LEFT]:
            p_angle += TURN_SPEED * dt
        if GLUT_KEY_RIGHT in special_keys_state and special_keys_state[GLUT_KEY_RIGHT]:
            p_angle -= TURN_SPEED * dt

        dx, dy = 0, 0
        if b'w' in keys and keys[b'w']:
            dx += math.cos(p_angle) * speed * dt
            dy += math.sin(p_angle) * speed * dt
        if b's' in keys and keys[b's']:
            dx -= math.cos(p_angle) * speed * dt
            dy -= math.sin(p_angle) * speed * dt
        if b'a' in keys and keys[b'a']:
            dx += math.cos(p_angle + math.pi/2) * speed * dt
            dy += math.sin(p_angle + math.pi/2) * speed * dt
        if b'd' in keys and keys[b'd']:
            dx += math.cos(p_angle - math.pi/2) * speed * dt
            dy += math.sin(p_angle - math.pi/2) * speed * dt
        
        if not check_wall_collision(px + dx, py, PLAYER_RADIUS): px += dx
        if not check_wall_collision(px, py + dy, PLAYER_RADIUS): py += dy

    for p in projectiles:
        if p.active:
            p.update(dt)
            hit_occurred = False
            for i, ghost in enumerate(ghosts):
                dist_sq = (p.x - ghost['x'])**2 + (p.y - ghost['y'])**2
                hit_radius = (NEXTBOT_SIZE/2 + p.radius)
                if dist_sq < hit_radius**2:
                    relocate_ghost(i)
                    hit_occurred = True
                    break 
            if hit_occurred: p.active = False 

    for ghost in ghosts:
        vx = px - ghost['x']
        vy = py - ghost['y']
        dist = math.sqrt(vx*vx + vy*vy)
        
        if dist < 3.0:
            if not is_autopilot: 
                jumpscare_active = True
                print(f"You got caught!! Beat: {total_hits}, Survived for {survival_time:.2f} seconds")
                return 
        
        if dist > 0:
            vx /= dist; vy /= dist
            ndx = vx * NEXTBOT_SPEED * dt
            ndy = vy * NEXTBOT_SPEED * dt
            if not check_wall_collision(ghost['x'] + ndx, ghost['y'], 1.0): 
                ghost['x'] += ndx
            if not check_wall_collision(ghost['x'], ghost['y'] + ndy, 1.0): 
                ghost['y'] += ndy

# =============================================================================
# RENDERING
# =============================================================================

def draw_ceiling_lights():
    if is_ghost_light_on: return
    glDisable(GL_TEXTURE_2D)
    glMaterialfv(GL_FRONT, GL_EMISSION, [1.0, 1.0, 0.8, 1.0])
    glColor3f(*COLOR_LIGHT_BULB)
    for (lx, ly, lz) in ceiling_lights:
        glPushMatrix()
        glTranslatef(lx, ly, lz)
        glutSolidSphere(0.3, 8, 8) 
        glPopMatrix()
    glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])

def draw_maze_3d():
    glDisable(GL_TEXTURE_2D)
    draw_ceiling_lights()

    glBegin(GL_QUADS)
    for y in range(maze_h):
        for x in range(maze_w):
            wx = x * CELL_SIZE; wy = y * CELL_SIZE
            
            # Floor
            glNormal3f(0, 0, 1)
            glColor3f(*COLOR_FLOOR)
            glVertex3f(wx, wy, 0); glVertex3f(wx+CELL_SIZE, wy, 0)
            glVertex3f(wx+CELL_SIZE, wy+CELL_SIZE, 0); glVertex3f(wx, wy+CELL_SIZE, 0)
            
            # Ceiling
            if not is_third_person:
                glNormal3f(0, 0, -1)
                glColor3f(*COLOR_CEILING)
                glVertex3f(wx, wy, WALL_HEIGHT); glVertex3f(wx+CELL_SIZE, wy, WALL_HEIGHT)
                glVertex3f(wx+CELL_SIZE, wy+CELL_SIZE, WALL_HEIGHT); glVertex3f(wx, wy+CELL_SIZE, WALL_HEIGHT)
            
            # Walls
            if maze[y][x] == 1:
                glColor3f(*COLOR_WALL)
                glNormal3f(0, -1, 0)
                glVertex3f(wx, wy, 0); glVertex3f(wx+CELL_SIZE, wy, 0)
                glVertex3f(wx+CELL_SIZE, wy, WALL_HEIGHT); glVertex3f(wx, wy, WALL_HEIGHT)
                glNormal3f(0, 1, 0)
                glVertex3f(wx, wy+CELL_SIZE, 0); glVertex3f(wx+CELL_SIZE, wy+CELL_SIZE, 0)
                glVertex3f(wx+CELL_SIZE, wy+CELL_SIZE, WALL_HEIGHT); glVertex3f(wx, wy+CELL_SIZE, WALL_HEIGHT)
                glNormal3f(-1, 0, 0)
                glVertex3f(wx, wy, 0); glVertex3f(wx, wy+CELL_SIZE, 0)
                glVertex3f(wx, wy+CELL_SIZE, WALL_HEIGHT); glVertex3f(wx, wy, WALL_HEIGHT)
                glNormal3f(1, 0, 0)
                glVertex3f(wx+CELL_SIZE, wy, 0); glVertex3f(wx+CELL_SIZE, wy+CELL_SIZE, 0)
                glVertex3f(wx+CELL_SIZE, wy+CELL_SIZE, WALL_HEIGHT); glVertex3f(wx+CELL_SIZE, wy, WALL_HEIGHT)
    glEnd()

def draw_player_model():
    if not is_third_person: return
    glPushMatrix()
    glTranslatef(px, py, 0)
    glRotatef(math.degrees(p_angle) - 90, 0, 0, 1)
    glColor3f(*COLOR_PLAYER)
    gluCylinder(quadric, PLAYER_RADIUS, PLAYER_RADIUS, PLAYER_HEIGHT, 16, 1)
    glPushMatrix()
    glTranslatef(0, 0, PLAYER_HEIGHT)
    gluSphere(quadric, PLAYER_RADIUS, 16, 16)
    glPopMatrix()
    glPopMatrix()

def draw_projectiles():
    glColor3f(*COLOR_BALL)
    for p in projectiles:
        if p.active:
            glPushMatrix()
            glTranslatef(p.x, p.y, p.z)
            glutSolidSphere(p.radius, 8, 8)
            glPopMatrix()

def draw_nextbots():
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, nextbot_tex)
    glColor3f(1, 1, 1)
    hs = NEXTBOT_SIZE / 2
    for ghost in ghosts:
        glPushMatrix()
        glTranslatef(ghost['x'], ghost['y'], WALL_HEIGHT/2)
        dx = px - ghost['x']; dy = py - ghost['y']
        angle = math.degrees(math.atan2(dy, dx))
        glRotatef(angle - 90, 0, 0, 1)
        
        if is_ghost_light_on:
             glMaterialfv(GL_FRONT, GL_EMISSION, [1.0, 1.0, 1.0, 1.0])
             glColor3f(1.0, 1.0, 1.0) 
        elif not is_torch_on: 
             glColor3f(*ghost['color']) 
             glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])
        else: 
             glColor3f(1,1,1)
             glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])
             
        glNormal3f(0, -1, 0) 
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex3f(-hs, 0, -hs)
        glTexCoord2f(1, 0); glVertex3f(hs, 0, -hs)
        glTexCoord2f(1, 1); glVertex3f(hs, 0, hs)
        glTexCoord2f(0, 1); glVertex3f(-hs, 0, hs)
        glEnd()
        glPopMatrix()
        
    glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])
    glDisable(GL_TEXTURE_2D)

def draw_jumpscare():
    # 1. Disable Lighting and Depth Test so 2D elements draw properly on top
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST) 
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    
    # 2. Draw the Background Image (Red Tint)
    glEnable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, nextbot_tex)
    glColor3f(1, 0, 0) # Red tint
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(0, 0); glTexCoord2f(1, 0); glVertex2f(WINDOW_WIDTH, 0)
    glTexCoord2f(1, 1); glVertex2f(WINDOW_WIDTH, WINDOW_HEIGHT); glTexCoord2f(0, 1); glVertex2f(0, WINDOW_HEIGHT)
    glEnd()
    glDisable(GL_TEXTURE_2D)
    
    # 3. Draw Center "You Died" Text
    glColor3f(1, 1, 1) # White
    msg_center = "YOU DIED"
    glRasterPos2f(WINDOW_WIDTH/2 - 50, WINDOW_HEIGHT/2)
    for ch in msg_center: glutBitmapCharacter(GLUT_BITMAP_TIMES_ROMAN_24, ord(ch))
    glRasterPos2f(WINDOW_WIDTH/2 - 80, WINDOW_HEIGHT/2 - 40)
    for ch in "(Press 'R' to Restart)": glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(ch))
    
    # 4. Draw Result Text (Top-Left) - YELLOW
    result_msg = f"You got caught!! Beat: {total_hits}, Survived for {survival_time:.2f} seconds"
    glColor3f(1.0, 1.0, 0.0) # Yellow
    glRasterPos2f(20, WINDOW_HEIGHT - 50) 
    for ch in result_msg:
        glutBitmapCharacter(GLUT_BITMAP_TIMES_ROMAN_24, ord(ch))
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)
    
    # 5. Re-enable Depth Test for the rest of the game
    glEnable(GL_DEPTH_TEST)

def draw_hud():
    glDisable(GL_LIGHTING) 
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    
    # -------------------------------------------------------------
    # NEW CODE: BEAT COUNTER TOP-LEFT
    # -------------------------------------------------------------
    beat_msg = f"Beat : {total_hits}"
    glColor3f(1.0, 1.0, 0.2) # Bright Yellow
    # Position: X=20, Y=Height-40 (Near top left)
    glRasterPos2f(20, WINDOW_HEIGHT - 40)
    for ch in beat_msg:
        glutBitmapCharacter(GLUT_BITMAP_TIMES_ROMAN_24, ord(ch))
    # -------------------------------------------------------------

    # Stamina Bar
    glColor3f(0.2, 0.2, 0.2); glRectf(10, 10, 210, 30)
    if stamina > 20: glColor3f(0, 1, 0)
    else: glColor3f(1, 0, 0)
    glRectf(10, 10, 10 + (stamina/MAX_STAMINA)*200, 30)
    
    # Bottom HUD Text
    glColor3f(1, 1, 1)
    glRasterPos2f(10, 40)
    
    status_msg = "OFF"
    if is_ghost_light_on: status_msg = "INTENSE"
    
    hud_msg = f"Time: {survival_time:.1f}s | G: Ghost Light ({status_msg}) | Space: Throw"
    for ch in hud_msg: glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(ch))
    
    if is_autopilot:
        glColor3f(0.3, 0.8, 1.0) 
        cheat_msg = "[AUTOPILOT ENGAGED]"
        glRasterPos2f(10, 70)
        for ch in cheat_msg: glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(ch))

    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)

def draw_minimap():
    map_size = 200
    padding = 10
    glPushAttrib(GL_VIEWPORT_BIT)
    glViewport(WINDOW_WIDTH - map_size - padding, WINDOW_HEIGHT - map_size - padding, map_size, map_size)
    
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    world_w = maze_w * CELL_SIZE
    world_h = maze_h * CELL_SIZE
    gluOrtho2D(-10, world_w + 10, -10, world_h + 10)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    
    glDisable(GL_TEXTURE_2D); glDisable(GL_LIGHTING); glDisable(GL_DEPTH_TEST)
    
    glColor4f(0.0, 0.0, 0.0, 0.6)
    glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glRectf(-10, -10, world_w+10, world_h+10)
    glDisable(GL_BLEND)
    
    glColor3f(0.5, 0.5, 0.5)
    glBegin(GL_QUADS)
    for y in range(maze_h):
        for x in range(maze_w):
            if maze[y][x] == 1:
                wx = x * CELL_SIZE; wy = y * CELL_SIZE
                glVertex2f(wx, wy); glVertex2f(wx+CELL_SIZE, wy)
                glVertex2f(wx+CELL_SIZE, wy+CELL_SIZE); glVertex2f(wx, wy+CELL_SIZE)
    glEnd()
    
    glColor3f(1.0, 1.0, 0.5)
    glPointSize(2.0)
    glBegin(GL_POINTS)
    for lx, ly, lz in ceiling_lights:
        glVertex2f(lx, ly)
    glEnd()
    
    for ghost in ghosts:
        glColor3f(*ghost['color'])
        glPushMatrix()
        glTranslatef(ghost['x'], ghost['y'], 0)
        glBegin(GL_POLYGON)
        for i in range(12):
            theta = 2.0 * math.pi * i / 12
            glVertex2f(NEXTBOT_SIZE/2 * math.cos(theta), NEXTBOT_SIZE/2 * math.sin(theta))
        glEnd()
        glPopMatrix()
    
    if is_autopilot: glColor3f(0, 1, 1) 
    else: glColor3f(0, 1, 0)
    
    glPushMatrix()
    glTranslatef(px, py, 0)
    glRotatef(math.degrees(p_angle), 0, 0, 1)
    glBegin(GL_TRIANGLES)
    glVertex2f(6, 0); glVertex2f(-4, 4); glVertex2f(-4, -4)
    glEnd()
    glPopMatrix()
    
    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW); glPopMatrix()
    glPopAttrib()
    glEnable(GL_DEPTH_TEST)

def setup_lighting():
    if is_torch_on:
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        light_pos = [px, py, PLAYER_HEIGHT, 1.0]
        spot_dir = [math.cos(p_angle), math.sin(p_angle), -0.2]
        glLightfv(GL_LIGHT0, GL_POSITION, light_pos)
        glLightfv(GL_LIGHT0, GL_SPOT_DIRECTION, spot_dir)
        glLightf(GL_LIGHT0, GL_SPOT_CUTOFF, 45.0) 
        glLightf(GL_LIGHT0, GL_SPOT_EXPONENT, 2.0)
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [1, 1, 1, 1])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.05, 0.05, 0.05, 1]) 
    else:
        glDisable(GL_LIGHT0)
        glEnable(GL_LIGHTING)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    available_hw_lights = [GL_LIGHT1, GL_LIGHT2, GL_LIGHT3, GL_LIGHT4, GL_LIGHT5, GL_LIGHT6, GL_LIGHT7]
    
    def dist_sq_to_player(pos):
        return (pos[0]-px)**2 + (pos[1]-py)**2

    if is_ghost_light_on:
        ghost_sources = []
        for g in ghosts:
            ghost_sources.append( (g['x'], g['y'], WALL_HEIGHT/2, g['color']) )
            
        closest_sources = sorted(ghost_sources, key=dist_sq_to_player)[:7]
        
        for i, hw_light in enumerate(available_hw_lights):
            if i < len(closest_sources):
                glEnable(hw_light)
                gx, gy, gz, col = closest_sources[i]
                
                glLightfv(hw_light, GL_POSITION, [gx, gy, gz, 1.0])
                glLightfv(hw_light, GL_DIFFUSE, [col[0], col[1], col[2], 1.0])
                glLightfv(hw_light, GL_SPECULAR, [1.0, 1.0, 1.0, 1.0])
                
                glLightf(hw_light, GL_CONSTANT_ATTENUATION, 0.05) 
                glLightf(hw_light, GL_LINEAR_ATTENUATION, 0.02)   
                glLightf(hw_light, GL_QUADRATIC_ATTENUATION, 0.005) 
            else:
                glDisable(hw_light)
                
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.05, 0.05, 0.05, 1.0])

    else:
        closest_lights = sorted(ceiling_lights, key=dist_sq_to_player)[:7]
        
        for i, hw_light in enumerate(available_hw_lights):
            if i < len(closest_lights):
                glEnable(hw_light)
                lx, ly, lz = closest_lights[i]
                
                glLightfv(hw_light, GL_POSITION, [lx, ly, lz, 1.0])
                glLightfv(hw_light, GL_DIFFUSE, [0.8, 0.8, 0.6, 1.0])
                glLightfv(hw_light, GL_SPECULAR, [1.0, 1.0, 1.0, 1.0])
                
                glLightf(hw_light, GL_CONSTANT_ATTENUATION, 0.5)
                glLightf(hw_light, GL_LINEAR_ATTENUATION, 0.1)
                glLightf(hw_light, GL_QUADRATIC_ATTENUATION, 0.02)
            else:
                glDisable(hw_light)
                
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.2, 0.2, 0.2, 1.0])

def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    if jumpscare_active:
        draw_jumpscare()
    else:
        if is_third_person:
            cx = px - math.cos(p_angle) * THIRD_PERSON_DIST
            cy = py - math.sin(p_angle) * THIRD_PERSON_DIST
            gluLookAt(cx, cy, THIRD_PERSON_HEIGHT, px, py, PLAYER_HEIGHT, 0, 0, 1)
        else:
            cam_height = WALL_HEIGHT * 0.6
            cx = px + math.cos(p_angle)
            cy = py + math.sin(p_angle)
            gluLookAt(px, py, cam_height, cx, cy, cam_height, 0, 0, 1)
        
        setup_lighting() 
        draw_maze_3d()
        draw_projectiles()
        draw_player_model()
        draw_nextbots() 
        draw_hud()
        draw_minimap()
    glutSwapBuffers()

def idle():
    global last_frame_time
    curr = time.time()
    if last_frame_time == 0: last_frame_time = curr
    dt = curr - last_frame_time
    last_frame_time = curr
    if dt > 0.1: dt = 0.1
    update(dt)
    glutPostRedisplay()

def keyboard(key, x, y):
    global is_third_person, is_torch_on, is_autopilot, is_ghost_light_on
    try: key_char = key.decode('utf-8').lower().encode('utf-8')
    except: key_char = key
    keys[key_char] = True
    
    if key == b'\x1b': glutLeaveMainLoop()
    if key == b'r': reset_game()
    if key == b'f' or key == b'F': is_third_person = not is_third_person
    if key == b't' or key == b'T': is_torch_on = not is_torch_on
    if key == b'c' or key == b'C': is_autopilot = not is_autopilot
    
    if key == b' ': projectiles.append(Projectile(px, py, PLAYER_HEIGHT, p_angle))

    if key == b'g' or key == b'G':
        is_ghost_light_on = not is_ghost_light_on
        state = "ON" if is_ghost_light_on else "OFF"
        print(f"Ghost Lights are now {state}")

def keyboard_up(key, x, y):
    try: key_char = key.decode('utf-8').lower().encode('utf-8')
    except: key_char = key
    keys[key_char] = False

def special(key, x, y): 
    special_keys_state[key] = True
    mod = glutGetModifiers()
    keys[b'shift'] = (mod == GLUT_ACTIVE_SHIFT)
def special_up(key, x, y): 
    special_keys_state[key] = False
    keys[b'shift'] = False

def init():
    global maze, maze_w, maze_h, nextbot_tex, start_time, quadric, ceiling_lights
    glClearColor(0, 0, 0, 1)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_NORMALIZE) 
    
    maze = generate_maze(MAZE_SIZE, MAZE_SIZE)
    maze_w = len(maze[0]); maze_h = len(maze)
    
    ceiling_lights = []
    for y in range(maze_h):
        for x in range(maze_w):
            if maze[y][x] == 0:
                lx = x * CELL_SIZE + CELL_SIZE/2.0
                ly = y * CELL_SIZE + CELL_SIZE/2.0
                lz = WALL_HEIGHT
                ceiling_lights.append((lx, ly, lz))
    
    nextbot_tex = create_nextbot_texture()
    quadric = gluNewQuadric()
    spawn_entities()
    start_time = time.time()

def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_WIDTH, WINDOW_HEIGHT)
    glutCreateWindow(b"Nextbot AI: [F] View, [T] Torch, [G] Ghost Light")
    init()
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluPerspective(60, WINDOW_WIDTH/WINDOW_HEIGHT, 0.1, 100.0)
    glMatrixMode(GL_MODELVIEW)
    glutDisplayFunc(display); glutIdleFunc(idle)
    glutKeyboardFunc(keyboard); glutKeyboardUpFunc(keyboard_up)
    glutSpecialFunc(special); glutSpecialUpFunc(special_up)
    glutMainLoop()

if __name__ == "__main__":
    main()

# space --> Shoot ball - Physics + After every three kill, ghost number incrreases by one
# F/f --> first person/ third person view (roof removed)
# W/A/S/D --> Move
# left/right arrow --> Turn left/right
# R/r --> Restart game 
# T/t --> Toggle torch light
# C/c --> autopilot mode (cheat)
# G/g --> toggle ghost light (new intense light from ghosts)

# tried to show result on jumpscare window
# autopilot doesnot work well
