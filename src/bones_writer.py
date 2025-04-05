import curses
import time
import humanize
import os
from datetime import datetime, timedelta
from pathlib import Path

# 0-1000
GRAY_LEVEL=200
GRAY_PAIR=1
GRAY_COLOR=100

class BonesWriter:
    def __init__(self):
        self.running = True
        now = datetime.now()
        self.dir = Path.joinpath(Path.home(), "Documents", "bones")
        self.filename = now.strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
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
        self.new_word = None
        self.live_word_count = 0

    def write_char(self, win, char):
        self.outfile.write(char)
        win.addstr(char)
        win.refresh()

    def make_win(self):
        # other things will depend on this, not sure if this is the safest location
        self.screen_height, self.screen_width = self.stdscr.getmaxyx()

        win_height = self.screen_height - self.margin_top - self.margin_bottom
        win_width = self.screen_width - self.margin_sides * 2
        win_x = self.margin_sides
        win_y = self.margin_top

        win = curses.newwin(win_height, win_width, win_y, win_x)

        return win

    def live_word_counter(self):
        if self.new_word is True:
            return
        if self.new_word is not None:
            self.live_word_count += 1
        self.new_word = True

    def status_bar(self, stdscr, raw_string, gap):
        string = str(raw_string)
        # start from top right stacking strings
        self.status_y -= gap + len(string)
        stdscr.addstr(0, self.status_y, string, curses.color_pair(GRAY_PAIR))

    def inner_loop(self, stdscr, win):
        try:
            key = win.getch()
        except KeyboardInterrupt:
            self.running = False
            return
        if key == -1:
            pass
        elif key == ord(' '):  # Space key
            self.live_word_counter()
            self.write_char(win, " ")
        elif key == 10 or key == 13:  # Enter key (ASCII 10 or 13)
            self.live_word_counter()
            self.write_char(win, "\n")
        elif 32 <= key <= 126:  # Printable ASCII characters
            self.new_word = False
            self.write_char(win, f"{chr(key)}")

        # display status bar
        # currently only updates during keypresses

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
            stdscr.addstr(0, 0, ' ' * self.screen_width)
            self.status_bar(stdscr, timer, 2)
            self.status_bar(stdscr, self.live_word_count, 2)
            self.status_bar(stdscr, "Words:", 1)
            self.status_bar(stdscr, wpm, 2)
            self.status_bar(stdscr, "WPM:", 1)
            win.move(cursor_y, cursor_x)
            stdscr.refresh()

    def curses_loop(self, stdscr):
        # curses.curs_set(0)  # Hide the cursor
        stdscr.nodelay(1)   # Make getch() non-blocking
        stdscr.timeout(100) # Refresh every 100ms

        curses.start_color()
        curses.init_color(GRAY_COLOR, GRAY_LEVEL, GRAY_LEVEL, GRAY_LEVEL)
        curses.init_pair(GRAY_PAIR, GRAY_COLOR, curses.COLOR_BLACK)

        # Is this bad practice?
        self.stdscr = stdscr

        win = self.make_win()
        win.scrollok(True)

        with open(self.filepath, "a") as outfile:
            # Is this bad practice?
            self.outfile = outfile
            while self.running:
                self.inner_loop(stdscr, win)

    def seconds(self, ns):
        # convert nanoseconds from time_ns to seconds
        return int(ns / 1e9)

    def elapsed_seconds(self):
        now = time.time_ns()
        diff_ns = now - self.start_time
        return self.seconds(diff_ns)

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

        wpm = int(word_count / ( diff_seconds / 60.0 ))

        print(f"WPM: {wpm}")

    def main(self):
        curses.wrapper(self.curses_loop)
        self.cleanup()

if __name__ == '__main__':
    bonesWriter = BonesWriter()
    bonesWriter.main()
