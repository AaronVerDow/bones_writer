import curses
import time
import humanize
from datetime import datetime

class BonesWriter:
    def __init__(self):
        self.running = True
        now = datetime.now()
        self.filename = now.strftime("%Y-%m-%d_%H-%M-%S")
        self.filename += ".txt" 
        self.start_time = time.time_ns()

    def write_char(self, char):
        self.stdscr.addstr(char)
        self.outfile.write(char)
        self.stdscr.refresh()

    def inner_loop(self):
        try:
            key = self.stdscr.getch()
        except KeyboardInterrupt:
            self.running = False
            return
        if key == -1:
            return
        elif key == ord(' '):  # Space key
            self.write_char(" ")
        elif key == 10 or key == 13:  # Enter key (ASCII 10 or 13)
            self.write_char("\n")
        elif 32 <= key <= 126:  # Printable ASCII characters
            self.write_char(f"{chr(key)}")

    def curses_loop(self, stdscr):
        # curses.curs_set(0)  # Hide the cursor
        stdscr.nodelay(1)   # Make getch() non-blocking
        stdscr.timeout(100) # Refresh every 100ms
        stdscr.scrollok(True)

        # Is this bad practice?
        self.stdscr = stdscr

        with open(self.filename, "a") as outfile:
            # Is this bad practice?
            self.outfile = outfile
            while self.running:
                self.inner_loop()

    def cleanup(self):
        end_time = time.time_ns()
        diff_ns = end_time - self.start_time
        diff_seconds = int(diff_ns / 1e9)
        human_readable = humanize.precisedelta(diff_seconds)
        print(f"Session time: {human_readable}")

        word_count = 0
        with open(self.filename, "r") as file:
            for line in file:
                words = line.split()
                word_count += len(words)

        print(f"Words: {word_count}")


        
    def main(self):
        curses.wrapper(self.curses_loop)
        self.cleanup()

if __name__ == '__main__':
    bonesWriter = BonesWriter()
    bonesWriter.main()
