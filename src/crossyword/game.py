"""Game state management for crossword puzzles."""

import json
import datetime as dt
from pathlib import Path

import puz
from sqlmodel import Session, select

from .models import CompletedPuzzle, PlayerProgress, Puzzle, User


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
        clues = self.numbering.across if direction.lower() == "across" else self.numbering.down
        for clue in clues:
            if clue["num"] == num:
                return clue
        return None

    def get_clue_text(self, direction: str, num: int) -> str | None:
        """Get the clue text for a specific clue."""
        clues = self.numbering.across if direction.lower() == "across" else self.numbering.down
        clue_texts = (
            self.puz_data.clues[: len(self.numbering.across)]
            if direction.lower() == "across"
            else self.puz_data.clues[len(self.numbering.across) :]
        )

        for i, clue in enumerate(clues):
            if clue["num"] == num:
                return clue_texts[i] if i < len(clue_texts) else None
        return None

    def submit_answer(self, direction: str, num: int, answer: str) -> tuple[bool, str]:
        """
        Submit an answer for a clue.

        Returns (is_correct, message) tuple.
        """
        clue = self.get_clue(direction, num)
        if not clue:
            return False, "Clue not found"

        answer = answer.upper()
        expected_length = clue["len"]

        if len(answer) != expected_length:
            return False, f"Answer must be {expected_length} letters"

        cell = clue["cell"]
        width = self.puz_data.width
        correct_answer = ""

        for i in range(expected_length):
            if direction.lower() == "across":
                idx = cell + i
            else:
                idx = cell + (i * width)
            correct_answer += self.puz_data.solution[idx]

        for i, char in enumerate(answer):
            if direction.lower() == "across":
                idx = cell + i
            else:
                idx = cell + (i * width)

            if self.current_fill[idx] != ".":
                self.current_fill[idx] = char

        clue_id = f"{num}{direction[0].upper()}"
        is_correct = answer == correct_answer

        if is_correct:
            self.solved_clues.add(clue_id)
            message = "Correct!"
        else:
            self.solved_clues.discard(clue_id)
            message = "Answer saved"

        return is_correct, message

    def clear_answer(self, direction: str, num: int) -> bool:
        """Clear the answer for a specific clue."""
        clue = self.get_clue(direction, num)
        if not clue:
            return False

        cell = clue["cell"]
        width = self.puz_data.width

        for i in range(clue["len"]):
            if direction.lower() == "across":
                idx = cell + i
            else:
                idx = cell + (i * width)

            if self.current_fill[idx] != ".":
                self.current_fill[idx] = " "

        clue_id = f"{num}{direction[0].upper()}"
        self.solved_clues.discard(clue_id)

        return True

    def is_complete(self) -> bool:
        """Check if the puzzle is fully and correctly solved."""
        return "".join(self.current_fill) == self.puz_data.solution

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

    def save(self) -> None:
        """Persist current state to database."""
        if self.progress is None:
            self.progress = PlayerProgress(
                user_id=self.user.id,
                puzzle_id=self.puzzle.id,
                current_fill="".join(self.current_fill),
                solved_clues=json.dumps(list(self.solved_clues)),
                started_at=dt.datetime.utcnow(),
            )
            self.session.add(self.progress)
        else:
            self.progress.current_fill = "".join(self.current_fill)
            self.progress.solved_clues = json.dumps(list(self.solved_clues))
            self.progress.last_updated = dt.datetime.utcnow()

        if self.is_complete():
            self._record_completion()

        self.session.commit()

    def _record_completion(self) -> None:
        """Record puzzle completion for leaderboard."""
        statement = select(CompletedPuzzle).where(
            CompletedPuzzle.user_id == self.user.id,
            CompletedPuzzle.puzzle_id == self.puzzle.id,
        )
        existing = self.session.exec(statement).first()

        if existing:
            return

        time_delta = dt.datetime.utcnow() - self.progress.started_at
        completion_time = int(time_delta.total_seconds())

        completed = CompletedPuzzle(
            user_id=self.user.id,
            puzzle_id=self.puzzle.id,
            completion_time_seconds=completion_time,
        )
        self.session.add(completed)
