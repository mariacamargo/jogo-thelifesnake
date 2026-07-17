"""
The Life Snake - jogo de cobrinha estilo retro (inspirado no classico "Worm")
com fundo bordo, 12 modulos, mensagens especiais nos modulos 7 e 12,
selecao de dificuldade e a cobrinha catando copinhos de cerveja.
"""
import math
import os
import random
import sys

import pygame

# ----------------------------------------------------------------------------
# Configuracao geral
# ----------------------------------------------------------------------------
CELL = 20
COLS, ROWS = 28, 18
MARGIN = 20
PLAY_W, PLAY_H = COLS * CELL, ROWS * CELL
WIDTH = PLAY_W + MARGIN * 2
HEIGHT = PLAY_H + MARGIN * 2 + 70

BOARD_LEFT = MARGIN
BOARD_TOP = MARGIN
BOARD_RIGHT = BOARD_LEFT + PLAY_W
BOARD_BOTTOM = BOARD_TOP + PLAY_H

FOOD_PER_LEVEL = 3
MAX_LEVEL = 12
MILESTONE_LEVELS = {
    7: "PARABENS! A LOLO E GAY E VC TBM",
    12: ("PARABENS! PARABENS! PARABENS! VOCE GANHOU O JOGO, "
         "MINHA CRIATIVIDADE MORREU NA ULTIMA FRASE, "
         "MAS CE FOI MARA, PARCEIRA! VAI CURINTHIA"),
}
GAME_OVER_MESSAGE = "LASCOU-SE, TENTE NOVAMENTE"

DIFFICULTIES = {
    "facil": {"label": "FACIL", "tagline": "SOU LENTO", "base_fps": 6, "step": 0.7, "max_fps": 13},
    "dificil": {"label": "DIFICIL", "tagline": "ME GARANTO", "base_fps": 11, "step": 1.4, "max_fps": 26},
}

BORDO = (70, 5, 22)
BORDO_ESCURO = (45, 2, 14)
CREME = (235, 225, 205)
PRETO_COBRA = (18, 16, 20)
ROSA_COBRA = (255, 60, 165)
ROSA_COBRA_ESCURO = (195, 15, 110)
CONTORNO_COBRA = (210, 195, 175)
DOURADO = (255, 200, 60)
VERMELHO_GAMEOVER = (255, 90, 90)
AMBAR = (214, 140, 20)
ESPUMA = (255, 250, 235)
BOTAO_COR = (110, 15, 38)
BOTAO_BORDA = (235, 225, 205)
BOTAO_HOVER = (150, 25, 52)

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
AUDIO_EXTENSIONS = ("mp3", "ogg", "wav")
SAMPLE_RATE = 44100

UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)


def find_head_image():
    """Procura qualquer imagem dentro de assets/ para usar na cabeca da cobra (qualquer nome de arquivo serve)."""
    if not os.path.isdir(ASSETS_DIR):
        return None
    for filename in sorted(os.listdir(ASSETS_DIR)):
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in ("png", "jpg", "jpeg", "webp", "bmp"):
            return os.path.join(ASSETS_DIR, filename)
    return None


def find_music_file():
    """Procura qualquer arquivo de audio (mp3/ogg/wav) dentro de assets/ para tocar como musica de fundo."""
    if not os.path.isdir(ASSETS_DIR):
        return None
    for filename in sorted(os.listdir(ASSETS_DIR)):
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in AUDIO_EXTENSIONS:
            return os.path.join(ASSETS_DIR, filename)
    return None


def generate_chiptune_loop():
    """Gera uma musiquinha 8-bit original e curtinha em loop, caso nao haja arquivo de audio em assets/."""
    try:
        import numpy as np
    except ImportError:
        return None

    def tone(freq, duration, volume=0.22):
        t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
        wave = np.sign(np.sin(2 * np.pi * freq * t))
        fade = int(SAMPLE_RATE * 0.006)
        if fade > 0 and len(wave) > 2 * fade:
            wave[:fade] *= np.linspace(0, 1, fade)
            wave[-fade:] *= np.linspace(1, 0, fade)
        return wave * volume

    melody = [
        (261.63, 0.22), (329.63, 0.22), (392.00, 0.22), (523.25, 0.30),
        (392.00, 0.22), (440.00, 0.22), (392.00, 0.22), (329.63, 0.22),
        (293.66, 0.22), (392.00, 0.22), (349.23, 0.22), (293.66, 0.30),
    ]
    segments = [tone(freq, dur) for freq, dur in melody]
    waveform = np.concatenate(segments)
    samples = (waveform * 32767).astype(np.int16)

    mixer_info = pygame.mixer.get_init()
    channels = mixer_info[2] if mixer_info else 1
    if channels == 2:
        samples = np.column_stack((samples, samples))

    try:
        sound = pygame.sndarray.make_sound(samples)
    except Exception:
        return None
    return sound


def build_head_surface(size):
    """Recorta a foto em assets/ num circulo do tamanho `size` para virar a cabeca da cobra."""
    path = find_head_image()
    if not path:
        return None
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    try:
        img = Image.open(path).convert("RGBA")
    except Exception:
        return None

    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    img.putalpha(mask)

    mode = img.mode
    data = img.tobytes()
    surface = pygame.image.fromstring(data, (size, size), mode)
    return surface.convert_alpha()


def draw_fallback_head(surface, rect):
    """Cabeca desenhada caso nenhuma foto tenha sido encontrada em assets/."""
    pygame.draw.ellipse(surface, DOURADO, rect)
    cx, cy = rect.center
    r = rect.width // 6
    pygame.draw.circle(surface, PRETO_COBRA, (cx - r, cy - r // 2), 2)
    pygame.draw.circle(surface, PRETO_COBRA, (cx + r, cy - r // 2), 2)


class Game:
    def __init__(self):
        try:
            pygame.mixer.pre_init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=512)
        except Exception:
            pass
        pygame.init()
        pygame.display.set_caption("The Life Snake")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_hud = pygame.font.SysFont("couriernew", 20, bold=True)
        self.font_msg = pygame.font.SysFont("couriernew", 22, bold=True)
        self.font_big = pygame.font.SysFont("couriernew", 34, bold=True)
        self.font_title = pygame.font.SysFont("couriernew", 44, bold=True)
        self.font_btn = pygame.font.SysFont("couriernew", 22, bold=True)

        self.head_size = int(CELL * 1.8)
        self.head_surface = build_head_surface(self.head_size)
        self.logo_head_size = 100
        self.logo_head_surface = build_head_surface(self.logo_head_size)
        title_zone = pygame.Rect(WIDTH // 2 - 240, 130, 480, 90)
        self._sparkles = []
        while len(self._sparkles) < 12:
            x = random.randint(25, WIDTH - 25)
            y = random.randint(15, 220)
            if title_zone.collidepoint(x, y):
                continue
            self._sparkles.append((x, y, random.choice([7, 9, 12])))

        self.difficulty = "facil"
        self.state = "MENU"
        self.snake = []
        self.score = 0
        self.level = 1
        self.message = ""
        self.seen_milestones = set()
        self.food = (0, 0)

        self.btn_facil_rect = pygame.Rect(0, 0, 0, 0)
        self.btn_dificil_rect = pygame.Rect(0, 0, 0, 0)

        self.setup_music()

    def setup_music(self):
        """Toca um arquivo de assets/ se houver, senao gera uma musiquinha 8-bit propria em loop."""
        music_path = find_music_file()
        if music_path:
            try:
                pygame.mixer.music.load(music_path)
                pygame.mixer.music.set_volume(0.5)
                pygame.mixer.music.play(loops=-1)
                return
            except Exception:
                pass

        try:
            sound = generate_chiptune_loop()
            if sound:
                sound.set_volume(0.35)
                sound.play(loops=-1)
        except Exception:
            pass

    def start_game(self, difficulty):
        self.difficulty = difficulty
        cx, cy = COLS // 2, ROWS // 2
        self.snake = [(cx - 1, cy), (cx - 2, cy), (cx - 3, cy)]
        self.direction = RIGHT
        self.pending_direction = RIGHT
        self.score = 0
        self.level = 1
        self.food = self.spawn_food()
        self.state = "PLAYING"
        self.message = ""
        self.seen_milestones = set()

    def spawn_food(self):
        occupied = set(self.snake)
        while True:
            pos = (random.randint(0, COLS - 1), random.randint(0, ROWS - 1))
            if pos not in occupied:
                return pos

    def current_fps(self):
        cfg = DIFFICULTIES[self.difficulty]
        return min(cfg["base_fps"] + (self.level - 1) * cfg["step"], cfg["max_fps"])

    # ------------------------------------------------------------------
    # Entrada
    # ------------------------------------------------------------------
    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

                if self.state == "MENU":
                    if event.key in (pygame.K_1, pygame.K_f):
                        self.start_game("facil")
                    elif event.key in (pygame.K_2, pygame.K_d):
                        self.start_game("dificil")

                elif self.state == "PLAYING":
                    if event.key in (pygame.K_UP, pygame.K_w) and self.direction != DOWN:
                        self.pending_direction = UP
                    elif event.key in (pygame.K_DOWN, pygame.K_s) and self.direction != UP:
                        self.pending_direction = DOWN
                    elif event.key in (pygame.K_LEFT, pygame.K_a) and self.direction != RIGHT:
                        self.pending_direction = LEFT
                    elif event.key in (pygame.K_RIGHT, pygame.K_d) and self.direction != LEFT:
                        self.pending_direction = RIGHT

                elif self.state == "MILESTONE":
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        self.state = "PLAYING"

                elif self.state in ("GAME_OVER", "WIN"):
                    if event.key == pygame.K_r:
                        self.state = "MENU"

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.state == "MENU":
                    if self.btn_facil_rect.collidepoint(event.pos):
                        self.start_game("facil")
                    elif self.btn_dificil_rect.collidepoint(event.pos):
                        self.start_game("dificil")

    def update(self):
        if self.state != "PLAYING":
            return

        self.direction = self.pending_direction
        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        if not (0 <= new_head[0] < COLS and 0 <= new_head[1] < ROWS):
            self.state = "GAME_OVER"
            return

        if new_head in self.snake:
            self.state = "GAME_OVER"
            return

        self.snake.insert(0, new_head)

        if new_head == self.food:
            self.score += 1
            new_level = min(1 + self.score // FOOD_PER_LEVEL, MAX_LEVEL)
            if new_level != self.level:
                self.level = new_level
                if self.level in MILESTONE_LEVELS and self.level not in self.seen_milestones:
                    self.seen_milestones.add(self.level)
                    self.message = MILESTONE_LEVELS[self.level]
                    self.state = "WIN" if self.level == MAX_LEVEL else "MILESTONE"
                    return
            self.food = self.spawn_food()
        else:
            self.snake.pop()

    # ------------------------------------------------------------------
    # Desenho - menu
    # ------------------------------------------------------------------
    def draw_logo_snake(self, center_x, center_y):
        """Desenha uma cobrinha rosa bem caricata, toda torta e balancando, com a foto como cabeca."""
        n_segments = 8
        spacing = 25
        amplitude = 26
        wobble_t = pygame.time.get_ticks() / 300.0
        start_x = center_x - (n_segments * spacing) // 2

        points = []
        for i in range(n_segments + 1):
            x = start_x + i * spacing
            y = center_y + amplitude * math.sin(i * 1.1 + wobble_t)
            points.append((x, y))

        for i, (x, y) in enumerate(points[:-1]):
            radius = 15 - i
            pygame.draw.circle(self.screen, ROSA_COBRA, (int(x), int(y)), max(radius, 6))
            pygame.draw.circle(self.screen, ROSA_COBRA_ESCURO, (int(x), int(y)), max(radius, 6), width=2)

        # rabinho enrolado no final da cobra
        tail_x, tail_y = points[0]
        pygame.draw.arc(
            self.screen, ROSA_COBRA,
            pygame.Rect(int(tail_x) - 16, int(tail_y) - 10, 22, 22),
            0.4, 5.0, width=5
        )

        head_x, head_y = points[-1]
        head_size = self.logo_head_size
        head_rect = pygame.Rect(0, 0, head_size, head_size)
        head_rect.center = (int(head_x), int(head_y))
        if self.logo_head_surface:
            self.screen.blit(self.logo_head_surface, head_rect)
        else:
            draw_fallback_head(self.screen, head_rect)
        pygame.draw.circle(self.screen, CONTORNO_COBRA, head_rect.center, head_size // 2, width=3)

        # chapeuzinho de festa em cima da cabeca
        hat_tip = (head_rect.centerx + 14, head_rect.top - 30)
        hat_left = (head_rect.centerx - 12, head_rect.top + 6)
        hat_right = (head_rect.centerx + 18, head_rect.top + 10)
        pygame.draw.polygon(self.screen, DOURADO, [hat_tip, hat_left, hat_right])
        pygame.draw.polygon(self.screen, CONTORNO_COBRA, [hat_tip, hat_left, hat_right], width=2)
        pygame.draw.circle(self.screen, ESPUMA, hat_tip, 5)

        # oculos escuros caidos sobre a foto, de sacanagem
        lens_w, lens_h = head_size // 3, head_size // 5
        lens_y = head_rect.centery - 6
        left_lens = pygame.Rect(0, 0, lens_w, lens_h)
        left_lens.center = (head_rect.centerx - lens_w // 2 - 4, lens_y)
        right_lens = pygame.Rect(0, 0, lens_w, lens_h)
        right_lens.center = (head_rect.centerx + lens_w // 2 + 4, lens_y)
        pygame.draw.rect(self.screen, PRETO_COBRA, left_lens, border_radius=6)
        pygame.draw.rect(self.screen, PRETO_COBRA, right_lens, border_radius=6)
        pygame.draw.line(self.screen, PRETO_COBRA, left_lens.midright, right_lens.midleft, 3)

        # bochechas coradas, bem de caricatura
        blush_y = head_rect.centery + head_size // 5
        blush_surf = pygame.Surface((head_size, head_size), pygame.SRCALPHA)
        pygame.draw.ellipse(blush_surf, (255, 90, 130, 110), (2, blush_y - head_rect.top - 6, 22, 12))
        pygame.draw.ellipse(blush_surf, (255, 90, 130, 110), (head_size - 24, blush_y - head_rect.top - 6, 22, 12))
        self.screen.blit(blush_surf, head_rect.topleft)

        # linguinha vermelha pra fora, tipo cobra de desenho animado
        tongue_root = (head_rect.right - 6, head_rect.centery + head_size // 4)
        tongue_tip = (tongue_root[0] + 26, tongue_root[1] + 4)
        pygame.draw.line(self.screen, VERMELHO_GAMEOVER, tongue_root, tongue_tip, 4)
        pygame.draw.line(self.screen, VERMELHO_GAMEOVER, tongue_tip, (tongue_tip[0] + 8, tongue_tip[1] - 6), 3)
        pygame.draw.line(self.screen, VERMELHO_GAMEOVER, tongue_tip, (tongue_tip[0] + 8, tongue_tip[1] + 6), 3)

    def draw_sparkles(self):
        for x, y, size in self._sparkles:
            pygame.draw.line(self.screen, DOURADO, (x - size, y), (x + size, y), 2)
            pygame.draw.line(self.screen, DOURADO, (x, y - size), (x, y + size), 2)
            pygame.draw.line(self.screen, DOURADO, (x - size * 0.7, y - size * 0.7), (x + size * 0.7, y + size * 0.7), 2)
            pygame.draw.line(self.screen, DOURADO, (x - size * 0.7, y + size * 0.7), (x + size * 0.7, y - size * 0.7), 2)

    def draw_starburst(self, center, outer_r, inner_r, spikes, color):
        points = []
        for i in range(spikes * 2):
            r = outer_r if i % 2 == 0 else inner_r
            angle = math.pi * i / spikes
            points.append((center[0] + r * math.sin(angle), center[1] - r * math.cos(angle)))
        pygame.draw.polygon(self.screen, color, points)

    def draw_bouncy_title(self, text, center_y):
        letter_surfs = [self.font_title.render(ch, True, DOURADO) for ch in text]
        total_w = sum(s.get_width() for s in letter_surfs) + 2 * (len(text) - 1)
        x = WIDTH // 2 - total_w // 2
        t = pygame.time.get_ticks() / 220.0
        colors = [DOURADO, CREME]
        for i, ch in enumerate(text):
            bounce = int(7 * math.sin(t + i * 0.5))
            color = colors[i % 2] if ch != " " else DOURADO
            shadow = self.font_title.render(ch, True, BORDO_ESCURO)
            glyph = self.font_title.render(ch, True, color)
            y = center_y + bounce
            self.screen.blit(shadow, (x + 3, y + 3))
            self.screen.blit(glyph, (x, y))
            x += glyph.get_width() + 2

    def draw_menu(self):
        self.screen.fill(BORDO)
        pygame.draw.rect(self.screen, CREME, (10, 10, WIDTH - 20, HEIGHT - 20), width=3)

        self.draw_sparkles()
        burst_pulse = 6 * math.sin(pygame.time.get_ticks() / 260.0)
        self.draw_starburst((WIDTH // 2, 182), 140 + burst_pulse, 100 + burst_pulse, 10, BOTAO_HOVER)
        self.draw_logo_snake(WIDTH // 2, 100)
        self.draw_bouncy_title("THE LIFE SNAKE", 180)

        subtitle_surf = self.font_msg.render("Escolha a dificuldade, parceira:", True, CREME)
        self.screen.blit(subtitle_surf, subtitle_surf.get_rect(center=(WIDTH // 2, 225)))

        mouse_pos = pygame.mouse.get_pos()

        self.btn_facil_rect = pygame.Rect(0, 0, 320, 48)
        self.btn_facil_rect.center = (WIDTH // 2, 265)
        self.btn_dificil_rect = pygame.Rect(0, 0, 320, 48)
        self.btn_dificil_rect.center = (WIDTH // 2, 325)

        facil = DIFFICULTIES["facil"]
        dificil = DIFFICULTIES["dificil"]
        self._draw_button(self.btn_facil_rect, f"1 - {facil['label']}: {facil['tagline']}", mouse_pos)
        self._draw_button(self.btn_dificil_rect, f"2 - {dificil['label']}: {dificil['tagline']}", mouse_pos)

        hint1 = self.font_hud.render("Setas / WASD para mover  -  ESC para sair", True, CREME)
        self.screen.blit(hint1, hint1.get_rect(center=(WIDTH // 2, HEIGHT - 40)))

    def _draw_button(self, rect, label, mouse_pos):
        color = BOTAO_HOVER if rect.collidepoint(mouse_pos) else BOTAO_COR
        pygame.draw.rect(self.screen, color, rect, border_radius=8)
        pygame.draw.rect(self.screen, BOTAO_BORDA, rect, width=2, border_radius=8)
        label_surf = self.font_btn.render(label, True, CREME)
        self.screen.blit(label_surf, label_surf.get_rect(center=rect.center))

    # ------------------------------------------------------------------
    # Desenho - jogo
    # ------------------------------------------------------------------
    def draw_board(self):
        self.screen.fill(BORDO)
        pygame.draw.rect(
            self.screen, BORDO_ESCURO,
            (BOARD_LEFT, BOARD_TOP, PLAY_W, PLAY_H)
        )
        pygame.draw.rect(
            self.screen, CREME,
            (BOARD_LEFT, BOARD_TOP, PLAY_W, PLAY_H), width=3
        )

    def cell_rect(self, cx, cy):
        return pygame.Rect(
            BOARD_LEFT + cx * CELL, BOARD_TOP + cy * CELL, CELL, CELL
        )

    def draw_snake(self):
        for i, (cx, cy) in enumerate(reversed(self.snake)):
            rect = self.cell_rect(cx, cy).inflate(-4, -4)
            pygame.draw.rect(self.screen, ROSA_COBRA, rect, border_radius=4)
            pygame.draw.rect(self.screen, ROSA_COBRA_ESCURO, rect, width=2, border_radius=4)

        head_cx, head_cy = self.snake[0]
        head_rect = self.cell_rect(head_cx, head_cy)
        head_rect.inflate_ip(self.head_size - CELL, self.head_size - CELL)
        if self.head_surface:
            self.screen.blit(self.head_surface, head_rect)
        else:
            draw_fallback_head(self.screen, head_rect)

    def draw_food(self):
        """Desenha um baita copo de cerveja (bem maior que a celula) no lugar da comida."""
        fx, fy = self.food
        cx = BOARD_LEFT + fx * CELL + CELL // 2
        cy = BOARD_TOP + fy * CELL + CELL // 2
        w = int(CELL * 1.5)
        h = int(CELL * 1.4)
        top_y = cy - h // 2
        bottom_y = cy + h // 2
        top_half = w // 2
        bottom_half = max(top_half - 3, 3)

        cup_points = [
            (cx - top_half, top_y),
            (cx + top_half, top_y),
            (cx + bottom_half, bottom_y),
            (cx - bottom_half, bottom_y),
        ]
        pygame.draw.polygon(self.screen, AMBAR, cup_points)
        pygame.draw.polygon(self.screen, CREME, cup_points, width=2)

        # alcinha do copo, pra parecer caneca de chopp
        handle_rect = pygame.Rect(cx + top_half - 5, cy - h // 4, 14, h // 2 + 2)
        pygame.draw.arc(self.screen, CREME, handle_rect, -1.3, 1.3, width=3)

        foam_rect = pygame.Rect(0, 0, w + 4, 10)
        foam_rect.center = (cx, top_y)
        pygame.draw.ellipse(self.screen, ESPUMA, foam_rect)
        for bx in (cx - top_half // 2, cx, cx + top_half // 2):
            pygame.draw.circle(self.screen, ESPUMA, (bx, top_y - 4), 3)

    def draw_hud(self):
        y = BOARD_BOTTOM + 20
        score_surf = self.font_hud.render(f"SCORE: {self.score}", True, CREME)
        level_surf = self.font_hud.render(f"NIVEL: {self.level}/{MAX_LEVEL}", True, CREME)
        diff_label = DIFFICULTIES[self.difficulty]["label"]
        diff_surf = self.font_hud.render(diff_label, True, DOURADO)
        self.screen.blit(score_surf, (BOARD_LEFT, y))
        self.screen.blit(diff_surf, diff_surf.get_rect(center=(WIDTH // 2, y + 10)))
        self.screen.blit(level_surf, (BOARD_RIGHT - level_surf.get_width(), y))

    def draw_message_overlay(self, title, subtitle, color):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        self.screen.blit(overlay, (0, 0))

        words = self.message.split(" ")
        lines, current = [], ""
        for word in words:
            test = (current + " " + word).strip()
            if self.font_msg.size(test)[0] > WIDTH - 60:
                lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)

        title_surf = self.font_big.render(title, True, color)
        self.screen.blit(title_surf, title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 90)))

        total_h = len(lines) * 30
        start_y = HEIGHT // 2 - total_h // 2
        for i, line in enumerate(lines):
            line_surf = self.font_msg.render(line, True, CREME)
            self.screen.blit(line_surf, line_surf.get_rect(center=(WIDTH // 2, start_y + i * 30)))

        sub_surf = self.font_hud.render(subtitle, True, DOURADO)
        self.screen.blit(sub_surf, sub_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + total_h // 2 + 50)))

    def draw_message_overlay_gameover(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        self.screen.blit(overlay, (0, 0))
        title_surf = self.font_big.render(GAME_OVER_MESSAGE, True, VERMELHO_GAMEOVER)
        self.screen.blit(title_surf, title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40)))
        info_surf = self.font_msg.render(f"Score: {self.score}  -  Modulo: {self.level}", True, CREME)
        self.screen.blit(info_surf, info_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 15)))
        sub_surf = self.font_hud.render("Pressione R para voltar ao menu", True, CREME)
        self.screen.blit(sub_surf, sub_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 55)))

    def draw(self):
        if self.state == "MENU":
            self.draw_menu()
            pygame.display.flip()
            return

        self.draw_board()
        self.draw_snake()
        self.draw_food()
        self.draw_hud()

        if self.state == "MILESTONE":
            self.draw_message_overlay(f"MODULO {self.level}!", "Pressione ESPACO para continuar", DOURADO)
        elif self.state == "WIN":
            self.draw_message_overlay("VOCE VENCEU!", "Pressione R para voltar ao menu", DOURADO)
        elif self.state == "GAME_OVER":
            self.draw_message_overlay_gameover()

        pygame.display.flip()

    def run(self):
        while True:
            self.handle_input()
            self.update()
            self.draw()
            fps = self.current_fps() if self.state != "MENU" else 30
            self.clock.tick(fps)


if __name__ == "__main__":
    Game().run()
