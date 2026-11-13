#!/usr/bin/env python3
"""
Flappy Bird with Arduino Touch Sensor Control
Run with:
    python main.py
    python main.py --port COM3
    python main.py --list-ports
"""

import argparse
import os
import sys

# Ensure execution directory is the project root (handles relative paths everywhere)
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT_DIR)

from src.arduino import auto_detect_arduino_port, list_serial_ports


def parse_args():
    parser = argparse.ArgumentParser(
        description="Flappy Bird with Arduino Touch Sensor & Keyboard Controls",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                  # Auto-detect Arduino or run with keyboard/mouse
  python main.py --port COM3       # Connect to specific COM port on Windows
  python main.py -p /dev/ttyUSB0   # Connect to serial port on Linux / macOS
  python main.py --no-arduino      # Force keyboard / mouse only mode
  python main.py --list-ports      # Display all detected serial devices
        """,
    )
    parser.add_argument(
        "-p",
        "--port",
        type=str,
        default=None,
        help="Serial port for Arduino (e.g. COM3, /dev/ttyACM0, /dev/ttyUSB0). If omitted, auto-discovery is used.",
    )
    parser.add_argument(
        "-b",
        "--baud",
        type=int,
        default=9600,
        help="Serial baud rate (default: 9600).",
    )
    parser.add_argument(
        "--no-arduino",
        action="store_true",
        help="Disable Arduino connection and play using only keyboard/mouse.",
    )
    parser.add_argument(
        "-l",
        "--list-ports",
        action="store_true",
        help="List available serial/COM ports and exit.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.list_ports:
        print("\n--- Available Serial Ports ---")
        ports = list_serial_ports()
        if not ports:
            print("No serial ports detected.")
        else:
            for device, desc, hwid in ports:
                print(f"  • {device:<12} : {desc} [{hwid}]")
        auto_port = auto_detect_arduino_port()
        if auto_port:
            print(f"\nAuto-detection candidate: {auto_port}")
        print("------------------------------\n")
        return

    port = None
    if args.no_arduino:
        print("[Info] Arduino integration disabled by --no-arduino flag.")
        port = "none"
    elif args.port:
        port = args.port
        print(f"[Info] Configured Arduino serial port: {port}")
    else:
        print("[Info] Auto-detecting Arduino touch controller...")

    try:
        import asyncio
        from src.flappy import Flappy
    except ImportError as e:
        print(f"\n[Error] Missing dependency: {e}")
        print("Please install requirements using:")
        print("    pip install -r requirements.txt\n")
        sys.exit(1)

    game = Flappy(port=port)
    try:
        asyncio.run(game.start())
    except KeyboardInterrupt:
        print("\n[Game] Exited by user.")
    except Exception as e:
        print(f"\n[Error] Game terminated: {e}")
        raise


if __name__ == "__main__":
    main()
