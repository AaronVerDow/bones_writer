import curses
import time
import humanize
import os
import shutil
import readline
import re
from datetime import datetime, timedelta
from pathlib import Path

# adjust for darknes of live stats, 0-1000
GRAY_LEVEL = 200

# required by curses to define custom color, changes nothing
GRAY_PAIR = 1
GRAY_COLOR = 100

# Timeout in seconds before blanking the text
BLANK_TIMEOUT = 5.0


class CategoryCompleter:
    def __init__(self, categories):
        self.categories = categories

    def complete(self, text, state):
        options = [i for i in self.categories if i.startswith(text)]
        if state < len(options):
            return options[state]
        return None


class BonesWriter:
    def __init__(self):
        self.running = True
        now = datetime.now()

        self.dir = Path.joinpath(Path.home(), "Documents", "bones")

        self.filename = now.strftime("%Y-%m-%d_%H-%M-%S") + ".Rmd"
        self.filepath = Path.joinpath(self.dir, self.filename)

        # I am tracking sub-second time in case I want to do something with average time per keypress
        self.start_time = time.time_ns()
        self.elapsed = ""
        try:
            os.mkdir(self.dir)
        except FileExistsError:
            pass

        self.margin_top = 2
        self.margin_bottom = self.margin_top
        self.margin_sides = 6

        # used to track when new words start for live word count
        self.in_word = False
        self.live_word_count = 0

        # Text blanking related variables
        self.last_keypress_time = time.time()
        self.blank = False
        self.text_content = []
        self.current_line = 0
        self.current_col = 0

    def write_char(self, win, char):
        self.outfile.write(char)

        y, x = win.getyx()
        self.text_content.append((char, y, x))

        if self.timeout():
            self.show_text(win)

        self.last_keypress_time = time.time()

        win.addstr(char)
        win.refresh()

        if char == "\n":
            self.current_line += 1
            self.current_col = 0
        else:
            self.current_col += 1

    def blank_text(self, win):
        # Only run once
        if self.blank:
            return
        cursor_y, cursor_x = win.getyx()  # Save cursor position
        win.clear()
        win.refresh()
        win.move(cursor_y, cursor_x)  # Restore cursor position
        self.blank = True

    def show_text(self, win):
        cursor_y, cursor_x = win.getyx()  # Save cursor position
        win.clear()
        for char, y, x in self.text_content:
            try:
                win.addstr(y, x, char)
                win.refresh()  # Refresh after each character to ensure proper display
            except curses.error:
                pass  # Handle potential curses errors when writing at window boundaries
        win.move(cursor_y, cursor_x)  # Restore cursor position
        self.blank = False

    def timeout(self):
        return time.time() - self.last_keypress_time > BLANK_TIMEOUT

    def make_win(self):
        # other things will depend on this, not sure if this is the safest location
        self.screen_height, self.screen_width = self.stdscr.getmaxyx()

        win_height = self.screen_height - self.margin_top - self.margin_bottom
        win_width = self.screen_width - self.margin_sides * 2
        win_x = self.margin_sides
        win_y = self.margin_top

        win = curses.newwin(win_height, win_width, win_y, win_x)

        return win

    # True - within new word
    # False - within whitespace
    def end_word(self):
        self.in_word = False

    def start_word(self):
        if self.in_word is False:
            self.live_word_count += 1
        self.in_word = True

    def status_bar(self, stdscr, raw_string, gap):
        string = str(raw_string)

        # start from top right stacking strings
        self.status_y -= gap + len(string)
        stdscr.addstr(0, self.status_y, string, curses.color_pair(GRAY_PAIR))

    def update_status_bar(self, stdscr, win):
        delta = self.elapsed_seconds()
        if self.elapsed != delta:
            self.status_y = self.screen_width
            self.elapsed = delta
            timer = str(timedelta(seconds=delta))
            try:
                wpm = int(self.live_word_count / (delta / 60))
            except ZeroDivisionError:
                wpm = 0
            cursor_y, cursor_x = win.getyx()
            stdscr.addstr(0, 0, " " * self.screen_width)
            self.status_bar(stdscr, timer, 2)
            self.status_bar(stdscr, self.live_word_count, 2)
            self.status_bar(stdscr, "Words:", 1)
            self.status_bar(stdscr, wpm, 2)
            self.status_bar(stdscr, "WPM:", 1)
            win.move(cursor_y, cursor_x)
            stdscr.refresh()

    def sanitize_title(self, title):
        # Replace spaces with underscores
        title = title.replace(" ", "_")
        # Remove any non-alphanumeric characters except underscores
        title = re.sub(r"[^a-zA-Z0-9_]", "", title)
        return title

    def move_file_to_category(self, category, title):
        # Sanitize the category name
        sanitized_category = self.sanitize_title(category)

        # Create category directory if it doesn't exist
        category_dir = Path.joinpath(self.dir, sanitized_category)
        try:
            os.makedirs(category_dir)
        except FileExistsError:
            pass

        # Sanitize the title for the filename
        sanitized_title = self.sanitize_title(title)

        # Create new filename with sanitized title
        new_filename = f"{self.filename[:-4]}_{sanitized_title}.Rmd"
        new_filepath = Path.joinpath(category_dir, new_filename)

        # Move the file
        shutil.move(self.filepath, new_filepath)
        self.filepath = new_filepath

    def cleanup(self):
        diff_seconds = self.elapsed_seconds()
        human_readable = humanize.precisedelta(diff_seconds)
        print(f"Session time: {human_readable}")

        word_count = 0
        with open(self.filepath, "r") as file:
            for line in file:
                words = line.split()
                word_count += len(words)

        print(f"Words: {word_count}")

        wpm = int(word_count / (diff_seconds / 60.0))
        print(f"WPM: {wpm}")

        # Get existing categories
        categories = [d.name for d in self.dir.iterdir() if d.is_dir()]

        # Set up tab completion
        completer = CategoryCompleter(categories)
        readline.set_completer(completer.complete)
        readline.parse_and_bind("tab: complete")

        # Prompt for category and title
        print("\nPlease enter details for your writing:")
        category = input("Category: ").strip()
        title = input("Title: ").strip()

        if not category:
            category = "uncategorized"
        if not title:
            title = "untitled"

        # Add title to the top of the file
        with open(self.filepath, "r") as file:
            content = file.read()

        with open(self.filepath, "w") as file:
            file.write(f"## {title}\n\n{content}")

        self.move_file_to_category(category, title)
        print(f"\nFile written to: {self.filepath}")

    def inner_loop(self, stdscr, win):
        try:
            key = win.getch()
        except KeyboardInterrupt:
            self.running = False
            return

        if key == -1:
            if self.timeout():
                self.blank_text(win)
            return

        if key == ord(" "):  # Space key
            self.end_word()
            self.write_char(win, " ")
        elif key == 10 or key == 13:  # Enter key (ASCII 10 or 13)
            self.end_word()
            self.write_char(win, "\n")
        elif 32 <= key <= 126:  # Printable ASCII characters
            self.start_word()
            self.write_char(win, f"{chr(key)}")

    def curses_loop(self, stdscr):
        stdscr.clear()
        stdscr.refresh()

        stdscr.timeout(50)

        curses.start_color()
        curses.init_color(GRAY_COLOR, GRAY_LEVEL, GRAY_LEVEL, GRAY_LEVEL)
        curses.init_pair(GRAY_PAIR, GRAY_COLOR, curses.COLOR_BLACK)

        # Is this bad practice?
        self.stdscr = stdscr

        win = self.make_win()
        win.scrollok(True)
        win.nodelay(1)  # Make getch() non-blocking on writing window

        with open(self.filepath, "a") as outfile:
            # Is this bad practice?
            self.outfile = outfile
            while self.running:
                self.inner_loop(stdscr, win)
                self.update_status_bar(stdscr, win)

    def seconds(self, ns):
        # convert nanoseconds from time_ns to seconds
        return int(ns / 1e9)

    def elapsed_seconds(self):
        now = time.time_ns()
        diff_ns = now - self.start_time
        return self.seconds(diff_ns)

    def main(self):
        curses.wrapper(self.curses_loop)
        self.cleanup()


if __name__ == "__main__":
    bonesWriter = BonesWriter()
    bonesWriter.main()
