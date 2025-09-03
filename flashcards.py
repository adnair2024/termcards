import os
import json
import random
import curses
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FLASHCARDS_DIR = os.path.join(BASE_DIR, "flashcards")
PROGRESS_FILE = os.path.join(FLASHCARDS_DIR, "progress.json")

# ------------------- File & Subject Utilities ------------------- #
def list_subjects():
    return [d for d in os.listdir(FLASHCARDS_DIR) if os.path.isdir(os.path.join(FLASHCARDS_DIR, d))]

def list_files(subject):
    subject_path = os.path.join(FLASHCARDS_DIR, subject)
    return [f for f in os.listdir(subject_path) if f.endswith(".json") and os.path.isfile(os.path.join(subject_path, f))]

def load_flashcards(subject, filename=None):
    subject_path = os.path.join(FLASHCARDS_DIR, subject)
    cards = []
    if filename is None:  # load all files
        for file in list_files(subject):
            with open(os.path.join(subject_path, file), "r") as f:
                cards.extend(json.load(f))
    else:
        with open(os.path.join(subject_path, filename), "r") as f:
            cards = json.load(f)
    return cards

# ------------------- Progress Utilities ------------------- #
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_progress(progress):
    os.makedirs(FLASHCARDS_DIR, exist_ok=True)
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

def reset_subject_progress(subject):
    progress = load_progress()
    if subject in progress:
        progress[subject]["mastered"] = {}
        progress[subject]["time_spent"] = 0
        save_progress(progress)

def get_progress_percentage(subject, cards):
    progress = load_progress()
    if subject not in progress or "mastered" not in progress[subject]:
        return 0
    correct_count = sum(1 for card in cards if card['question'] in progress[subject]["mastered"])
    return round(correct_count / len(cards) * 100, 1) if cards else 0

# ------------------- Menu Picker ------------------- #
def menu_picker(stdscr, title, options):
    curses.curs_set(0)
    idx = 0
    while True:
        stdscr.clear()
        stdscr.addstr(1, 2, title)
        for i, opt in enumerate(options):
            if i == idx:
                stdscr.addstr(3+i, 4, f"> {opt}", curses.A_REVERSE)
            else:
                stdscr.addstr(3+i, 6, opt)
        stdscr.refresh()
        key = stdscr.getch()
        if key == curses.KEY_UP and idx > 0:
            idx -= 1
        elif key == curses.KEY_DOWN and idx < len(options)-1:
            idx += 1
        elif key in [10, 13]:  # Enter
            return options[idx]
        elif key == ord("q"):
            return None

def menu_picker_with_progress(stdscr, title, options, subject=None):
    curses.curs_set(0)
    idx = 0
    while True:
        stdscr.clear()
        stdscr.addstr(1, 2, title)

        for i, opt in enumerate(options):
            display = opt
            if subject:
                cards = load_flashcards(subject) if opt == "All files" else load_flashcards(subject, opt)
                pct = get_progress_percentage(subject, cards)
                display += f" ({pct}% learned)"

            if i == idx:
                stdscr.addstr(3+i, 4, f"> {display}", curses.A_REVERSE)
            else:
                stdscr.addstr(3+i, 6, display)

        stdscr.refresh()
        key = stdscr.getch()

        if key == curses.KEY_UP and idx > 0:
            idx -= 1
        elif key == curses.KEY_DOWN and idx < len(options)-1:
            idx += 1
        elif key in [10, 13]:  # Enter
            return options[idx]
        elif key == ord("q"):
            return None

# ------------------- Flashcards TUI ------------------- #
def flashcards_tui(stdscr, cards, subject):
    curses.curs_set(0)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)  # correct = green
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)    # wrong = red

    progress = load_progress()
    if subject not in progress:
        progress[subject] = {"mastered": {}, "time_spent": 0}

    start_time = time.time()
    correct_count = 0
    total = len(cards)

    remaining_cards = cards[:]

    while remaining_cards:
        wrong_questions = []

        for card in remaining_cards:
            stdscr.clear()
            choices = card["choices"][:]
            random.shuffle(choices)

            stdscr.addstr(1, 2, f"Q: {card['question']}")
            for i, choice in enumerate(choices, 1):
                stdscr.addstr(3+i, 4, f"{i}. {choice}")

            stdscr.addstr(len(choices)+6, 2, "Select (1-n), q to quit: ")
            stdscr.refresh()

            key = stdscr.getch()
            if key == ord("q"):
                elapsed = int(time.time() - start_time)
                progress[subject]["time_spent"] += elapsed
                save_progress(progress)
                return show_summary(stdscr, subject, cards, elapsed)

            if ord("1") <= key <= ord(str(len(choices))):
                selected = choices[key - ord("1")]
                for i, choice in enumerate(choices, 1):
                    if choice == card["answer"]:
                        stdscr.addstr(3+i, 4, f"{i}. {choice}", curses.color_pair(1))
                    elif choice == selected:
                        stdscr.addstr(3+i, 4, f"{i}. {choice}", curses.color_pair(2))

                if selected == card["answer"]:
                    correct_count += 1
                    progress[subject]["mastered"][card["question"]] = 1
                else:
                    wrong_questions.append(card)

                stdscr.refresh()
                time.sleep(1.5)

        remaining_cards = wrong_questions

    elapsed = int(time.time() - start_time)
    progress[subject]["time_spent"] += elapsed
    save_progress(progress)
    show_summary(stdscr, subject, cards, elapsed)

# ------------------- Summary ------------------- #
def show_summary(stdscr, subject, cards, elapsed):
    progress = load_progress()
    mastered = len(progress[subject]["mastered"])
    total = len(cards)
    left = total - mastered
    total_time = progress[subject]["time_spent"]

    # convert seconds → minutes (rounded to 1 decimal)
    elapsed_min = round(elapsed / 60, 1)
    total_min = round(total_time / 60, 1)

    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)  # green
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)    # red

    stdscr.clear()
    stdscr.addstr(1, 2, "📊 Study Session Summary")

    # Time stats
    stdscr.addstr(3, 4, f"Time this session: {elapsed_min} min ({elapsed} sec)")
    stdscr.addstr(4, 4, f"Total time spent: {total_min} min ({total_time} sec)")

    # Progress stats with colors
    stdscr.addstr(6, 4, f"Cards mastered: {mastered}/{total}", curses.color_pair(1))
    stdscr.addstr(7, 4, f"Cards left to master: {left}", curses.color_pair(2))
    stdscr.addstr(8, 4, f"Total terms learned: {mastered}")

    stdscr.addstr(10, 2, "Press any key to exit...")
    stdscr.refresh()
    stdscr.getch()

# ------------------- Main Run Function ------------------- #
def run():
    subjects = list_subjects()
    if not subjects:
        print("No subjects found.")
        return

    subject = curses.wrapper(menu_picker, "Choose a subject:", subjects)
    if not subject:
        return

    files = list_files(subject)
    if not files:
        print(f"No JSON flashcard files found in {subject}.")
        return

    # Ask if user wants to reset progress
    reset_choice = input(f"Do you want to reset progress for '{subject}'? (y/n): ").strip().lower()
    if reset_choice == "y":
        reset_subject_progress(subject)

    options = ["All files"] + files
    file_choice = curses.wrapper(menu_picker_with_progress, f"Choose file in {subject}:", options, subject)
    if not file_choice:
        return

    filename = None if file_choice == "All files" else file_choice
    cards = load_flashcards(subject, filename)
    if not cards:
        print("No cards found in the selected file(s).")
        return

    random.shuffle(cards)
    curses.wrapper(flashcards_tui, cards, subject)

# ------------------- Entry Point ------------------- #
if __name__ == "__main__":
    run()

