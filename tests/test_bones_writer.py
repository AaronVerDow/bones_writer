import pytest
from unittest.mock import patch, MagicMock
from src.bones_writer import BonesWriter
import os
from pathlib import Path
import time


class MockCursesWindow:
    def __init__(self):
        self.content = []
        self.cursor_y = 0
        self.cursor_x = 0
        self.height = 24
        self.width = 80

    def addstr(self, *args):
        # Support addstr(string), addstr(y, x, string), addstr(y, x, string, attr)
        if len(args) == 1:
            string = args[0]
            self.content.append((self.cursor_y, self.cursor_x, string))
            self.cursor_x += len(str(string))
        elif len(args) == 3:
            y, x, string = args
            self.content.append((y, x, string))
            self.cursor_y, self.cursor_x = y, x + len(str(string))
        elif len(args) == 4:
            y, x, string, attr = args
            self.content.append((y, x, string, attr))
            self.cursor_y, self.cursor_x = y, x + len(str(string))
        else:
            raise TypeError(f"addstr called with unexpected arguments: {args}")

    def getyx(self):
        return self.cursor_y, self.cursor_x

    def move(self, y, x):
        self.cursor_y = y
        self.cursor_x = x

    def getch(self):
        return -1  # Default to no input

    def refresh(self):
        pass

    def clear(self):
        self.content = []


@pytest.fixture
def mock_stdscr():
    return MockCursesWindow()


@pytest.fixture
def bones_writer():
    writer = BonesWriter()
    yield writer
    # Cleanup after tests
    if os.path.exists(writer.filepath):
        os.remove(writer.filepath)


def test_write_char(bones_writer, mock_stdscr):
    bones_writer.outfile = MagicMock()  # Mock the outfile
    # Test writing a single character
    bones_writer.write_char(mock_stdscr, "a")
    # Verify the character was written to the window
    assert mock_stdscr.content[-1][2] == "a"
    # Verify the character was written to the file
    bones_writer.outfile.write.assert_called_with("a")


def test_word_counting(bones_writer, mock_stdscr):
    bones_writer.outfile = MagicMock()  # Mock the outfile
    # Test word counting functionality
    # Write a word
    bones_writer.write_char(mock_stdscr, "h")
    bones_writer.start_word()
    bones_writer.write_char(mock_stdscr, "e")
    bones_writer.start_word()
    bones_writer.write_char(mock_stdscr, "l")
    bones_writer.start_word()
    bones_writer.write_char(mock_stdscr, "l")
    assert bones_writer.live_word_count == 1
    bones_writer.start_word()
    bones_writer.write_char(mock_stdscr, "o")
    bones_writer.start_word()
    bones_writer.write_char(mock_stdscr, " ")
    bones_writer.end_word()
    bones_writer.write_char(mock_stdscr, " ")
    bones_writer.end_word()
    assert bones_writer.live_word_count == 1
    bones_writer.write_char(mock_stdscr, "w")
    bones_writer.start_word()
    bones_writer.write_char(mock_stdscr, "0")
    bones_writer.start_word()
    assert bones_writer.live_word_count == 2


def test_blank_text(bones_writer, mock_stdscr):
    bones_writer.outfile = MagicMock()  # Mock the outfile
    # Test text blanking functionality
    # Write some text
    bones_writer.write_char(mock_stdscr, "t")
    bones_writer.write_char(mock_stdscr, "e")
    bones_writer.write_char(mock_stdscr, "s")
    bones_writer.write_char(mock_stdscr, "t")
    # Blank the text
    bones_writer.blank_text(mock_stdscr)
    # Verify the window was cleared
    assert len(mock_stdscr.content) == 0
    assert bones_writer.blank == True


def test_status_bar(bones_writer, mock_stdscr):
    # Test status bar updates
    bones_writer.screen_width = 80
    bones_writer.status_y = 80
    with patch("curses.color_pair", return_value=0):
        # Update status bar
        bones_writer.status_bar(mock_stdscr, "Test", 2)
    # Verify status bar content
    assert len(mock_stdscr.content) > 0
    assert mock_stdscr.content[0][2] == "Test"


def test_initialization(bones_writer):
    """Test that BonesWriter initializes with correct default values"""
    assert bones_writer.running is True
    assert bones_writer.margin_top == 2
    assert bones_writer.margin_bottom == 2
    assert bones_writer.margin_sides == 6
    assert bones_writer.live_word_count == 0
    assert bones_writer.in_word is False
    assert bones_writer.blank is False


def test_file_creation(bones_writer):
    """Test that the output file is created in the correct location"""
    assert bones_writer.dir == Path.joinpath(Path.home(), "Documents", "bones")
    # Simulate file creation
    with open(bones_writer.filepath, "w") as f:
        f.write("")
    assert bones_writer.filepath.exists()


def test_timeout_function(bones_writer):
    """Test the text blanking timeout functionality"""
    assert (
        bones_writer.timeout() is False
    )  # Should be False immediately after initialization

    # Simulate waiting longer than BLANK_TIMEOUT
    bones_writer.last_keypress_time = time.time() - 6.0  # BLANK_TIMEOUT is 5.0
    assert bones_writer.timeout() is True


def test_make_win(bones_writer):
    """Test window creation"""
    mock_stdscr = MagicMock()
    mock_stdscr.getmaxyx.return_value = (24, 80)
    bones_writer.stdscr = mock_stdscr
    # Patch curses.newwin to avoid needing initscr
    with patch("curses.newwin", return_value=MagicMock(getmaxyx=lambda: (20, 68))):
        win = bones_writer.make_win()
        assert win is not None
        assert win.getmaxyx() == (20, 68)


def test_cleanup(bones_writer):
    """Test cleanup functionality"""
    # Write some content to the file
    with open(bones_writer.filepath, "w") as f:
        f.write("test content\n")
    # Patch elapsed_seconds to avoid ZeroDivisionError
    with patch.object(bones_writer, "elapsed_seconds", return_value=60):
        # Mock the input calls
        with patch("builtins.input", side_effect=["test_category", "test_title"]):
            bones_writer.cleanup()
    # Verify file exists and has content
    assert os.path.exists(bones_writer.filepath)
    with open(bones_writer.filepath, "r") as f:
        content = f.read()
        assert "test content" in content


def test_curses_loop(bones_writer):
    """Test the main curses loop"""
    mock_stdscr = MagicMock()
    mock_win = MagicMock()
    mock_win.getch.return_value = ord("q")  # Simulate 'q' key press
    with patch.object(bones_writer, "make_win", return_value=mock_win):
        with patch.object(bones_writer, "inner_loop") as mock_inner:
            with patch.object(bones_writer, "update_status_bar") as mock_status:
                with patch("curses.start_color"), patch("curses.init_color"), patch(
                    "curses.init_pair"
                ):
                    # Patch running to False after first iteration to prevent infinite loop
                    def stop_running(*args, **kwargs):
                        bones_writer.running = False

                    mock_inner.side_effect = stop_running
                    bones_writer.curses_loop(mock_stdscr)
                    assert mock_inner.called
                    assert mock_status.called


def test_show_text(bones_writer, mock_stdscr):
    """Test showing text after blanking"""
    bones_writer.outfile = MagicMock()  # Mock the outfile
    # Write some text
    bones_writer.write_char(mock_stdscr, "t")
    bones_writer.write_char(mock_stdscr, "e")
    bones_writer.write_char(mock_stdscr, "s")
    bones_writer.write_char(mock_stdscr, "t")
    # Blank the text
    bones_writer.blank_text(mock_stdscr)
    assert bones_writer.blank is True
    # Show the text again
    bones_writer.show_text(mock_stdscr)
    assert bones_writer.blank is False
    assert len(mock_stdscr.content) > 0
