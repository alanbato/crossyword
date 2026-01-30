"""Integration tests for puzzle routes."""

import datetime as dt

from freezegun import freeze_time
from sqlmodel import Session

from crossyword.models import DailyPuzzle, User


class TestPuzzleHome:
    """Tests for /puzzle route."""

    def test_requires_certificate(self, client):
        """Puzzle page requires client certificate."""
        response = client.get("/puzzle")

        assert response.is_certificate_required

    def test_authenticated_without_display_name_redirects(self, client):
        """User without display name is prompted to register."""
        # Create user without display name
        with Session(client._app.state.engine) as session:
            user = User(
                fingerprint="no-name-fingerprint",
                display_name=None,
            )
            session.add(user)
            session.commit()

        auth_client = client.with_certificate("no-name-fingerprint")
        response = auth_client.get("/puzzle")

        assert response.is_success
        # Should show registration page
        assert "name" in response.body.lower() or "register" in response.body.lower()

    def test_authenticated_with_puzzle(self, auth_client):
        """Authenticated user with display name can access puzzle."""
        response = auth_client.get("/puzzle")

        assert response.is_success
        # Should show puzzle grid
        assert "+" in response.body
        assert "|" in response.body


class TestViewClue:
    """Tests for /puzzle/clue/{direction}/{num} route."""

    def test_requires_certificate(self, client):
        """Clue page requires client certificate."""
        response = client.get("/puzzle/clue/across/1")

        assert response.is_certificate_required

    def test_invalid_direction(self, auth_client):
        """Invalid direction returns error."""
        response = auth_client.get("/puzzle/clue/invalid/1")

        assert response.is_success  # Error pages are still 20 status
        assert "direction" in response.body.lower()

    def test_clue_not_found(self, auth_client):
        """Non-existent clue returns error."""
        response = auth_client.get("/puzzle/clue/across/999")

        assert response.is_success
        assert "not found" in response.body.lower()

    def test_valid_clue(self, auth_client):
        """Valid clue shows clue text and context."""
        response = auth_client.get("/puzzle/clue/across/1")

        assert response.is_success
        # Should show clue info
        assert "current" in response.body.lower() or "_" in response.body


class TestSubmitAnswer:
    """Tests for /puzzle/answer/{direction}/{num} route."""

    def test_input_route_prompts_first(self, client):
        """Input routes prompt for input before checking certificate."""
        # Note: @app.input routes return INPUT status first,
        # certificate is checked when submitting the actual input
        response = client.get("/puzzle/answer/across/1")

        assert response.is_input_required

    def test_prompts_for_input(self, auth_client):
        """Answer route prompts for input."""
        response = auth_client.get("/puzzle/answer/across/1")

        # Note: Since @app.input always returns input prompt first
        assert response.is_input_required
        assert "answer" in response.input_prompt.lower()

    def test_submit_valid_answer(self, auth_client):
        """Can submit an answer of correct length."""
        # First get clue info to know the length
        clue_response = auth_client.get("/puzzle/clue/across/1")
        assert clue_response.is_success

        # Submit answer via input
        response = auth_client.get_input("/puzzle/answer/across/1", "TESTANSWER")

        # Should redirect to puzzle or show result
        assert response.is_redirect or response.is_success

    def test_submit_wrong_length(self, auth_client):
        """Wrong length answer shows error."""
        # Submit very short answer (likely wrong length)
        response = auth_client.get_input("/puzzle/answer/across/1", "X")

        assert response.is_success
        assert "letters" in response.body.lower()


class TestCheckPuzzle:
    """Tests for /puzzle/check route."""

    def test_requires_certificate(self, client):
        """Check route requires client certificate."""
        response = client.get("/puzzle/check")

        assert response.is_certificate_required

    def test_check_unfilled_puzzle(self, auth_client):
        """Check route handles unfilled puzzle."""
        response = auth_client.get("/puzzle/check")

        assert response.is_success
        # Should indicate puzzle not filled
        body_lower = response.body.lower()
        assert "fill" in body_lower or "empty" in body_lower or "complete" in body_lower


class TestClearAnswer:
    """Tests for /puzzle/clear/{direction}/{num} route."""

    def test_requires_certificate(self, client):
        """Clear route requires client certificate."""
        response = client.get("/puzzle/clear/across/1")

        assert response.is_certificate_required

    def test_clear_answer(self, auth_client):
        """Can clear an answer."""
        # First submit an answer
        auth_client.get_input("/puzzle/answer/across/1", "TESTANSWER")

        # Then clear it
        response = auth_client.get("/puzzle/clear/across/1")

        assert response.is_success
        assert "clear" in response.body.lower()

    def test_invalid_direction(self, auth_client):
        """Invalid direction returns error."""
        response = auth_client.get("/puzzle/clear/invalid/1")

        assert response.is_success
        assert "direction" in response.body.lower()


class TestArchive:
    """Tests for /archive route."""

    def test_requires_certificate(self, client):
        """Archive requires client certificate."""
        response = client.get("/archive")

        assert response.is_certificate_required

    def test_archive_accessible(self, auth_client):
        """Archive is accessible to authenticated users."""
        response = auth_client.get("/archive")

        assert response.is_success

    def test_archive_auto_pauses_active_puzzle(self, auth_client):
        """Navigating to archive auto-pauses active puzzles."""
        from crossyword.models import PlayerProgress

        # First visit puzzle to create active progress
        auth_client.get("/puzzle")

        # Verify puzzle is not paused
        with Session(auth_client._app.state.engine) as session:
            progress = session.exec(
                __import__("sqlmodel").select(PlayerProgress)
            ).first()
            assert progress is not None
            assert progress.is_paused is False

        # Navigate to archive
        auth_client.get("/archive")

        # Verify puzzle is now paused
        with Session(auth_client._app.state.engine) as session:
            progress = session.exec(
                __import__("sqlmodel").select(PlayerProgress)
            ).first()
            assert progress.is_paused is True


class TestArchivedPuzzle:
    """Tests for /puzzle/{date_str} routes."""

    @freeze_time("2025-01-15")
    def test_requires_certificate(self, client):
        """Archived puzzle requires certificate."""
        response = client.get("/puzzle/2025-01-14")

        assert response.is_certificate_required

    @freeze_time("2025-01-15")
    def test_valid_date(self, auth_client):
        """Can access archived puzzle by date."""
        # First assign a puzzle to yesterday
        with Session(auth_client._app.state.engine) as session:
            from crossyword.models import Puzzle

            puzzle = session.exec(__import__("sqlmodel").select(Puzzle)).first()
            if puzzle:
                daily = DailyPuzzle(date=dt.date(2025, 1, 14), puzzle_id=puzzle.id)
                session.add(daily)
                session.commit()

        response = auth_client.get("/puzzle/2025-01-14")

        # Should show puzzle or no puzzle error
        assert response.is_success

    @freeze_time("2025-01-15")
    def test_future_date_rejected(self, auth_client):
        """Cannot access future puzzle dates."""
        response = auth_client.get("/puzzle/2025-01-16")

        assert response.is_success
        assert "future" in response.body.lower()

    def test_invalid_date_format(self, auth_client):
        """Invalid date format returns error."""
        response = auth_client.get("/puzzle/not-a-date")

        assert response.is_success
        assert "format" in response.body.lower() or "invalid" in response.body.lower()


class TestPausePuzzle:
    """Tests for /puzzle/pause route."""

    def test_requires_certificate(self, client):
        """Pause route requires client certificate."""
        response = client.get("/puzzle/pause")

        assert response.is_certificate_required

    def test_pause_redirects_to_puzzle(self, auth_client):
        """Pause route redirects back to puzzle page."""
        # First visit puzzle to create progress
        auth_client.get("/puzzle")

        response = auth_client.get("/puzzle/pause")

        assert response.is_redirect
        assert "/puzzle" in response.redirect_url

    def test_pause_sets_paused_state(self, auth_client):
        """Pause route sets the paused state."""
        from crossyword.models import PlayerProgress

        # First visit puzzle to create progress
        auth_client.get("/puzzle")

        # Pause
        auth_client.get("/puzzle/pause")

        # Check the paused state in database
        with Session(auth_client._app.state.engine) as session:
            progress = session.exec(
                __import__("sqlmodel").select(PlayerProgress)
            ).first()
            assert progress is not None
            assert progress.is_paused is True

    def test_paused_puzzle_shows_paused_message(self, auth_client):
        """Paused puzzle shows paused message instead of grid."""
        # Visit puzzle and pause
        auth_client.get("/puzzle")
        auth_client.get("/puzzle/pause")

        # Visit puzzle again
        response = auth_client.get("/puzzle")

        assert response.is_success
        assert "paused" in response.body.lower()

    def test_paused_puzzle_hides_grid(self, auth_client):
        """Paused puzzle hides the grid."""
        # Visit puzzle and pause
        auth_client.get("/puzzle")
        auth_client.get("/puzzle/pause")

        # Visit puzzle again - grid should be hidden
        response = auth_client.get("/puzzle")

        assert response.is_success
        # Grid uses +----+ pattern, which should not be present
        assert "+----+" not in response.body

    def test_paused_puzzle_shows_resume_link(self, auth_client):
        """Paused puzzle shows resume link."""
        # Visit puzzle and pause
        auth_client.get("/puzzle")
        auth_client.get("/puzzle/pause")

        # Visit puzzle again
        response = auth_client.get("/puzzle")

        assert response.is_success
        assert (
            "/puzzle/resume" in response.body.lower()
            or "resume" in response.body.lower()
        )

    def test_active_puzzle_shows_pause_link(self, auth_client):
        """Active puzzle shows pause link."""
        response = auth_client.get("/puzzle")

        assert response.is_success
        assert (
            "/puzzle/pause" in response.body.lower() or "pause" in response.body.lower()
        )


class TestResumePuzzle:
    """Tests for /puzzle/resume route."""

    def test_requires_certificate(self, client):
        """Resume route requires client certificate."""
        response = client.get("/puzzle/resume")

        assert response.is_certificate_required

    def test_resume_redirects_to_puzzle(self, auth_client):
        """Resume route redirects back to puzzle page."""
        # First visit puzzle and pause
        auth_client.get("/puzzle")
        auth_client.get("/puzzle/pause")

        response = auth_client.get("/puzzle/resume")

        assert response.is_redirect
        assert "/puzzle" in response.redirect_url

    def test_resume_clears_paused_state(self, auth_client):
        """Resume route clears the paused state."""
        from crossyword.models import PlayerProgress

        # Visit puzzle, pause, then resume
        auth_client.get("/puzzle")
        auth_client.get("/puzzle/pause")
        auth_client.get("/puzzle/resume")

        # Check the paused state in database
        with Session(auth_client._app.state.engine) as session:
            progress = session.exec(
                __import__("sqlmodel").select(PlayerProgress)
            ).first()
            assert progress is not None
            assert progress.is_paused is False

    def test_resumed_puzzle_shows_grid(self, auth_client):
        """Resumed puzzle shows the grid again."""
        # Visit puzzle, pause, then resume
        auth_client.get("/puzzle")
        auth_client.get("/puzzle/pause")
        auth_client.get("/puzzle/resume")

        # Visit puzzle again
        response = auth_client.get("/puzzle")

        assert response.is_success
        # Grid should be visible again
        assert "+----+" in response.body or "+" in response.body


class TestPauseGuards:
    """Tests for pause guards on other routes."""

    def test_clue_redirects_when_paused(self, auth_client):
        """View clue redirects to puzzle when paused."""
        # Visit puzzle and pause
        auth_client.get("/puzzle")
        auth_client.get("/puzzle/pause")

        # Try to view clue
        response = auth_client.get("/puzzle/clue/across/1")

        assert response.is_redirect
        assert "/puzzle" in response.redirect_url

    def test_submit_answer_redirects_when_paused(self, auth_client):
        """Submit answer redirects to puzzle when paused."""
        # Visit puzzle and pause
        auth_client.get("/puzzle")
        auth_client.get("/puzzle/pause")

        # Try to submit answer (need to use get_input to submit)
        response = auth_client.get_input("/puzzle/answer/across/1", "TESTANSWER")

        assert response.is_redirect
        assert "/puzzle" in response.redirect_url

    def test_check_redirects_when_paused(self, auth_client):
        """Check puzzle redirects to puzzle when paused."""
        # Visit puzzle and pause
        auth_client.get("/puzzle")
        auth_client.get("/puzzle/pause")

        # Try to check puzzle
        response = auth_client.get("/puzzle/check")

        assert response.is_redirect
        assert "/puzzle" in response.redirect_url

    def test_clear_redirects_when_paused(self, auth_client):
        """Clear answer redirects to puzzle when paused."""
        # Visit puzzle and pause
        auth_client.get("/puzzle")
        auth_client.get("/puzzle/pause")

        # Try to clear answer
        response = auth_client.get("/puzzle/clear/across/1")

        assert response.is_redirect
        assert "/puzzle" in response.redirect_url

    def test_can_continue_after_resume(self, auth_client):
        """Can continue solving puzzle after resume."""
        # Visit puzzle, submit answer, pause, resume, submit another answer
        auth_client.get("/puzzle")
        auth_client.get_input("/puzzle/answer/across/1", "TESTANSWER")
        auth_client.get("/puzzle/pause")
        auth_client.get("/puzzle/resume")

        # Should be able to view clue now
        response = auth_client.get("/puzzle/clue/across/1")

        assert response.is_success
        assert "current" in response.body.lower() or "_" in response.body


class TestArchivedPuzzlePause:
    """Tests for pause/resume on archived puzzles."""

    @freeze_time("2025-01-15")
    def test_archived_pause_route(self, auth_client):
        """Can pause archived puzzle."""
        # First assign a puzzle to yesterday
        with Session(auth_client._app.state.engine) as session:
            from crossyword.models import Puzzle

            puzzle = session.exec(__import__("sqlmodel").select(Puzzle)).first()
            if puzzle:
                daily = DailyPuzzle(date=dt.date(2025, 1, 14), puzzle_id=puzzle.id)
                session.add(daily)
                session.commit()

        # Visit archived puzzle and pause
        auth_client.get("/puzzle/2025-01-14")
        response = auth_client.get("/puzzle/2025-01-14/pause")

        assert response.is_redirect
        assert "2025-01-14" in response.redirect_url

    @freeze_time("2025-01-15")
    def test_archived_resume_route(self, auth_client):
        """Can resume archived puzzle."""
        # First assign a puzzle to yesterday
        with Session(auth_client._app.state.engine) as session:
            from crossyword.models import Puzzle

            puzzle = session.exec(__import__("sqlmodel").select(Puzzle)).first()
            if puzzle:
                daily = DailyPuzzle(date=dt.date(2025, 1, 14), puzzle_id=puzzle.id)
                session.add(daily)
                session.commit()

        # Visit archived puzzle, pause, and resume
        auth_client.get("/puzzle/2025-01-14")
        auth_client.get("/puzzle/2025-01-14/pause")
        response = auth_client.get("/puzzle/2025-01-14/resume")

        assert response.is_redirect
        assert "2025-01-14" in response.redirect_url

    @freeze_time("2025-01-15")
    def test_archived_paused_hides_grid(self, auth_client):
        """Paused archived puzzle hides grid."""
        # First assign a puzzle to yesterday
        with Session(auth_client._app.state.engine) as session:
            from crossyword.models import Puzzle

            puzzle = session.exec(__import__("sqlmodel").select(Puzzle)).first()
            if puzzle:
                daily = DailyPuzzle(date=dt.date(2025, 1, 14), puzzle_id=puzzle.id)
                session.add(daily)
                session.commit()

        # Visit archived puzzle and pause
        auth_client.get("/puzzle/2025-01-14")
        auth_client.get("/puzzle/2025-01-14/pause")

        # Visit again
        response = auth_client.get("/puzzle/2025-01-14")

        assert response.is_success
        assert "paused" in response.body.lower()
        assert "+----+" not in response.body
