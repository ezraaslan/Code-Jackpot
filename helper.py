from datetime import timedelta
import time
import random
import ast
import sys
import os
from pynput import keyboard, mouse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pynput import keyboard as kb
import customtkinter as ctk
import tkinter.messagebox as messagebox
import tkinter as tk
from tkinter import TclError
import pickle
from plyer import notification
from datetime import date

last_activity = None
last_afk_penalty = 0
last_line_count = 0
current_errors = 0
odds = 0.2
last_content = ""

paused = False
pause_start_time = None
total_pause_duration = 0
frozen_time = 0
frozen_elapsed = 0

finished = False
early = False

ui_running = True

lines_added = 0
errors = 0

daily_streak = 0
last_used_date = None

RESET = "\033[0m"
BLUE  = "\033[94m"
GREEN = "\033[92m"
RED   = "\033[91m" 

def layered_code_bar(total_lines, added_lines, error_lines, width=40):
    if total_lines <= 0:
        return "[no data]"

    added_lines = min(added_lines, total_lines)
    error_lines = min(error_lines, added_lines)

    added_ratio = added_lines / total_lines
    error_ratio = error_lines / total_lines 

    added_blocks = int(width * added_ratio)
    error_blocks = int(width * error_ratio)

    error_blocks = min(error_blocks, added_blocks)
    good_added_blocks = added_blocks - error_blocks

    base_blocks = width - added_blocks

    bar = (
        BLUE + "█" * base_blocks +
        RED + "█" * error_blocks +
        GREEN + "█" * good_added_blocks +
        RESET
    )

    return f"[{bar}]"


def slot_machine_animation(win):
    symbols = ["🍒", "🍋", "⭐", "💎", "7"]

    slot_root = tk.Toplevel()
    slot_root.title("Rolling...")
    slot_root.geometry("300x180")
    slot_root.attributes("-topmost", True)

    frame = tk.Frame(slot_root)
    frame.pack(expand=True)

    reels = []
    for _ in range(3):
        lbl = tk.Label(frame, text="❓", font=("Segoe UI Emoji", 40))
        lbl.pack(side="left", padx=10)
        reels.append(lbl)

    result_label = tk.Label(slot_root, text="", font=("Segoe UI", 16))
    result_label.pack(pady=10)

    def spin(count=20):
        for r in reels:
            r.config(text=random.choice(symbols))

        if count > 0:
            slot_root.after(100, spin, count - 1)
        else:
            #symbols
            if win:
                s = random.choice(symbols)
                final = [s, s, s] 
            else:
                final = random.sample(symbols, 3) 

            for r, s in zip(reels, final):
                r.config(text=s)

            if win:
                result_label.config(text="YOU WIN!", fg="green")
            else:
                result_label.config(text="YOU LOSE", fg="red")

            slot_root.after(1500, slot_root.destroy)

    spin()
    slot_root.mainloop()


def update_activity(_=None):
    global last_activity
    last_activity = time.time()

def afk_time():
    if last_activity is None:
        return 0
    return time.time() - last_activity

def clamp(value, min_val=0.0, max_val=1.0):
    return max(min_val, min(value, max_val))

def count_syntax_errors(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        ast.parse(source)
        return 0
    except SyntaxError:
        return 1

def bet(balance):
    while True:
        wager_input = input(f"You have ${balance:.2f}. Enter amount to wager: ").strip()
        try:
            wager = float(wager_input)
            if 0 <= wager <= balance:
                return wager
            print("Insufficient funds.")
        except ValueError:
            print("Enter a number.")

def get_hours():
    while True:
        hours = input("Hours: ").strip()
        try:
            hours = float(hours)
            if hours < 0:
                print("Enter a valid number.")
                continue
            if hours > 5:
                go = input("That's a long time. Are you sure? (y/n): ").lower()
                if go == "y":
                    return hours
                else:
                    continue
            return hours
        except ValueError:
            print("Enter a number.")

def get_minutes():
    while True:
        minutes = input("Minutes: ").strip()
        try:
            minutes = float(minutes)
            if minutes < 0:
                print("Enter a valid number.")
                continue
            return minutes
        except ValueError:
            print("Enter a number.")

class FileUpdateHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if paused:
            return

        global current_errors, odds, last_line_count, last_content, lines_added, errors

        if os.path.abspath(event.src_path) != TARGET_FILE:
            return

        try:
            with open(TARGET_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_content = "".join(lines)
        except Exception:
            return

        old_lines = last_content.splitlines()
        new_lines = new_content.splitlines()

        afk_reset = False
        for i, new_line in enumerate(new_lines):
            old_line = old_lines[i] if i < len(old_lines) else ""
            if new_line != old_line and new_line.strip():
                afk_reset = True

        if afk_reset:
            update_activity()

        old_errors = current_errors
        current_errors = count_syntax_errors(TARGET_FILE)

        if current_errors < old_errors:
            odds += 0.01
        elif current_errors > old_errors:
            odds -= 0.01
            errors += 1

        new_line_count = len(lines)

        if new_line_count > last_line_count:
            lines_added += 1
            previous_normalized = set(l.strip() for l in old_lines if l.strip() != "")

            for i in range(last_line_count, new_line_count):
                raw_line = lines[i]
                stripped = raw_line.strip()
                if stripped == "":
                    continue
                if stripped.startswith("def "):
                    odds += 0.02
                if stripped not in previous_normalized:
                    if current_errors == old_errors:
                        odds += 0.01
                    else:
                        odds -= 0.01
                        errors += 1
                    previous_normalized.add(stripped)

        last_line_count = new_line_count
        last_content = new_content

def main():
    global TARGET_FILE, last_line_count, last_afk_penalty, odds, last_content, last_activity, finished, early, paused

    try:
        with open("streak.pkl", "rb") as f:
            daily_streak, last_used_date = pickle.load(f)
    except:
        daily_streak = 0
        last_used_date = None

    today = date.today()

    if last_used_date == today:
        # already counted
        pass

    elif last_used_date == today - timedelta(days=1):
        #next day
        daily_streak += 1

    else:
        daily_streak = 0

    last_used_date = today

    streak_bonus = daily_streak * 0.01
    odds += streak_bonus
    odds = clamp(odds)
    streak_bonus = min(daily_streak * 0.01, 0.3)  # max 1 month
    if daily_streak >= 30:
        print("Wow! You've reached the max streak! Streak bonus resets tomorrow.")
    daily_streak = 0


    try:
        with open("balance.pkl", "rb") as f:
            balance = pickle.load(f)
    except:
        balance = 10

    while True:
        file_path = input("Enter the path of the file you will be working on: ").strip()
        if not file_path:
            print("No file path provided.")
            continue
            
        TARGET_FILE = os.path.abspath(file_path)

        if not os.path.exists(TARGET_FILE):
            print("Error: File does not exist.")
            continue
        
        else:
            break

    try:
        with open(TARGET_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            last_line_count = len(lines)
            last_content = "".join(lines)
    except Exception:
        last_line_count = 0
        last_content = ""

    wager = bet(balance)
    balance -= wager

    print("How long will you code for?")
    while True:
        hours = get_hours()
        minutes = get_minutes()
        if hours + minutes <= .005:
            print("Time must be greater than 0h and .005m.")
            continue
        break
    goal_time = hours * 3600 + minutes * 60

    update_activity()
    last_afk_penalty = 0

    start_time = time.time()

    observer = Observer()
    handler = FileUpdateHandler()
    TARGET_DIR = os.path.dirname(TARGET_FILE)
    observer.schedule(handler, TARGET_DIR, recursive=False)
    observer.start()

    try:
        print("\nTimer started! Monitoring file...\n")
        print("Press Ctrl+C to stop.")

        # tkinter display bar
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        root = ctk.CTk()
        root.title("Code Helper")
        root.geometry("900x50")

        status_label = ctk.CTkLabel(
            root,
            text="Starting...",
            font=("Segoe UI", 20)
        )
        status_label.pack(pady=10)

        #make top frame for label and button
        top_frame = ctk.CTkFrame(root)
        top_frame.pack(pady=10)

        status_label.pack(side="left", padx=10)

        def toggle_pause():
            global paused, pause_start_time, total_pause_duration, frozen_afk, frozen_elapsed, last_activity

            if not paused:
                paused = True
                pause_start_time = time.time()

                frozen_afk = afk_time()
                frozen_elapsed = time.time() - start_time - total_pause_duration

                generate_button.configure(text='RESUME')

            else:
                paused = False
                total_pause_duration += time.time() - pause_start_time
                
                last_activity = time.time() - frozen_afk
                
                generate_button.configure(text='PAUSE')


        generate_button = ctk.CTkButton(
            top_frame,
            text="PAUSE",
            font=("Segoe UI Semilight", 18, "bold"),
            command=toggle_pause
        )

        generate_button.pack(side="left", padx=10)

        
        def update_ui():
            global last_afk_penalty, odds, finished, ui_running

            if not ui_running:
                return

            if paused:
                elapsed = frozen_elapsed
                afk_elapsed = frozen_afk
            else:
                elapsed = time.time() - start_time - total_pause_duration
                afk_elapsed = afk_time()


            remaining = max(0, goal_time - elapsed)
            remaining_str = str(timedelta(seconds=remaining)).split(".")[0]

            status_label.configure(
                text=f" Daily Streak: {daily_streak}   |   AFK: {afk_elapsed:6.1f}s   |   Odds: {100 * odds:.0f}%   |   Remaining: {remaining_str}"
            )

            now = time.time()
            if now - last_afk_penalty >= 120:
                if afk_elapsed >= 120:
                    odds -= 0.05
                    odds = clamp(odds)
                    notification.notify(
                        title='AFK Timer',
                        message="You haven't typed in 2 minutes!",
                        app_name='Python Notifier',
                        timeout=5
                    )
                last_afk_penalty = now

            if elapsed >= goal_time:
                print("\nGoal complete!")
                finished = True
                ui_running = False
                root.quit()
                return

            root.after(100, update_ui)

        root.attributes("-topmost", True)
        update_ui()
        root.mainloop()



    finally:
        # listener.stop()
        observer.stop()
        observer.join()
        if not finished:
            print("\nProgram ended before goal was reached.\n")
            return


    roll = random.random()
    win = roll < odds

    slot_machine_animation(win)

    if win:
        print("\nMoney doubled!")
        balance += wager * 2
    else:
        print("\nMoney lost.")


    print(f"Balance: ${balance:.2f}")
    with open('balance.pkl', 'wb') as outf:
            pickle.dump(balance, outf)
    
    with open("streak.pkl", "wb") as f:
        pickle.dump((daily_streak, last_used_date), f)


    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        total_lines = len(f.readlines())

    if total_lines > 0:
        lines_percent = (lines_added/total_lines) * 100
    else:
        lines_percent = 0.0
    if lines_added > 0:
        errors_percent = (errors/lines_added) * 100
    else:
        errors_percent = 0.0
    
    print("Session Summary:")
    print(f"Lines Added: {lines_added} ({lines_percent:.0f}% of the file)")
    print(f"Errors Added: {errors} ({errors_percent:.0f}% of added lines)")

    print(layered_code_bar(total_lines, lines_added, errors))

if __name__ == "__main__":
    main()
    input("\nPress Enter to exit...")
