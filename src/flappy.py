import asyncio
import sys
from typing import Optional

import pygame
from pygame.locals import K_ESCAPE, K_SPACE, K_UP, KEYDOWN, QUIT

from .arduino import ARDUINO_JUMP_EVENT, ArduinoController
from .entities import (
    Background,
    Floor,
    GameOver,
    Pipes,
    Player,
    PlayerMode,
    Score,
    WelcomeMessage,
)
from .utils import GameConfig, Images, Sounds, Window


class Flappy:
    def __init__(self, port: Optional[str] = None):
        pygame.init()
        pygame.display.set_caption("Flappy Bird (Arduino Touch & Keyboard)")
        window = Window(288, 512)
        screen = pygame.display.set_mode((window.width, window.height))
        images = Images()

        self.config = GameConfig(
            screen=screen,
            clock=pygame.time.Clock(),
            fps=30,
            window=window,
            images=images,
            sounds=Sounds(),
        )

        # Initialize Arduino touch controller (non-blocking thread)
        self.arduino = ArduinoController(port=port)
        self.arduino.start()

        # Status font
        try:
            if not pygame.font.get_init():
                pygame.font.init()
            self.status_font = pygame.font.SysFont("Segoe UI", 11)
        except Exception:
            self.status_font = None

    async def start(self):
        try:
            while True:
                self.background = Background(self.config)
                self.floor = Floor(self.config)
                self.player = Player(self.config)
                self.welcome_message = WelcomeMessage(self.config)
                self.game_over_message = GameOver(self.config)
                self.pipes = Pipes(self.config)
                self.score = Score(self.config)
                await self.splash()
                await self.play()
                await self.game_over()
        finally:
            if hasattr(self, "arduino") and self.arduino:
                self.arduino.stop()

    async def splash(self):
        """Shows welcome splash screen animation of flappy bird."""
        self.player.set_mode(PlayerMode.SHM)

        while True:
            for event in pygame.event.get():
                self.check_quit_event(event)
                if self.is_tap_event(event):
                    return

            # Check direct jump queue from Arduino bridge
            if self.arduino.get_jump():
                return

            self.background.tick()
            self.floor.tick()
            self.player.tick()
            self.welcome_message.tick()

            # Render connection indicator on the welcome screen
            self.draw_arduino_status()

            pygame.display.update()
            await asyncio.sleep(0)
            self.config.tick()

    def check_quit_event(self, event):
        if event.type == QUIT or (
            event.type == KEYDOWN and event.key == K_ESCAPE
        ):
            if hasattr(self, "arduino") and self.arduino:
                self.arduino.stop()
            pygame.quit()
            sys.exit()

    def is_tap_event(self, event):
        m_left, _, _ = pygame.mouse.get_pressed()
        space_or_up = event.type == KEYDOWN and (
            event.key == K_SPACE or event.key == K_UP
        )
        screen_tap = event.type == pygame.FINGERDOWN
        arduino_event = event.type == ARDUINO_JUMP_EVENT
        return m_left or space_or_up or screen_tap or arduino_event

    def draw_arduino_status(self):
        """Displays a clean status banner at the bottom of the splash screen."""
        if not self.status_font:
            return

        try:
            if self.arduino and self.arduino.is_connected:
                status_text = f"Touch: {self.arduino.port} (Ready)"
                dot_color = (46, 204, 113)  # Bright Green
            else:
                status_text = "Touch: Disconnected (Using Keys)"
                dot_color = (241, 196, 15)  # Soft Gold / Amber

            text_surf = self.status_font.render(status_text, True, (255, 255, 255))
            shadow_surf = self.status_font.render(status_text, True, (0, 0, 0))

            y_pos = self.config.window.height - 20
            # Small colored status dot
            pygame.draw.circle(self.config.screen, (0, 0, 0), (15, y_pos + 6), 5)
            pygame.draw.circle(self.config.screen, dot_color, (15, y_pos + 6), 4)

            self.config.screen.blit(shadow_surf, (26, y_pos + 1))
            self.config.screen.blit(text_surf, (25, y_pos))
        except Exception:
            pass

    async def play(self):
        self.score.reset()
        self.player.set_mode(PlayerMode.NORMAL)

        while True:
            if self.player.collided(self.pipes, self.floor):
                return

            for i, pipe in enumerate(self.pipes.upper):
                if self.player.crossed(pipe):
                    self.score.add()

            for event in pygame.event.get():
                self.check_quit_event(event)
                if self.is_tap_event(event):
                    self.player.flap()

            # Poll Arduino bridge queue
            if self.arduino.get_jump():
                self.player.flap()

            self.background.tick()
            self.floor.tick()
            self.pipes.tick()
            self.score.tick()
            self.player.tick()

            pygame.display.update()
            await asyncio.sleep(0)
            self.config.tick()

    async def game_over(self):
        """Crashes the player down and shows game over screen."""
        self.player.set_mode(PlayerMode.CRASH)
        self.pipes.stop()
        self.floor.stop()

        while True:
            restart = False
            for event in pygame.event.get():
                self.check_quit_event(event)
                if self.is_tap_event(event):
                    restart = True

            if self.arduino.get_jump():
                restart = True

            if restart and (self.player.y + self.player.h >= self.floor.y - 1):
                return

            self.background.tick()
            self.floor.tick()
            self.pipes.tick()
            self.score.tick()
            self.player.tick()
            self.game_over_message.tick()

            self.config.tick()
            pygame.display.update()
            await asyncio.sleep(0)
