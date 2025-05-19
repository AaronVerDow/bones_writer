import pytest
import curses
from unittest.mock import patch, MagicMock
from src.bones_writer import BonesWriter

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
    return BonesWriter()

def test_write_char(bones_writer, mock_stdscr):
    bones_writer.outfile = MagicMock()  # Mock the outfile
    # Test writing a single character
    bones_writer.write_char(mock_stdscr, 'a')
    # Verify the character was written to the window
    assert mock_stdscr.content[-1][2] == 'a'
    # Verify the character was written to the file
    bones_writer.outfile.write.assert_called_with('a')

def test_word_counting(bones_writer, mock_stdscr):
    bones_writer.outfile = MagicMock()  # Mock the outfile
    # Test word counting functionality
    # Write a word
    bones_writer.write_char(mock_stdscr, 'h')
    bones_writer.start_word()
    bones_writer.write_char(mock_stdscr, 'e')
    bones_writer.start_word()
    bones_writer.write_char(mock_stdscr, 'l')
    bones_writer.start_word()
    bones_writer.write_char(mock_stdscr, 'l')
    assert bones_writer.live_word_count == 1
    bones_writer.start_word()
    bones_writer.write_char(mock_stdscr, 'o')
    bones_writer.start_word()
    bones_writer.write_char(mock_stdscr, ' ')
    bones_writer.end_word()
    bones_writer.write_char(mock_stdscr, ' ')
    bones_writer.end_word()
    assert bones_writer.live_word_count == 1
    bones_writer.write_char(mock_stdscr, 'w')
    bones_writer.start_word()
    bones_writer.write_char(mock_stdscr, '0')
    bones_writer.start_word()
    assert bones_writer.live_word_count == 2

def test_blank_text(bones_writer, mock_stdscr):
    bones_writer.outfile = MagicMock()  # Mock the outfile
    # Test text blanking functionality
    # Write some text
    bones_writer.write_char(mock_stdscr, 't')
    bones_writer.write_char(mock_stdscr, 'e')
    bones_writer.write_char(mock_stdscr, 's')
    bones_writer.write_char(mock_stdscr, 't')
    # Blank the text
    bones_writer.blank_text(mock_stdscr)
    # Verify the window was cleared
    assert len(mock_stdscr.content) == 0
    assert bones_writer.blank == True

def test_status_bar(bones_writer, mock_stdscr):
    # Test status bar updates
    bones_writer.screen_width = 80
    bones_writer.status_y = 80
    with patch('curses.color_pair', return_value=0):
        # Update status bar
        bones_writer.status_bar(mock_stdscr, "Test", 2)
    # Verify status bar content
    assert len(mock_stdscr.content) > 0
    assert mock_stdscr.content[0][2] == "Test" 
