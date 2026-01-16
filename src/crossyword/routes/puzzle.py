"""Puzzle gameplay routes."""

from sqlmodel import Session
from xitzin import Redirect, Request, Xitzin
from xitzin.auth import get_identity, require_certificate

from ..daily import get_or_assign_todays_puzzle
from ..game import GameState
from ..rendering import render_clue_context, render_grid
from ..users import get_or_create_user, requires_registration


def register_routes(app: Xitzin) -> None:
    """Register puzzle routes."""

    def get_game_or_error(session: Session, request: Request):
        """Load game state with validation checks. Returns (game, error) tuple."""
        identity = get_identity(request)
        user = get_or_create_user(session, identity.fingerprint)

        if requires_registration(user):
            return None, app.template("register_username.gmi")

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

    def render_puzzle_page(game: GameState):
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
