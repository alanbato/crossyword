"""Tests for crossyword.game module - GameState class."""

import json

import puz
from sqlmodel import Session, select

from crossyword.game import GameState
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
