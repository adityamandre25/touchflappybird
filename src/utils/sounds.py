import logging
import sys
import pygame

logger = logging.getLogger("FlappyBird")


class DummySound:
    """Safe fallback sound that performs no-op when audio fails to initialize."""
    def play(self):
        pass


class Sounds:
    die: pygame.mixer.Sound
    hit: pygame.mixer.Sound
    point: pygame.mixer.Sound
    swoosh: pygame.mixer.Sound
    wing: pygame.mixer.Sound

    def __init__(self) -> None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()

            if "win" in sys.platform:
                ext = "wav"
            else:
                ext = "ogg"

            self.die = pygame.mixer.Sound(f"assets/audio/die.{ext}")
            self.hit = pygame.mixer.Sound(f"assets/audio/hit.{ext}")
            self.point = pygame.mixer.Sound(f"assets/audio/point.{ext}")
            self.swoosh = pygame.mixer.Sound(f"assets/audio/swoosh.{ext}")
            self.wing = pygame.mixer.Sound(f"assets/audio/wing.{ext}")
        except Exception as e:
            logger.warning("Audio mixer initialization failed or audio files unavailable: %s. Continuing silently.", e)
            self.die = DummySound()
            self.hit = DummySound()
            self.point = DummySound()
            self.swoosh = DummySound()
            self.wing = DummySound()
