#!/usr/bin/env python3
"""
Single-File Self-Contained Flappy Bird with Arduino Touch Sensor Control.
- Zero sound dependencies (runs silently without audio crashes).
- Pure Pygame procedural graphics (zero external image assets required).
- Non-blocking background thread for Arduino serial communication.
- Full keyboard (SPACE / UP) & mouse controls as backup.
- Configurable COM port with automatic discovery.

Requirements:
    pip install pygame pyserial
Run:
    python flappy_single.py
    python flappy_single.py --port COM3
"""

import argparse
import math
import queue
import random
import sys
import threading
import time

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


# ==========================================
# Arduino Serial Controller (Background Thread)
# ==========================================
class ArduinoBridge:
    def __init__(self, port=None, baudrate=9600):
        self.requested_port = port
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.connected = False
        self.jump_queue = queue.Queue()
        self.running = True

    def find_port(self):
        if not SERIAL_AVAILABLE:
            return None
        ports = serial.tools.list_ports.comports()
        if not ports:
            return None

        # Look for Arduino / CH340 / USB Serial
        for p in ports:
            desc = (p.description or "").lower()
            hwid = (p.hwid or "").lower()
            if any(k in desc or k in hwid for k in ["arduino", "ch340", "cp210", "ftdi", "usb serial", "usb-serial", "ttyacm", "ttyusb"]):
                return p.device
        # Default to first available port if only one exists
        if len(ports) == 1:
            return ports[0].device
        return None

    def start(self):
        if not SERIAL_AVAILABLE:
            print("\n" + "=" * 60)
            print(" [WARNING] 'pyserial' is not installed in Python!")
            print(" Arduino CANNOT connect without it.")
            print(" Install it now by running:  pip install pyserial")
            print(" Falling back to Keyboard (SPACE / UP) & Mouse controls.")
            print("=" * 60 + "\n")
            return
        thread = threading.Thread(target=self._worker, daemon=True)
        thread.start()

    def _worker(self):
        last_logged_time = 0
        while self.running:
            if not self.connected:
                target = self.requested_port or self.find_port()
                if target:
                    try:
                        self.ser = serial.Serial(target, self.baudrate, timeout=0.1)
                        self.port = target
                        self.connected = True
                        print(f"[Arduino] Successfully connected on {self.port} at {self.baudrate} baud!")
                    except Exception as e:
                        self.ser = None
                        self.connected = False
                        # Rate limit warning messages
                        if time.time() - last_logged_time > 4.0:
                            last_logged_time = time.time()
                            print(f"[Arduino] Could not open port {target}: {e}")
                            print("  -> Tip: Make sure the Arduino IDE Serial Monitor is CLOSED!")
                time.sleep(1.5)
            else:
                try:
                    line = self.ser.readline()
                    if line:
                        msg = line.decode("utf-8", errors="ignore").strip()
                        if "JUMP" in msg:
                            self.jump_queue.put(True)
                except Exception as e:
                    print(f"[Arduino] Disconnected: {e}. Reverting to keyboard/mouse.")
                    if self.ser:
                        try:
                            self.ser.close()
                        except Exception:
                            pass
                    self.ser = None
                    self.connected = False
                    time.sleep(1.0)
            time.sleep(0.005)

    def pop_jump(self):
        try:
            self.jump_queue.get_nowait()
            return True
        except queue.Empty:
            return False

    def stop(self):
        self.running = False
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass


# ==========================================
# Procedural Pixel-Art Sprite Generator
# ==========================================
def create_bird_surface(pygame, wing_state=0):
    """Generates a crisp 34x24 retro bird surface."""
    surf = pygame.Surface((34, 24), pygame.SRCALPHA)
    # Body (Yellow)
    pygame.draw.ellipse(surf, (244, 180, 0), (4, 2, 24, 20))
    pygame.draw.ellipse(surf, (0, 0, 0), (4, 2, 24, 20), 2)
    # Belly highlight
    pygame.draw.ellipse(surf, (255, 225, 77), (8, 6, 16, 14))

    # Eye (White with black pupil)
    pygame.draw.circle(surf, (255, 255, 255), (20, 7), 5)
    pygame.draw.circle(surf, (0, 0, 0), (20, 7), 5, 1)
    pygame.draw.circle(surf, (0, 0, 0), (22, 7), 2)

    # Beak (Orange)
    pygame.draw.polygon(surf, (230, 81, 0), [(24, 10), (33, 14), (24, 18)])
    pygame.draw.polygon(surf, (0, 0, 0), [(24, 10), (33, 14), (24, 18)], 1)

    # Wing
    wing_y = 10 if wing_state == 0 else (6 if wing_state == 1 else 14)
    pygame.draw.ellipse(surf, (255, 255, 255), (6, wing_y, 12, 8))
    pygame.draw.ellipse(surf, (0, 0, 0), (6, wing_y, 12, 8), 1)
    return surf


def create_pipe_surfaces(pygame, width=64, height=450):
    """Generates upper and lower pipe surfaces with highlights and collars."""
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    surf.fill((115, 191, 46))
    pygame.draw.rect(surf, (0, 0, 0), (0, 0, width, height), 3)
    pygame.draw.line(surf, (168, 224, 99), (5, 0), (5, height), 4)
    pygame.draw.line(surf, (82, 148, 26), (width - 6, 0), (width - 6, height), 4)

    collar_h = 26
    collar = pygame.Surface((width + 8, collar_h), pygame.SRCALPHA)
    collar.fill((115, 191, 46))
    pygame.draw.rect(collar, (0, 0, 0), (0, 0, width + 8, collar_h), 3)
    pygame.draw.line(collar, (168, 224, 99), (6, 2), (6, collar_h - 2), 4)
    pygame.draw.line(collar, (82, 148, 26), (width + 2, 2), (width + 2, collar_h - 2), 4)

    lower = surf.copy()
    lower.blit(collar, (-4, 0))

    upper = surf.copy()
    upper.blit(collar, (-4, height - collar_h))
    return upper, lower


# ==========================================
# Main Game Class
# ==========================================
class FlappyBirdGame:
    def __init__(self, port=None):
        import pygame
        self.pygame = pygame
        pygame.init()
        # Zero sound calls or mixer initialization
        self.width = 400
        self.height = 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Flappy Bird (Arduino Touch & Keyboard)")
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_score = pygame.font.SysFont("Impact", 44)
        self.font_title = pygame.font.SysFont("Verdana", 20, bold=True)
        self.font_sub = pygame.font.SysFont("Verdana", 14)
        self.font_status = pygame.font.SysFont("Consolas", 12)

        # Pre-render graphics
        self.bird_frames = [
            create_bird_surface(pygame, 0),
            create_bird_surface(pygame, 1),
            create_bird_surface(pygame, 2),
            create_bird_surface(pygame, 1),
        ]
        self.pipe_width = 64
        self.pipe_gap = 140
        self.pipe_upper_template, self.pipe_lower_template = create_pipe_surfaces(pygame, self.pipe_width, 450)

        # Ground height
        self.ground_y = self.height - 80

        # Start Arduino Bridge
        self.arduino = ArduinoBridge(port=port)
        self.arduino.start()

        self.high_score = 0
        self.reset_game()

    def reset_game(self):
        self.state = "START"  # START, PLAYING, GAMEOVER
        self.bird_x = 70
        self.bird_y = self.height // 2 - 20
        self.bird_vel_y = 0
        self.bird_rot = 0
        self.gravity = 0.55
        self.jump_velocity = -8.5
        self.wing_frame = 0
        self.anim_tick = 0

        self.score = 0
        self.pipes = []
        self.pipe_speed = 3.2

        # Ground scroll
        self.ground_offset = 0

    def spawn_pipe(self, x):
        gap_center = random.randint(140, self.ground_y - 140)
        gap_top = gap_center - (self.pipe_gap // 2)
        gap_bottom = gap_center + (self.pipe_gap // 2)

        self.pipes.append({
            "x": x,
            "top_y": gap_top - 450,
            "bottom_y": gap_bottom,
            "passed": False,
        })

    def handle_flap(self):
        if self.state == "START":
            self.state = "PLAYING"
            self.bird_vel_y = self.jump_velocity
            self.spawn_pipe(self.width + 80)
            self.spawn_pipe(self.width + 80 + 200)
        elif self.state == "PLAYING":
            self.bird_vel_y = self.jump_velocity
        elif self.state == "GAMEOVER":
            self.reset_game()

    def update(self):
        pygame = self.pygame
        tap = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.arduino.stop()
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.arduino.stop()
                    pygame.quit()
                    sys.exit(0)
                elif event.key in (pygame.K_SPACE, pygame.K_UP):
                    tap = True
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                tap = True

        # Check Arduino Jump
        if self.arduino.pop_jump():
            tap = True

        if tap:
            self.handle_flap()

        self.anim_tick += 1
        if self.anim_tick % 5 == 0:
            self.wing_frame = (self.wing_frame + 1) % len(self.bird_frames)

        self.ground_offset = (self.ground_offset + 3) % 24

        if self.state == "START":
            self.bird_y = (self.height // 2 - 20) + math.sin(time.time() * 5) * 8
            self.bird_rot = 0

        elif self.state == "PLAYING":
            self.bird_vel_y += self.gravity
            self.bird_y += self.bird_vel_y

            target_rot = -self.bird_vel_y * 3.5
            self.bird_rot = max(-80, min(25, target_rot))

            for p in self.pipes:
                p["x"] -= self.pipe_speed

                if not p["passed"] and p["x"] + self.pipe_width < self.bird_x:
                    p["passed"] = True
                    self.score += 1
                    if self.score > self.high_score:
                        self.high_score = self.score

            if self.pipes and self.pipes[0]["x"] < -self.pipe_width - 20:
                self.pipes.pop(0)

            if len(self.pipes) < 3:
                last_x = self.pipes[-1]["x"] if self.pipes else self.width
                self.spawn_pipe(last_x + 200)

            bird_rect = pygame.Rect(self.bird_x + 4, self.bird_y + 4, 26, 16)

            if self.bird_y + 24 >= self.ground_y or self.bird_y <= 0:
                self.state = "GAMEOVER"

            for p in self.pipes:
                upper_rect = pygame.Rect(p["x"], p["top_y"], self.pipe_width, 450)
                lower_rect = pygame.Rect(p["x"], p["bottom_y"], self.pipe_width, 450)
                if bird_rect.colliderect(upper_rect) or bird_rect.colliderect(lower_rect):
                    self.state = "GAMEOVER"

        elif self.state == "GAMEOVER":
            if self.bird_y + 24 < self.ground_y:
                self.bird_vel_y += self.gravity
                self.bird_y += self.bird_vel_y
                self.bird_rot = -80

    def draw(self):
        pygame = self.pygame
        # Sky Background
        self.screen.fill((112, 197, 206))

        # Clouds
        pygame.draw.circle(self.screen, (255, 255, 255), (80, 120), 30)
        pygame.draw.circle(self.screen, (255, 255, 255), (110, 110), 40)
        pygame.draw.circle(self.screen, (255, 255, 255), (145, 120), 32)
        pygame.draw.circle(self.screen, (255, 255, 255), (300, 180), 28)
        pygame.draw.circle(self.screen, (255, 255, 255), (330, 170), 38)
        pygame.draw.circle(self.screen, (255, 255, 255), (360, 180), 28)

        # Pipes
        for p in self.pipes:
            self.screen.blit(self.pipe_upper_template, (p["x"], p["top_y"]))
            self.screen.blit(self.pipe_lower_template, (p["x"], p["bottom_y"]))

        # Ground
        pygame.draw.rect(self.screen, (222, 216, 149), (0, self.ground_y, self.width, self.height - self.ground_y))
        pygame.draw.rect(self.screen, (115, 191, 46), (0, self.ground_y, self.width, 14))
        pygame.draw.line(self.screen, (0, 0, 0), (0, self.ground_y), (self.width, self.ground_y), 2)
        pygame.draw.line(self.screen, (82, 148, 26), (0, self.ground_y + 14), (self.width, self.ground_y + 14), 2)

        # Ground pattern
        for gx in range(-24, self.width + 24, 24):
            x_pos = gx - self.ground_offset
            pygame.draw.line(self.screen, (158, 207, 74), (x_pos, self.ground_y + 2), (x_pos + 10, self.ground_y + 12), 3)

        # Bird
        bird_img = self.bird_frames[self.wing_frame]
        rotated_bird = pygame.transform.rotate(bird_img, self.bird_rot)
        rot_rect = rotated_bird.get_rect(center=(self.bird_x + 17, self.bird_y + 12))
        self.screen.blit(rotated_bird, rot_rect)

        # UI & Scores
        if self.state == "PLAYING":
            score_txt = self.font_score.render(str(self.score), True, (255, 255, 255))
            shadow_txt = self.font_score.render(str(self.score), True, (0, 0, 0))
            sx = (self.width - score_txt.get_width()) // 2
            self.screen.blit(shadow_txt, (sx + 2, 42))
            self.screen.blit(score_txt, (sx, 40))

        elif self.state == "START":
            title = self.font_title.render("FLAPPY BIRD", True, (255, 255, 255))
            t_sh = self.font_title.render("FLAPPY BIRD", True, (0, 0, 0))
            self.screen.blit(t_sh, ((self.width - title.get_width()) // 2 + 2, 142))
            self.screen.blit(title, ((self.width - title.get_width()) // 2, 140))

            sub1 = self.font_sub.render("Tap Touch Sensor or Space to Start", True, (255, 245, 157))
            s1_sh = self.font_sub.render("Tap Touch Sensor or Space to Start", True, (0, 0, 0))
            self.screen.blit(s1_sh, ((self.width - sub1.get_width()) // 2 + 1, 221))
            self.screen.blit(sub1, ((self.width - sub1.get_width()) // 2, 220))

            if self.high_score > 0:
                best_t = self.font_sub.render(f"BEST SCORE: {self.high_score}", True, (255, 215, 0))
                self.screen.blit(best_t, ((self.width - best_t.get_width()) // 2, 260))

        elif self.state == "GAMEOVER":
            go_txt = self.font_title.render("GAME OVER", True, (231, 76, 60))
            go_sh = self.font_title.render("GAME OVER", True, (0, 0, 0))
            self.screen.blit(go_sh, ((self.width - go_txt.get_width()) // 2 + 2, 162))
            self.screen.blit(go_txt, ((self.width - go_txt.get_width()) // 2, 160))

            score_msg = self.font_sub.render(f"Score: {self.score}   Best: {self.high_score}", True, (255, 255, 255))
            self.screen.blit(score_msg, ((self.width - score_msg.get_width()) // 2, 210))

            restart_msg = self.font_sub.render("Tap Touch Sensor or Space to Restart", True, (255, 245, 157))
            self.screen.blit(restart_msg, ((self.width - restart_msg.get_width()) // 2, 250))

        # Bottom Arduino Status Bar
        pygame.draw.rect(self.screen, (20, 24, 30), (0, self.height - 24, self.width, 24))
        if self.arduino.connected:
            dot_color = (46, 204, 113)
            status_text = f"Arduino: Connected ({self.arduino.port})"
        else:
            dot_color = (241, 196, 15)
            status_text = "Arduino: Disconnected (Using Spacebar/Mouse)"

        pygame.draw.circle(self.screen, dot_color, (14, self.height - 12), 4)
        stat_surf = self.font_status.render(status_text, True, (220, 220, 220))
        self.screen.blit(stat_surf, (26, self.height - 18))

        pygame.display.flip()

    def run(self):
        while True:
            self.update()
            self.draw()
            self.clock.tick(60)


# ==========================================
# Entry Point & CLI Arguments
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Single-file Flappy Bird with Arduino Support")
    parser.add_argument("-p", "--port", type=str, default=None, help="COM port (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("-l", "--list-ports", action="store_true", help="List detected serial ports")
    args = parser.parse_args()

    if args.list_ports:
        print("\n--- Detected Serial Ports ---")
        if not SERIAL_AVAILABLE:
            print("[Warning] pyserial is not installed! Run: pip install pyserial")
        else:
            ports = serial.tools.list_ports.comports()
            if not ports:
                print("No serial ports detected. Check USB cable and drivers.")
            for p in ports:
                print(f"  {p.device:<10} : {p.description}")
        print("-----------------------------\n")
        return

    try:
        import pygame
    except ImportError:
        print("\n" + "=" * 60)
        print(" [Error] Pygame is not installed!")
        print(" Run this command in your terminal:")
        print("     pip install pygame pyserial")
        print("=" * 60 + "\n")
        sys.exit(1)

    game = FlappyBirdGame(port=args.port)
    try:
        game.run()
    except KeyboardInterrupt:
        print("\nExiting Flappy Bird.")
    finally:
        game.arduino.stop()


if __name__ == "__main__":
    main()
