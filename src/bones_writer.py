import curses
import time
import humanize
import os
import shutil
import readline
import re
import typer
import yaml
from spellchecker import SpellChecker
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any
from tinydb import TinyDB, Query
import matplotlib.pyplot as plt
import git


# Constants
# required by curses to define custom color, changes nothing
GRAY_PAIR: int = 1
GRAY_COLOR: int = 100
TEXT_COLOR_START: int = 200  # Starting color number for text colors
NUM_FADE_STEPS: int = 32  # Number of brightness levels for fading
FADE_INTERVAL: float = 0.1  # Time in seconds between fade steps

# Defaults
# I don't know how I want to handle these yet.
CONFIG_DIR: Path = Path.joinpath(Path.home(), ".config", "bones_writer")
OUTPUT_DIR: Path = Path.joinpath(Path.home(), "Documents", "bones")
TRASH_DIR: Path = Path("/tmp")
CONFIG: Path = Path.joinpath(CONFIG_DIR, "config.yaml")
BLANK_TIMEOUT: float = 5.0  # Timeout in seconds before blanking the text
STATS_BRIGHTNESS: int = 200  # adjust for darknes of live stats, 0-1000

# Default configuration
DEFAULT_CONFIG: Dict[str, Any] = {
    "directory": OUTPUT_DIR,
    "trash_directory": TRASH_DIR,
    "stats_brightness": STATS_BRIGHTNESS,
    "blank_timeout": BLANK_TIMEOUT,
}


class CategoryCompleter:
    def __init__(self, categories: list[str]) -> None:
        self.categories = categories

    def complete(self, text: str, state: int) -> str | None:
        options = [i for i in self.categories if i.startswith(text)]
        if state < len(options):
            return options[state]
        return None


class BonesWriter:
    def __init__(
        self,
        directory: Path | None = None,
        config_path: Path | None = None,
        blank_timeout: float | None = None,
        stats_brightness: int | None = None,
    ) -> None:
        self.running = True
        now = datetime.now()

        # Load configuration
        if config_path is None:
            config_path = CONFIG
        self.config = self.load_config(config_path)

        if directory is not None:
            self.dir = directory
        else:
            self.dir = Path(self.config["directory"])

        self.db_path = Path.joinpath(self.dir, ".bones_database.json")
        # Ensure the directory exists
        self.dir.mkdir(parents=True, exist_ok=True)
        self.db = TinyDB(self.db_path)
        self.stats_table = self.db.table("sessions")

        if blank_timeout is not None:
            self.config["blank_timeout"] = blank_timeout

        if stats_brightness is not None:
            self.config["stats_brightness"] = stats_brightness

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

        # Text fading related variables
        self.last_keypress_time = time.time()
        self.blank = False
        self.text_content: list[tuple[str, int, int, int]] = []  # (char, y, x, color_pair)
        self.current_line = 0
        self.current_col = 0
        self.current_fade_step = 0
        self.last_fade_time = time.time()

        """Check if the given path is within a git repository."""

        try:
            self.repo = git.Repo(self.dir, search_parent_directories=True)
            print("Using git repository")
        except git.InvalidGitRepositoryError:
            self.repo = None

    def load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from file or return defaults if not found."""
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                return {**DEFAULT_CONFIG, **config}
        except (FileNotFoundError, yaml.YAMLError):
            # Create config directory if it doesn't exist
            config_path.parent.mkdir(parents=True, exist_ok=True)
            # Write default config
            with open(config_path, "w") as f:
                yaml.dump(DEFAULT_CONFIG, f)
            return DEFAULT_CONFIG

    def write_char(self, win: curses.window, char: str) -> None:
        self.outfile.write(char)

        y, x = win.getyx()
        self.text_content.append((char, y, x, 2))  # 2 is the first text color pair (full brightness)

        if self.timeout():
            self.show_text(win)

        self.last_keypress_time = time.time()
        self.current_fade_step = 0  # Reset fade step on new input

        win.addstr(char, curses.color_pair(2))  # Use full brightness color pair
        win.refresh()

        if char == "\n":
            self.current_line += 1
            self.current_col = 0
        else:
            self.current_col += 1

    def blank_text(self, win: curses.window) -> None:
        # Only run once per fade step
        now = time.time()
        if now - self.last_fade_time < FADE_INTERVAL:
            return

        self.last_fade_time = now
        cursor_y, cursor_x = win.getyx()  # Save cursor position

        if self.current_fade_step < NUM_FADE_STEPS:
            win.clear()
            # At final step, don't show any text
            if self.current_fade_step == NUM_FADE_STEPS - 1:
                win.refresh()
                self.blank = True
            else:
                # Update color pair for all text
                new_color_pair = self.current_fade_step + 2
                for char, y, x, _ in self.text_content:
                    try:
                        win.addstr(y, x, char, curses.color_pair(new_color_pair))
                    except curses.error:
                        pass
                win.refresh()
            self.current_fade_step += 1

        win.move(cursor_y, cursor_x)  # Restore cursor position

    def show_text(self, win: curses.window) -> None:
        cursor_y, cursor_x = win.getyx()  # Save cursor position
        win.clear()
        for char, y, x, color_pair in self.text_content:
            try:
                win.addstr(y, x, char, curses.color_pair(2))  # Always show at full brightness
                win.refresh()  # Refresh after each character to ensure proper display
            except curses.error:
                pass  # Handle potential curses errors when writing at window boundaries
        win.move(cursor_y, cursor_x)  # Restore cursor position
        self.blank = False
        self.current_fade_step = 0

    def timeout(self) -> bool:
        """Check if it's time to start fading the text"""
        return time.time() - self.last_keypress_time > self.config["blank_timeout"]

    def make_win(self) -> curses.window:
        # other things will depend on this, not sure if this is the safest location
        self.screen_height, self.screen_width = self.stdscr.getmaxyx()

        win_height = self.screen_height - self.margin_top - self.margin_bottom
        win_width = self.screen_width - self.margin_sides * 2
        win_x = self.margin_sides
        win_y = self.margin_top

        win = curses.newwin(win_height, win_width, win_y, win_x)

        return win

    def status_bar(self, stdscr: curses.window, raw_string: str | int, gap: int) -> None:
        string = str(raw_string)

        # start from top right stacking strings
        self.status_y -= gap + len(string)
        stdscr.addstr(0, self.status_y, string, curses.color_pair(GRAY_PAIR))

    def update_status_bar(self, stdscr: curses.window, win: curses.window) -> None:
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

    def sanitize_path(self, title: str) -> str:
        # Replace spaces with underscores
        title = title.replace(" ", "_")
        # Remove any non-alphanumeric characters except underscores
        title = re.sub(r"[^a-zA-Z0-9_]", "", title)
        return title

    def rename_file(self, category: str, title: str) -> None:
        # Sanitize the category name
        sanitized_category = self.sanitize_path(category)

        # Create category directory if it doesn't exist
        category_dir = Path.joinpath(self.dir, sanitized_category)
        try:
            os.makedirs(category_dir)
        except FileExistsError:
            pass

        # Sanitize the title for the filename
        sanitized_title = self.sanitize_path(title)

        # Create new filename with sanitized title
        new_filename = f"{self.filename[:-4]}_{sanitized_title}.Rmd"
        new_filepath = Path.joinpath(category_dir, new_filename)

        # Move the file
        shutil.move(self.filepath, new_filepath)
        self.filepath = new_filepath

    def check_spelling(self) -> int:
        """Check the spelling of words in the file and return the percentage of correctly spelled words."""
        spell = SpellChecker()

        # Read the file content
        with open(self.filepath, "r") as file:
            content = file.read()

        # Split content into words and filter out non-word characters
        words = re.findall(r"\b\w+\b", content.lower())

        if not words:
            return 0  # Return 0% if no words found

        # Find misspelled words
        misspelled = spell.unknown(words)

        # Calculate percentage of correctly spelled words
        total_words = len(words)
        correct_words = total_words - len(misspelled)
        percentage = int((correct_words / total_words) * 100)

        return percentage

    def cleanup(self) -> None:
        diff_seconds = self.elapsed_seconds()
        human_readable = humanize.precisedelta(diff_seconds)

        word_count = 0
        with open(self.filepath, "r") as file:
            for line in file:
                words = line.split()
                word_count += len(words)

        wpm = int(word_count / (diff_seconds / 60.0))
        spelling_percentage = self.check_spelling()

        print(f"Session time: {human_readable}")
        print(f"Words: {word_count}")
        print(f"WPM: {wpm}")
        print(f"Spelling accuracy: {spelling_percentage}%")

        category, title = self.prompt_name()
        
        # If both category and title are empty, move file to trash directory and return
        if category is None and title is None:
            # Ensure trash directory exists
            trash_dir = Path(self.config["trash_directory"])
            trash_dir.mkdir(parents=True, exist_ok=True)
            
            # Move file to trash with timestamp to avoid conflicts
            trash_filename = f"{int(time.time())}_{self.filepath.name}"
            trash_filepath = Path.joinpath(trash_dir, trash_filename)
            shutil.move(self.filepath, trash_filepath)
            print(f"\nNo category or title provided. File moved to trash: {trash_filepath}")
            return

        self.rename_file(category, title) # updates self.filepath
        self.add_title(self.filepath, title)
        print(f"\nFile written to: {self.filepath}")

        # Store session data in TinyDB
        session_data = {
            "timestamp": datetime.now().isoformat(),
            "filepath": str(self.relative_filepath(self.filepath)),
            "duration_seconds": diff_seconds,
            "word_count": word_count,
            "wpm": wpm,
            "spelling_accuracy": spelling_percentage,
        }
        self.stats_table.insert(session_data)

        self.git_commit_and_push([self.filepath, self.db_path], f"{category}: {title}")

    def add_title(self, path: Path, title: str) -> None:
        # Add title to the top of the file
        # There may be a more efficient method

        with open(path, "r") as file:
            content = file.read()

        with open(self.filepath, "w") as file:
            file.write(f"## {title}\n\n{content}")

    def prompt_name(self) -> tuple[str | None, str | None]:
        # Set up tab completion for categories
        categories = [d.name for d in self.dir.iterdir() if d.is_dir()]
        completer = CategoryCompleter(categories)
        readline.set_completer(completer.complete)
        readline.parse_and_bind("tab: complete")

        print("\nPlease enter details for your writing:")
        category = input("Category: ").strip()
        title = input("Title: ").strip()

        # If both are empty, return None for both
        if not category and not title:
            return None, None

        # Otherwise use defaults if either is empty
        if not category:
            category = "uncategorized"
        if not title:
            title = "untitled"

        return category, title


    def inner_loop(self, win: curses.window) -> None:
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
            self.in_word = False
            self.write_char(win, " ")
        elif key == 10 or key == 13:  # Enter key (ASCII 10 or 13)
            self.in_word = False
            self.write_char(win, "\n")
        elif 32 <= key <= 126:  # Printable ASCII characters
            if self.in_word is False:
                self.live_word_count += 1
            self.in_word = True
            self.write_char(win, f"{chr(key)}")

    def curses_loop(self, stdscr: curses.window) -> None:
        stdscr.clear()
        stdscr.refresh()

        stdscr.timeout(50)

        curses.start_color()
        # Initialize stats color
        curses.init_color(
            GRAY_COLOR,
            self.config["stats_brightness"],
            self.config["stats_brightness"],
            self.config["stats_brightness"],
        )
        curses.init_pair(GRAY_PAIR, GRAY_COLOR, curses.COLOR_BLACK)

        # Initialize text fading colors
        for i in range(NUM_FADE_STEPS):
            # Make the last step completely transparent (brightness 0)
            if i == NUM_FADE_STEPS - 1:
                brightness = 0
            else:
                # Distribute remaining brightness levels across other steps
                brightness = 1000 - (i * (1000 // (NUM_FADE_STEPS - 1)))
                brightness = max(1, brightness)  # Ensure non-zero brightness for visible steps
            
            color_num = TEXT_COLOR_START + i
            curses.init_color(color_num, brightness, brightness, brightness)
            curses.init_pair(i + 2, color_num, curses.COLOR_BLACK)  # Start from pair 2 since 1 is used for stats

        # Is this bad practice?
        self.stdscr = stdscr

        win = self.make_win()
        win.scrollok(True)
        win.nodelay(True)  # Make getch() non-blocking on writing window

        with open(self.filepath, "a") as outfile:
            # Is this bad practice?
            self.outfile = outfile
            while self.running:
                self.inner_loop(win)
                self.update_status_bar(stdscr, win)

    def seconds(self, ns: int) -> int:
        # convert nanoseconds from time_ns to seconds
        return int(ns / 1e9)

    def elapsed_seconds(self) -> int:
        now = time.time_ns()
        diff_ns = now - self.start_time
        return self.seconds(diff_ns)

    def main(self) -> None:
        self.pause_on_dirty_repo()
        curses.wrapper(self.curses_loop)
        self.cleanup()

    def plot_writing_stats(self, time_delta_days: int) -> None:
        """
        Query the database for writing sessions within the specified time range and plot the data.
        Only includes sessions with word counts >= 100.

        Args:
            time_delta_days (int): Number of days to look back for writing sessions.
        """
        # Query the database for sessions after the cutoff time with word count >= 100
        sessions = self.query_high_word_count_sessions(time_delta_days)

        if not sessions:
            print("No writing sessions with 100+ words found in the specified time range.")
            return

        # Extract data for plotting
        timestamps = [datetime.fromisoformat(session["timestamp"]) for session in sessions]
        durations = [session["duration_seconds"] / 60 for session in sessions]  # Convert to minutes
        word_counts = [session["word_count"] for session in sessions]
        wpms = [session["wpm"] for session in sessions]
        spelling_accuracies = [session["spelling_accuracy"] for session in sessions]

       # Create a figure with subplots
        fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(10, 12))
        fig.suptitle(f"Writing Stats for the Last {time_delta_days} Days (100+ words only)")

        # Plot duration
        ax1.plot(timestamps, durations, marker="o", color="b")
        ax1.set_ylabel("Duration (min)")
        ax1.grid(True)

        # Plot word count
        ax2.plot(timestamps, word_counts, marker="o", color="g")
        ax2.set_ylabel("Word Count")
        ax2.grid(True)

        # Plot WPM
        ax3.plot(timestamps, wpms, marker="o", color="r")
        ax3.set_ylabel("WPM")
        ax3.grid(True)

        # Plot spelling accuracy
        ax4.plot(timestamps, spelling_accuracies, marker="o", color="m")
        ax4.set_ylabel("Spelling Accuracy (%)")
        ax4.grid(True)

        # Rotate x-axis labels for better readability
        for ax in [ax1, ax2, ax3, ax4]:
            plt.sca(ax)
            plt.xticks(rotation=45)

        plt.tight_layout()
        plt.show()

    def query_high_word_count_sessions(self, time_delta_days: int) -> list[dict[str, Any]]:
        """
        Query the database for writing sessions within the specified time range and ignore entries with a word count less than 100.

        Args:
            time_delta_days (int): Number of days to look back for writing sessions.

        Returns:
            list[dict[str, Any]]: A list of sessions with word counts >= 100.
        """
        # Calculate the cutoff time
        cutoff_time = datetime.now() - timedelta(days=time_delta_days)

        # Query the database for sessions after the cutoff time and with word count >= 100
        WritingSession = Query()
        sessions = self.stats_table.search(
            (WritingSession.timestamp >= cutoff_time.isoformat()) & (WritingSession.word_count >= 100)
        )

        return sessions

    def pause_on_dirty_repo(self) -> None:
        error: str | None = self.check_repo_status()
        if error is None:
            return
        print(error)
        exit(1)

    def check_repo_status(self) -> str | None:
        """
        Check the status of the Git repository to determine if there are remote changes
        that would prevent pushing a commit, and if there are uncommitted changes locally.

        Returns:
            str: A message indicating the status of the repository.
        """
        if self.repo is None:
            # return "No Git repository found."
            return None

        try:
            # Check for uncommitted changes (staged or unstaged)
            if self.repo.is_dirty(untracked_files=False):
                return "There are uncommitted changes in the working tree."

            # Fetch the latest changes from the remote
            for remote in self.repo.remotes:
                remote.fetch()

            # Get the active branch
            active_branch = self.repo.active_branch
            remote_name = f"origin/{active_branch.name}"

            # Check if the remote branch exists
            if remote_name not in self.repo.refs:
                return f"Remote branch '{remote_name}' does not exist."

            # Compare the local and remote branches
            local_commit = self.repo.head.commit
            remote_commit = self.repo.refs[remote_name].commit

            if local_commit == remote_commit:
                return None
            else:
                return "Local branch is behind the remote. Pull changes before pushing."

        except git.GitCommandError as e:
            return f"Error checking repository status: {e}"

    def git_commit_and_push(self, file_paths: list[Path], commit_message: str) -> None:
        """
        Add files to Git, commit them with the provided message, and push the changes.

        Args:
            file_paths (list[Path]): The paths of the files to add and commit.
            commit_message (str): The commit message to use.
        """
        if self.repo is None:
            return None

        try:
            # Add the files to Git
            for file_path in file_paths:
                self.repo.git.add(str(file_path))

            # Commit the changes
            self.repo.git.commit("-m", commit_message)

            # Push the changes to the remote
            self.repo.git.push()
            print("Pushed upstream")
        except git.GitCommandError as e:
            raise RuntimeError(f"Failed to commit and push changes: {e}")

    def relative_filepath(self, filepath: Path) -> Path:
        """
        Returns the relative path from the repository root to the file.
        If no repository exists, returns the absolute filepath.

        Args:
            filepath (Path): The file path to resolve.

        Returns:
            Path: The relative path from the repo root or the absolute path.
        """
        if self.repo is None:
            return filepath
        return Path(os.path.relpath(filepath, self.repo.working_dir))


app = typer.Typer()


@app.command()
def main(
    directory: Path | None = None,
    config: Path | None = None,
    blank_timeout: float | None = typer.Option(None, help="Timeout in seconds before blanking the text"),
    stats_brightness: int | None = typer.Option(
        None,
        help="Brightness level for stats display (0-1000)",
        min=0,
        max=1000,
    ),
) -> None:
    """Start the bones writer application."""
    writer = BonesWriter(
        directory=directory,
        config_path=config,
        blank_timeout=blank_timeout,
        stats_brightness=stats_brightness,
    )
    writer.main()


@app.command()
def stats(
    days: int = typer.Option(7, help="Number of days to look back for writing sessions"),
    config: Path | None = None,
) -> None:
    """
    Show writing statistics for the specified time period.
    """
    writer = BonesWriter(config_path=config)
    writer.plot_writing_stats(days)


if __name__ == "__main__":
    app()
