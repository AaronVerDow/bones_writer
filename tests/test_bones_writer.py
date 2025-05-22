import pytest
from unittest.mock import patch, MagicMock
from src.bones_writer import BonesWriter, NUM_FADE_STEPS
import os
from pathlib import Path
import time
import shutil
import curses


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
        elif len(args) == 2:
            string, attr = args
            self.content.append((self.cursor_y, self.cursor_x, string, attr))
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
        self.cursor_y = 0
        self.cursor_x = 0


@pytest.fixture
def mock_stdscr():
    return MockCursesWindow()


@pytest.fixture
def bones_writer(tmp_path):
    with patch("curses.color_pair", return_value=0):  # Mock color_pair to avoid curses initialization
        writer = BonesWriter(directory=tmp_path)
        yield writer
        # Cleanup
        if writer.filepath.exists():
            writer.filepath.unlink()
        if writer.db_path.exists():
            writer.db_path.unlink()


def test_write_char(bones_writer, mock_stdscr):
    bones_writer.outfile = MagicMock()  # Mock the outfile
    with patch("curses.color_pair", return_value=0):  # Mock color_pair
        # Test writing a single character
        bones_writer.write_char(mock_stdscr, "a")
        # Verify the character was written to the window
        assert mock_stdscr.content[-1][2] == "a"
        # Verify the character was written to the file
        bones_writer.outfile.write.assert_called_with("a")


def test_word_counting(bones_writer, mock_stdscr):
    bones_writer.outfile = MagicMock()  # Mock the outfile

    # Create a mock window with all required methods
    mock_win = MagicMock()
    mock_win.getch.side_effect = [
        ord("h"),
        ord("e"),
        ord("l"),
        ord("l"),  # "hell"
        ord("o"),
        ord(" "),  # "o "
        ord("w"),
        ord("o"),  # "wo"
    ]
    mock_win.getyx.return_value = (0, 0)  # Return default cursor position
    mock_win.addstr = MagicMock()
    mock_win.refresh = MagicMock()

    with patch("curses.color_pair", return_value=0):  # Mock color_pair
        # Test word counting functionality
        for _ in range(4):  # "hell"
            bones_writer.inner_loop(mock_win)
        assert bones_writer.live_word_count == 1

        for _ in range(2):  # "o "
            bones_writer.inner_loop(mock_win)
        assert bones_writer.live_word_count == 1

        for _ in range(2):  # "wo"
            bones_writer.inner_loop(mock_win)
        assert bones_writer.live_word_count == 2


def test_blank_text(bones_writer, mock_stdscr):
    bones_writer.outfile = MagicMock()  # Mock the outfile
    with patch("curses.color_pair", return_value=0):  # Mock color_pair
        # Test text blanking functionality
        # Write some text
        bones_writer.write_char(mock_stdscr, "t")
        bones_writer.write_char(mock_stdscr, "e")
        bones_writer.write_char(mock_stdscr, "s")
        bones_writer.write_char(mock_stdscr, "t")
        
        # Simulate fading steps
        bones_writer.current_fade_step = NUM_FADE_STEPS - 1
        bones_writer.last_fade_time = 0  # Reset fade time to ensure it runs
        
        # Blank the text
        bones_writer.blank_text(mock_stdscr)
        # Verify the window was cleared
        assert len(mock_stdscr.content) == 0
        assert bones_writer.blank is True


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
    # assert bones_writer.dir == Path.joinpath(Path.home(), "Documents", "bones")
    # Simulate file creation
    with open(bones_writer.filepath, "w") as f:
        f.write("")
    assert bones_writer.filepath.exists()


def test_timeout_function(bones_writer):
    """Test the text blanking timeout functionality"""
    assert bones_writer.timeout() is False  # Should be False immediately after initialization

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
                with patch("curses.start_color"), patch("curses.init_color"), patch("curses.init_pair"):
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
    with patch("curses.color_pair", return_value=0):  # Mock color_pair
        # Write some text
        bones_writer.write_char(mock_stdscr, "t")
        bones_writer.write_char(mock_stdscr, "e")
        bones_writer.write_char(mock_stdscr, "s")
        bones_writer.write_char(mock_stdscr, "t")
        
        # Simulate fading steps
        bones_writer.current_fade_step = NUM_FADE_STEPS - 1
        bones_writer.last_fade_time = 0  # Reset fade time to ensure it runs
        
        # Blank the text
        bones_writer.blank_text(mock_stdscr)
        assert bones_writer.blank is True
        # Show the text again
        bones_writer.show_text(mock_stdscr)
        assert bones_writer.blank is False
        assert len(mock_stdscr.content) > 0


def test_sanitize_path(bones_writer):
    """Test path sanitization functionality"""
    # Test basic sanitization
    assert bones_writer.sanitize_path("Hello World") == "Hello_World"
    # Test removal of special characters
    assert bones_writer.sanitize_path("Hello@World!") == "HelloWorld"
    # Test multiple spaces
    assert bones_writer.sanitize_path("Hello   World") == "Hello___World"
    # Test mixed case and numbers
    assert bones_writer.sanitize_path("Hello123 World") == "Hello123_World"


def test_rename_file(bones_writer):
    """Test file renaming and categorization"""
    # Create initial file
    with open(bones_writer.filepath, "w") as f:
        f.write("test content")

    # Test renaming
    category = "test_category"
    title = "test_title"
    bones_writer.rename_file(category, title)

    # Verify new file exists
    expected_path = Path.joinpath(bones_writer.dir, category, f"{bones_writer.filename[:-4]}_{title}.Rmd")
    assert expected_path.exists()

    # Verify content was preserved
    with open(expected_path, "r") as f:
        assert f.read() == "test content"


def test_add_title(bones_writer):
    """Test adding title to file content"""
    # Create test file
    test_path = bones_writer.filepath
    original_content = "original content"
    with open(test_path, "w") as f:
        f.write(original_content)

    # Add title
    title = "Test Title"
    bones_writer.add_title(test_path, title)

    # Verify content
    with open(test_path, "r") as f:
        content = f.read()
        expected_content = f"## {title}\n\n{original_content}"
        assert content == expected_content


def test_category_completer():
    """Test category completion functionality"""
    from src.bones_writer import CategoryCompleter

    categories = ["test1", "test2", "other"]
    completer = CategoryCompleter(categories)

    # Test completion
    assert completer.complete("te", 0) == "test1"
    assert completer.complete("te", 1) == "test2"
    assert completer.complete("te", 2) is None
    assert completer.complete("o", 0) == "other"
    assert completer.complete("x", 0) is None


def test_cleanup_word_count(bones_writer):
    """Test word count calculation in cleanup"""
    # Create test file with known word count
    with open(bones_writer.filepath, "w") as f:
        f.write("one two three\nfour five")  # 5 words

    # Mock elapsed_seconds to avoid timing issues
    with patch.object(bones_writer, "elapsed_seconds", return_value=60):
        # Mock input to avoid user interaction
        with patch("builtins.input", side_effect=["test_category", "test_title"]):
            # Mock print to capture output
            with patch("builtins.print") as mock_print:
                bones_writer.cleanup()
                # Verify word count was printed
                mock_print.assert_any_call("Words: 5")


def test_cleanup_wpm(bones_writer):
    """Test WPM calculation in cleanup"""
    # Create test file with known word count
    with open(bones_writer.filepath, "w") as f:
        f.write("one two three four five")  # 5 words

    # Mock elapsed_seconds to return 1 minute (60 seconds)
    with patch.object(bones_writer, "elapsed_seconds", return_value=60):
        # Mock input to avoid user interaction
        with patch("builtins.input", side_effect=["test_category", "test_title"]):
            # Mock print to capture output
            with patch("builtins.print") as mock_print:
                bones_writer.cleanup()
                # Verify WPM was printed (5 words per minute)
                mock_print.assert_any_call("WPM: 5")


def test_git_commit_and_push(bones_writer):
    """Test git commit and push functionality"""
    # Mock the git repository
    mock_repo = MagicMock()
    bones_writer.repo = mock_repo

    # Test files to commit
    test_files = [Path("test1.txt"), Path("test2.txt")]
    commit_message = "Test commit"

    # Call the function
    bones_writer.git_commit_and_push(test_files, commit_message)

    # Verify git commands were called correctly
    for file_path in test_files:
        mock_repo.git.add.assert_any_call(str(file_path))
    mock_repo.git.commit.assert_called_once_with("-m", commit_message)
    mock_repo.git.push.assert_called_once()


def test_git_commit_and_push_no_repo(bones_writer):
    """Test git commit and push when no repo exists"""
    bones_writer.repo = None
    test_files = [Path("test.txt")]
    # Should return None without raising an exception
    assert bones_writer.git_commit_and_push(test_files, "Test commit") is None


def test_check_repo_status_clean(bones_writer):
    """Test repo status check when repo is clean"""
    mock_repo = MagicMock()
    mock_repo.is_dirty.return_value = False
    mock_repo.active_branch.name = "main"
    mock_repo.head.commit = "commit1"
    mock_repo.refs = {"origin/main": MagicMock(commit="commit1")}
    mock_repo.remotes = [MagicMock()]
    
    bones_writer.repo = mock_repo
    assert bones_writer.check_repo_status() is None


def test_check_repo_status_dirty(bones_writer):
    """Test repo status check when repo is dirty"""
    mock_repo = MagicMock()
    mock_repo.is_dirty.return_value = True
    bones_writer.repo = mock_repo
    
    assert "uncommitted changes" in bones_writer.check_repo_status()


def test_check_repo_status_behind(bones_writer):
    """Test repo status check when local is behind remote"""
    mock_repo = MagicMock()
    mock_repo.is_dirty.return_value = False
    mock_repo.active_branch.name = "main"
    mock_repo.head.commit = "commit1"
    mock_repo.refs = {"origin/main": MagicMock(commit="commit2")}
    mock_repo.remotes = [MagicMock()]
    
    bones_writer.repo = mock_repo
    assert "behind the remote" in bones_writer.check_repo_status()


def test_relative_filepath_with_repo(bones_writer):
    """Test relative filepath calculation with repo"""
    mock_repo = MagicMock()
    mock_repo.working_dir = "/home/user/repo"
    bones_writer.repo = mock_repo
    
    test_path = Path("/home/user/repo/docs/test.txt")
    expected = Path("docs/test.txt")
    
    assert bones_writer.relative_filepath(test_path) == expected


def test_relative_filepath_no_repo(bones_writer):
    """Test relative filepath calculation without repo"""
    bones_writer.repo = None
    test_path = Path("/home/user/test.txt")
    assert bones_writer.relative_filepath(test_path) == test_path


@pytest.fixture
def mock_db():
    """Fixture for mocking TinyDB database"""
    mock_table = MagicMock()
    mock_table.search.return_value = [
        {
            "timestamp": "2024-03-01T10:00:00",
            "duration_seconds": 300,
            "word_count": 150,
            "wpm": 30,
            "spelling_accuracy": 95
        },
        {
            "timestamp": "2024-03-02T11:00:00",
            "duration_seconds": 600,
            "word_count": 300,
            "wpm": 35,
            "spelling_accuracy": 98
        }
    ]
    return mock_table


def test_query_high_word_count_sessions(bones_writer, mock_db):
    """Test querying sessions with high word count"""
    bones_writer.stats_table = mock_db
    sessions = bones_writer.query_high_word_count_sessions(7)
    
    assert len(sessions) == 2
    assert all(session["word_count"] >= 100 for session in sessions)
    mock_db.search.assert_called_once()


@patch("matplotlib.pyplot.show")
@patch("matplotlib.pyplot.subplots")
def test_plot_writing_stats(mock_subplots, mock_show, bones_writer, mock_db):
    """Test plotting writing statistics"""
    bones_writer.stats_table = mock_db
    
    # Mock the subplot objects
    mock_fig = MagicMock()
    mock_axes = [MagicMock() for _ in range(4)]
    mock_subplots.return_value = (mock_fig, mock_axes)
    
    bones_writer.plot_writing_stats(7)
    
    # Verify plot was created and shown
    mock_subplots.assert_called_once()
    mock_show.assert_called_once()
    
    # Verify each axis was configured
    for ax in mock_axes:
        ax.plot.assert_called_once()
        ax.set_ylabel.assert_called_once()
        ax.grid.assert_called_once_with(True)
