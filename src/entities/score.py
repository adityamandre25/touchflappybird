import json
import os
import pygame

from ..utils import GameConfig
from .entity import Entity


class Score(Entity):
    def __init__(self, config: GameConfig) -> None:
        super().__init__(config)
        self.y = self.config.window.height * 0.1
        self.score = 0

        # High score persistence in a local 'data' folder
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.save_dir = os.path.join(root_dir, "data")
        self.save_file = os.path.join(self.save_dir, "highscore.json")
        self.high_score = self.load_high_score()
        self.font = None
        try:
            if pygame.font and not pygame.font.get_init():
                pygame.font.init()
            self.font = pygame.font.SysFont("Verdana", 14, bold=True)
        except Exception:
            self.font = None

    def load_high_score(self) -> int:
        """Loads locally saved high score, returning 0 if not present."""
        try:
            if os.path.exists(self.save_file):
                with open(self.save_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return int(data.get("high_score", 0))
        except Exception:
            pass
        return 0

    def save_high_score(self) -> None:
        """Saves current high score to local json file."""
        try:
            os.makedirs(self.save_dir, exist_ok=True)
            with open(self.save_file, "w", encoding="utf-8") as f:
                json.dump({"high_score": self.high_score}, f)
        except Exception:
            pass

    def reset(self) -> None:
        self.score = 0

    def add(self) -> None:
        self.score += 1
        if self.score > self.high_score:
            self.high_score = self.score
            self.save_high_score()
        self.config.sounds.point.play()

    @property
    def rect(self) -> pygame.Rect:
        score_digits = [int(x) for x in list(str(self.score))]
        images = [self.config.images.numbers[digit] for digit in score_digits]
        w = sum(image.get_width() for image in images)
        x = (self.config.window.width - w) / 2
        h = max(image.get_height() for image in images)
        return pygame.Rect(x, self.y, w, h)

    def draw(self) -> None:
        """Displays score in center of screen."""
        score_digits = [int(x) for x in list(str(self.score))]
        images = [self.config.images.numbers[digit] for digit in score_digits]
        digits_width = sum(image.get_width() for image in images)
        x_offset = (self.config.window.width - digits_width) / 2

        for image in images:
            self.config.screen.blit(image, (x_offset, self.y))
            x_offset += image.get_width()

        # Render high score banner
        if self.font:
            try:
                high_text = f"BEST: {self.high_score}"
                # Shadow
                shadow_surf = self.font.render(high_text, True, (0, 0, 0))
                text_surf = self.font.render(high_text, True, (255, 215, 0))
                high_x = 10
                high_y = 10
                self.config.screen.blit(shadow_surf, (high_x + 1, high_y + 1))
                self.config.screen.blit(text_surf, (high_x, high_y))
            except Exception:
                pass
