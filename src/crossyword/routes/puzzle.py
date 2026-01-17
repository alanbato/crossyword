"""Puzzle gameplay routes."""

from sqlmodel import Session, select
from xitzin import Redirect, Request, Xitzin
from xitzin.auth import get_identity, require_certificate

import datetime as dt

from ..daily import get_or_assign_todays_puzzle, get_puzzle_for_date
from ..game import GameState
from ..models import CompletedPuzzle, DailyPuzzle
from ..rendering import render_clue_context, render_grid
from ..users import get_or_create_user, requires_registration


def register_routes(app: Xitzin) -> None:
    """Register puzzle routes."""

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

    def validate_direction(direction: str):
        """Validate direction parameter. Returns error response or None."""
        if direction.lower() not in ["across", "down"]:
            return app.template(
                "error.gmi",
                title="Invalid Direction",
                message="Direction must be 'across' or 'down'.\n\n=> /puzzle Back to Puzzle",
            )
        return None

    def render_puzzle_page(
        game: GameState, is_completed: bool = False, date_str: str | None = None
    ):
        """Render the main puzzle page."""
        grid = render_grid(game.puz_data, "".join(game.current_fill))

        across_clues = []
        for clue in game.numbering.across:
            num = clue["num"]
            filled = game.is_clue_filled(clue, "across")
            across_clues.append(
                {
                    "num": num,
                    "text": clue.get("clue", "?"),
                    "status": "✓" if filled else "○",
                }
            )

        down_clues = []
        for clue in game.numbering.down:
            num = clue["num"]
            filled = game.is_clue_filled(clue, "down")
            down_clues.append(
                {
                    "num": num,
                    "text": clue.get("clue", "?"),
                    "status": "✓" if filled else "○",
                }
            )

        return app.template(
            "puzzle.gmi",
            puzzle=game.puzzle,
            grid=grid,
            progress=int(game.get_fill_percentage()),
            across_clues=across_clues,
            down_clues=down_clues,
            is_completed=is_completed,
            date_str=date_str,
        )

    @app.gemini("/puzzle")
    @require_certificate
    def puzzle_home(request: Request):
        """Main puzzle view with grid and all clues."""
        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request)
            if error:
                return error

            game.save()
            return render_puzzle_page(game)

    @app.gemini("/puzzle/clue/{direction}/{num}")
    @require_certificate
    def view_clue(request: Request, direction: str, num: int):
        """View specific clue with current answer."""
        if error := validate_direction(direction):
            return error

        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request)
            if error:
                return error

            clue_info = game.get_clue(direction, num)
            if not clue_info:
                return app.template(
                    "error.gmi",
                    title="Clue Not Found",
                    message="That clue doesn't exist in this puzzle.\n\n=> /puzzle Back to Puzzle",
                )

            clue_text = game.get_clue_text(direction, num)

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
            )

    @app.input(
        "/puzzle/answer/{direction}/{num}",
        prompt="Enter your answer (use SPACE for blanks):",
    )
    @require_certificate
    def submit_answer(request: Request, direction: str, num: int, query: str):
        """Process answer submission."""
        if error := validate_direction(direction):
            return error

        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request)
            if error:
                return error

            success, message = game.submit_answer(direction, num, query)

            if not success:
                return app.template(
                    "error.gmi",
                    title="Invalid Answer",
                    message=f"{message}\n\n=> /puzzle/clue/{direction}/{num} Back to Clue",
                )

            game.save()

            # Auto-check when puzzle becomes fully filled
            if game.is_filled():
                if game.is_complete():
                    return app.template(
                        "check_result.gmi",
                        is_filled=True,
                        is_complete=True,
                        incorrect_count=0,
                        incorrect_message="",
                    )

                incorrect = game.count_incorrect_clues()
                if incorrect > 3:
                    incorrect_message = "some"
                else:
                    incorrect_message = str(incorrect)

                return app.template(
                    "check_result.gmi",
                    is_filled=True,
                    is_complete=False,
                    incorrect_count=incorrect,
                    incorrect_message=incorrect_message,
                )

            return Redirect("/puzzle")

    @app.gemini("/puzzle/check")
    @require_certificate
    def check_puzzle(request: Request):
        """Check the puzzle solution."""
        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request)
            if error:
                return error

            if not game.is_filled():
                return app.template(
                    "check_result.gmi",
                    is_filled=False,
                    is_complete=False,
                    incorrect_count=0,
                    incorrect_message="",
                )

            if game.is_complete():
                game.save()  # Record completion
                return app.template(
                    "check_result.gmi",
                    is_filled=True,
                    is_complete=True,
                    incorrect_count=0,
                    incorrect_message="",
                )

            incorrect = game.count_incorrect_clues()
            if incorrect > 3:
                incorrect_message = "some"
            else:
                incorrect_message = str(incorrect)

            return app.template(
                "check_result.gmi",
                is_filled=True,
                is_complete=False,
                incorrect_count=incorrect,
                incorrect_message=incorrect_message,
            )

    @app.gemini("/puzzle/clear/{direction}/{num}")
    @require_certificate
    def clear_answer(request: Request, direction: str, num: int):
        """Clear the answer for a specific clue."""
        if error := validate_direction(direction):
            return error

        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request)
            if error:
                return error

            game.clear_answer(direction, num)
            game.save()

            return app.template(
                "answer_cleared.gmi",
                num=num,
                direction=direction,
            )

    # --- Helper functions for archived puzzles ---

    def parse_date_or_error(date_str: str):
        """Parse date string and validate. Returns (date, error) tuple."""
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

    def is_puzzle_completed(session: Session, user_id: int, puzzle_id: int) -> bool:
        """Check if user has completed the puzzle."""
        statement = select(CompletedPuzzle).where(
            CompletedPuzzle.user_id == user_id,
            CompletedPuzzle.puzzle_id == puzzle_id,
        )
        return session.exec(statement).first() is not None

    # --- Archived puzzle routes ---

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
            entries = []
            for daily in daily_puzzles:
                entries.append(
                    {
                        "date": daily.date.strftime("%Y-%m-%d"),
                        "title": daily.puzzle.title,
                        "completed": daily.puzzle.id in completed_ids,
                    }
                )

            return app.template("archive.gmi", entries=entries)

    @app.gemini("/puzzle/{date_str}")
    @require_certificate
    def archived_puzzle(request: Request, date_str: str):
        """View puzzle for a specific date."""
        target_date, error = parse_date_or_error(date_str)
        if error:
            return error

        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request, target_date)
            if error:
                return error

            completed = is_puzzle_completed(session, game.user.id, game.puzzle.id)

            game.save()
            return render_puzzle_page(game, is_completed=completed, date_str=date_str)

    @app.gemini("/puzzle/{date_str}/clue/{direction}/{num}")
    @require_certificate
    def archived_view_clue(request: Request, date_str: str, direction: str, num: int):
        """View specific clue for an archived puzzle."""
        target_date, error = parse_date_or_error(date_str)
        if error:
            return error

        if error := validate_direction(direction):
            return error

        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request, target_date)
            if error:
                return error

            clue_info = game.get_clue(direction, num)
            if not clue_info:
                return app.template(
                    "error.gmi",
                    title="Clue Not Found",
                    message=f"That clue doesn't exist in this puzzle.\n\n=> /puzzle/{date_str} Back to Puzzle",
                )

            clue_text = game.get_clue_text(direction, num)
            completed = is_puzzle_completed(session, game.user.id, game.puzzle.id)

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
        "/puzzle/{date_str}/answer/{direction}/{num}",
        prompt="Enter your answer (use SPACE for blanks):",
    )
    @require_certificate
    def archived_submit_answer(
        request: Request, date_str: str, direction: str, num: int, query: str
    ):
        """Process answer submission for an archived puzzle."""
        target_date, error = parse_date_or_error(date_str)
        if error:
            return error

        if error := validate_direction(direction):
            return error

        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request, target_date)
            if error:
                return error

            # Block modifications if puzzle is completed
            if is_puzzle_completed(session, game.user.id, game.puzzle.id):
                return app.template(
                    "error.gmi",
                    title="Puzzle Completed",
                    message=f"You've already completed this puzzle!\n\n=> /puzzle/{date_str} Back to Puzzle",
                )

            success, message = game.submit_answer(direction, num, query)

            if not success:
                return app.template(
                    "error.gmi",
                    title="Invalid Answer",
                    message=f"{message}\n\n=> /puzzle/{date_str}/clue/{direction}/{num} Back to Clue",
                )

            game.save()

            # Auto-check when puzzle becomes fully filled
            if game.is_filled():
                if game.is_complete():
                    return app.template(
                        "check_result.gmi",
                        is_filled=True,
                        is_complete=True,
                        incorrect_count=0,
                        incorrect_message="",
                        date_str=date_str,
                    )

                incorrect = game.count_incorrect_clues()
                if incorrect > 3:
                    incorrect_message = "some"
                else:
                    incorrect_message = str(incorrect)

                return app.template(
                    "check_result.gmi",
                    is_filled=True,
                    is_complete=False,
                    incorrect_count=incorrect,
                    incorrect_message=incorrect_message,
                    date_str=date_str,
                )

            return Redirect(f"/puzzle/{date_str}")

    @app.gemini("/puzzle/{date_str}/check")
    @require_certificate
    def archived_check_puzzle(request: Request, date_str: str):
        """Check the puzzle solution for an archived puzzle."""
        target_date, error = parse_date_or_error(date_str)
        if error:
            return error

        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request, target_date)
            if error:
                return error

            # Block check if puzzle is already completed
            if is_puzzle_completed(session, game.user.id, game.puzzle.id):
                return app.template(
                    "error.gmi",
                    title="Puzzle Completed",
                    message=f"You've already completed this puzzle!\n\n=> /puzzle/{date_str} Back to Puzzle",
                )

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
            if incorrect > 3:
                incorrect_message = "some"
            else:
                incorrect_message = str(incorrect)

            return app.template(
                "check_result.gmi",
                is_filled=True,
                is_complete=False,
                incorrect_count=incorrect,
                incorrect_message=incorrect_message,
                date_str=date_str,
            )

    @app.gemini("/puzzle/{date_str}/clear/{direction}/{num}")
    @require_certificate
    def archived_clear_answer(
        request: Request, date_str: str, direction: str, num: int
    ):
        """Clear the answer for a specific clue in an archived puzzle."""
        target_date, error = parse_date_or_error(date_str)
        if error:
            return error

        if error := validate_direction(direction):
            return error

        with Session(request.app.state.engine) as session:
            game, error = get_game_or_error(session, request, target_date)
            if error:
                return error

            # Block modifications if puzzle is completed
            if is_puzzle_completed(session, game.user.id, game.puzzle.id):
                return app.template(
                    "error.gmi",
                    title="Puzzle Completed",
                    message=f"You've already completed this puzzle!\n\n=> /puzzle/{date_str} Back to Puzzle",
                )

            game.clear_answer(direction, num)
            game.save()

            return app.template(
                "answer_cleared.gmi",
                num=num,
                direction=direction,
                date_str=date_str,
            )
