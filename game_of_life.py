"""
Jeu de la Vie — Conway's Game of Life
======================================
Développé pour le Palais de la découverte.

Dépendances :
    pip install pygame numpy

Lancement :
    python game_of_life.py

Raccourcis clavier :
    ESPACE      Démarrer / Pause  (mode Simulation)
    R           Réinitialiser aléatoirement
    E           Basculer Mode Édition / Simulation
    C           Vider la grille   (mode Édition)
    Clic        Activer / désactiver une cellule  (mode Édition)
    Glisser     Peindre plusieurs cellules         (mode Édition)
"""

import sys
import pygame
import numpy as np

# ─── Paramètres ───────────────────────────────────────────────────────────────

GRID_W, GRID_H    = 100, 100     # Taille de la grille (torique, fixe)
ALIVE_RATIO       = 0.30         # Densité initiale de cellules vivantes
POPULATED_RATIO   = 0.50         # Fraction verticale de la grille peuplée

WIN_W, WIN_H      = 1100, 800    # Taille initiale de la fenêtre

SPEED_STEPS       = [1, 2, 5, 10, 20, 30, 60]
SPEED_DEFAULT_IDX = 3            # 10 ét./s par défaut

# ─── Couleurs ─────────────────────────────────────────────────────────────────

COLOR_BG          = (10,  10,  10)
COLOR_ALIVE       = (80, 200,  80)
COLOR_DEAD        = (22,  22,  22)
COLOR_GRID_LINE   = (35,  35,  35)
COLOR_PANEL       = (18,  18,  18)
COLOR_BORDER      = (50,  50,  50)
COLOR_TEXT        = (220, 220, 220)
COLOR_ACCENT      = (80, 200,  80)
COLOR_MUTED       = (100, 100, 100)
COLOR_BTN         = (32,  32,  32)
COLOR_BTN_HOVER   = (52,  52,  52)
COLOR_EDIT_ACCENT = (210, 150,  40)
COLOR_CURSOR_LIVE = (110, 230, 110)
COLOR_CURSOR_DEAD = (180,  60,  60)

PANEL_W           = 230
PAD               = 14
BTN_H             = 38

# ─── Grille ───────────────────────────────────────────────────────────────────

def make_grid():
    """Initialise la grille : bande supérieure peuplée (30%), bande inférieure vide."""
    grid = np.zeros((GRID_H, GRID_W), dtype=np.uint8)
    populated_rows = int(GRID_H * POPULATED_RATIO)
    grid[:populated_rows, :] = (
        np.random.rand(populated_rows, GRID_W) < ALIVE_RATIO
    ).astype(np.uint8)
    return grid


def step(grid):
    """Calcule la génération suivante selon les règles de Conway (grille torique)."""
    neighbours = (
        np.roll(np.roll(grid, -1, axis=0), -1, axis=1) +
        np.roll(grid, -1, axis=0) +
        np.roll(np.roll(grid, -1, axis=0),  1, axis=1) +
        np.roll(grid,  1, axis=1) +
        np.roll(np.roll(grid,  1, axis=0),  1, axis=1) +
        np.roll(grid,  1, axis=0) +
        np.roll(np.roll(grid,  1, axis=0), -1, axis=1) +
        np.roll(grid, -1, axis=1)
    )
    birth    = (grid == 0) & (neighbours == 3)
    survival = (grid == 1) & ((neighbours == 2) | (neighbours == 3))
    return (birth | survival).astype(np.uint8)

# ─── Rendu ────────────────────────────────────────────────────────────────────

def render_grid(surface, grid, cell_px, gap, edit_mode, hover_cell):
    """
    Dessine la grille entière dans `surface`.
    hover_cell : (col, row) de la cellule survolée en mode édition, ou None.
    """
    surface.fill(COLOR_BG)
    step_px = cell_px + gap

    # Lignes de grille visibles si les cellules sont assez grandes
    if gap > 0:
        sw = surface.get_width()
        sh = surface.get_height()
        for c in range(GRID_W + 1):
            x = c * step_px - gap
            pygame.draw.line(surface, COLOR_GRID_LINE, (x, 0), (x, sh))
        for r in range(GRID_H + 1):
            y = r * step_px - gap
            pygame.draw.line(surface, COLOR_GRID_LINE, (0, y), (sw, y))

    # Cellules vivantes
    for r in range(GRID_H):
        for c in range(GRID_W):
            if grid[r, c]:
                surface.fill(COLOR_ALIVE,
                             (c * step_px, r * step_px, cell_px, cell_px))

    # Indicateur de survol (mode édition uniquement)
    if edit_mode and hover_cell is not None:
        hc, hr = hover_cell
        if 0 <= hc < GRID_W and 0 <= hr < GRID_H:
            outline = COLOR_CURSOR_DEAD if grid[hr, hc] else COLOR_CURSOR_LIVE
            pygame.draw.rect(surface, outline,
                             (hc * step_px, hr * step_px, cell_px, cell_px), 2)

# ─── Widgets ──────────────────────────────────────────────────────────────────

class Button:
    def __init__(self, rect, label, toggle=False, active=False, accent=False):
        self.rect   = pygame.Rect(rect)
        self.label  = label
        self.toggle = toggle
        self.active = active
        self.accent = accent

    def draw(self, surface, font, hovered=False, dimmed=False):
        if self.active and self.toggle:
            color  = (55, 100, 55) if not self.accent else (90, 65, 15)
            border = COLOR_EDIT_ACCENT if self.accent else COLOR_ACCENT
            tcol   = COLOR_EDIT_ACCENT if self.accent else COLOR_TEXT
        elif hovered and not dimmed:
            color, border, tcol = COLOR_BTN_HOVER, COLOR_BORDER, COLOR_TEXT
        else:
            color  = COLOR_BTN
            border = COLOR_BORDER
            tcol   = COLOR_MUTED if dimmed else COLOR_TEXT

        pygame.draw.rect(surface, color,  self.rect, border_radius=6)
        pygame.draw.rect(surface, border, self.rect, 1, border_radius=6)
        txt = font.render(self.label, True, tcol)
        surface.blit(txt, txt.get_rect(center=self.rect.center))

        if dimmed:
            dim = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 110))
            surface.blit(dim, self.rect.topleft)

    def hit(self, pos):
        return self.rect.collidepoint(pos)


class Slider:
    def __init__(self, rect, label, values, idx=0):
        self.rect     = pygame.Rect(rect)
        self.label    = label
        self.values   = values
        self.idx      = idx
        self.dragging = False

    @property
    def value(self):
        return self.values[self.idx]

    def draw(self, surface, font_sm, font_xs, disabled=False):
        accent = COLOR_MUTED if disabled else COLOR_ACCENT
        surface.blit(font_xs.render(self.label, True, COLOR_MUTED),
                     (self.rect.x, self.rect.y - 18))
        val = font_sm.render(str(self.value), True, accent)
        surface.blit(val, (self.rect.right - val.get_width(), self.rect.y - 18))

        track_y = self.rect.centery
        pygame.draw.line(surface, COLOR_BORDER,
                         (self.rect.x, track_y), (self.rect.right, track_y), 2)
        t      = self.idx / max(1, len(self.values) - 1)
        fill_x = self.rect.x + int(t * self.rect.width)
        pygame.draw.line(surface, accent,
                         (self.rect.x, track_y), (fill_x, track_y), 2)
        pygame.draw.circle(surface, accent,      (fill_x, track_y), 7)
        pygame.draw.circle(surface, COLOR_PANEL, (fill_x, track_y), 4)

        if disabled:
            dim = pygame.Surface((self.rect.w + 4, 32), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 100))
            surface.blit(dim, (self.rect.x - 2, self.rect.y - 8))

    def handle_event(self, event, disabled=False):
        if disabled:
            self.dragging = False
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.inflate(0, 24).collidepoint(event.pos):
                self.dragging = True
                self._set_from_x(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._set_from_x(event.pos[0])
            return True
        return False

    def _set_from_x(self, x):
        t = (x - self.rect.x) / self.rect.width
        self.idx = round(max(0.0, min(1.0, t)) * (len(self.values) - 1))

# ─── Application ──────────────────────────────────────────────────────────────

def make_ui():
    x = PAD
    y = PAD + 36
    w = PANEL_W - 2 * PAD

    btn_edit  = Button((x, y, w, BTN_H), "✏  Mode Édition",  toggle=True, accent=True)
    y += BTN_H + 6
    btn_clear = Button((x, y, w, BTN_H), "✕  Vider la grille")
    y += BTN_H + 14

    btn_reset = Button((x, y, w, BTN_H), "⟳  Initialiser (aléatoire)")
    y += BTN_H + 8
    btn_play  = Button((x, y, w, BTN_H), "▶  Démarrer", toggle=True)
    y += BTN_H + 32

    spd_slider = Slider((x, y + 18, w, 16), "Vitesse (ét./s)",
                        SPEED_STEPS, SPEED_DEFAULT_IDX)
    return btn_edit, btn_clear, btn_reset, btn_play, spd_slider


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
    pygame.display.set_caption("Jeu de la Vie — Conway")
    clock = pygame.time.Clock()

    font_md = pygame.font.SysFont("DejaVu Sans", 13, bold=True)
    font_sm = pygame.font.SysFont("DejaVu Sans", 12)
    font_xs = pygame.font.SysFont("DejaVu Sans", 10)

    # ── État ────────────────────────────────────────────────────────────────
    grid       = make_grid()
    generation = 0
    running    = False
    edit_mode  = False
    draw_value = None        # Valeur fixée au premier clic (0 ou 1)

    last_step_time = 0.0

    btn_edit, btn_clear, btn_reset, btn_play, spd_slider = make_ui()

    def toggle_play():
        nonlocal running
        running = not running
        btn_play.active = running
        btn_play.label  = "⏸  Pause" if running else "▶  Démarrer"

    def toggle_edit():
        nonlocal edit_mode, running
        edit_mode = not edit_mode
        btn_edit.active = edit_mode
        if edit_mode:
            running = False
            btn_play.active = False
            btn_play.label  = "▶  Démarrer"

    def reset_alea():
        nonlocal grid, generation, running
        grid = make_grid(); generation = 0; running = False
        btn_play.active = False; btn_play.label = "▶  Démarrer"

    # ── Boucle principale ───────────────────────────────────────────────────
    while True:
        now  = pygame.time.get_ticks() / 1000.0
        W, H = screen.get_size()
        view_w = W - PANEL_W

        # Taille de cellule calculée automatiquement pour remplir la zone
        cell_px = max(1, min(view_w // GRID_W, H // GRID_H))
        gap     = 1 if cell_px >= 5 else 0
        step_px = cell_px + gap
        grid_px_w = GRID_W * step_px - gap
        grid_px_h = GRID_H * step_px - gap

        # Centrage de la grille dans la zone de simulation
        off_x = PANEL_W + (view_w - grid_px_w) // 2
        off_y = (H - grid_px_h) // 2

        mouse_pos = pygame.mouse.get_pos()
        in_grid   = (off_x <= mouse_pos[0] < off_x + grid_px_w and
                     off_y <= mouse_pos[1] < off_y + grid_px_h)

        # Cellule survolée (coordonnées grille)
        hover_cell = None
        if in_grid:
            hc = (mouse_pos[0] - off_x) // step_px
            hr = (mouse_pos[1] - off_y) // step_px
            if 0 <= hc < GRID_W and 0 <= hr < GRID_H:
                hover_cell = (int(hc), int(hr))

        # ── Événements ──────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            spd_slider.handle_event(event, disabled=running or edit_mode)

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and not edit_mode:
                    toggle_play()
                elif event.key == pygame.K_r:
                    reset_alea()
                elif event.key == pygame.K_e:
                    toggle_edit()
                elif event.key == pygame.K_c and edit_mode:
                    grid[:] = 0

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if edit_mode and hover_cell is not None:
                    hc, hr     = hover_cell
                    draw_value = 1 - int(grid[hr, hc])
                    grid[hr, hc] = draw_value
                elif btn_edit.hit(mouse_pos):
                    toggle_edit()
                elif btn_clear.hit(mouse_pos) and edit_mode:
                    grid[:] = 0
                elif btn_reset.hit(mouse_pos):
                    reset_alea()
                elif btn_play.hit(mouse_pos) and not edit_mode:
                    toggle_play()

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                draw_value = None

            elif event.type == pygame.MOUSEMOTION:
                if draw_value is not None and edit_mode and hover_cell is not None:
                    hc, hr = hover_cell
                    grid[hr, hc] = draw_value

        # ── Avance de la simulation ─────────────────────────────────────────
        if running and not edit_mode:
            if now - last_step_time >= 1.0 / spd_slider.value:
                grid = step(grid)
                generation += 1
                last_step_time = now

        # ── Dessin ──────────────────────────────────────────────────────────
        screen.fill(COLOR_PANEL)

        sim_surf = pygame.Surface((grid_px_w, grid_px_h))
        render_grid(sim_surf, grid, cell_px, gap, edit_mode, hover_cell)
        screen.blit(sim_surf, (off_x, off_y))

        # Bordure de la grille
        border_col = COLOR_EDIT_ACCENT if edit_mode else COLOR_BORDER
        pygame.draw.rect(screen, border_col,
                         (off_x - 1, off_y - 1, grid_px_w + 2, grid_px_h + 2), 1)

        # Séparateur panneau
        pygame.draw.line(screen, COLOR_BORDER, (PANEL_W, 0), (PANEL_W, H), 1)

        # ── Panneau gauche ───────────────────────────────────────────────────
        panel = screen.subsurface(pygame.Rect(0, 0, PANEL_W, H))

        title_col = COLOR_EDIT_ACCENT if edit_mode else COLOR_ACCENT
        panel.blit(font_md.render("JEU DE LA VIE", True, title_col), (PAD, PAD))
        panel.blit(font_xs.render("Conway  ·  1970", True, COLOR_MUTED), (PAD, PAD + 17))

        mp = mouse_pos
        btn_edit.draw(panel,  font_sm, btn_edit.rect.collidepoint(mp))
        btn_clear.draw(panel, font_sm,
                       btn_clear.rect.collidepoint(mp) and edit_mode,
                       dimmed=not edit_mode)
        btn_reset.draw(panel, font_sm, btn_reset.rect.collidepoint(mp))
        btn_play.draw(panel,  font_sm,
                      btn_play.rect.collidepoint(mp) and not edit_mode,
                      dimmed=edit_mode)

        spd_slider.draw(panel, font_sm, font_xs, disabled=running or edit_mode)

        _draw_info(panel, font_sm, font_xs, generation, int(grid.sum()), edit_mode, H)

        # Indicateur de mode
        mode_lbl = "● MODE ÉDITION" if edit_mode else "● SIMULATION"
        mode_col = COLOR_EDIT_ACCENT if edit_mode else COLOR_ACCENT
        ms = font_xs.render(mode_lbl, True, mode_col)
        panel.blit(ms, (PAD, H - PAD - ms.get_height()))

        pygame.display.flip()
        clock.tick(120)


def _draw_info(surface, font_sm, font_xs, generation, alive, edit_mode, panel_h):
    lines = [
        ("Génération", f"{generation:,}"),
        ("Cellules",   f"{alive:,}"),
        ("Grille",     f"{GRID_W} × {GRID_H}"),
    ]
    if edit_mode:
        helps    = ["Clic       Activer/désactiver",
                    "Glisser    Peindre",
                    "C          Vider la grille",
                    "E          Quitter édition"]
        help_col = COLOR_EDIT_ACCENT
    else:
        helps    = ["ESPACE     Démarrer / Pause",
                    "R          Réinitialiser",
                    "E          Mode Édition"]
        help_col = COLOR_MUTED

    total_h = len(lines) * 22 + 12 + len(helps) * 16 + 30
    y = panel_h - PAD - total_h - 20

    for label, value in lines:
        surface.blit(font_xs.render(label, True, COLOR_MUTED), (PAD, y))
        v = font_sm.render(value, True, COLOR_TEXT)
        surface.blit(v, (PANEL_W - PAD - v.get_width(), y))
        y += 22

    y += 12
    for h in helps:
        surface.blit(font_xs.render(h, True, help_col), (PAD, y))
        y += 16


if __name__ == "__main__":
    main()