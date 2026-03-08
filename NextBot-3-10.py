from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
import random
import time
import collections
import sys
import os

# IMPORT PILLOW FOR IMAGE LOADING
try:
    from PIL import Image
except ImportError:
    print("Error: This script requires the Pillow library to load the image.")
    print("Please run: /opt/homebrew/bin/python3 -m pip install Pillow --break-system-packages")
    sys.exit()

# =============================================================================
# CONFIGURATION
# =============================================================================
WINDOW_WIDTH, WINDOW_HEIGHT = 800, 600
MAZE_SIZE = 16 
CELL_SIZE = 10.0
WALL_HEIGHT = 10.0

# IMAGE CONFIGURATION
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GHOST_FILENAMES = [f"ghost{i}.jpg" for i in range(1, 7)]

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

# Switch Settings
SWITCH_RADIUS = 1.0  
HIT_RADIUS = 2.5     

# Colors 
COLOR_WALL = (0.8, 0.7, 0.4) 
COLOR_FLOOR = (0.6, 0.5, 0.3)
COLOR_CEILING = (0.9, 0.9, 0.8)
COLOR_PLAYER = (0.2, 0.8, 0.2)
COLOR_BALL = (1.0, 0.2, 0.2)
COLOR_LIGHT_BULB = (1.0, 1.0, 0.8) 
COLOR_SWITCH_OFF = (0.0, 0.0, 1.0) 
COLOR_SWITCH_ON = (0.0, 1.0, 1.0)  

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
        
        # Check Switch Collision
        check_switch_hit(self)

        if self.z < -10 or (abs(self.vx) < 0.1 and abs(self.vy) < 0.1 and abs(self.vz) < 0.1):
            self.active = False

# =============================================================================
# TEXTURE LOADING
# =============================================================================
def create_nextbot_textures():
    print(f"--- ATTEMPTING TO LOAD TEXTURES ---")
    texture_ids = []
    for filename in GHOST_FILENAMES:
        full_path = os.path.join(SCRIPT_DIR, filename)
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        
        try:
            image = Image.open(full_path)
            image = image.transpose(Image.FLIP_TOP_BOTTOM)
            if image.mode != "RGB":
                image = image.convert("RGB")
            image = image.resize((256, 256))
            img_data = image.tobytes("raw", "RGB", 0, -1)
            
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, 256, 256, 0, GL_RGB, GL_UNSIGNED_BYTE, img_data)
            print(f"SUCCESS: Loaded {filename}")
        except Exception as e:
            print(f"ERROR: Could not load {filename}. Using placeholder. {e}")
            width, height = 64, 64
            data = bytearray(width * height * 3)
            for y in range(height):
                for x in range(width):
                    if (x // 8 + y // 8) % 2 == 0: r, g, b = 255, 0, 255 
                    else: r, g, b = 0, 0, 0 
                    idx = (y * width + x) * 3
                    data[idx] = r; data[idx+1] = g; data[idx+2] = b
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE, bytes(data))
        
        texture_ids.append(tex_id)
    return texture_ids

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

nextbot_textures = [] 
killer_tex_id = None 

quadric = None
ceiling_lights = [] 
switches = [] 

# Diamond & Gate Logic
diamonds = []
diamonds_left = 5
gate_x = 0
gate_y = 0
gate_open = False
game_won = False

# Light System State
light_state = "OFF" 
light_timer = 0.0
blink_counter = 0
blink_interval_timer = 0.0
is_light_actually_on = False 

# Player
px, py = 0, 0
p_angle = 0
stamina = MAX_STAMINA
is_third_person = False
is_torch_on = False 

# Autopilot State
is_autopilot = False
shoot_cooldown = 0.0

# Entities
ghosts = [] 
projectiles = []

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
                is_solid = maze[gy][gx] == 1 or (maze[gy][gx] == 2 and not gate_open)
                if is_solid:
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

def check_switch_hit(projectile):
    global light_state, light_timer, is_light_actually_on
    for s in switches:
        dx = projectile.x - s['x']
        dy = projectile.y - s['y']
        dz = projectile.z - s['z']
        dist_sq = dx*dx + dy*dy + dz*dz
        
        if dist_sq < HIT_RADIUS**2:
            if light_state == "OFF":
                print("SWITCH HIT! Lights ON for 20s.")
                light_state = "ON"
                light_timer = 20.0
                is_light_actually_on = True

def generate_switches():
    global switches
    switches = []
    potential_spots = []
    
    for y in range(1, maze_h-1):
        for x in range(1, maze_w-1):
            if maze[y][x] == 1:
                cx = x * CELL_SIZE + CELL_SIZE/2
                cy = y * CELL_SIZE + CELL_SIZE/2
                cz = WALL_HEIGHT / 2 
                offset = CELL_SIZE/2 + 0.2
                
                if maze[y][x+1] == 0: 
                    potential_spots.append({'x': cx + offset, 'y': cy, 'z': cz})
                elif maze[y][x-1] == 0: 
                    potential_spots.append({'x': cx - offset, 'y': cy, 'z': cz})
                elif maze[y+1][x] == 0: 
                    potential_spots.append({'x': cx, 'y': cy + offset, 'z': cz})
                elif maze[y-1][x] == 0: 
                    potential_spots.append({'x': cx, 'y': cy - offset, 'z': cz})

    if potential_spots:
        random.shuffle(potential_spots)
        switches = potential_spots[:3]
        print(f"Generated {len(switches)} switches.")

def check_line_of_sight(x1, y1, x2, y2):
    dist = math.sqrt((x2-x1)**2 + (y2-y1)**2)
    if dist == 0: return True
    step_size = 0.5 
    steps = int(dist / step_size)
    dx = (x2 - x1) / steps
    dy = (y2 - y1) / steps
    cx, cy = x1, y1
    for i in range(steps):
        if check_wall_collision(cx, cy, 0.2): return False
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

def setup_gate():
    global gate_x, gate_y, gate_open, game_won
    gate_open = False
    game_won = False
    found = False
    for y in [1, maze_h-2]:
        for x in range(1, maze_w-1):
            if maze[y][x] == 0:
                if y == 1:
                    maze[0][x] = 2 
                    gate_x, gate_y = x, 0
                else:
                    maze[maze_h-1][x] = 2
                    gate_x, gate_y = x, maze_h-1
                found = True
                break
        if found: break

def generate_diamonds():
    global diamonds, diamonds_left
    diamonds = []
    diamonds_left = 5
    for _ in range(5):
        dx, dy = get_random_empty_spot()
        diamonds.append({'x': dx, 'y': dy, 'z': WALL_HEIGHT / 2, 'rot': random.uniform(0, 360)})

def spawn_entities():
    global px, py, ghosts
    px, py = get_random_empty_spot()
    ghosts = []
    add_new_ghost() 
    generate_switches() 
    generate_diamonds()

def add_new_ghost():
    gx, gy = get_random_empty_spot()
    while (gx-px)**2 + (gy-py)**2 < 100*100:
        gx, gy = get_random_empty_spot()
    
    tex_idx = random.randint(0, len(nextbot_textures) - 1) if nextbot_textures else 0
    ghosts.append({
        'x': gx, 
        'y': gy, 
        'color': (1.0, 1.0, 1.0),
        'tex_idx': tex_idx 
    })

def relocate_ghost(ghost_index):
    gx, gy = get_random_empty_spot()
    ghosts[ghost_index]['x'] = gx
    ghosts[ghost_index]['y'] = gy

def reset_game():
    global stamina, jumpscare_active, start_time, keys, projectiles
    global light_state, light_timer, is_light_actually_on, killer_tex_id
    
    setup_gate()
    spawn_entities()
    stamina = MAX_STAMINA
    jumpscare_active = False
    projectiles = []
    start_time = time.time()
    keys = {}
    killer_tex_id = None
    
    # Reset Lights
    light_state = "OFF"
    light_timer = 0.0
    is_light_actually_on = False

def update(dt):
    global px, py, p_angle, stamina, jumpscare_active, survival_time, game_won
    global light_state, light_timer, blink_counter, blink_interval_timer, is_light_actually_on
    global killer_tex_id, diamonds_left, gate_open 

    if jumpscare_active or game_won: return
    survival_time = time.time() - start_time

    # --- LIGHT TIMER LOGIC ---
    if light_state == "ON":
        light_timer -= dt
        is_light_actually_on = True
        if light_timer <= 0:
            print("Lights entering blinking phase.")
            light_state = "BLINK"
            blink_counter = 0
            blink_interval_timer = 0.3 
            is_light_actually_on = False

    elif light_state == "BLINK":
        blink_interval_timer -= dt
        if blink_interval_timer <= 0:
            blink_interval_timer = 0.3 
            blink_counter += 1
            is_light_actually_on = not is_light_actually_on 
            if blink_counter >= 6:
                print("Lights OFF.")
                light_state = "OFF"
                is_light_actually_on = False
    
    elif light_state == "OFF":
        is_light_actually_on = False
    # -------------------------

    # --- DIAMOND LOGIC ---
    for d in diamonds[:]:
        d['rot'] += 100.0 * dt
        dist = math.sqrt((px - d['x'])**2 + (py - d['y'])**2)
        if dist < PLAYER_RADIUS + 1.5:
            diamonds.remove(d)
            diamonds_left -= 1
            # Add 5 new ghosts per diamond collected
            for _ in range(5):
                add_new_ghost()
            
            if diamonds_left == 0:
                gate_open = True
                print("Gate Unlocked! Escape!")
    
    # --- ESCAPE LOGIC ---
    if gate_open:
        dist_to_gate = math.sqrt((px - (gate_x * CELL_SIZE + CELL_SIZE/2))**2 + (py - (gate_y * CELL_SIZE + CELL_SIZE/2))**2)
        if dist_to_gate < CELL_SIZE:
            game_won = True
            print(f"ESCAPED! Survived for {survival_time:.2f}s")
            return

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
                if len(nextbot_textures) > 0 and ghost['tex_idx'] < len(nextbot_textures):
                    killer_tex_id = nextbot_textures[ghost['tex_idx']]
                jumpscare_active = True
                print(f"You got caught!! Survived for {survival_time:.2f} seconds")
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
    glDisable(GL_TEXTURE_2D)
    
    if is_light_actually_on:
        glMaterialfv(GL_FRONT, GL_EMISSION, [1.0, 1.0, 0.8, 1.0]) 
        glColor3f(*COLOR_LIGHT_BULB)
    else:
        glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0]) 
        glColor3f(0.1, 0.1, 0.1) 

    for (lx, ly, lz) in ceiling_lights:
        glPushMatrix()
        glTranslatef(lx, ly, lz)
        glutSolidSphere(0.3, 8, 8) 
        glPopMatrix()
        
    glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])

def draw_switches():
    glDisable(GL_TEXTURE_2D)
    
    for s in switches:
        glPushMatrix()
        glTranslatef(s['x'], s['y'], s['z'])
        
        if light_state == "OFF":
             glColor3f(*COLOR_SWITCH_OFF) 
             glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 1.0, 1.0]) 
        else:
             glColor3f(*COLOR_SWITCH_ON) 
             glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.5, 0.5, 1.0])
             
        glutSolidSphere(SWITCH_RADIUS, 10, 10)
        glPopMatrix()
        
    glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])

def draw_diamonds():
    glDisable(GL_TEXTURE_2D)
    glMaterialfv(GL_FRONT, GL_EMISSION, [0.2, 0.8, 1.0, 1.0])
    glColor3f(0.0, 1.0, 1.0)
    for d in diamonds:
        glPushMatrix()
        glTranslatef(d['x'], d['y'], d['z'] + math.sin(survival_time * 4) * 1.5)
        glRotatef(d['rot'], 0, 0, 1)
        glRotatef(45, 1, 0, 0)
        glScalef(1.5, 1.5, 1.5)
        glutSolidOctahedron() 
        glPopMatrix()
    glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])

def draw_maze_3d():
    glDisable(GL_TEXTURE_2D)
    draw_ceiling_lights()
    draw_switches() 
    draw_diamonds()

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
            
            # Walls & Gate
            if maze[y][x] == 1 or maze[y][x] == 2:
                if maze[y][x] == 2 and gate_open:
                    # Draw open glowing exit portal
                    glColor3f(1.0, 1.0, 1.0)
                    glMaterialfv(GL_FRONT, GL_EMISSION, [1.0, 1.0, 1.0, 1.0])
                    glNormal3f(0, 0, 1)
                    glVertex3f(wx, wy, 0); glVertex3f(wx+CELL_SIZE, wy, 0)
                    glVertex3f(wx+CELL_SIZE, wy+CELL_SIZE, 0); glVertex3f(wx, wy+CELL_SIZE, 0)
                    glNormal3f(0, -1, 0)
                    glVertex3f(wx, wy, 0); glVertex3f(wx+CELL_SIZE, wy, 0)
                    glVertex3f(wx+CELL_SIZE, wy, WALL_HEIGHT); glVertex3f(wx, wy, WALL_HEIGHT)
                    glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])
                    continue 
                elif maze[y][x] == 2 and not gate_open:
                    glColor3f(0.2, 0.2, 0.2) # Dark metal locked gate
                    glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])
                else:
                    glColor3f(*COLOR_WALL) 
                    glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])

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
    glMaterialfv(GL_FRONT, GL_EMISSION, [1.0, 0.4, 0.4, 1.0])
    glColor3f(*COLOR_BALL)
    for p in projectiles:
        if p.active:
            glPushMatrix()
            glTranslatef(p.x, p.y, p.z)
            glutSolidSphere(p.radius, 8, 8)
            glPopMatrix()
    glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])

def draw_nextbots():
    glEnable(GL_TEXTURE_2D)
    hs = NEXTBOT_SIZE / 2
    
    for ghost in ghosts:
        idx = ghost['tex_idx']
        if idx < len(nextbot_textures):
            glBindTexture(GL_TEXTURE_2D, nextbot_textures[idx])
        
        glPushMatrix()
        glTranslatef(ghost['x'], ghost['y'], WALL_HEIGHT/2)
        dx = px - ghost['x']; dy = py - ghost['y']
        angle = math.degrees(math.atan2(dy, dx))
        
        glRotatef(angle - 90, 0, 0, 1) 
        
        glColor3f(1.0, 1.0, 1.0)
        glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])
             
        glNormal3f(0, -1, 0) 
        glBegin(GL_QUADS)
        glTexCoord2f(0, 1); glVertex3f(-hs, 0, -hs)
        glTexCoord2f(1, 1); glVertex3f(hs, 0, -hs)
        glTexCoord2f(1, 0); glVertex3f(hs, 0, hs)
        glTexCoord2f(0, 0); glVertex3f(-hs, 0, hs)
        glEnd()
        glPopMatrix()
        
    glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])
    glDisable(GL_TEXTURE_2D)

def draw_jumpscare():
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST) 
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    
    glEnable(GL_TEXTURE_2D)
    if killer_tex_id is not None:
        glBindTexture(GL_TEXTURE_2D, killer_tex_id)
    elif len(nextbot_textures) > 0:
        glBindTexture(GL_TEXTURE_2D, nextbot_textures[0]) 
        
    glColor3f(1, 1, 1) 
    glBegin(GL_QUADS)
    glTexCoord2f(0, 1); glVertex2f(0, 0)
    glTexCoord2f(1, 1); glVertex2f(WINDOW_WIDTH, 0)
    glTexCoord2f(1, 0); glVertex2f(WINDOW_WIDTH, WINDOW_HEIGHT)
    glTexCoord2f(0, 0); glVertex2f(0, WINDOW_HEIGHT)
    glEnd()
    glDisable(GL_TEXTURE_2D)
    
    glColor3f(1, 0, 0)
    msg_center = "YOU DIED"
    glRasterPos2f(WINDOW_WIDTH/2 - 50, WINDOW_HEIGHT/2)
    for ch in msg_center: glutBitmapCharacter(GLUT_BITMAP_TIMES_ROMAN_24, ord(ch))
    glRasterPos2f(WINDOW_WIDTH/2 - 80, WINDOW_HEIGHT/2 - 40)
    for ch in "(Press 'R' to Restart)": glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(ch))
    
    result_msg = f"Survived for {survival_time:.2f} seconds"
    glColor3f(1.0, 1.0, 0.0) 
    glRasterPos2f(20, WINDOW_HEIGHT - 50) 
    for ch in result_msg:
        glutBitmapCharacter(GLUT_BITMAP_TIMES_ROMAN_24, ord(ch))
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)
    
    glEnable(GL_DEPTH_TEST)

def draw_victory():
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST) 
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    
    glColor3f(1, 1, 1)
    msg_center = "YOU ESCAPED!"
    glRasterPos2f(WINDOW_WIDTH/2 - 80, WINDOW_HEIGHT/2)
    for ch in msg_center: glutBitmapCharacter(GLUT_BITMAP_TIMES_ROMAN_24, ord(ch))
    
    glRasterPos2f(WINDOW_WIDTH/2 - 80, WINDOW_HEIGHT/2 - 40)
    for ch in "(Press 'R' to Restart)": glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(ch))
    
    result_msg = f"Survived for {survival_time:.2f} seconds"
    glColor3f(1.0, 1.0, 0.0) 
    glRasterPos2f(20, WINDOW_HEIGHT - 50) 
    for ch in result_msg:
        glutBitmapCharacter(GLUT_BITMAP_TIMES_ROMAN_24, ord(ch))
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)
    
    glEnable(GL_DEPTH_TEST)

def draw_hud():
    glDisable(GL_LIGHTING) 
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    
    diamond_msg = f"Diamonds: {diamonds_left}"
    if diamonds_left == 0:
        diamond_msg = "GATE UNLOCKED! ESCAPE!"
        glColor3f(0.0, 1.0, 0.0)
    else:
        glColor3f(0.0, 1.0, 1.0)
    glRasterPos2f(20, WINDOW_HEIGHT - 40)
    for ch in diamond_msg:
        glutBitmapCharacter(GLUT_BITMAP_TIMES_ROMAN_24, ord(ch))

    glColor3f(0.2, 0.2, 0.2); glRectf(10, 10, 210, 30)
    if stamina > 20: glColor3f(0, 1, 0)
    else: glColor3f(1, 0, 0)
    glRectf(10, 10, 10 + (stamina/MAX_STAMINA)*200, 30)
    
    glColor3f(1, 1, 1)
    glRasterPos2f(10, 40)
    
    if light_state == "ON":
        status_msg = f"ON ({int(light_timer)}s)"
    elif light_state == "BLINK":
        status_msg = "BLINKING"
    else:
        status_msg = "OFF (Hit Blue Button)"
    
    hud_msg = f"Time: {survival_time:.1f}s | Lights: {status_msg} | Space: Throw"
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
            elif maze[y][x] == 2:
                wx = x * CELL_SIZE; wy = y * CELL_SIZE
                if gate_open: glColor3f(1.0, 1.0, 1.0)
                else: glColor3f(0.3, 0.3, 0.3)
                glVertex2f(wx, wy); glVertex2f(wx+CELL_SIZE, wy)
                glVertex2f(wx+CELL_SIZE, wy+CELL_SIZE); glVertex2f(wx, wy+CELL_SIZE)
                glColor3f(0.5, 0.5, 0.5) 
    glEnd()
    
    glPointSize(5.0)
    glBegin(GL_POINTS)
    for s in switches:
        if light_state == "OFF":
             glColor3f(*COLOR_SWITCH_OFF)
        else:
             glColor3f(*COLOR_SWITCH_ON)
        glVertex2f(s['x'], s['y'])
    glEnd()

    # Draw Diamonds on map
    glColor3f(0.0, 1.0, 1.0)
    glPointSize(6.0)
    glBegin(GL_POINTS)
    for d in diamonds:
        glVertex2f(d['x'], d['y'])
    glEnd()

    glColor3f(1.0, 1.0, 0.5)
    glPointSize(2.0)
    glBegin(GL_POINTS)
    if is_light_actually_on: 
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
    # -------------------------------------------------------------
    # 1. TORCH LOGIC
    # -------------------------------------------------------------
    if is_torch_on:
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        light_pos = [px, py, PLAYER_HEIGHT, 1.0]
        spot_dir = [math.cos(p_angle), math.sin(p_angle), -0.2]
        
        glLightfv(GL_LIGHT0, GL_POSITION, light_pos)
        glLightfv(GL_LIGHT0, GL_SPOT_DIRECTION, spot_dir)
        
        glLightf(GL_LIGHT0, GL_SPOT_CUTOFF, 40.0) 
        glLightf(GL_LIGHT0, GL_SPOT_EXPONENT, 8.0)
        glLightf(GL_LIGHT0, GL_CONSTANT_ATTENUATION, 0.1) 
        glLightf(GL_LIGHT0, GL_LINEAR_ATTENUATION, 0.02)
        glLightf(GL_LIGHT0, GL_QUADRATIC_ATTENUATION, 0.003) 
        
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0, 1]) 
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1]) 
    else:
        glDisable(GL_LIGHT0)
        glEnable(GL_LIGHTING)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    # -------------------------------------------------------------
    # 2. GATHER LIGHT SOURCES
    # -------------------------------------------------------------
    light_candidates = []

    def dist_sq_to_player(pos):
        return (pos[0]-px)**2 + (pos[1]-py)**2

    # A. PROJECTILE LIGHTS
    for p in projectiles:
        if p.active:
            light_candidates.append({
                'pos': [p.x, p.y, p.z, 1.0],
                'diffuse': [1.0, 0.3, 0.3, 1.0], 
                'specular': [1.0, 0.5, 0.5, 1.0],
                'attenuation': (0.5, 0.1, 0.02)
            })

    # B. SWITCH GLOW
    for s in switches:
        d = dist_sq_to_player([s['x'], s['y']])
        if d < 1000:
             if light_state == "OFF": col = [0.0, 0.0, 1.0, 1.0] 
             else: col = [0.0, 1.0, 1.0, 1.0] 
             light_candidates.append({
                'pos': [s['x'], s['y'], s['z'], 1.0],
                'diffuse': col, 
                'specular': col,
                'attenuation': (0.2, 0.1, 0.1) 
            })

    # C. DIAMOND GLOW
    for d_obj in diamonds:
        d_dist = dist_sq_to_player([d_obj['x'], d_obj['y']])
        if d_dist < 1000:
            light_candidates.append({
                'pos': [d_obj['x'], d_obj['y'], d_obj['z'], 1.0],
                'diffuse': [0.0, 1.0, 1.0, 1.0], 
                'specular': [0.5, 1.0, 1.0, 1.0],
                'attenuation': (0.2, 0.1, 0.05) 
            })

    # D. GATE OPEN LIGHT
    if gate_open:
        light_candidates.append({
            'pos': [gate_x * CELL_SIZE + CELL_SIZE/2, gate_y * CELL_SIZE + CELL_SIZE/2, WALL_HEIGHT/2, 1.0],
            'diffuse': [1.0, 1.0, 1.0, 1.0],
            'specular': [1.0, 1.0, 1.0, 1.0],
            'attenuation': (0.1, 0.01, 0.001) 
        })

    # E. CEILING LIGHTS
    if is_light_actually_on:
        for l in ceiling_lights:
             d = dist_sq_to_player(l)
             if d < 4000: 
                lx, ly, lz = l
                if check_line_of_sight(px, py, lx, ly):
                    light_candidates.append({
                        'pos': [lx, ly, lz, 1.0],
                        'diffuse': [0.8, 0.8, 0.6, 1.0],
                        'specular': [1.0, 1.0, 1.0, 1.0],
                        'attenuation': (0.5, 0.1, 0.02) 
                    })
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.2, 0.2, 0.2, 1.0])
    else:
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.01, 0.01, 0.01, 1.0])

    # -------------------------------------------------------------
    # 3. SORT AND ASSIGN
    # -------------------------------------------------------------
    light_candidates.sort(key=lambda l: dist_sq_to_player(l['pos']))
    
    available_hw_lights = [GL_LIGHT1, GL_LIGHT2, GL_LIGHT3, GL_LIGHT4, GL_LIGHT5, GL_LIGHT6, GL_LIGHT7]
    
    for i, hw_light in enumerate(available_hw_lights):
        if i < len(light_candidates):
            l = light_candidates[i]
            glEnable(hw_light)
            glLightfv(hw_light, GL_POSITION, l['pos'])
            glLightfv(hw_light, GL_DIFFUSE, l['diffuse'])
            glLightfv(hw_light, GL_SPECULAR, l['specular'])
            
            att = l['attenuation']
            glLightf(hw_light, GL_CONSTANT_ATTENUATION, att[0])
            glLightf(hw_light, GL_LINEAR_ATTENUATION, att[1])
            glLightf(hw_light, GL_QUADRATIC_ATTENUATION, att[2])
        else:
            glDisable(hw_light)

def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    if game_won:
        draw_victory()
    elif jumpscare_active:
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
    global is_third_person, is_torch_on, is_autopilot
    try: key_char = key.decode('utf-8').lower().encode('utf-8')
    except: key_char = key
    keys[key_char] = True
    
    if key == b'\x1b': glutLeaveMainLoop()
    if key == b'r': reset_game()
    if key == b'f' or key == b'F': is_third_person = not is_third_person
    if key == b't' or key == b'T': is_torch_on = not is_torch_on
    if key == b'c' or key == b'C': is_autopilot = not is_autopilot
    
    if key == b' ': projectiles.append(Projectile(px, py, PLAYER_HEIGHT, p_angle))

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
    global maze, maze_w, maze_h, nextbot_textures, start_time, quadric, ceiling_lights
    glClearColor(0, 0, 0, 1)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_NORMALIZE) 
    
    maze = generate_maze(MAZE_SIZE, MAZE_SIZE)
    maze_w = len(maze[0]); maze_h = len(maze)
    
    setup_gate()
    
    ceiling_lights = []
    for y in range(maze_h):
        for x in range(maze_w):
            if maze[y][x] == 0:
                lx = x * CELL_SIZE + CELL_SIZE/2.0
                ly = y * CELL_SIZE + CELL_SIZE/2.0
                lz = WALL_HEIGHT
                ceiling_lights.append((lx, ly, lz))
    
    nextbot_textures = create_nextbot_textures()
    
    quadric = gluNewQuadric()
    spawn_entities()
    start_time = time.time()

def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_WIDTH, WINDOW_HEIGHT)
    glutCreateWindow(b"Nextbot AI: Find 5 Diamonds and Escape!")
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