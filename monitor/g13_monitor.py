#!/usr/bin/env python3
import time
import psutil
import os
import sys
import glob
from datetime import datetime

# Path to the Named Pipe (Must match the path in the C++ driver)
PIPE_PATH = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "g13-lcd")

# LCD is 160x43 px, driver draws text at x=2 using a 5x7 font with a
# 6px advance per glyph (see G13::write_text in G13.cpp / font_5x7 in
# Font.h). Usable width is (160 - 2) = 158px, so max chars per line is
# floor(158 / 6) = 26.
LCD_WIDTH = 26


def create_bar(percent, length=10):
    """Creates a simple ASCII loading bar."""
    filled_length = int(length * percent // 100)
    bar = 'X' * filled_length + '-' * (length - filled_length)
    return f"[{bar}]"


def format_bytes(size):
    """Converts bytes to GB."""
    power = 2**30  # 1024**3
    n = size / power
    return f"{n:.1f}"


def get_cpu_temp():
    """Returns CPU package temp in whole degrees C, or None if unavailable."""
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return None

    if not temps:
        return None

    if 'k10temp' in temps:
        for entry in temps['k10temp']:
            if entry.label == 'Tctl':
                return round(entry.current)
        if temps['k10temp']:
            return round(temps['k10temp'][0].current)

    if 'coretemp' in temps:
        for entry in temps['coretemp']:
            if entry.label.startswith('Package id 0'):
                return round(entry.current)
        if temps['coretemp']:
            return round(temps['coretemp'][0].current)

    # Fall back to the first available sensor group/reading.
    for group in temps.values():
        if group:
            return round(group[0].current)

    return None


def get_gpu_vram_dir():
    """Finds the drm card device dir with the largest VRAM (the discrete GPU)."""
    best_dir = None
    best_total = -1
    for device_dir in glob.glob('/sys/class/drm/card*/device'):
        used_path = os.path.join(device_dir, 'mem_info_vram_used')
        total_path = os.path.join(device_dir, 'mem_info_vram_total')
        if os.path.isfile(used_path) and os.path.isfile(total_path):
            try:
                with open(total_path) as f:
                    total = int(f.read().strip())
            except (OSError, ValueError):
                continue
            if total > best_total:
                best_total = total
                best_dir = device_dir
    return best_dir


def get_gpu_temp():
    """Returns amdgpu temp in whole degrees C (edge preferred), or None."""
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return None

    if not temps or 'amdgpu' not in temps or not temps['amdgpu']:
        return None

    for entry in temps['amdgpu']:
        if entry.label == 'edge':
            return round(entry.current)

    return round(temps['amdgpu'][0].current)


def get_gpu_line():
    """Builds the GPU line: VRAM usage + temp. Degrades gracefully."""
    parts = []

    vram_dir = get_gpu_vram_dir()
    if vram_dir:
        try:
            with open(os.path.join(vram_dir, 'mem_info_vram_used')) as f:
                used = int(f.read().strip())
            with open(os.path.join(vram_dir, 'mem_info_vram_total')) as f:
                total = int(f.read().strip())
            used_gb = used / (2**30)
            total_gb = total / (2**30)
            parts.append(f"{used_gb:.1f}/{total_gb:.0f}G")
        except (OSError, ValueError):
            pass

    gpu_temp = get_gpu_temp()
    if gpu_temp is not None:
        parts.append(f"{gpu_temp}C")

    if not parts:
        return "GPU n/a"
    return "GPU " + " ".join(parts)


def format_header_line(width=LCD_WIDTH):
    """date left (MM/DD/YY), username centered, time right (HH:MM:SS)."""
    now = datetime.now()
    date_str = now.strftime("%m/%d/%y")
    time_str = now.strftime("%H:%M:%S")
    username = os.environ.get("USER") or os.environ.get("LOGNAME") or "user"

    middle_width = max(width - len(date_str) - len(time_str), 0)
    if len(username) > middle_width:
        username = username[:middle_width]
    middle = f"{username:^{middle_width}}"

    return f"{date_str}{middle}{time_str}"


def write_to_pipe(message):
    """Writes the string to the pipe."""
    if not os.path.exists(PIPE_PATH):
        print(f"Error: Pipe {PIPE_PATH} not found. Is the driver running?")
        return

    try:
        # We reopen the pipe on every write.
        # This is safe for Named Pipes on Linux and prevents deadlocks.
        with open(PIPE_PATH, 'w') as pipe:
            pipe.write(message)
    except OSError as e:
        print(f"Error writing to pipe: {e}")
    except BrokenPipeError:
        print("Driver closed the connection.")


def main():
    print("G13 Monitor started. Press Ctrl+C to exit.")

    while True:
        try:
            # 1. Collect data
            cpu_percent = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            cpu_temp = get_cpu_temp()

            # 2. Create Layout (max 6 lines of 26 chars)
            # Line 1: date | username | time (no labels)
            line1 = format_header_line()

            # Line 2: CPU bar/percent + package temp
            temp_str = f" {cpu_temp}C" if cpu_temp is not None else ""
            line2 = f"CPU {create_bar(cpu_percent, 10)} {int(cpu_percent):>3}%{temp_str}"

            # Line 3: RAM usage
            line3 = f"RAM {format_bytes(ram.used)}/{format_bytes(ram.total)}G {ram.percent:.0f}%"

            # Line 4: GPU VRAM usage + temp
            line4 = get_gpu_line()

            # Line 5: reserved for future use (left blank)
            line5 = ""

            # 3. Assemble message
            final_msg = f"{line1}\n{line2}\n{line3}\n{line4}\n{line5}"

            # 4. Send
            write_to_pipe(final_msg)

            # Refresh rate (1 second is good for LCDs)
            time.sleep(1)

        except KeyboardInterrupt:
            print("\nStopping monitor...")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(5)  # Wait before retry


if __name__ == "__main__":
    main()
