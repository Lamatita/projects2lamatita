import pygame
import random
import sys
import math

# --- Init ---
pygame.init()
WIDTH, HEIGHT = 900, 650
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pierre · Papier · Ciseaux")
clock = pygame.time.Clock()

# --- Couleurs ---
BG_DARK      = (15, 12, 30)
BG_CARD      = (28, 24, 52)
ACCENT_BLUE  = (80, 120, 255)
ACCENT_PINK  = (255, 80, 160)
ACCENT_CYAN  = (60, 220, 200)
WHITE        = (240, 235, 255)
GRAY         = (120, 110, 150)
WIN_COLOR    = (60, 220, 140)
LOSE_COLOR   = (255, 80, 100)
DRAW_COLOR   = (200, 180, 80)
HOVER_GLOW   = (255, 255, 255, 30)

# --- Polices ---
font_title  = pygame.font.SysFont("segoeuisemibold", 52, bold=True)
font_big    = pygame.font.SysFont("segoeuisemibold", 72)
font_med    = pygame.font.SysFont("segoeui", 32)
font_small  = pygame.font.SysFont("segoeui", 22)
font_score  = pygame.font.SysFont("segoeuisemibold", 28, bold=True)

# --- Emojis / Symboles en texte ---
CHOICES = ["Pierre", "Papier", "Ciseaux"]
EMOJIS  = ["🪨", "📄", "✂️"]
SYMBOLS = ["●", "▬", "✂"]   # fallback si emoji KO

# --- Logique du jeu ---
def get_winner(player, computer):
    if player == computer:
        return "draw"
    wins = {("Pierre", "Ciseaux"), ("Papier", "Pierre"), ("Ciseaux", "Papier")}
    return "player" if (player, computer) in wins else "computer"

# --- Dessin d'une carte choix ---
def draw_choice_card(surface, label, emoji, x, y, w, h, hovered, selected, color):
    radius = 18
    # Ombre portée
    shadow = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 80), shadow.get_rect(), border_radius=radius)
    surface.blit(shadow, (x - 4, y + 6))

    # Fond carte
    card = pygame.Surface((w, h), pygame.SRCALPHA)
    base_col = (38, 32, 72) if not selected else tuple(min(c + 40, 255) for c in color)
    pygame.draw.rect(card, (*base_col, 230), card.get_rect(), border_radius=radius)
    surface.blit(card, (x, y))

    # Bordure colorée
    border_col = color if (hovered or selected) else (60, 55, 100)
    border_w   = 3 if (hovered or selected) else 1
    pygame.draw.rect(surface, border_col, (x, y, w, h), border_w, border_radius=radius)

    # Halo si hovered
    if hovered:
        glow = pygame.Surface((w + 20, h + 20), pygame.SRCALPHA)
        pygame.draw.rect(glow, (*color, 30), glow.get_rect(), border_radius=radius + 6)
        surface.blit(glow, (x - 10, y - 10))

    # Emoji / symbole
    em_surf = font_big.render(emoji, True, WHITE)
    em_rect = em_surf.get_rect(center=(x + w // 2, y + h // 2 - 18))
    surface.blit(em_surf, em_rect)

    # Label
    lbl = font_med.render(label, True, color if (hovered or selected) else GRAY)
    surface.blit(lbl, lbl.get_rect(center=(x + w // 2, y + h - 36)))

# --- Barre de score ---
def draw_score_bar(surface, score_p, score_c, total):
    bar_x, bar_y, bar_w, bar_h = 180, 110, 540, 14
    pygame.draw.rect(surface, (40, 35, 70), (bar_x, bar_y, bar_w, bar_h), border_radius=7)
    if total > 0:
        p_w = int(bar_w * score_p / total)
        c_w = int(bar_w * score_c / total)
        pygame.draw.rect(surface, WIN_COLOR,  (bar_x, bar_y, p_w, bar_h), border_radius=7)
        pygame.draw.rect(surface, LOSE_COLOR, (bar_x + bar_w - c_w, bar_y, c_w, bar_h), border_radius=7)

# --- Animation particules ---
class Particle:
    def __init__(self, x, y, color):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(2, 7)
        self.x, self.y = x, y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed - 2
        self.color = color
        self.life = random.randint(30, 60)
        self.max_life = self.life
        self.size = random.randint(3, 7)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.15
        self.life -= 1

    def draw(self, surface):
        alpha = int(255 * self.life / self.max_life)
        s = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (self.size, self.size), self.size)
        surface.blit(s, (int(self.x) - self.size, int(self.y) - self.size))

# --- État du jeu ---
state = {
    "score_p": 0,
    "score_c": 0,
    "total":   0,
    "player_choice":   None,
    "computer_choice": None,
    "result":          None,   # "player", "computer", "draw"
    "phase": "choose",         # "choose" | "reveal"
    "reveal_timer": 0,
    "particles": [],
    "hovered": None,
}

CARD_W, CARD_H = 200, 220
CARD_Y = 290
CARD_POSITIONS = [
    (WIDTH // 2 - 320, CARD_Y),
    (WIDTH // 2 - 100, CARD_Y),
    (WIDTH // 2 + 120, CARD_Y),
]
CARD_COLORS = [ACCENT_BLUE, ACCENT_CYAN, ACCENT_PINK]

def spawn_particles(x, y, color, n=40):
    for _ in range(n):
        state["particles"].append(Particle(x, y, color))

def handle_choice(idx):
    state["player_choice"]   = CHOICES[idx]
    state["computer_choice"] = random.choice(CHOICES)
    state["result"]          = get_winner(state["player_choice"], state["computer_choice"])
    if state["result"] == "player":
        state["score_p"] += 1
        spawn_particles(WIDTH // 2, HEIGHT // 2, WIN_COLOR)
    elif state["result"] == "computer":
        state["score_c"] += 1
        spawn_particles(WIDTH // 2, HEIGHT // 2, LOSE_COLOR)
    else:
        spawn_particles(WIDTH // 2, HEIGHT // 2, DRAW_COLOR)
    state["total"]       += 1
    state["phase"]        = "reveal"
    state["reveal_timer"] = 0

def reset():
    state["player_choice"]   = None
    state["computer_choice"] = None
    state["result"]          = None
    state["phase"]           = "choose"
    state["reveal_timer"]    = 0

# --- Boucle principale ---
running = True
while running:
    dt = clock.tick(60)
    mx, my = pygame.mouse.get_pos()

    # --- Événements ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if state["phase"] == "choose":
                for i, (cx, cy) in enumerate(CARD_POSITIONS):
                    if cx <= mx <= cx + CARD_W and cy <= my <= cy + CARD_H:
                        handle_choice(i)
            elif state["phase"] == "reveal" and state["reveal_timer"] > 90:
                # Clic sur "Rejouer"
                btn_x, btn_y, btn_w, btn_h = WIDTH // 2 - 110, 570, 220, 50
                if btn_x <= mx <= btn_x + btn_w and btn_y <= my <= btn_y + btn_h:
                    reset()

        if event.type == pygame.KEYDOWN:
            if state["phase"] == "choose":
                if event.key == pygame.K_1: handle_choice(0)
                if event.key == pygame.K_2: handle_choice(1)
                if event.key == pygame.K_3: handle_choice(2)
            elif state["phase"] == "reveal" and state["reveal_timer"] > 90:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    reset()

    # --- Détection hover ---
    state["hovered"] = None
    if state["phase"] == "choose":
        for i, (cx, cy) in enumerate(CARD_POSITIONS):
            if cx <= mx <= cx + CARD_W and cy <= my <= cy + CARD_H:
                state["hovered"] = i

    # --- Timer reveal ---
    if state["phase"] == "reveal":
        state["reveal_timer"] += 1

    # --- Particules ---
    state["particles"] = [p for p in state["particles"] if p.life > 0]
    for p in state["particles"]:
        p.update()

    # =================== DESSIN ===================
    screen.fill(BG_DARK)

    # Grille décorative en fond
    for gx in range(0, WIDTH, 60):
        pygame.draw.line(screen, (30, 26, 55), (gx, 0), (gx, HEIGHT))
    for gy in range(0, HEIGHT, 60):
        pygame.draw.line(screen, (30, 26, 55), (0, gy), (WIDTH, gy))

    # --- Titre ---
    title = font_title.render("Pierre · Papier · Ciseaux", True, WHITE)
    screen.blit(title, title.get_rect(center=(WIDTH // 2, 52)))

    # --- Scores ---
    sc_p = font_score.render(f"Toi  {state['score_p']}", True, WIN_COLOR)
    sc_c = font_score.render(f"{state['score_c']}  Ordi", True, LOSE_COLOR)
    screen.blit(sc_p, (80, 95))
    screen.blit(sc_c, (WIDTH - 80 - sc_c.get_width(), 95))
    draw_score_bar(screen, state["score_p"], state["score_c"], max(state["total"], 1))

    # --- Particules ---
    for p in state["particles"]:
        p.draw(screen)

    # ---- Phase CHOISIR ----
    if state["phase"] == "choose":
        hint = font_small.render("Choisis ton coup  (ou touches 1 · 2 · 3)", True, GRAY)
        screen.blit(hint, hint.get_rect(center=(WIDTH // 2, 175)))

        for i, (cx, cy) in enumerate(CARD_POSITIONS):
            draw_choice_card(
                screen, CHOICES[i], EMOJIS[i],
                cx, cy, CARD_W, CARD_H,
                hovered=(state["hovered"] == i),
                selected=False,
                color=CARD_COLORS[i]
            )

    # ---- Phase RÉSULTAT ----
    elif state["phase"] == "reveal":
        t = min(state["reveal_timer"] / 60, 1.0)   # 0 → 1 en 1 s

        # Cartes joueur & ordi
        pi = CHOICES.index(state["player_choice"])
        ci = CHOICES.index(state["computer_choice"])

        # Joueur (gauche)
        draw_choice_card(
            screen, state["player_choice"], EMOJIS[pi],
            80, CARD_Y, CARD_W, CARD_H,
            hovered=False, selected=True,
            color=CARD_COLORS[pi]
        )
        lbl_p = font_small.render("TOI", True, WIN_COLOR)
        screen.blit(lbl_p, lbl_p.get_rect(center=(80 + CARD_W // 2, CARD_Y - 24)))

        # Ordi (droite)
        draw_choice_card(
            screen, state["computer_choice"], EMOJIS[ci],
            WIDTH - 80 - CARD_W, CARD_Y, CARD_W, CARD_H,
            hovered=False, selected=True,
            color=CARD_COLORS[ci]
        )
        lbl_c = font_small.render("ORDI", True, LOSE_COLOR)
        screen.blit(lbl_c, lbl_c.get_rect(center=(WIDTH - 80 - CARD_W // 2, CARD_Y - 24)))

        # Résultat central (apparition progressive)
        if state["reveal_timer"] > 30:
            if state["result"] == "player":
                res_text, res_col = "TU GAGNES !", WIN_COLOR
            elif state["result"] == "computer":
                res_text, res_col = "L'ORDI GAGNE…", LOSE_COLOR
            else:
                res_text, res_col = "ÉGALITÉ !", DRAW_COLOR

            alpha = min(int(255 * (state["reveal_timer"] - 30) / 30), 255)
            res_surf = font_title.render(res_text, True, res_col)
            res_surf.set_alpha(alpha)
            screen.blit(res_surf, res_surf.get_rect(center=(WIDTH // 2, 200)))

            vs = font_med.render("VS", True, GRAY)
            screen.blit(vs, vs.get_rect(center=(WIDTH // 2, CARD_Y + CARD_H // 2)))

        # Bouton Rejouer
        if state["reveal_timer"] > 90:
            btn_x, btn_y, btn_w, btn_h = WIDTH // 2 - 110, 570, 220, 50
            btn_hov = btn_x <= mx <= btn_x + btn_w and btn_y <= my <= btn_y + btn_h
            pygame.draw.rect(screen, ACCENT_BLUE if btn_hov else (50, 45, 90),
                             (btn_x, btn_y, btn_w, btn_h), border_radius=12)
            pygame.draw.rect(screen, ACCENT_BLUE, (btn_x, btn_y, btn_w, btn_h), 2, border_radius=12)
            play_txt = font_med.render("▶  Rejouer", True, WHITE)
            screen.blit(play_txt, play_txt.get_rect(center=(btn_x + btn_w // 2, btn_y + btn_h // 2)))

            hint2 = font_small.render("ou Entrée / Espace", True, GRAY)
            screen.blit(hint2, hint2.get_rect(center=(WIDTH // 2, 632)))

    pygame.display.flip()

pygame.quit()
sys.exit()
