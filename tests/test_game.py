"""Tests for crossyword.game module - GameState class."""

import datetime as dt
import json

import puz
from sqlmodel import Session, select

from crossyword.game import GameState, auto_pause_active_puzzles
from crossyword.models import CompletedPuzzle, PlayerProgress, Puzzle, User


class TestGameStateInit:
    """Tests for GameState initialization."""

    def test_init_without_progress(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """GameState initializes with empty fill when no progress exists."""
        game = GameState(db_session, test_user, test_puzzle, puz_data, progress=None)

        assert game.user == test_user
        assert game.puzzle == test_puzzle
        assert game.puz_data == puz_data
        assert game.progress is None
        assert len(game.current_fill) == len(puz_data.solution)
        assert game.solved_clues == set()

        # Verify empty fill (spaces for white cells, dots for black)
        for i, char in enumerate(game.current_fill):
            if puz_data.solution[i] == ".":
                assert char == "."
            else:
                assert char == " "

    def test_init_with_progress(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """GameState restores state from existing progress."""
        # Modify progress with some data
        test_progress.current_fill = puz_data.solution  # Fully solved
        test_progress.solved_clues = json.dumps(["1A", "2D"])
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)

        assert game.progress == test_progress
        assert "".join(game.current_fill) == puz_data.solution
        assert game.solved_clues == {"1A", "2D"}


class TestGameStateClues:
    """Tests for clue retrieval methods."""

    def test_get_clue_across(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """get_clue returns correct across clue info."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        first_across = numbering.across[0]

        clue = game.get_clue("across", first_across["num"])

        assert clue is not None
        assert clue["num"] == first_across["num"]
        assert "len" in clue
        assert "cell" in clue

    def test_get_clue_down(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """get_clue returns correct down clue info."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        first_down = numbering.down[0]

        clue = game.get_clue("down", first_down["num"])

        assert clue is not None
        assert clue["num"] == first_down["num"]

    def test_get_clue_not_found(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """get_clue returns None for non-existent clue."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)

        assert game.get_clue("across", 999) is None
        assert game.get_clue("down", 999) is None

    def test_get_clue_text(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """get_clue_text returns the clue text."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        first_across = numbering.across[0]

        text = game.get_clue_text("across", first_across["num"])

        assert text is not None
        assert len(text) > 0

    def test_get_clue_text_not_found(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """get_clue_text returns None for non-existent clue."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)

        assert game.get_clue_text("across", 999) is None


class TestGameStateSubmitAnswer:
    """Tests for submit_answer method."""

    def test_submit_correct_length(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """submit_answer accepts answers of correct length."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        clue = numbering.across[0]
        answer = "X" * clue["len"]

        success, message = game.submit_answer("across", clue["num"], answer)

        assert success is True
        assert message == "Answer saved"

    def test_submit_wrong_length(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """submit_answer rejects answers of wrong length."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        clue = numbering.across[0]

        success, message = game.submit_answer("across", clue["num"], "X")

        assert success is False
        assert f"{clue['len']} letters" in message

    def test_submit_invalid_clue(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """submit_answer returns error for non-existent clue."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)

        success, message = game.submit_answer("across", 999, "TEST")

        assert success is False
        assert "not found" in message.lower()

    def test_submit_updates_fill_across(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """submit_answer updates current_fill for across answers."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        clue = numbering.across[0]
        answer = "A" * clue["len"]

        game.submit_answer("across", clue["num"], answer)

        # Check cells are filled
        cell = clue["cell"]
        for i in range(clue["len"]):
            assert game.current_fill[cell + i] == "A"

    def test_submit_updates_fill_down(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """submit_answer updates current_fill for down answers."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        clue = numbering.down[0]
        answer = "B" * clue["len"]

        game.submit_answer("down", clue["num"], answer)

        # Check cells are filled (down uses width stride)
        cell = clue["cell"]
        width = puz_data.width
        for i in range(clue["len"]):
            assert game.current_fill[cell + (i * width)] == "B"

    def test_submit_tracks_solved_clue(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """submit_answer adds clue to solved_clues set."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        clue = numbering.across[0]
        answer = "X" * clue["len"]

        game.submit_answer("across", clue["num"], answer)

        assert f"{clue['num']}A" in game.solved_clues

    def test_submit_converts_to_uppercase(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """submit_answer converts answers to uppercase."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        clue = numbering.across[0]
        answer = "a" * clue["len"]

        game.submit_answer("across", clue["num"], answer)

        cell = clue["cell"]
        assert game.current_fill[cell] == "A"


class TestGameStateClearAnswer:
    """Tests for clear_answer method."""

    def test_clear_across(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """clear_answer clears across answer cells."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        clue = numbering.across[0]

        # First fill it
        game.submit_answer("across", clue["num"], "X" * clue["len"])
        # Then clear it
        result = game.clear_answer("across", clue["num"])

        assert result is True
        cell = clue["cell"]
        for i in range(clue["len"]):
            assert game.current_fill[cell + i] == " "

    def test_clear_down(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """clear_answer clears down answer cells."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        clue = numbering.down[0]

        # First fill it
        game.submit_answer("down", clue["num"], "Y" * clue["len"])
        # Then clear it
        result = game.clear_answer("down", clue["num"])

        assert result is True
        cell = clue["cell"]
        width = puz_data.width
        for i in range(clue["len"]):
            assert game.current_fill[cell + (i * width)] == " "

    def test_clear_removes_from_solved(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """clear_answer removes clue from solved_clues."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        clue = numbering.across[0]

        game.submit_answer("across", clue["num"], "X" * clue["len"])
        game.clear_answer("across", clue["num"])

        assert f"{clue['num']}A" not in game.solved_clues

    def test_clear_invalid_clue(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """clear_answer returns False for non-existent clue."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)

        result = game.clear_answer("across", 999)

        assert result is False


class TestGameStateCompletion:
    """Tests for completion checking methods."""

    def test_is_complete_empty(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """is_complete returns False for empty puzzle."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)

        assert game.is_complete() is False

    def test_is_complete_solved(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """is_complete returns True when solution matches."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        game.current_fill = list(puz_data.solution)

        assert game.is_complete() is True

    def test_is_complete_wrong(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """is_complete returns False for wrong answers."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        # Fill with wrong letters, preserving black squares
        for i, char in enumerate(puz_data.solution):
            if char == ".":
                game.current_fill[i] = "."
            else:
                game.current_fill[i] = "X" if char != "X" else "Y"

        assert game.is_complete() is False

    def test_is_filled_empty(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """is_filled returns False when cells are empty."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)

        assert game.is_filled() is False

    def test_is_filled_complete(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """is_filled returns True when all cells have letters."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        # Fill all white cells with X
        for i, char in enumerate(puz_data.solution):
            if char != ".":
                game.current_fill[i] = "X"

        assert game.is_filled() is True

    def test_is_filled_partial(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """is_filled returns False when some cells are empty."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        # Fill only first non-black cell
        for i, char in enumerate(puz_data.solution):
            if char != ".":
                game.current_fill[i] = "X"
                break

        assert game.is_filled() is False


class TestGameStateMetrics:
    """Tests for metric calculation methods."""

    def test_count_incorrect_clues_all_correct(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """count_incorrect_clues returns 0 when all correct."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        game.current_fill = list(puz_data.solution)

        assert game.count_incorrect_clues() == 0

    def test_count_incorrect_clues_all_wrong(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """count_incorrect_clues counts all clues when all wrong."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        # Fill with wrong answers
        for i, char in enumerate(puz_data.solution):
            if char != ".":
                game.current_fill[i] = "X" if char != "X" else "Y"

        numbering = puz_data.clue_numbering()
        total_clues = len(numbering.across) + len(numbering.down)

        assert game.count_incorrect_clues() == total_clues

    def test_get_completion_percentage_empty(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """get_completion_percentage returns 0 for empty puzzle."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)

        assert game.get_completion_percentage() == 0

    def test_get_completion_percentage_complete(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """get_completion_percentage returns 100 for solved puzzle."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        game.current_fill = list(puz_data.solution)

        assert game.get_completion_percentage() == 100.0

    def test_get_fill_percentage_empty(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """get_fill_percentage returns 0 for empty puzzle."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)

        assert game.get_fill_percentage() == 0

    def test_get_fill_percentage_complete(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """get_fill_percentage returns 100 when all filled."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        # Fill all white cells
        for i, char in enumerate(puz_data.solution):
            if char != ".":
                game.current_fill[i] = "X"

        assert game.get_fill_percentage() == 100.0

    def test_is_clue_filled_empty(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """is_clue_filled returns False for empty clue."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        clue = numbering.across[0]

        assert game.is_clue_filled(clue, "across") is False

    def test_is_clue_filled_complete(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """is_clue_filled returns True for filled clue."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        clue = numbering.across[0]

        game.submit_answer("across", clue["num"], "X" * clue["len"])

        assert game.is_clue_filled(clue, "across") is True

    def test_is_clue_correct(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """_is_clue_correct validates against solution."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        clue = numbering.across[0]

        # Get the correct answer from solution
        cell = clue["cell"]
        correct_answer = ""
        for i in range(clue["len"]):
            correct_answer += puz_data.solution[cell + i]

        game.submit_answer("across", clue["num"], correct_answer)

        assert game._is_clue_correct(clue, "across") is True

    def test_is_clue_incorrect(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """_is_clue_correct returns False for wrong answer."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        clue = numbering.across[0]

        # Submit a wrong answer
        game.submit_answer("across", clue["num"], "X" * clue["len"])

        assert game._is_clue_correct(clue, "across") is False


class TestGameStateSave:
    """Tests for save method and persistence."""

    def test_save_creates_progress(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """save creates PlayerProgress when none exists."""
        game = GameState(db_session, test_user, test_puzzle, puz_data)
        numbering = puz_data.clue_numbering()
        clue = numbering.across[0]
        game.submit_answer("across", clue["num"], "X" * clue["len"])

        game.save()

        assert game.progress is not None
        assert game.progress.id is not None
        assert game.progress.user_id == test_user.id
        assert game.progress.puzzle_id == test_puzzle.id

    def test_save_updates_existing_progress(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """save updates existing PlayerProgress."""
        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)
        numbering = puz_data.clue_numbering()
        clue = numbering.across[0]

        game.submit_answer("across", clue["num"], "Y" * clue["len"])
        game.save()

        assert "Y" in game.progress.current_fill

    def test_save_records_completion(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """save records CompletedPuzzle when puzzle is complete."""
        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)
        game.current_fill = list(puz_data.solution)

        game.save()

        # Check CompletedPuzzle was created
        stmt = select(CompletedPuzzle).where(
            CompletedPuzzle.user_id == test_user.id,
            CompletedPuzzle.puzzle_id == test_puzzle.id,
        )
        completed = db_session.exec(stmt).first()
        assert completed is not None

    def test_save_records_completion_only_once(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """save only records completion once."""
        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)
        game.current_fill = list(puz_data.solution)

        game.save()
        game.save()  # Second save

        # Check only one CompletedPuzzle exists
        stmt = select(CompletedPuzzle).where(
            CompletedPuzzle.user_id == test_user.id,
            CompletedPuzzle.puzzle_id == test_puzzle.id,
        )
        completed_list = list(db_session.exec(stmt).all())
        assert len(completed_list) == 1


class TestGameStateLoadOrCreate:
    """Tests for load_or_create class method."""

    def test_load_or_create_new(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puzzles_dir,
    ):
        """load_or_create creates new game when no progress exists."""
        game = GameState.load_or_create(db_session, test_user, test_puzzle, puzzles_dir)

        assert game.progress is None
        assert game.user == test_user
        assert game.puzzle == test_puzzle

    def test_load_or_create_existing(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        test_progress: PlayerProgress,
        puzzles_dir,
    ):
        """load_or_create loads existing progress."""
        # Modify progress
        test_progress.current_fill = "X" + test_progress.current_fill[1:]
        test_progress.solved_clues = json.dumps(["1A"])
        db_session.commit()

        game = GameState.load_or_create(db_session, test_user, test_puzzle, puzzles_dir)

        assert game.progress == test_progress
        assert game.current_fill[0] == "X"
        assert "1A" in game.solved_clues


class TestGameStatePause:
    """Tests for pause/resume functionality."""

    def test_is_paused_false_without_progress(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """is_paused returns False when no progress exists."""
        game = GameState(db_session, test_user, test_puzzle, puz_data, progress=None)

        assert game.is_paused is False

    def test_is_paused_reflects_progress_state(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """is_paused returns the pause state from progress."""
        test_progress.is_paused = True
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)

        assert game.is_paused is True

    def test_pause_returns_false_without_progress(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """pause() returns False when no progress exists."""
        game = GameState(db_session, test_user, test_puzzle, puz_data, progress=None)

        result = game.pause()

        assert result is False

    def test_pause_sets_paused_state(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """pause() sets is_paused to True and returns True."""
        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)

        result = game.pause()

        assert result is True
        assert game.progress.is_paused is True
        assert game.progress.pause_started_at is not None

    def test_pause_accumulates_time(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """pause() accumulates elapsed time before pausing."""
        import datetime as dt

        # Set last_updated to 60 seconds ago
        test_progress.last_updated = dt.datetime.utcnow() - dt.timedelta(seconds=60)
        test_progress.accumulated_seconds = 100
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)
        game.pause()

        # Should have accumulated approximately 60 more seconds
        assert game.progress.accumulated_seconds >= 159  # Allow for timing variance
        assert game.progress.accumulated_seconds <= 162

    def test_pause_returns_false_if_already_paused(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """pause() returns False when already paused."""
        test_progress.is_paused = True
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)

        result = game.pause()

        assert result is False

    def test_resume_returns_false_without_progress(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """resume() returns False when no progress exists."""
        game = GameState(db_session, test_user, test_puzzle, puz_data, progress=None)

        result = game.resume()

        assert result is False

    def test_resume_clears_paused_state(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """resume() clears is_paused and returns True."""
        import datetime as dt

        test_progress.is_paused = True
        test_progress.pause_started_at = dt.datetime.utcnow()
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)

        result = game.resume()

        assert result is True
        assert game.progress.is_paused is False
        assert game.progress.pause_started_at is None

    def test_resume_returns_false_if_not_paused(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """resume() returns False when not paused."""
        test_progress.is_paused = False
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)

        result = game.resume()

        assert result is False

    def test_resume_updates_last_updated(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """resume() updates last_updated timestamp."""
        import datetime as dt

        old_time = dt.datetime.utcnow() - dt.timedelta(hours=1)
        test_progress.is_paused = True
        test_progress.last_updated = old_time
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)
        game.resume()

        # last_updated should be recent (within last second)
        assert game.progress.last_updated > old_time


class TestGameStateElapsedTime:
    """Tests for get_elapsed_seconds() method."""

    def test_elapsed_seconds_zero_without_progress(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """get_elapsed_seconds() returns 0 when no progress exists."""
        game = GameState(db_session, test_user, test_puzzle, puz_data, progress=None)

        assert game.get_elapsed_seconds() == 0

    def test_elapsed_seconds_when_paused(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """get_elapsed_seconds() returns accumulated time when paused (no active session)."""
        test_progress.is_paused = True
        test_progress.accumulated_seconds = 300
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)

        assert game.get_elapsed_seconds() == 300

    def test_elapsed_seconds_when_active(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """get_elapsed_seconds() returns accumulated + current session when active."""
        import datetime as dt

        # Set last_updated to 30 seconds ago
        test_progress.is_paused = False
        test_progress.accumulated_seconds = 100
        test_progress.last_updated = dt.datetime.utcnow() - dt.timedelta(seconds=30)
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)

        elapsed = game.get_elapsed_seconds()

        # Should be approximately 130 seconds (100 + 30)
        assert elapsed >= 129
        assert elapsed <= 132

    def test_elapsed_seconds_legacy_fallback(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """get_elapsed_seconds() falls back to wall-clock for legacy puzzles."""
        import datetime as dt

        # Legacy puzzle: accumulated_seconds=0 but has filled cells
        test_progress.accumulated_seconds = 0
        test_progress.started_at = dt.datetime.utcnow() - dt.timedelta(seconds=600)
        # Fill some cells to indicate progress was made
        fill = list(test_progress.current_fill)
        fill[0] = "X"
        test_progress.current_fill = "".join(fill)
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)

        elapsed = game.get_elapsed_seconds()

        # Should use wall-clock time (approximately 600 seconds)
        assert elapsed >= 599
        assert elapsed <= 602

    def test_elapsed_seconds_no_legacy_for_new_puzzles(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """get_elapsed_seconds() doesn't fall back for new empty puzzles."""
        import datetime as dt

        # New puzzle: accumulated_seconds=0 and no filled cells
        test_progress.accumulated_seconds = 0
        test_progress.is_paused = False
        test_progress.last_updated = dt.datetime.utcnow() - dt.timedelta(seconds=5)
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)

        elapsed = game.get_elapsed_seconds()

        # Should be approximately 5 seconds (current session only)
        assert elapsed >= 4
        assert elapsed <= 7


class TestGameStatePauseSaveIntegration:
    """Tests for pause state persistence through save()."""

    def test_save_persists_pause_state(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """save() persists the paused state to database."""
        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)

        game.pause()
        game.save()

        # Reload from database
        db_session.refresh(test_progress)

        assert test_progress.is_paused is True
        assert test_progress.pause_started_at is not None

    def test_save_persists_accumulated_seconds(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """save() persists accumulated_seconds to database."""
        import datetime as dt

        test_progress.last_updated = dt.datetime.utcnow() - dt.timedelta(seconds=45)
        test_progress.accumulated_seconds = 100
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)
        game.save()

        # Reload from database
        db_session.refresh(test_progress)

        # Should have accumulated approximately 45 more seconds
        assert test_progress.accumulated_seconds >= 144
        assert test_progress.accumulated_seconds <= 147

    def test_save_does_not_accumulate_when_paused(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """save() does not accumulate time when paused."""
        import datetime as dt

        test_progress.is_paused = True
        test_progress.last_updated = dt.datetime.utcnow() - dt.timedelta(seconds=3600)
        test_progress.accumulated_seconds = 100
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)
        game.save()

        # Reload from database
        db_session.refresh(test_progress)

        # Should NOT have accumulated time while paused
        assert test_progress.accumulated_seconds == 100

    def test_new_puzzle_initializes_pause_fields(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
    ):
        """save() initializes pause fields for new puzzles."""
        game = GameState(db_session, test_user, test_puzzle, puz_data, progress=None)

        game.save()

        assert game.progress is not None
        assert game.progress.is_paused is False
        assert game.progress.accumulated_seconds == 0
        assert game.progress.pause_started_at is None


class TestGameStatePauseCompletion:
    """Tests for completion timing with pause feature."""

    def test_completion_uses_accumulated_time(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """Completion records accumulated time, not wall-clock time."""
        import datetime as dt

        # Set up: started 1 hour ago, but only 5 minutes of active time
        test_progress.started_at = dt.datetime.utcnow() - dt.timedelta(hours=1)
        test_progress.accumulated_seconds = 300  # 5 minutes
        test_progress.last_updated = dt.datetime.utcnow()  # Just updated
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)
        # Set to correct solution
        game.current_fill = list(puz_data.solution)
        game.save()

        # Check completion time
        stmt = select(CompletedPuzzle).where(
            CompletedPuzzle.user_id == test_user.id,
            CompletedPuzzle.puzzle_id == test_puzzle.id,
        )
        completed = db_session.exec(stmt).first()

        assert completed is not None
        # Should be approximately 300 seconds, NOT 3600
        assert completed.completion_time_seconds >= 299
        assert completed.completion_time_seconds <= 302

    def test_completion_while_paused_uses_accumulated_time(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """Completion while paused uses accumulated time only."""
        import datetime as dt

        test_progress.is_paused = True
        test_progress.accumulated_seconds = 180  # 3 minutes
        test_progress.pause_started_at = dt.datetime.utcnow() - dt.timedelta(hours=2)
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)
        # Set to correct solution
        game.current_fill = list(puz_data.solution)
        game.save()

        # Check completion time
        stmt = select(CompletedPuzzle).where(
            CompletedPuzzle.user_id == test_user.id,
            CompletedPuzzle.puzzle_id == test_puzzle.id,
        )
        completed = db_session.exec(stmt).first()

        assert completed is not None
        # Should be 180 seconds (accumulated), not including pause time
        assert completed.completion_time_seconds == 180

    def test_pause_resume_cycle_tracks_time_correctly(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        puz_data: puz.Puzzle,
        test_progress: PlayerProgress,
    ):
        """Multiple pause/resume cycles track time correctly."""
        import datetime as dt

        # Start with 60 seconds accumulated
        test_progress.accumulated_seconds = 60
        test_progress.last_updated = dt.datetime.utcnow() - dt.timedelta(seconds=30)
        db_session.commit()

        game = GameState(db_session, test_user, test_puzzle, puz_data, test_progress)

        # Pause (should accumulate ~30 more seconds)
        game.pause()
        game.save()

        # Check accumulated time after pause (should be ~90)
        assert game.progress.accumulated_seconds >= 89
        assert game.progress.accumulated_seconds <= 92
        assert game.progress.is_paused is True

        # Resume
        game.resume()
        game.save()

        assert game.progress.is_paused is False

        # The accumulated seconds should stay the same until next action
        # (resume updates last_updated but doesn't add time)
        initial_accumulated = game.progress.accumulated_seconds

        # Simulate some more active time by setting last_updated back
        game.progress.last_updated = dt.datetime.utcnow() - dt.timedelta(seconds=20)
        db_session.commit()

        # Save again (should accumulate ~20 more seconds)
        game.save()

        assert game.progress.accumulated_seconds >= initial_accumulated + 19
        assert game.progress.accumulated_seconds <= initial_accumulated + 22


class TestAutoPauseActivePuzzles:
    """Tests for auto_pause_active_puzzles function."""

    def test_pauses_active_puzzle(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        test_progress: PlayerProgress,
    ):
        """auto_pause_active_puzzles pauses an active puzzle."""
        test_progress.is_paused = False
        test_progress.accumulated_seconds = 100
        db_session.commit()

        count = auto_pause_active_puzzles(db_session, test_user.id)

        db_session.refresh(test_progress)
        assert count == 1
        assert test_progress.is_paused is True

    def test_skips_already_paused_puzzle(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        test_progress: PlayerProgress,
    ):
        """auto_pause_active_puzzles skips already paused puzzles."""
        test_progress.is_paused = True
        test_progress.accumulated_seconds = 100
        db_session.commit()

        count = auto_pause_active_puzzles(db_session, test_user.id)

        assert count == 0

    def test_returns_zero_when_no_puzzles(
        self,
        db_session: Session,
        test_user: User,
    ):
        """auto_pause_active_puzzles returns 0 when user has no puzzles."""
        count = auto_pause_active_puzzles(db_session, test_user.id)

        assert count == 0

    def test_accumulates_time_before_pausing(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        test_progress: PlayerProgress,
    ):
        """auto_pause_active_puzzles accumulates time before pausing."""
        test_progress.is_paused = False
        test_progress.accumulated_seconds = 50
        test_progress.last_updated = dt.datetime.utcnow() - dt.timedelta(seconds=30)
        db_session.commit()

        auto_pause_active_puzzles(db_session, test_user.id)

        db_session.refresh(test_progress)
        # Should have accumulated ~30 more seconds
        assert test_progress.accumulated_seconds >= 79
        assert test_progress.accumulated_seconds <= 82

    def test_pauses_multiple_active_puzzles(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        test_progress: PlayerProgress,
        puz_data: puz.Puzzle,
        test_puz_path,
    ):
        """auto_pause_active_puzzles pauses all active puzzles for a user."""
        # Create a second puzzle
        puzzle2 = Puzzle(
            filename="test_puzzle_2.puz",
            title="Test Puzzle 2",
            width=puz_data.width,
            height=puz_data.height,
            clue_count=10,
        )
        db_session.add(puzzle2)
        db_session.commit()
        db_session.refresh(puzzle2)

        # Create progress for the second puzzle
        empty_fill = "".join("." if c == "." else " " for c in puz_data.solution)
        progress2 = PlayerProgress(
            user_id=test_user.id,
            puzzle_id=puzzle2.id,
            current_fill=empty_fill,
            solved_clues="[]",
            is_paused=False,
            accumulated_seconds=200,
        )
        db_session.add(progress2)

        # Make sure first progress is active too
        test_progress.is_paused = False
        test_progress.accumulated_seconds = 100
        db_session.commit()

        count = auto_pause_active_puzzles(db_session, test_user.id)

        db_session.refresh(test_progress)
        db_session.refresh(progress2)

        assert count == 2
        assert test_progress.is_paused is True
        assert progress2.is_paused is True

    def test_only_pauses_users_own_puzzles(
        self,
        db_session: Session,
        test_user: User,
        test_puzzle: Puzzle,
        test_progress: PlayerProgress,
    ):
        """auto_pause_active_puzzles only affects the specified user's puzzles."""
        # Create another user with an active puzzle
        other_user = User(
            fingerprint="other-user-fingerprint",
            display_name="OtherPlayer",
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        other_progress = PlayerProgress(
            user_id=other_user.id,
            puzzle_id=test_puzzle.id,
            current_fill=test_progress.current_fill,
            solved_clues="[]",
            is_paused=False,
            accumulated_seconds=300,
        )
        db_session.add(other_progress)
        test_progress.is_paused = False
        db_session.commit()

        # Pause only test_user's puzzles
        count = auto_pause_active_puzzles(db_session, test_user.id)

        db_session.refresh(test_progress)
        db_session.refresh(other_progress)

        assert count == 1
        assert test_progress.is_paused is True
        assert other_progress.is_paused is False  # Other user's puzzle unchanged
