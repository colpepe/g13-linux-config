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

# Path to the driver's active-profile state file (must match the path the
# C++ driver writes in G13::loadBindings).
PROFILE_STATE_PATH = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "g13-profile")


def get_active_profile():
    """Returns the active profile number as a string, or '?' if unavailable."""
    try:
        with open(PROFILE_STATE_PATH) as f:
            value = f.read().strip()
            return value if value else "?"
    except OSError:
        return "?"


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


def get_ram_temp():
    """Returns a memory/mainboard temp in whole degrees C, or None.

    Preference order: DDR5 DIMM sensor (spd5118, averaged across
    reported DIMMs) -> motherboard/chipset sensor (nct*/it87*/asus*)
    -> None (omit gracefully).
    """
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return None

    if not temps:
        return None

    for key, entries in temps.items():
        if key.lower().startswith('spd5118') and entries:
            avg = sum(e.current for e in entries) / len(entries)
            return round(avg)

    for prefix in ('nct', 'it87', 'asus'):
        for key, entries in temps.items():
            if key.lower().startswith(prefix) and entries:
                return round(entries[0].current)

    return None


def get_gpu_busy_percent(vram_dir):
    """Returns GPU busy percent (utilization) for the given device dir, or None."""
    if not vram_dir:
        return None
    try:
        with open(os.path.join(vram_dir, 'gpu_busy_percent')) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def get_gpu_vram_text(vram_dir):
    """Returns 'used/total G' text (one decimal place) for the given device dir, or None."""
    if not vram_dir:
        return None
    try:
        with open(os.path.join(vram_dir, 'mem_info_vram_used')) as f:
            used = int(f.read().strip())
        with open(os.path.join(vram_dir, 'mem_info_vram_total')) as f:
            total = int(f.read().strip())
        used_gb = used / (2**30)
        total_gb = total / (2**30)
        return f"{used_gb:.1f}/{total_gb:.1f}G"
    except (OSError, ValueError):
        return None


def format_header_line(width=LCD_WIDTH):
    """date left (MM/DD/YY), active profile "G13:X" centered, time right (HH:MM:SS)."""
    now = datetime.now()
    date_str = now.strftime("%m/%d/%y")
    time_str = now.strftime("%H:%M:%S")
    profile_str = f"G13:{get_active_profile()}"

    middle_width = max(width - len(date_str) - len(time_str), 0)
    if len(profile_str) > middle_width:
        profile_str = profile_str[:middle_width]
    middle = f"{profile_str:^{middle_width}}"

    return f"{date_str}{middle}{time_str}"


def format_stat_line(label, center_text, pct, temp, width=LCD_WIDTH):
    """Builds a strict-column stat line.

    Fixed columns on a 26-char line: label flush left (3); memory
    fraction right-aligned in a 14-char field so its final char (the
    "G") always lands at index 16 on every line; one space; pct field
    (width 4, zero-padded to two digits, fits "100%") ending at index
    21; temp field (width 4, fits "100C") flush right ending at index
    25. The shared right edges keep the G's, %'s and C's vertically
    aligned across CPU/RAM/GPU lines.
    """
    TEMP_W = 4
    PCT_W = 4
    MEM_W = width - 3 - 1 - PCT_W - TEMP_W  # 14 on a 26-char line

    label_str = f"{label:<3}"
    temp_str = f"{temp}C" if temp is not None else ""
    temp_field = f"{temp_str:>{TEMP_W}}"
    pct_str = f"{pct:02.0f}%" if pct is not None else ""
    pct_field = f"{pct_str:>{PCT_W}}"
    mem_field = f"{center_text:>{MEM_W}}"[:MEM_W]

    return f"{label_str}{mem_field} {pct_field}{temp_field}"


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
            ram_temp = get_ram_temp()
            gpu_vram_dir = get_gpu_vram_dir()
            gpu_vram_text = get_gpu_vram_text(gpu_vram_dir) or "n/a"
            gpu_busy = get_gpu_busy_percent(gpu_vram_dir)
            gpu_temp = get_gpu_temp()

            # 2. Create Layout (max 6 lines of 26 chars)
            # Line 1: date | username | time (no labels)
            line1 = format_header_line()

            # Line 2: CPU percent + package temp (no bar)
            line2 = format_stat_line("CPU", "", cpu_percent, cpu_temp)

            # Line 3: RAM usage
            ram_text = f"{format_bytes(ram.used)}/{format_bytes(ram.total)}G"
            line3 = format_stat_line("RAM", ram_text, ram.percent, ram_temp)

            # Line 4: GPU VRAM usage + busy% + temp
            line4 = format_stat_line("GPU", gpu_vram_text, gpu_busy, gpu_temp)

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
