"""Puzzle gameplay routes."""

import datetime as dt

from sqlmodel import Session, select
from xitzin import Redirect, Request, Xitzin
from xitzin.auth import get_identity, require_certificate

from ..daily import get_or_assign_todays_puzzle, get_puzzle_for_date
from ..game import GameState
from ..models import CompletedPuzzle, DailyPuzzle
from ..rendering import apply_colors, render_clue_context, render_grid
from ..users import get_or_create_user, requires_registration


def register_routes(app: Xitzin) -> None:
    """Register puzzle routes."""

    def parse_date_or_error(date_str: str | None):
        """Parse date string and validate. Returns (date, error) tuple."""
        if date_str is None:
            return None, None

        try:
            target_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None, app.template(
                "error.gmi",
                title="Invalid Date",
                message="Use format: YYYY-MM-DD\n\n=> /archive Back to Archive",
            )

        if target_date > dt.date.today():
            return None, app.template(
                "error.gmi",
                title="Future Puzzle",
                message="Cannot access future puzzles.\n\n=> /archive Back to Archive",
            )

        return target_date, None

    def get_game_or_error(
        session: Session, request: Request, target_date: dt.date | None = None
    ):
        """Load game state with validation checks. Returns (game, error) tuple."""
        identity = get_identity(request)
        user = get_or_create_user(session, identity.fingerprint)

        if requires_registration(user):
            return None, app.template("register_username.gmi")

        if target_date:
            puzzle = get_puzzle_for_date(session, target_date)
        else:
            puzzle = get_or_assign_todays_puzzle(session)

        if not puzzle:
            return None, app.template("no_puzzle.gmi")

        config = request.app.state.config
        game = GameState.load_or_create(session, user, puzzle, config.puzzles_dir)
        return game, None

    def validate_direction(direction: str, date_str: str | None = None):
        """Validate direction parameter. Returns error response or None."""
        if direction.lower() not in ["across", "down"]:
            back_path = f"/puzzle/{date_str}" if date_str else "/puzzle"
            return app.template(
                "error.gmi",
                title="Invalid Direction",
                message=f"Direction must be 'across' or 'down'.\n\n=> {back_path} Back to Puzzle",
            )
        return None

    def is_puzzle_completed(session: Session, user_id: int, puzzle_id: int) -> bool:
        """Check if user has completed the puzzle."""
        statement = select(CompletedPuzzle).where(
            CompletedPuzzle.user_id == user_id,
            CompletedPuzzle.puzzle_id == puzzle_id,
        )
        return session.exec(statement).first() is not None

    def check_not_completed(session: Session, game: GameState, date_str: str | None):
        """For archived puzzles, check if already completed. Returns error or None."""
        if date_str and is_puzzle_completed(session, game.user.id, game.puzzle.id):
            return app.template(
                "error.gmi",
                title="Puzzle Completed",
                message=f"You've already completed this puzzle!\n\n=> /puzzle/{date_str} Back to Puzzle",
            )
        return None

    def build_clue_list(game: GameState, direction: str) -> list[dict]:
        """Build clue list for template rendering."""
        clues = game.numbering.across if direction == "across" else game.numbering.down
        return [
            {
                "num": clue["num"],
                "text": clue.get("clue", "?"),
                "status": "✓" if game.is_clue_filled(clue, direction) else "○",
            }
            for clue in clues
        ]

    def render_puzzle_page(
        game: GameState,
        is_completed: bool = False,
        date_str: str | None = None,
        crossyword_date: str | None = None,
    ):
        """Render the main puzzle page."""
        grid = render_grid(game.puz_data, "".join(game.current_fill))
        if game.user.use_colors:
            grid = apply_colors(grid)

        # Use crossyword_date if provided, otherwise use date_str (for archived),
        # otherwise use today's date (for today's puzzle)
        leaderboard_date = (
            crossyword_date or date_str or dt.date.today().strftime("%Y-%m-%d")
        )

        return app.template(
            "puzzle.gmi",
            puzzle=game.puzzle,
            grid=grid,
            progress=int(game.get_fill_percentage()),
            across_clues=build_clue_list(game, "across"),
            down_clues=build_clue_list(game, "down"),
            is_completed=is_completed,
            date_str=date_str,
            crossyword_date=leaderboard_date,
        )

    def format_check_result(game: GameState, date_str: str | None = None):
        """Format check result template response."""
        if not game.is_filled():
            return app.template(
                "check_result.gmi",
                is_filled=False,
                is_complete=False,
                incorrect_count=0,
                incorrect_message="",
                date_str=date_str,
            )

        if game.is_complete():
            game.save()  # Record completion
            return app.template(
                "check_result.gmi",
                is_filled=True,
                is_complete=True,
                incorrect_count=0,
                incorrect_message="",
                date_str=date_str,
            )

        incorrect = game.count_incorrect_clues()
        incorrect_message = "some" if incorrect > 3 else str(incorrect)

        return app.template(
            "check_result.gmi",
            is_filled=True,
            is_complete=False,
            incorrect_count=incorrect,
            incorrect_message=incorrect_message,
            date_str=date_str,
        )

    # --- Specific routes first (to take precedence over wildcard) ---

    @app.gemini("/puzzle/clue/{direction}/{num}", name="view_clue")
    @app.gemini("/puzzle/{date_str}/clue/{direction}/{num}", name="archived_view_clue")
    @require_certificate
    def view_clue(
        request: Request, direction: str, num: int, date_str: str | None = None
    ):
        """View specific clue with current answer."""
        target_date, error = parse_date_or_error(date_str)
        if error:
            return error

        if error := validate_direction(direction, date_str):
            return error

        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request, target_date)
            if error:
                return error

            clue_info = game.get_clue(direction, num)
            if not clue_info:
                back_path = f"/puzzle/{date_str}" if date_str else "/puzzle"
                return app.template(
                    "error.gmi",
                    title="Clue Not Found",
                    message=f"That clue doesn't exist in this puzzle.\n\n=> {back_path} Back to Puzzle",
                )

            clue_text = game.get_clue_text(direction, num)
            completed = (
                is_puzzle_completed(session, game.user.id, game.puzzle.id)
                if date_str
                else False
            )

            context = render_clue_context(
                game.puz_data,
                "".join(game.current_fill),
                direction,
                clue_info,
            )

            return app.template(
                "clue.gmi",
                num=num,
                direction=direction,
                clue_text=clue_text or "No clue text available",
                length=clue_info["len"],
                context=context,
                is_solved=game.is_clue_filled(clue_info, direction),
                is_completed=completed,
                date_str=date_str,
            )

    @app.input(
        "/puzzle/answer/{direction}/{num}",
        prompt="Enter your answer (use SPACE for blanks):",
        name="submit_answer",
    )
    @app.input(
        "/puzzle/{date_str}/answer/{direction}/{num}",
        prompt="Enter your answer (use SPACE for blanks):",
        name="archived_submit_answer",
    )
    @require_certificate
    def submit_answer(
        request: Request,
        direction: str,
        num: int,
        query: str,
        date_str: str | None = None,
    ):
        """Process answer submission."""
        target_date, error = parse_date_or_error(date_str)
        if error:
            return error

        if error := validate_direction(direction, date_str):
            return error

        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request, target_date)
            if error:
                return error

            if error := check_not_completed(session, game, date_str):
                return error

            success, message = game.submit_answer(direction, num, query)

            if not success:
                back_path = (
                    f"/puzzle/{date_str}/clue/{direction}/{num}"
                    if date_str
                    else f"/puzzle/clue/{direction}/{num}"
                )
                return app.template(
                    "error.gmi",
                    title="Invalid Answer",
                    message=f"{message}\n\n=> {back_path} Back to Clue",
                )

            game.save()

            # Auto-check when puzzle becomes fully filled
            if game.is_filled():
                return format_check_result(game, date_str)

            redirect_path = f"/puzzle/{date_str}" if date_str else "/puzzle"
            return Redirect(redirect_path)

    @app.gemini("/puzzle/check", name="check_puzzle")
    @app.gemini("/puzzle/{date_str}/check", name="archived_check_puzzle")
    @require_certificate
    def check_puzzle(request: Request, date_str: str | None = None):
        """Check the puzzle solution."""
        target_date, error = parse_date_or_error(date_str)
        if error:
            return error

        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request, target_date)
            if error:
                return error

            if error := check_not_completed(session, game, date_str):
                return error

            return format_check_result(game, date_str)

    @app.gemini("/puzzle/clear/{direction}/{num}", name="clear_answer")
    @app.gemini(
        "/puzzle/{date_str}/clear/{direction}/{num}", name="archived_clear_answer"
    )
    @require_certificate
    def clear_answer(
        request: Request, direction: str, num: int, date_str: str | None = None
    ):
        """Clear the answer for a specific clue."""
        target_date, error = parse_date_or_error(date_str)
        if error:
            return error

        if error := validate_direction(direction, date_str):
            return error

        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request, target_date)
            if error:
                return error

            if error := check_not_completed(session, game, date_str):
                return error

            game.clear_answer(direction, num)
            game.save()

            return app.template(
                "answer_cleared.gmi",
                num=num,
                direction=direction,
                date_str=date_str,
            )

    # --- Main puzzle route (registered last so specific routes match first) ---

    @app.gemini("/puzzle", name="puzzle_home")
    @app.gemini("/puzzle/{date_str}", name="archived_puzzle")
    @require_certificate
    def puzzle_home(request: Request, date_str: str | None = None):
        """Main puzzle view with grid and all clues."""
        target_date, error = parse_date_or_error(date_str)
        if error:
            return error

        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request, target_date)
            if error:
                return error

            completed = (
                is_puzzle_completed(session, game.user.id, game.puzzle.id)
                if date_str
                else False
            )

            game.save()
            return render_puzzle_page(game, is_completed=completed, date_str=date_str)

    # --- Archive index route ---

    @app.gemini("/archive")
    @require_certificate
    def archive_index(request: Request):
        """Browse all available puzzles by date."""
        identity = get_identity(request)

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)

            if requires_registration(user):
                return app.template("register_username.gmi")

            # Get all daily puzzles up to today
            today = dt.date.today()
            statement = (
                select(DailyPuzzle)
                .where(DailyPuzzle.date <= today)
                .order_by(DailyPuzzle.date.desc())
            )
            daily_puzzles = session.exec(statement).all()

            # Get user's completed puzzle IDs
            completed_stmt = select(CompletedPuzzle.puzzle_id).where(
                CompletedPuzzle.user_id == user.id
            )
            completed_ids = set(session.exec(completed_stmt).all())

            # Build archive entries
            entries = [
                {
                    "date": daily.date.strftime("%Y-%m-%d"),
                    "title": daily.puzzle.title,
                    "completed": daily.puzzle.id in completed_ids,
                }
                for daily in daily_puzzles
            ]

            return app.template("archive.gmi", entries=entries)
