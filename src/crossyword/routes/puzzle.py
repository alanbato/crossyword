"""Puzzle gameplay routes."""

from sqlmodel import Session
from xitzin import Request, Xitzin
from xitzin.auth import get_identity, require_certificate

from ..daily import get_or_assign_todays_puzzle
from ..game import GameState
from ..rendering import render_clue_context, render_grid
from ..users import get_or_create_user


def register_routes(app: Xitzin) -> None:
    """Register puzzle routes."""

    @app.gemini("/puzzle")
    @require_certificate
    def puzzle_home(request: Request):
        """Main puzzle view with grid and all clues."""
        identity = get_identity(request)

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)
            puzzle = get_or_assign_todays_puzzle(session)

            if not puzzle:
                return app.template("no_puzzle.gmi")

            config = request.app.state.config
            game = GameState.load_or_create(session, user, puzzle, config.puzzles_dir)
            game.save()

            grid = render_grid(game.puz_data, "".join(game.current_fill))

            # Build clue data for templates
            across_texts = game.puz_data.clues[: len(game.numbering.across)]
            down_texts = game.puz_data.clues[len(game.numbering.across) :]

            across_clues = []
            for i, clue in enumerate(game.numbering.across):
                num = clue["num"]
                clue_id = f"{num}A"
                across_clues.append(
                    {
                        "num": num,
                        "text": across_texts[i] if i < len(across_texts) else "?",
                        "status": "[x]" if clue_id in game.solved_clues else "[ ]",
                    }
                )

            down_clues = []
            for i, clue in enumerate(game.numbering.down):
                num = clue["num"]
                clue_id = f"{num}D"
                down_clues.append(
                    {
                        "num": num,
                        "text": down_texts[i] if i < len(down_texts) else "?",
                        "status": "[x]" if clue_id in game.solved_clues else "[ ]",
                    }
                )

            return app.template(
                "puzzle.gmi",
                puzzle=puzzle,
                grid=grid,
                progress=int(game.get_completion_percentage()),
                is_complete=game.is_complete(),
                across_clues=across_clues,
                down_clues=down_clues,
            )

    @app.gemini("/puzzle/clue/{direction}/{num}")
    @require_certificate
    def view_clue(request: Request, direction: str, num: int):
        """View specific clue with current answer."""
        identity = get_identity(request)

        if direction.lower() not in ["across", "down"]:
            return app.template("error.gmi", title="Invalid Direction", message="")

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)
            puzzle = get_or_assign_todays_puzzle(session)

            if not puzzle:
                return app.template("no_puzzle.gmi")

            config = request.app.state.config
            game = GameState.load_or_create(session, user, puzzle, config.puzzles_dir)

            clue_info = game.get_clue(direction, num)
            if not clue_info:
                return app.template("error.gmi", title="Clue Not Found", message="")

            clue_text = game.get_clue_text(direction, num)
            clue_id = f"{num}{direction[0].upper()}"

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
                is_solved=clue_id in game.solved_clues,
            )

    @app.input(
        "/puzzle/answer/{direction}/{num}",
        prompt="Enter your answer (use SPACE for blanks):",
    )
    @require_certificate
    def submit_answer(request: Request, direction: str, num: int, query: str):
        """Process answer submission."""
        identity = get_identity(request)

        if direction.lower() not in ["across", "down"]:
            return app.template("error.gmi", title="Invalid Direction", message="")

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)
            puzzle = get_or_assign_todays_puzzle(session)

            if not puzzle:
                return app.template("no_puzzle.gmi")

            config = request.app.state.config
            game = GameState.load_or_create(session, user, puzzle, config.puzzles_dir)

            is_correct, message = game.submit_answer(direction, num, query)
            game.save()

            return app.template(
                "answer_result.gmi",
                answer=query.upper(),
                message=message,
                is_complete=game.is_complete(),
                direction=direction,
                num=num,
            )

    @app.gemini("/puzzle/clear/{direction}/{num}")
    @require_certificate
    def clear_answer(request: Request, direction: str, num: int):
        """Clear the answer for a specific clue."""
        identity = get_identity(request)

        if direction.lower() not in ["across", "down"]:
            return app.template("error.gmi", title="Invalid Direction", message="")

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)
            puzzle = get_or_assign_todays_puzzle(session)

            if not puzzle:
                return app.template("no_puzzle.gmi")

            config = request.app.state.config
            game = GameState.load_or_create(session, user, puzzle, config.puzzles_dir)

            game.clear_answer(direction, num)
            game.save()

            return app.template(
                "answer_cleared.gmi",
                num=num,
                direction=direction,
            )
