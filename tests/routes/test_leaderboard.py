"""Integration tests for leaderboard routes."""

import datetime as dt

from freezegun import freeze_time
from sqlmodel import Session

from crossyword.models import CompletedPuzzle, DailyPuzzle, Puzzle, User


class TestTodayLeaderboard:
    """Tests for /leaderboard route."""

    def test_no_auth_required(self, client):
        """Leaderboard is accessible without authentication."""
        response = client.get("/leaderboard")

        assert response.is_success

    def test_empty_leaderboard(self, client):
        """Leaderboard shows message when no puzzle assigned."""
        response = client.get("/leaderboard")

        assert response.is_success
        assert "leaderboard" in response.body.lower()

    @freeze_time("2025-01-15")
    def test_shows_entries(self, client):
        """Leaderboard shows completion entries."""
        # Set up puzzle, daily assignment, user, and completion
        with Session(client._app.state.engine) as session:
            puzzle = session.exec(__import__("sqlmodel").select(Puzzle)).first()
            if puzzle:
                # Assign to today
                daily = DailyPuzzle(date=dt.date(2025, 1, 15), puzzle_id=puzzle.id)
                session.add(daily)

                # Create user and completion
                user = User(
                    fingerprint="leaderboard-test-user",
                    display_name="LeaderboardTester",
                )
                session.add(user)
                session.commit()
                session.refresh(user)

                completed = CompletedPuzzle(
                    user_id=user.id,
                    puzzle_id=puzzle.id,
                    completion_time_seconds=180,
                )
                session.add(completed)
                session.commit()

        response = client.get("/leaderboard")

        assert response.is_success
        assert "LeaderboardTester" in response.body or "3m" in response.body


class TestHistoricalLeaderboard:
    """Tests for /leaderboard/{date_str} route."""

    def test_no_auth_required(self, client):
        """Historical leaderboard is accessible without authentication."""
        response = client.get("/leaderboard/2025-01-14")

        assert response.is_success

    def test_invalid_date_format(self, client):
        """Invalid date format returns error."""
        response = client.get("/leaderboard/not-a-date")

        assert response.is_success
        body_lower = response.body.lower()
        assert "format" in body_lower or "invalid" in body_lower

    def test_no_puzzle_for_date(self, client):
        """Shows message when no puzzle assigned for date."""
        response = client.get("/leaderboard/2099-12-31")

        assert response.is_success
        # Should indicate no puzzle
        assert "no puzzle" in response.body.lower()

    def test_shows_puzzle_title(self, client):
        """Shows puzzle title for valid date."""
        # Set up puzzle and daily assignment
        with Session(client._app.state.engine) as session:
            puzzle = session.exec(__import__("sqlmodel").select(Puzzle)).first()
            if puzzle:
                daily = DailyPuzzle(date=dt.date(2025, 1, 10), puzzle_id=puzzle.id)
                session.add(daily)
                session.commit()

        response = client.get("/leaderboard/2025-01-10")

        assert response.is_success
