import curses
import time
import humanize
import os
from datetime import datetime
from pathlib import Path

class BonesWriter:
    def __init__(self):
        self.running = True
        now = datetime.now()
        self.dir = Path.joinpath(Path.home(), "Documents", "bones")
        self.filename = now.strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
        self.filepath = Path.joinpath(self.dir, self.filename)
        self.start_time = time.time_ns()
        try:
            os.mkdir(self.dir)
        except FileExistsError:
            pass

        self.margin_top = 2
        self.margin_bottom = self.margin_top
        self.margin_sides = 6

    def write_char(self, win, char):
        self.outfile.write(char)
        win.addstr(char)
        win.refresh()

    def make_win(self):
        screen_height, screen_width = self.stdscr.getmaxyx()
        win_height = screen_height - self.margin_top - self.margin_bottom
        win_width = screen_width - self.margin_sides * 2
        win_x = self.margin_sides
        win_y = self.margin_top

        win = curses.newwin(win_height, win_width, win_y, win_x)

        return win

    def inner_loop(self, win):
        try:
            key = win.getch()
        except KeyboardInterrupt:
            self.running = False
            return
        if key == -1:
            return
        elif key == ord(' '):  # Space key
            self.write_char(win, " ")
        elif key == 10 or key == 13:  # Enter key (ASCII 10 or 13)
            self.write_char(win, "\n")
        elif 32 <= key <= 126:  # Printable ASCII characters
            self.write_char(win, f"{chr(key)}")

    def curses_loop(self, stdscr):
        # curses.curs_set(0)  # Hide the cursor
        stdscr.nodelay(1)   # Make getch() non-blocking
        stdscr.timeout(100) # Refresh every 100ms
        stdscr.scrollok(True)

        # Is this bad practice?
        self.stdscr = stdscr

        win = self.make_win()

        with open(self.filepath, "a") as outfile:
            # Is this bad practice?
            self.outfile = outfile
            while self.running:
                self.inner_loop(win)

    def cleanup(self):
        end_time = time.time_ns()
        diff_ns = end_time - self.start_time
        diff_seconds = int(diff_ns / 1e9)
        human_readable = humanize.precisedelta(diff_seconds)
        print(f"Session time: {human_readable}")

        word_count = 0
        with open(self.filepath, "r") as file:
            for line in file:
                words = line.split()
                word_count += len(words)

        print(f"Words: {word_count}")

        wpm = word_count / ( diff_seconds / 60.0 )

        print(f"WPM: {wpm}")

    def main(self):
        curses.wrapper(self.curses_loop)
        self.cleanup()

if __name__ == '__main__':
    bonesWriter = BonesWriter()
    bonesWriter.main()
