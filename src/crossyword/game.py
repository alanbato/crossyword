"""Game state management for crossword puzzles."""

import json
import datetime as dt
from pathlib import Path

import puz
from sqlmodel import Session, select

from .logging import get_logger
from .models import CompletedPuzzle, PlayerProgress, Puzzle, User

logger = get_logger(__name__)


class GameState:
    """Manages game state for a player's puzzle session."""

    def __init__(
        self,
        session: Session,
        user: User,
        puzzle: Puzzle,
        puz_data: puz.Puzzle,
        progress: PlayerProgress | None = None,
    ):
        self.session = session
        self.user = user
        self.puzzle = puzzle
        self.puz_data = puz_data
        self.progress = progress
        self.numbering = puz_data.clue_numbering()

        if progress:
            self.current_fill = list(progress.current_fill)
            self.solved_clues = set(json.loads(progress.solved_clues))
        else:
            self.current_fill = list(puz_data.fill)
            for i, char in enumerate(self.current_fill):
                if char != ".":
                    self.current_fill[i] = " "
            self.solved_clues = set()

    @classmethod
    def load_or_create(
        cls,
        session: Session,
        user: User,
        puzzle: Puzzle,
        puzzles_dir: Path,
    ) -> "GameState":
        """Load existing progress or create new game state."""
        puz_path = puzzles_dir / puzzle.filename
        puz_data = puz.read(str(puz_path))

        statement = select(PlayerProgress).where(
            PlayerProgress.user_id == user.id,
            PlayerProgress.puzzle_id == puzzle.id,
        )
        progress = session.exec(statement).first()

        return cls(session, user, puzzle, puz_data, progress)

    def get_clue(self, direction: str, num: int) -> dict | None:
        """Get clue info by direction and number."""
        clues = (
            self.numbering.across
            if direction.lower() == "across"
            else self.numbering.down
        )
        for clue in clues:
            if clue["num"] == num:
                return clue
        return None

    def get_clue_text(self, direction: str, num: int) -> str | None:
        """Get the clue text for a specific clue."""
        clue = self.get_clue(direction, num)
        if clue:
            return clue.get("clue")
        return None

    def _get_clue_cell_indices(self, clue: dict, direction: str) -> list[int]:
        """Get all cell indices for a clue's letters."""
        cell = clue["cell"]
        width = self.puz_data.width
        is_across = direction.lower() == "across"
        return [
            cell + i if is_across else cell + (i * width) for i in range(clue["len"])
        ]

    def submit_answer(self, direction: str, num: int, answer: str) -> tuple[bool, str]:
        """
        Submit an answer for a clue.

        Returns (success, message) tuple. Does not reveal if answer is correct.
        """
        clue = self.get_clue(direction, num)
        if not clue:
            return False, "Clue not found"

        answer = answer.upper()
        expected_length = clue["len"]

        if len(answer) != expected_length:
            return False, f"Answer must be {expected_length} letters"

        indices = self._get_clue_cell_indices(clue, direction)
        for idx, char in zip(indices, answer):
            if self.current_fill[idx] != ".":
                self.current_fill[idx] = char

        # Track that this clue has been answered (not necessarily correct)
        clue_id = f"{num}{direction[0].upper()}"
        self.solved_clues.add(clue_id)

        logger.info(
            "answer_submitted",
            fingerprint=self.user.fingerprint,
            puzzle_id=self.puzzle.id,
            clue=clue_id,
        )

        return True, "Answer saved"

    def clear_answer(self, direction: str, num: int) -> bool:
        """Clear the answer for a specific clue."""
        clue = self.get_clue(direction, num)
        if not clue:
            return False

        for idx in self._get_clue_cell_indices(clue, direction):
            if self.current_fill[idx] != ".":
                self.current_fill[idx] = " "

        clue_id = f"{num}{direction[0].upper()}"
        self.solved_clues.discard(clue_id)

        return True

    def is_complete(self) -> bool:
        """Check if the puzzle is fully and correctly solved."""
        return "".join(self.current_fill) == self.puz_data.solution

    def is_filled(self) -> bool:
        """Check if all cells have been filled (no empty spaces)."""
        for char in self.current_fill:
            if char == " ":
                return False
        return True

    def count_incorrect_clues(self) -> int:
        """Count the number of clues with incorrect answers."""
        incorrect = 0

        for clue in self.numbering.across:
            if not self._is_clue_correct(clue, "across"):
                incorrect += 1

        for clue in self.numbering.down:
            if not self._is_clue_correct(clue, "down"):
                incorrect += 1

        return incorrect

    def _is_clue_correct(self, clue: dict, direction: str) -> bool:
        """Check if a specific clue's answer is correct."""
        return all(
            self.current_fill[idx] == self.puz_data.solution[idx]
            for idx in self._get_clue_cell_indices(clue, direction)
        )

    def is_clue_filled(self, clue: dict, direction: str) -> bool:
        """Check if all cells for a clue are filled (no empty spaces)."""
        return all(
            self.current_fill[idx] != " "
            for idx in self._get_clue_cell_indices(clue, direction)
        )

    def get_completion_percentage(self) -> float:
        """Calculate percentage of correctly filled cells."""
        correct = 0
        total = 0

        for i, char in enumerate(self.current_fill):
            if char != ".":
                total += 1
                if char == self.puz_data.solution[i]:
                    correct += 1

        return (correct / total * 100) if total > 0 else 0

    def get_fill_percentage(self) -> float:
        """Calculate percentage of filled (non-empty) cells."""
        filled = 0
        total = 0

        for char in self.current_fill:
            if char != ".":
                total += 1
                if char != " ":
                    filled += 1

        return (filled / total * 100) if total > 0 else 0

    @property
    def is_paused(self) -> bool:
        """Check if the puzzle timer is currently paused."""
        return self.progress.is_paused if self.progress else False

    def get_elapsed_seconds(self) -> int:
        """Get total active play time in seconds.

        For legacy puzzles (accumulated_seconds=0 with existing progress),
        falls back to wall-clock time calculation.
        For new puzzles, returns accumulated active time.
        """
        if not self.progress:
            return 0

        # Legacy support: if accumulated_seconds is 0 and puzzle has been worked on,
        # use wall-clock time for backward compatibility
        has_progress = self.progress.current_fill and any(
            c not in (".", " ") for c in self.progress.current_fill
        )
        if self.progress.accumulated_seconds == 0 and has_progress:
            time_delta = dt.datetime.utcnow() - self.progress.started_at
            return int(time_delta.total_seconds())

        # New timing: accumulated time + current session if not paused
        elapsed = self.progress.accumulated_seconds
        if not self.progress.is_paused:
            current_session = dt.datetime.utcnow() - self.progress.last_updated
            elapsed += int(current_session.total_seconds())

        return elapsed

    def _accumulate_time_if_active(self) -> None:
        """Add elapsed active time to accumulated total if timer is running."""
        if not self.progress or self.progress.is_paused:
            return

        now = dt.datetime.utcnow()
        elapsed = now - self.progress.last_updated
        self.progress.accumulated_seconds += int(elapsed.total_seconds())
        self.progress.last_updated = now

    def pause(self) -> bool:
        """Pause the puzzle timer.

        Returns True if successfully paused, False if already paused or no progress.
        """
        if not self.progress or self.progress.is_paused:
            return False

        self._accumulate_time_if_active()
        self.progress.is_paused = True
        self.progress.pause_started_at = dt.datetime.utcnow()

        logger.info(
            "puzzle_paused",
            fingerprint=self.user.fingerprint,
            puzzle_id=self.puzzle.id,
            accumulated_seconds=self.progress.accumulated_seconds,
        )
        return True

    def resume(self) -> bool:
        """Resume the puzzle timer.

        Returns True if successfully resumed, False if not paused or no progress.
        """
        if not self.progress or not self.progress.is_paused:
            return False

        self.progress.is_paused = False
        self.progress.pause_started_at = None
        self.progress.last_updated = dt.datetime.utcnow()

        logger.info(
            "puzzle_resumed",
            fingerprint=self.user.fingerprint,
            puzzle_id=self.puzzle.id,
        )
        return True

    def save(self) -> None:
        """Persist current state to database."""
        now = dt.datetime.utcnow()

        if self.progress is None:
            self.progress = PlayerProgress(
                user_id=self.user.id,
                puzzle_id=self.puzzle.id,
                current_fill="".join(self.current_fill),
                solved_clues=json.dumps(list(self.solved_clues)),
                started_at=now,
                last_updated=now,
                accumulated_seconds=0,
                is_paused=False,
                pause_started_at=None,
            )
            self.session.add(self.progress)
        else:
            # Accumulate active time before saving if timer is running
            self._accumulate_time_if_active()
            self.progress.current_fill = "".join(self.current_fill)
            self.progress.solved_clues = json.dumps(list(self.solved_clues))

        if self.is_complete():
            self._record_completion()

        self.session.commit()
        logger.debug(
            "game_state_saved",
            fingerprint=self.user.fingerprint,
            puzzle_id=self.puzzle.id,
        )

    def _record_completion(self) -> None:
        """Record puzzle completion for leaderboard."""
        statement = select(CompletedPuzzle).where(
            CompletedPuzzle.user_id == self.user.id,
            CompletedPuzzle.puzzle_id == self.puzzle.id,
        )
        existing = self.session.exec(statement).first()

        if existing:
            return

        # Use accumulated active time for leaderboard
        completion_time = self.get_elapsed_seconds()

        completed = CompletedPuzzle(
            user_id=self.user.id,
            puzzle_id=self.puzzle.id,
            completion_time_seconds=completion_time,
        )
        self.session.add(completed)
        logger.info(
            "puzzle_completed",
            fingerprint=self.user.fingerprint,
            puzzle_id=self.puzzle.id,
            completion_time_seconds=completion_time,
        )


def auto_pause_active_puzzles(session: Session, user_id: int) -> int:
    """Pause all active (non-paused) puzzles for a user.

    This is called when navigating away from puzzle routes to ensure
    the timer doesn't run while the user is browsing other pages.

    Returns the number of puzzles that were paused.
    """
    now = dt.datetime.utcnow()

    # Find all in-progress puzzles that are not paused
    statement = select(PlayerProgress).where(
        PlayerProgress.user_id == user_id,
        PlayerProgress.is_paused == False,  # noqa: E712
    )
    active_puzzles = session.exec(statement).all()

    paused_count = 0
    for progress in active_puzzles:
        # Accumulate time before pausing
        elapsed = now - progress.last_updated
        progress.accumulated_seconds += int(elapsed.total_seconds())
        progress.last_updated = now

        # Set paused state
        progress.is_paused = True
        progress.pause_started_at = now
        paused_count += 1

    if paused_count > 0:
        session.commit()
        logger.debug(
            "auto_paused_puzzles",
            user_id=user_id,
            count=paused_count,
        )

    return paused_count
