#!/usr/bin/env python3
import pygame
import random
import time
import sys
import math
import traceback
import os
import subprocess
import asyncio

# Auto-install dependencies check
def ensure_library(lib_name, import_name=None):
    if import_name is None:
        import_name = lib_name
    try:
        __import__(import_name)
    except ImportError:
        print(f"Bibliothèque {lib_name} manquante. Tentative d'installation...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib_name])
            print(f"{lib_name} installée avec succès.")
        except Exception as e:
            print(f"Erreur lors de l'installation de {lib_name}: {e}")

# Check for required non-standard libraries
ensure_library("imageio")
ensure_library("numpy")
ensure_library("pygame")

import imageio.v3 as iio
import numpy as np
VIDEO_AVAILABLE = True


# --- Constants ---
SCREEN_WIDTH = 900
SCREEN_HEIGHT = 700
GREEN_FELT_COLOR = (53, 101, 77) # #35654d
CARD_BACK_COLOR = (65, 105, 225) # Royal Blue
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GOLD = (255, 215, 0)

CARD_WIDTH = 71
CARD_HEIGHT = 96
MARGIN = 20
VERTICAL_SPACING = 25

SUITS = {
    'Hearts': ('♥', RED),
    'Diamonds': ('♦', RED),
    'Clubs': ('♣', BLACK),
    'Spades': ('♠', BLACK)
}
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
RANK_VALUES = {r: i+1 for i, r in enumerate(RANKS)}

RULES_TEXT = [
    "RÈGLES DU JEU - Le Solitaire (Klondike)",
    "Objectif du jeu",
    "Le but est de reconstituer les 4 piles de fondation (♥ ♦ ♣ ♠),",
    "en ordre croissant de l'As au Roi.",
    "Déroulement du jeu",
    "- Colonnes : ordre décroissant (Roi à As), couleurs alternées (R/N).",
    "- On peut déplacer une carte ou une suite ordonnée.",
    "- Une case vide ne peut accueillir qu'un Roi.",
    "- Pioche : retournez les cartes pour les jouer.",
    "- Fondations : par couleur, de l'As au Roi.",
    "Fin de la partie",
    "Gagné quand les 4 fondations sont complètes.",
    "Perdu si aucun mouvement n'est possible."
]

def log_error(msg):
    with open("game_errors.log", "a") as f:
        f.write(f"{time.ctime()}: {msg}\n")
    print(msg)

class Card:
    FONT_SMALL = None
    FONT_LARGE = None

    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.color = SUITS[suit][1]
        self.symbol = SUITS[suit][0]
        self.face_up = False
        self.rect = pygame.Rect(0, 0, CARD_WIDTH, CARD_HEIGHT)
        self.dragging = False

    def get_fonts(self):
        if Card.FONT_SMALL is None:
            try:
                Card.FONT_SMALL = pygame.font.SysFont('Arial', 18, bold=True)
                Card.FONT_LARGE = pygame.font.SysFont('Arial', 48)
            except:
                # Fallback if font init fails
                Card.FONT_SMALL = pygame.font.Font(None, 18)
                Card.FONT_LARGE = pygame.font.Font(None, 48)
        return Card.FONT_SMALL, Card.FONT_LARGE

    def draw(self, surface, x, y):
        self.rect.topleft = (x, y)
        
        # Shadow
        pygame.draw.rect(surface, (0,0,0,50), (x+2, y+2, CARD_WIDTH, CARD_HEIGHT), border_radius=5)

        if self.face_up:
            pygame.draw.rect(surface, WHITE, (x, y, CARD_WIDTH, CARD_HEIGHT), border_radius=5)
            pygame.draw.rect(surface, BLACK, (x, y, CARD_WIDTH, CARD_HEIGHT), 1, border_radius=5)
            
            f_small, f_large = self.get_fonts()
            
            # Rank Top-Left
            text_surf = f_small.render(f"{self.rank}", True, self.color)
            surface.blit(text_surf, (x + 5, y + 5))
            
            # Symbol Top-Left
            try:
                sym_surf = f_small.render(self.symbol, True, self.color)
                surface.blit(sym_surf, (x + 5, y + 25))
            except:
                pygame.draw.circle(surface, self.color, (x+10, y+35), 5)

            # Center Symbol
            try:
                center_surf = f_large.render(self.symbol, True, self.color)
                cx, cy = x + CARD_WIDTH//2 - center_surf.get_width()//2, y + CARD_HEIGHT//2 - center_surf.get_height()//2
                surface.blit(center_surf, (cx, cy))
            except:
                pygame.draw.circle(surface, self.color, (x + CARD_WIDTH//2, y + CARD_HEIGHT//2), 15)
                
        else:
            pygame.draw.rect(surface, CARD_BACK_COLOR, (x, y, CARD_WIDTH, CARD_HEIGHT), border_radius=5)
            pygame.draw.line(surface, WHITE, (x, y), (x+CARD_WIDTH, y+CARD_HEIGHT), 1)
            pygame.draw.line(surface, WHITE, (x+CARD_WIDTH, y), (x, y+CARD_HEIGHT), 1)
            pygame.draw.rect(surface, WHITE, (x, y, CARD_WIDTH, CARD_HEIGHT), 1, border_radius=5)

class CardAnimation:
    def __init__(self, cards, start_pos, target_pos, duration, on_complete):
        self.cards = cards
        self.start_pos = start_pos
        self.target_pos = target_pos
        self.start_time = time.time()
        self.duration = duration
        self.on_complete = on_complete
        self.finished = False

    def update(self):
        now = time.time()
        progress = (now - self.start_time) / self.duration
        if progress >= 1.0:
            progress = 1.0
            self.finished = True
        
        # Ease Out Cubic
        t = 1 - (1 - progress) ** 3
        
        sx, sy = self.start_pos
        tx, ty = self.target_pos
        
        curr_x = sx + (tx - sx) * t
        curr_y = sy + (ty - sy) * t
        
        for i, card in enumerate(self.cards):
            card.rect.topleft = (curr_x, curr_y + i * VERTICAL_SPACING)

class Konami:
    SEQUENCE = [
        pygame.K_UP, pygame.K_UP,
        pygame.K_DOWN, pygame.K_DOWN,
        pygame.K_LEFT, pygame.K_RIGHT,
        pygame.K_LEFT, pygame.K_RIGHT,
        pygame.K_b, pygame.K_a
    ]

    def __init__(self, game):
        self.game = game
        self.progress = 0
        self.video_path = "attached_assets/chèvre_1770762071299.mp4"
        self.reader = None
        self.frame_iter = None
        self.audio_path = "/tmp/konami_audio.mp3"
        self.audio_prepared = False

    def check_input(self, key):
        if key == self.SEQUENCE[self.progress]:
            self.progress += 1
            if self.progress == len(self.SEQUENCE):
                self.trigger()
                self.progress = 0
        else:
            self.progress = 0
            if key == self.SEQUENCE[0]:
                self.progress = 1

    def trigger(self):
        self.game.game_state = "KONAMI_EGG"
        self.prepare_media()
        
        if VIDEO_AVAILABLE:
            try:
                self.reader = iio.imap(self.video_path)
                self.frame_iter = iter(self.reader)
            except Exception as e:
                log_error(f"Video init error: {e}")

        try:
             if not pygame.mixer.get_init():
                 pygame.mixer.init()
             pygame.mixer.music.set_volume(1.0)
             if os.path.exists(self.audio_path):
                 pygame.mixer.music.load(self.audio_path)
                 pygame.mixer.music.play()
        except Exception as e:
             log_error(f"Audio error: {e}")

    def prepare_media(self):
        if self.audio_prepared: return
        try:
            if not os.path.exists(self.audio_path) and os.path.exists(self.video_path):
                # Try to check if ffmpeg is available before running
                import subprocess
                try:
                    subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    log_error("ffmpeg not found, skipping audio extraction")
                    return

                # Extract audio using ffmpeg
                cmd = [
                    "ffmpeg", "-y", "-i", self.video_path,
                    "-vn", "-acodec", "libmp3lame", "-q:a", "2",
                    self.audio_path
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.audio_prepared = True
        except Exception as e:
            log_error(f"FFmpeg error: {e}")

    def update_and_draw(self, screen):
        if self.frame_iter and VIDEO_AVAILABLE:
            try:
                frame = next(self.frame_iter)
                # frame is (H, W, 3). Pygame wants (W, H, 3).
                surf = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
                surf = pygame.transform.scale(surf, (SCREEN_WIDTH, SCREEN_HEIGHT))
                screen.blit(surf, (0, 0))
            except StopIteration:
                self.frame_iter = iter(self.reader)
            except Exception as e:
                pass
        elif self.game.game_state == "KONAMI_EGG" and not VIDEO_AVAILABLE:
            # Fallback (should not happen if install works)
            screen.fill((0, 0, 0)) 
            font = pygame.font.Font(None, 40)
            text = font.render("Erreur: Vidéo impossible à lire (libs manquantes)", True, (255, 0, 0))
            screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, SCREEN_HEIGHT//2))

class SolitaireGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Solitaire Python")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Arial', 16)
        
        self.reset_game_state()
        
        self.timer_mode = "CHRONO"
        self.last_mouse_move = time.time()
        self.is_paused = False
        self.elapsed_time = 0
        self.start_time = 0
        self.game_state = "WELCOME"
        
        self.ripples = []
        self.shaking_cards = {}
        self.animations = []
        
        # Safe Drag Init
        self.dragging_cards = []
        self.drag_offset = (0, 0)
        self.drag_source = None
        self.drag_start_pos = (0, 0)
        
        self.konami = Konami(self)
        self.rules_surface = None
        self.rules_scroll_y = 0
        self.prev_game_state = "WELCOME"
        self.prev_paused_state = False
        self.fullscreen = False
        self.hint_mode = False
        self.last_play_time = time.time()

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    
    def toggle_rules(self):
        print("Toggling rules...")
        if self.game_state == "RULES":
            self.game_state = self.prev_game_state
            self.is_paused = self.prev_paused_state
            self.rules_surface = None
            print(f"Rules closed. State: {self.game_state}")
        else:
            self.prev_game_state = self.game_state
            self.prev_paused_state = self.is_paused
            self.game_state = "RULES"
            self.is_paused = True
            self.rules_scroll_y = 0
            
            try:
                # Create blurred background
                surf = pygame.display.get_surface().copy()
                # Scale down and up for fast blur effect
                small_surf = pygame.transform.smoothscale(surf, (SCREEN_WIDTH // 10, SCREEN_HEIGHT // 10))
                self.rules_surface = pygame.transform.smoothscale(small_surf, (SCREEN_WIDTH, SCREEN_HEIGHT))
            except Exception as e:
                print(f"Blur failed: {e}")
                self.rules_surface = None
            print("Rules opened.")

    def reset_game_state(self):
        self.deck = [Card(r, s) for s in SUITS for r in RANKS]
        random.shuffle(self.deck)
        
        self.piles = [[] for _ in range(7)]
        self.foundations = {s: [] for s in SUITS}
        self.stock = []
        self.waste = []
        self.animations = []
        self.score = 0
        
        for i in range(7):
            for j in range(i + 1):
                if self.deck:
                    card = self.deck.pop()
                    if j == i: card.face_up = True
                    self.piles[i].append(card)
        self.stock = self.deck[:]
        self.deck = []

    def update_animations(self):
        active_animations = []
        for anim in self.animations:
            anim.update()
            if anim.finished:
                anim.on_complete(anim.cards)
            else:
                active_animations.append(anim)
        self.animations = active_animations

    def animate_move(self, cards, target, source=None):
        if source is None:
            if not self.drag_source: return
            source = self.drag_source
            
        src_type, src_id = source[0], source[1] if len(source)>1 else None
        
        if src_type == 'waste':
            if not self.waste or self.waste[-1] != cards[0]: return
            self.waste.pop()
        elif src_type == 'foundation':
            if not self.foundations[src_id] or self.foundations[src_id][-1] != cards[0]: return
            self.foundations[src_id].pop()
        elif src_type == 'pile':
            if cards[0] not in self.piles[src_id]: return 
            idx = self.piles[src_id].index(cards[0])
            del self.piles[src_id][idx:]
            if self.piles[src_id]: self.piles[src_id][-1].face_up = True

        tgt_type, tgt_id = target[0], target[1]
        target_x, target_y = 0, 0
        
        if tgt_type == 'foundation':
            suit_idx = list(SUITS.keys()).index(tgt_id)
            target_x = SCREEN_WIDTH - MARGIN - (4 - suit_idx) * (CARD_WIDTH + MARGIN)
            target_y = MARGIN + 60
        elif tgt_type == 'pile':
            target_x = MARGIN + tgt_id * (CARD_WIDTH + MARGIN)
            current_len = len(self.piles[tgt_id])
            target_y = MARGIN + 60 + CARD_HEIGHT + MARGIN + current_len * VERTICAL_SPACING
            
        def on_complete(moved_cards):
            if tgt_type == 'foundation':
                self.foundations[tgt_id].extend(moved_cards)
                fx = SCREEN_WIDTH - MARGIN - (4 - list(SUITS.keys()).index(tgt_id)) * (CARD_WIDTH + MARGIN)
                fy = MARGIN + 60
                self.add_ripple(fx + CARD_WIDTH//2, fy + CARD_HEIGHT//2)
            elif tgt_type == 'pile':
                self.piles[tgt_id].extend(moved_cards)

        start_pos = (cards[0].rect.x, cards[0].rect.y)
        self.animations.append(CardAnimation(cards, start_pos, (target_x, target_y), 0.2, on_complete))

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                self.toggle_fullscreen()
            self.konami.check_input(event.key)

        if event.type == pygame.MOUSEWHEEL:
             if self.game_state == "RULES":
                 scroll_speed = 30  # Increased scroll speed
                 self.rules_scroll_y += event.y * scroll_speed
                 if self.rules_scroll_y > 0: self.rules_scroll_y = 0
                 
                 # Calculate limit based on text size (approx 30px per line)
                 total_h = len(RULES_TEXT) * 30 + 300 # Added MUCH more padding at bottom
                 # Panel height is 500, usable text area approx 440
                 min_scroll = min(0, 440 - total_h)
                 if self.rules_scroll_y < min_scroll: self.rules_scroll_y = min_scroll

        if event.type == pygame.MOUSEMOTION:
            self.last_mouse_move = time.time()
            if self.hint_mode:
                ht = self.get_hint_target()
                if ht:
                    t_rect = ht.rect if isinstance(ht, Card) else ht
                    if t_rect.collidepoint(event.pos):
                        self.last_play_time = time.time()
            if self.dragging_cards:
                x, y = event.pos
                dx, dy = self.drag_offset
                for i, card in enumerate(self.dragging_cards):
                    card.rect.topleft = (x + dx, y + dy + i * VERTICAL_SPACING)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.last_play_time = time.time()
                self.on_click(event.pos)

        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.on_release(event.pos)

    def on_click(self, pos):
        x, y = pos

        # Check for Hint button click
        if 560 <= x <= 640 and 20 <= y <= 50:
             self.hint_mode = not self.hint_mode
             self.last_play_time = time.time()
             return

        # Check for Rules button click (updated position)
        if 650 <= x <= 750 and 20 <= y <= 50:
             print("Button Rules clicked!")
             self.toggle_rules()
             return

        # Check for Fullscreen button click
        if 760 <= x <= 790 and 20 <= y <= 50:
             self.toggle_fullscreen()
             return

        if self.game_state == "RULES":
             # Click anywhere to close rules
             self.toggle_rules()
             return
        
        if self.game_state == "WELCOME":
            if 300 <= x <= 600 and 310 <= y <= 390:
                self.game_state = "PLAYING"
                self.start_time = time.time()
                self.elapsed_time = 0
                return
            cx, cy = 450, 430
            if cx - 60 <= x <= cx + 60 and cy - 15 <= y <= cy + 15:
                self.timer_mode = "FLEMME" if self.timer_mode == "CHRONO" else "CHRONO"
            return
            
        if self.game_state == "VICTORY":
             cx, cy = 450, 450
             if cx - 100 <= x <= cx + 100 and cy <= y <= cy + 50:
                 self.reset_game_state()
                 self.game_state = "WELCOME"
             return

        if self.game_state == "DEFEAT":
             cx, cy = 450, 450
             if cx - 100 <= x <= cx + 100 and cy <= y <= cy + 50:
                 self.reset_game_state()
                 self.game_state = "WELCOME"
             return

        if 20 <= x <= 140 and 20 <= y <= 50:
            self.timer_mode = "FLEMME" if self.timer_mode == "CHRONO" else "CHRONO"
            return
        if 160 <= x <= 280 and 20 <= y <= 50:
            self.reset_game_state()
            self.game_state = "WELCOME"
            return
        if self.can_auto_win() and self.game_state == "PLAYING":
             if 350 <= x <= 550 and 20 <= y <= 50:
                 self.game_state = "AUTO_WIN"
                 return

        if MARGIN <= x <= MARGIN + CARD_WIDTH and MARGIN + 60 <= y <= MARGIN + 60 + CARD_HEIGHT:
            if self.stock:
                card = self.stock.pop()
                card.face_up = True
                self.waste.append(card)
            elif self.waste:
                self.stock = list(reversed(self.waste))
                self.waste = []
                for c in self.stock: c.face_up = False
            return

        wx = MARGIN + CARD_WIDTH + MARGIN
        wy = MARGIN + 60
        if self.waste and wx <= x <= wx + CARD_WIDTH and wy <= y <= wy + CARD_HEIGHT:
            self.start_drag([self.waste[-1]], (x, y), ('waste',))
            return

        start_y = MARGIN + 60 + CARD_HEIGHT + MARGIN
        for i, pile in enumerate(self.piles):
            px = MARGIN + i * (CARD_WIDTH + MARGIN)
            for j in range(len(pile)-1, -1, -1):
                card = pile[j]
                cy_pos = start_y + j * VERTICAL_SPACING
                visible_h = CARD_HEIGHT if j == len(pile)-1 else VERTICAL_SPACING
                if px <= x <= px + CARD_WIDTH and cy_pos <= y <= cy_pos + visible_h:
                    if card.face_up:
                        self.start_drag(pile[j:], (x, y), ('pile', i))
                    return
        
        for i, suit in enumerate(SUITS):
            fx = SCREEN_WIDTH - MARGIN - (4 - i) * (CARD_WIDTH + MARGIN)
            fy = MARGIN + 60
            if fx <= x <= fx + CARD_WIDTH and fy <= y <= fy + CARD_HEIGHT:
                if self.foundations[suit]:
                    self.start_drag([self.foundations[suit][-1]], (x, y), ('foundation', suit))
                return

    def start_drag(self, cards, mouse_pos, source):
        self.dragging_cards = cards
        self.drag_source = source
        self.drag_start_pos = mouse_pos
        cx, cy = mouse_pos
        self.drag_offset = (cards[0].rect.x - cx, cards[0].rect.y - cy)

    def check_defeat(self):
        # 1. Check if stock is empty and waste is empty
        if self.stock or self.waste:
            # If there are cards in stock or waste, we can still draw/recycle
            # BUT: if we cycle through the deck without any moves, it's a defeat.
            # Detecting infinite loop without moves is hard. 
            # Simplified rule: Defeat only if NO moves are possible from anywhere
            # AND we cannot draw any new cards (which implies stock is empty).
            # But wait, we can recycle waste to stock.
            # So "defeat" in this flexible version is hard to reach unless we track "no moves after full deck cycle".
            # Let's check for available moves on board first.
            pass

        # Check moves from piles to foundation
        for i, pile in enumerate(self.piles):
            if pile:
                card = pile[-1]
                if self.is_valid_foundation_move(card, card.suit):
                    return False
        
        # Check moves from piles to piles
        for i, pile in enumerate(self.piles):
            if not pile: continue
            # Try to move any face-up card from this pile
            for j in range(len(pile)):
                if not pile[j].face_up: continue
                card = pile[j]
                
                # Try to move to other piles
                for k, target_pile in enumerate(self.piles):
                    if i == k: continue
                    target_card = target_pile[-1] if target_pile else None
                    if self.is_valid_tableau_move(card, target_card):
                        return False
        
        # Check moves from waste to foundation/piles
        if self.waste:
            card = self.waste[-1]
            if self.is_valid_foundation_move(card, card.suit):
                return False
            for i, pile in enumerate(self.piles):
                target_card = pile[-1] if pile else None
                if self.is_valid_tableau_move(card, target_card):
                    return False

        # If stock is not empty, we can still play (potentially)
        if self.stock:
             return False
        
        # If waste is not empty, we can recycle... UNLESS we already cycled through it without moves.
        # For simplicity in this request: If stock is empty AND no moves from waste/tableau, 
        # AND we can't move anything after a full cycle... 
        # Actually, standard solitaire allows infinite recycling. 
        # So "defeat" is strictly: Stock Empty AND Waste Empty AND No moves on board.
        # OR: Stock Empty, Waste Not Empty, but we cycled through all waste cards and found no moves.
        # Implementing "No moves possible even with recycling" requires tracking state.
        
        # Let's implement a simpler "No visible moves" check.
        # If Stock is empty AND no moves from Waste top card AND no moves from Tableau.
        # This is "stuck" state if we can't draw more useful cards.
        
        # To be safe and avoid false positives with recycling:
        # We will trigger DEFEAT only if Stock is Empty AND Waste is Empty (rare) 
        # OR if the user manually gives up? No the user asked for "when we cannot play anymore".
        
        # Correct Logic for "No more moves":
        # 1. Can we move any card from Tableau -> Foundation?
        # 2. Can we move any card from Tableau -> Tableau?
        # 3. Can we move from Waste -> Foundation?
        # 4. Can we move from Waste -> Tableau?
        # 5. Can we Draw from Stock? (Always yes if stock > 0)
        # 6. Can we Recycle Waste -> Stock? (Always yes if waste > 0)
        
        # If infinite recycling is allowed, "defeat" is only theoretical (you can always flip cards).
        # But if you flip through the whole deck and can't move anything, you are stuck.
        # We need to detect "Full cycle with zero moves".
        
        # Let's add a "moves_since_last_cycle" counter or similar?
        # Too complex for single file maybe?
        
        # Alternative: Just check if Stock is Empty. 
        # If Stock is Empty, and we have cards in Waste, we can recycle. 
        # So really, we are only TRULY stuck if Stock is Empty AND Waste is Empty AND no tableau moves.
        # But usually we get stuck with cards in Waste that can't be placed.
        
        # Let's add a simplified check: 
        # If we have gone through the stock (stock empty) and we can't play the top waste card, 
        # and we can't play any tableau card... we might be stuck.
        # But we could recycle waste.
        
        # Let's try to detect if we are truly stuck. 
        # If stock is empty, we only have Waste and Tableau.
        # If we can't move Waste->Board/Foundation, and can't move Tableau->Board/Foundation...
        # AND recycling waste won't help? Recycling just reverses order.
        
        # Actually, let's stick to the user request: "when we cannot play anymore".
        # If I can click the deck to recycle, I can technically "play".
        # But if I do that 100 times and nothing changes...
        
        # Let's implement:
        # Defeat if:
        # 1. Stock is empty.
        # 2. No move possible from Waste -> Foundation/Tableau.
        # 3. No move possible from Tableau -> Foundation/Tableau.
        # 4. (Crucial) AND... we can't get new cards from waste recycling?
        # If waste has cards, we can recycle. But if none of the cards in waste can be played?
        # Checking ALL cards in waste is the way.
        
        if self.stock: return False # Can still draw
        
        # Check if ANY card in waste can be played?
        # No, only the top card of waste is accessible at a time.
        # But if we recycle, all cards in waste eventually become top card.
        # So, if ANY card in current Waste (treated as a set) can be moved to Foundation or Tableau, we are NOT stuck.
        
        for w_card in self.waste:
            if self.is_valid_foundation_move(w_card, w_card.suit):
                return False
            for i, pile in enumerate(self.piles):
                target_card = pile[-1] if pile else None
                if self.is_valid_tableau_move(w_card, target_card):
                    return False
        
        return True # Stock empty, and NO card in waste can be played anywhere, and (checked above) no tableau moves.

    def on_release(self, pos):
        if not self.dragging_cards: return
        
        x, y = pos
        sx, sy = self.drag_start_pos
        lead_card = self.dragging_cards[0]
        
        if math.hypot(x - sx, y - sy) < 5:
            try:
                self.handle_auto_move(self.dragging_cards)
            except Exception as e:
                log_error(f"Auto move error: {e}")
            
            self.dragging_cards = []
            self.drag_source = None
            if self.check_victory():
                self.game_state = "VICTORY"
            return

        moved = False
        
        fy = MARGIN + 60
        if fy <= y <= fy + CARD_HEIGHT + 20:
             for i, suit in enumerate(SUITS):
                fx = SCREEN_WIDTH - MARGIN - (4 - i) * (CARD_WIDTH + MARGIN)
                if fx - 20 <= x <= fx + CARD_WIDTH + 20:
                    if len(self.dragging_cards) == 1:
                        if self.is_valid_foundation_move(lead_card, suit):
                            self.animate_move(self.dragging_cards, ('foundation', suit))
                            self.score += 10
                            moved = True
                    break
        
        if not moved:
            start_y = MARGIN + 60 + CARD_HEIGHT + MARGIN
            for i in range(7):
                px = MARGIN + i * (CARD_WIDTH + MARGIN)
                if px - 20 <= x <= px + CARD_WIDTH + 20:
                     target_card = self.piles[i][-1] if self.piles[i] else None
                     if self.is_valid_tableau_move(lead_card, target_card):
                         self.animate_move(self.dragging_cards, ('pile', i))
                         if self.drag_source[0] != 'pile': self.score += 5
                         moved = True
                     break
        
        self.dragging_cards = []
        self.drag_source = None
        
        if self.check_victory():
            self.game_state = "VICTORY"
        elif self.check_defeat():
            self.game_state = "DEFEAT"

    def handle_auto_move(self, cards):
        if not cards: return
        lead_card = cards[0]
        
        if len(cards) == 1:
            if self.is_valid_foundation_move(lead_card, lead_card.suit):
                self.animate_move(cards, ('foundation', lead_card.suit))
                self.score += 10
                return

        for i in range(7):
            target_card = self.piles[i][-1] if self.piles[i] else None
            if self.is_valid_tableau_move(lead_card, target_card):
                self.animate_move(cards, ('pile', i))
                if self.drag_source and self.drag_source[0] != 'pile': self.score += 5
                return

        self.trigger_shake(cards)

    def trigger_shake(self, cards):
        t = time.time()
        for c in cards:
            self.shaking_cards[c] = t

    def is_valid_foundation_move(self, card, suit):
        if card.suit != suit: return False
        target = self.foundations[suit]
        rank_val = RANK_VALUES[card.rank]
        if not target: return rank_val == 1
        return rank_val == RANK_VALUES[target[-1].rank] + 1

    def is_valid_tableau_move(self, card, target_card):
        if not target_card: return card.rank == 'K'
        if card.color == target_card.color: return False
        return RANK_VALUES[card.rank] == RANK_VALUES[target_card.rank] - 1

    def can_auto_win(self):
        for p in self.piles:
            for c in p:
                if not c.face_up: return False
        return True

    def check_victory(self):
        return sum(len(f) for f in self.foundations.values()) == 52

    def check_defeat(self):
        # 1. Check moves from piles to foundation or piles
        for i, pile in enumerate(self.piles):
            if not pile: continue
            
            # Check top card for foundation move
            card = pile[-1]
            if self.is_valid_foundation_move(card, card.suit):
                return False
            
            # Check all face-up cards for tableau moves
            for j in range(len(pile)):
                if not pile[j].face_up: continue
                card = pile[j]
                
                # Try to move to other piles
                for k, target_pile in enumerate(self.piles):
                    if i == k: continue
                    target_card = target_pile[-1] if target_pile else None
                    if self.is_valid_tableau_move(card, target_card):
                        return False
        
        # 2. Check if we can draw from stock
        if self.stock: 
            return False

        # 3. Check if any card in waste can be played (since we can recycle waste)
        # If stock is empty, we can recycle waste. So effectively we can access ANY card in waste eventually.
        # If ANY card in waste can be moved to board or foundation, we are not stuck.
        for w_card in self.waste:
            # Check move to foundation
            if self.is_valid_foundation_move(w_card, w_card.suit):
                return False
            
            # Check move to tableau
            for i, pile in enumerate(self.piles):
                target_card = pile[-1] if pile else None
                if self.is_valid_tableau_move(w_card, target_card):
                    return False
        
        # If we get here: Stock is empty, No moves on board, No useful cards in waste.
        return True

    def get_hint_target(self):
        # 1. Foundation moves
        if self.waste:
            card = self.waste[-1]
            if self.is_valid_foundation_move(card, card.suit): return card
        for pile in self.piles:
            if pile:
                card = pile[-1]
                if self.is_valid_foundation_move(card, card.suit): return card

        # 2. Waste to Tableau
        if self.waste:
            card = self.waste[-1]
            for pile in self.piles:
                if self.is_valid_tableau_move(card, pile[-1] if pile else None): return card
        
        # 3. Tableau to Tableau (Useful: reveals a hidden card)
        for i, pile in enumerate(self.piles):
            for j, card in enumerate(pile):
                if not card.face_up: continue
                for k, target_pile in enumerate(self.piles):
                    if i == k: continue
                    target = target_pile[-1] if target_pile else None
                    if self.is_valid_tableau_move(card, target):
                        if j > 0 and not pile[j-1].face_up:
                            return card
                            
        # 4. Tableau to Tableau (Useless: doesn't reveal anything, just moving duplicates)
        for i, pile in enumerate(self.piles):
            for j, card in enumerate(pile):
                if not card.face_up: continue
                for k, target_pile in enumerate(self.piles):
                    if i == k: continue
                    target = target_pile[-1] if target_pile else None
                    if self.is_valid_tableau_move(card, target):
                        # Skip moving King to empty if it's already the only card in its pile
                        if card.rank == 'K' and not target and j == 0:
                            continue
                        return card
                        
        # 5. Draw from stock
        if self.stock:
            return self.stock[-1]
            
        # 6. Recycle waste
        if self.waste and not self.stock:
            return pygame.Rect(MARGIN, MARGIN + 60, CARD_WIDTH, CARD_HEIGHT)
            
        return None

    def auto_win_step(self):
        for i in range(7):
            if self.piles[i]:
                card = self.piles[i][-1]
                if self.is_valid_foundation_move(card, card.suit):
                    self.animate_move([card], ('foundation', card.suit), source=('pile', i))
                    return

        if self.waste:
            card = self.waste[-1]
            if self.is_valid_foundation_move(card, card.suit):
                self.animate_move([card], ('foundation', card.suit), source=('waste',))
                return

        if self.stock:
            card = self.stock.pop()
            card.face_up = True
            self.waste.append(card)
        elif self.waste:
            self.stock = list(reversed(self.waste))
            self.waste = []
            for c in self.stock: c.face_up = False

    def draw(self):
        self.screen.fill(GREEN_FELT_COLOR)
        
        sw_color = (76, 175, 80) if self.timer_mode == "CHRONO" else (255, 152, 0)
        pygame.draw.rect(self.screen, sw_color, (20, 20, 120, 30), border_radius=15)
        pygame.draw.circle(self.screen, WHITE, (125 if self.timer_mode == "CHRONO" else 35, 35), 12)
        txt = self.font.render(self.timer_mode, True, WHITE)
        self.screen.blit(txt, (20 + (120 - txt.get_width()) // 2, 20 + (30 - txt.get_height()) // 2))
        
        pygame.draw.rect(self.screen, WHITE, (160, 20, 120, 30), border_radius=5)
        ng_txt = self.font.render("Nouvelle Partie", True, BLACK)
        self.screen.blit(ng_txt, (160 + (120 - ng_txt.get_width()) // 2, 20 + (30 - ng_txt.get_height()) // 2))
        
        if self.can_auto_win() and self.game_state == "PLAYING":
            pygame.draw.rect(self.screen, GOLD, (350, 20, 200, 30), border_radius=5)
            atxt = self.font.render("✨ Finir Automatiquement ✨", True, BLACK)
            self.screen.blit(atxt, (350 + (200 - atxt.get_width()) // 2, 20 + (30 - atxt.get_height()) // 2))

        st_txt = self.font.render("Règles", True, WHITE)
        pygame.draw.rect(self.screen, (70, 130, 180), (650, 20, 100, 30), border_radius=5) # SteelBlue
        self.screen.blit(st_txt, (650 + (100 - st_txt.get_width()) // 2, 20 + (30 - st_txt.get_height()) // 2))

        # Hint Button
        hx = 560
        hy = 20
        pygame.draw.rect(self.screen, (200, 150, 0) if self.hint_mode else (100, 100, 100), (hx, hy, 80, 30), border_radius=5)
        h_txt = self.font.render("Indices", True, BLACK if self.hint_mode else WHITE)
        self.screen.blit(h_txt, (hx + (80 - h_txt.get_width()) // 2, hy + (30 - h_txt.get_height()) // 2))

        # Fullscreen Button (Icon style)
        fs_color = (100, 100, 100)
        pygame.draw.rect(self.screen, fs_color, (760, 20, 30, 30), border_radius=5)
        # Draw expand icon
        pygame.draw.lines(self.screen, WHITE, False, [(765, 25), (770, 25)], 2)
        pygame.draw.lines(self.screen, WHITE, False, [(765, 25), (765, 30)], 2)
        pygame.draw.lines(self.screen, WHITE, False, [(785, 45), (780, 45)], 2)
        pygame.draw.lines(self.screen, WHITE, False, [(785, 45), (785, 40)], 2)
        # Draw diagonals
        pygame.draw.line(self.screen, WHITE, (765, 25), (785, 45), 2)
        
        if not self.is_paused and (self.game_state == "PLAYING" or self.game_state == "KONAMI_EGG"):
             mins, secs = divmod(int(self.elapsed_time), 60)
             t_txt = self.font.render(f"Temps: {mins:02}:{secs:02}", True, WHITE)
             self.screen.blit(t_txt, (800, 25))
        elif self.is_paused:
             t_txt = self.font.render("PAUSE", True, GOLD)
             self.screen.blit(t_txt, (800, 25))

        top_y = MARGIN + 60
        
        pygame.draw.rect(self.screen, WHITE, (MARGIN, top_y, CARD_WIDTH, CARD_HEIGHT), 2, border_radius=5)
        if self.stock:
            self.stock[-1].draw(self.screen, MARGIN, top_y)
        else:
            pygame.draw.circle(self.screen, WHITE, (MARGIN + CARD_WIDTH//2, top_y + CARD_HEIGHT//2), 15, 2)

        pygame.draw.rect(self.screen, WHITE, (MARGIN + CARD_WIDTH + MARGIN, top_y, CARD_WIDTH, CARD_HEIGHT), 2, border_radius=5)
        if self.waste and (not self.dragging_cards or self.drag_source[0] != 'waste'):
            self.draw_shakable_card(self.waste[-1], MARGIN + CARD_WIDTH + MARGIN, top_y)

        for i, suit in enumerate(SUITS):
            x = SCREEN_WIDTH - MARGIN - (4 - i) * (CARD_WIDTH + MARGIN)
            pygame.draw.rect(self.screen, WHITE, (x, top_y, CARD_WIDTH, CARD_HEIGHT), 2, border_radius=5)
            if not self.foundations[suit] or (self.dragging_cards and self.drag_source == ('foundation', suit)):
                font_l = pygame.font.Font(None, 40)
                t = font_l.render(SUITS[suit][0], True, (0, 100, 0))
                self.screen.blit(t, (x + 20, top_y + 30))
            if self.foundations[suit] and (not self.dragging_cards or self.drag_source != ('foundation', suit)):
                self.draw_shakable_card(self.foundations[suit][-1], x, top_y)

        pile_y = top_y + CARD_HEIGHT + MARGIN
        for i, pile in enumerate(self.piles):
            x = MARGIN + i * (CARD_WIDTH + MARGIN)
            pygame.draw.rect(self.screen, (255,255,255,50), (x, pile_y, CARD_WIDTH, CARD_HEIGHT), 2, border_radius=5)
            y = pile_y
            for card in pile:
                if self.dragging_cards and card in self.dragging_cards: continue
                self.draw_shakable_card(card, x, y)
                y += VERTICAL_SPACING

        if self.dragging_cards:
            for i, card in enumerate(self.dragging_cards):
                card.draw(self.screen, card.rect.x, card.rect.y)

        for anim in self.animations:
            for card in anim.cards:
                card.draw(self.screen, card.rect.x, card.rect.y)

        # Glow effect
        if self.hint_mode and not self.dragging_cards and self.game_state == "PLAYING" and not self.animations:
            idle_time = time.time() - self.last_play_time
            if idle_time > 5:
                ht = self.get_hint_target()
                if ht:
                    intensity = min(250, int((idle_time - 5) * 30))
                    dark_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                    dark_overlay.fill((0, 0, 0, intensity))
                    self.screen.blit(dark_overlay, (0, 0))
                    
                    t_rect = ht.rect if isinstance(ht, Card) else ht
                    glow_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                    max_glow_size = min(200, int((idle_time - 5) * 15))
                    if max_glow_size > 2:
                        for i in range(2, max_glow_size, 4):
                            alpha = max(0, 200 - (i * 200 // max_glow_size))
                            g_rect = t_rect.inflate(i, i)
                            pygame.draw.rect(glow_surface, (255, 215, 0, alpha), g_rect, border_radius=10)
                    self.screen.blit(glow_surface, (0, 0))
                    
                    if isinstance(ht, Card):
                        ht.draw(self.screen, t_rect.x, t_rect.y)
                    else:
                        pygame.draw.rect(self.screen, (255, 215, 0), t_rect, 3, border_radius=5)

        new_ripples = []
        for x, y, r, alpha in self.ripples:
            if alpha > 0:
                s = pygame.Surface((2*r, 2*r), pygame.SRCALPHA)
                pygame.draw.circle(s, (255, 255, 255, alpha), (r, r), r, 2)
                self.screen.blit(s, (x - r, y - r))
                new_ripples.append((x, y, r + 2, alpha - 5))
        self.ripples = new_ripples

        if self.game_state == "WELCOME":
            s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            s.set_alpha(180)
            s.fill(BLACK)
            self.screen.blit(s, (0,0))
            
            pygame.draw.rect(self.screen, WHITE, (300, 310, 300, 80), border_radius=10)
            t = self.font.render("Commencez cette partie", True, BLACK)
            t = pygame.transform.scale(t, (int(t.get_width()*1.5), int(t.get_height()*1.5)))
            self.screen.blit(t, (300 + (300 - t.get_width()) // 2, 310 + (80 - t.get_height()) // 2))
            
            cx, cy = 450, 430
            sw_color = (76, 175, 80) if self.timer_mode == "CHRONO" else (255, 152, 0)
            pygame.draw.rect(self.screen, sw_color, (cx - 60, cy - 15, 120, 30), border_radius=15)
            pygame.draw.circle(self.screen, WHITE, (cx + 45 if self.timer_mode == "CHRONO" else cx - 45, cy), 12)
            
            t_f = self.font.render("Flemme", True, WHITE)
            t_c = self.font.render("Chrono", True, WHITE)
            self.screen.blit(t_f, (cx - 120, cy - 10))
            self.screen.blit(t_c, (cx + 70, cy - 10))

        if self.game_state == "RULES":
            if self.rules_surface:
                self.screen.blit(self.rules_surface, (0, 0))
            else:
                 s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                 s.set_alpha(180)
                 s.fill(BLACK)
                 self.screen.blit(s, (0,0))

            # Draw Rules Panel
            panel_w, panel_h = 600, 500
            panel_x = (SCREEN_WIDTH - panel_w) // 2
            panel_y = (SCREEN_HEIGHT - panel_h) // 2
            
            pygame.draw.rect(self.screen, WHITE, (panel_x, panel_y, panel_w, panel_h), border_radius=15)
            pygame.draw.rect(self.screen, BLACK, (panel_x, panel_y, panel_w, panel_h), 2, border_radius=15)
            
            # Title
            title_font = pygame.font.SysFont('Arial', 24, bold=True)
            body_font = pygame.font.SysFont('Arial', 18)
            
            # Text Clipping area
            text_rect = pygame.Rect(panel_x + 20, panel_y + 20, panel_w - 40, panel_h - 60)
            old_clip = self.screen.get_clip()
            self.screen.set_clip(text_rect)
            
            y_offset = panel_y + 30 + self.rules_scroll_y
            
            for line in RULES_TEXT:
                if line.startswith("RÈGLES") or line.startswith("1.") or line.startswith("2.") or line.startswith("3.") or line.startswith("4."):
                    f = title_font
                    col = (0, 0, 139) # DarkBlue
                else:
                    f = body_font
                    col = BLACK
                
                txt_surf = f.render(line, True, col)
                # Draw the text (clipping will handle visibility)
                self.screen.blit(txt_surf, (panel_x + 40, y_offset))
                y_offset += 30
            
            self.screen.set_clip(old_clip)

            close_txt = self.font.render("(Cliquer pour fermer)", True, (100, 100, 100))
            self.screen.blit(close_txt, (SCREEN_WIDTH//2 - close_txt.get_width()//2, panel_y + panel_h - 40))

        if self.game_state == "VICTORY":
            s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            s.set_alpha(200)
            s.fill(BLACK)
            self.screen.blit(s, (0,0))
            
            t = pygame.font.Font(None, 80).render("GAGNÉ !", True, GOLD)
            self.screen.blit(t, (SCREEN_WIDTH//2 - t.get_width()//2, 250))
            
            mins, secs = divmod(int(self.elapsed_time), 60)
            st = pygame.font.Font(None, 40).render(f"Temps final: {mins:02}:{secs:02}", True, WHITE)
            self.screen.blit(st, (SCREEN_WIDTH//2 - st.get_width()//2, 350))
            
            pygame.draw.rect(self.screen, WHITE, (350, 450, 200, 50), border_radius=10)
            rt = self.font.render("Nouvelle Partie", True, BLACK)
            self.screen.blit(rt, (350 + (200 - rt.get_width()) // 2, 450 + (50 - rt.get_height()) // 2))

        if self.game_state == "DEFEAT":
            s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            s.set_alpha(200)
            s.fill(BLACK)
            self.screen.blit(s, (0,0))
            
            t = pygame.font.Font(None, 80).render("PERDU...", True, RED)
            self.screen.blit(t, (SCREEN_WIDTH//2 - t.get_width()//2, 250))
            
            st = pygame.font.Font(None, 40).render("Plus aucun mouvement possible", True, WHITE)
            self.screen.blit(st, (SCREEN_WIDTH//2 - st.get_width()//2, 350))
            
            pygame.draw.rect(self.screen, WHITE, (350, 450, 200, 50), border_radius=10)
            rt = self.font.render("Recommencer", True, BLACK)
            self.screen.blit(rt, (350 + (200 - rt.get_width()) // 2, 450 + (50 - rt.get_height()) // 2))
            
        if self.game_state == "KONAMI_EGG":
             self.konami.update_and_draw(self.screen)

    def draw_shakable_card(self, card, x, y):
        offset_x = 0
        if card in self.shaking_cards:
            elapsed = time.time() - self.shaking_cards[card]
            if elapsed > 0.4:
                del self.shaking_cards[card]
            else:
                offset_x = int(math.sin(elapsed * 30) * 5)
        card.draw(self.screen, x + offset_x, y)

    def add_ripple(self, x, y):
        self.ripples.append((x, y, 10, 255))

    async def run(self):
        last_time = time.time()
        try:
            while True:
                dt = time.time() - last_time
                last_time = time.time()
                
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                    self.handle_input(event)

                if (self.game_state == "PLAYING" or self.game_state == "KONAMI_EGG") and not self.is_paused:
                    self.elapsed_time += dt
                
                if self.game_state == "PLAYING" and self.timer_mode == "FLEMME":
                    if time.time() - self.last_mouse_move > 2.0:
                        self.is_paused = True
                    else:
                        self.is_paused = False
                
                self.update_animations()

                if self.game_state == "AUTO_WIN":
                    self.auto_win_step()
                    if self.check_victory():
                        self.game_state = "VICTORY"

                self.draw()
                pygame.display.flip()
                self.clock.tick(60)
                await asyncio.sleep(0) # Required for pygbag
        except Exception as e:
            log_error(f"CRASH: {e}")
            traceback.print_exc()
            pygame.quit()
            sys.exit()

async def main():
    game = SolitaireGame()
    await game.run()

if __name__ == "__main__":
    asyncio.run(main())
