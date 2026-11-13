"""
Arduino Serial Bridge for Flappy Bird
Handles non-blocking serial communication with an Arduino Uno / TTP223 touch sensor.
Supports automatic port discovery, manual port configuration, dynamic disconnection,
and graceful fallback to keyboard/mouse controls.
"""

import logging
import queue
import threading
import time
from typing import List, Optional, Tuple

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

try:
    import pygame
    PYGAME_AVAILABLE = True
    ARDUINO_JUMP_EVENT = pygame.USEREVENT + 1
except ImportError:
    PYGAME_AVAILABLE = False
    ARDUINO_JUMP_EVENT = 24  # Fallback integer ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ArduinoController")

# Common USB-Serial Vendor IDs
KNOWN_VENDORS = {
    0x2341: "Arduino",
    0x2A03: "Arduino.org",
    0x1A86: "WCH CH340",
    0x10C4: "Silicon Labs CP210x",
    0x0403: "FTDI",
    0x1B4F: "SparkFun",
    0x239A: "Adafruit",
}


def list_serial_ports() -> List[Tuple[str, str, str]]:
    """Returns a list of tuples: (device_name, description, hardware_id)."""
    if not SERIAL_AVAILABLE:
        return []
    ports = serial.tools.list_ports.comports()
    return [(p.device, p.description, p.hwid) for p in ports]


def auto_detect_arduino_port() -> Optional[str]:
    """
    Attempts to auto-detect an connected Arduino or compatible USB-serial device.
    Returns the port name (e.g. 'COM3' or '/dev/ttyUSB0') if found, else None.
    """
    if not SERIAL_AVAILABLE:
        return None

    ports = serial.tools.list_ports.comports()
    if not ports:
        return None

    # Step 1: Match known VID/PID or keywords in description
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()

        # Check vendor IDs
        if p.vid and p.vid in KNOWN_VENDORS:
            logger.info("Found known controller vendor (%s) on %s", KNOWN_VENDORS[p.vid], p.device)
            return p.device

        # Check keyword matches
        keywords = ["arduino", "ch340", "cp210", "ft232", "usb serial", "usb-serial", "ttyacm", "ttyusb"]
        if any(kw in desc or kw in hwid for kw in keywords):
            logger.info("Auto-detected Arduino-compatible device on %s (%s)", p.device, p.description)
            return p.device

    # Step 2: If there is exactly one serial port on the computer, offer it as a candidate
    if len(ports) == 1:
        candidate = ports[0].device
        logger.info("Single serial device detected: %s (%s). Using as default.", candidate, ports[0].description)
        return candidate

    return None


class ArduinoController:
    """
    Manages non-blocking serial communication with the Arduino in a background thread.
    Catches disconnections gracefully so the game never crashes.
    """

    def __init__(self, port: Optional[str] = None, baudrate: int = 9600):
        self.requested_port = port
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.is_connected = False
        self.jump_queue: queue.Queue = queue.Queue()
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the background reading thread."""
        if not SERIAL_AVAILABLE:
            logger.warning("pyserial is not installed. Arduino touch input disabled. Using keyboard/mouse.")
            return

        self.running = True
        self.thread = threading.Thread(target=self._worker, name="ArduinoReaderThread", daemon=True)
        self.thread.start()

    def _attempt_connection(self) -> bool:
        """Tries to connect to the specified or auto-detected serial port."""
        target_port = self.requested_port
        if not target_port or target_port.lower() == "auto":
            target_port = auto_detect_arduino_port()

        if not target_port:
            return False

        try:
            self.ser = serial.Serial(target_port, self.baudrate, timeout=0.1)
            self.port = target_port
            self.is_connected = True
            logger.info("Connected to Arduino on port %s at %d baud.", self.port, self.baudrate)
            return True
        except (serial.SerialException, OSError, PermissionError) as e:
            self.ser = None
            self.is_connected = False
            return False

    def _worker(self):
        """Background loop reading serial data and handling reconnection."""
        # Initial connection attempt
        connected = self._attempt_connection()
        if not connected:
            if self.requested_port:
                logger.warning("Could not open requested port '%s'. Will retry in background.", self.requested_port)
            else:
                logger.info("No Arduino detected on startup. Running in Keyboard/Mouse mode.")

        last_reconnect_attempt = time.time()

        while self.running:
            if self.is_connected and self.ser:
                try:
                    line = self.ser.readline()
                    if line:
                        decoded = line.decode("utf-8", errors="ignore").strip()
                        if "JUMP" in decoded:
                            self.jump_queue.put(True)
                            # Post a Pygame event if Pygame is active
                            if PYGAME_AVAILABLE and pygame.get_init():
                                try:
                                    pygame.event.post(pygame.event.Event(ARDUINO_JUMP_EVENT, {"source": "arduino"}))
                                except Exception:
                                    pass
                except (serial.SerialException, OSError) as e:
                    logger.warning("Arduino disconnected: %s. Reverting to keyboard/mouse.", e)
                    self._close_serial()
                    self.is_connected = False
            else:
                # Attempt to reconnect every 3 seconds if disconnected
                now = time.time()
                if now - last_reconnect_attempt > 3.0:
                    last_reconnect_attempt = now
                    if self._attempt_connection():
                        logger.info("Arduino reconnected successfully on %s!", self.port)

            time.sleep(0.005)

    def _close_serial(self):
        """Safely closes serial handle without throwing."""
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def get_jump(self) -> bool:
        """Polls whether a jump was registered from the Arduino."""
        try:
            self.jump_queue.get_nowait()
            return True
        except queue.Empty:
            return False

    def stop(self):
        """Stops the worker thread and cleans up resources."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self._close_serial()
        logger.info("Arduino controller stopped.")
