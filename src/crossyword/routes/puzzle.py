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
                return "# No Puzzle Available\n\nCheck back tomorrow!\n\n=> / Home"

            config = request.app.state.config
            game = GameState.load_or_create(session, user, puzzle, config.puzzles_dir)
            game.save()

            grid = render_grid(game.puz_data, "".join(game.current_fill))
            correct_pct = game.get_completion_percentage()

            lines = [
                f"# {puzzle.title}",
                "",
            ]

            if puzzle.author:
                lines.append(f"by {puzzle.author}")
                lines.append("")

            lines.extend(
                [
                    "```crossword",
                    grid,
                    "```",
                    "",
                    f"Progress: {correct_pct:.0f}% correct",
                    "",
                ]
            )

            if game.is_complete():
                lines.extend(
                    [
                        "Congratulations! You've completed this puzzle!",
                        "",
                        "=> /leaderboard View Leaderboard",
                        "",
                    ]
                )

            # Across clues
            lines.append("## Across")
            lines.append("")
            across_texts = game.puz_data.clues[: len(game.numbering.across)]
            for i, clue in enumerate(game.numbering.across):
                num = clue["num"]
                clue_id = f"{num}A"
                text = across_texts[i] if i < len(across_texts) else "?"
                status = "[x]" if clue_id in game.solved_clues else "[ ]"
                lines.append(f"=> /puzzle/clue/across/{num} {status} {num}. {text}")

            lines.append("")

            # Down clues
            lines.append("## Down")
            lines.append("")
            down_texts = game.puz_data.clues[len(game.numbering.across) :]
            for i, clue in enumerate(game.numbering.down):
                num = clue["num"]
                clue_id = f"{num}D"
                text = down_texts[i] if i < len(down_texts) else "?"
                status = "[x]" if clue_id in game.solved_clues else "[ ]"
                lines.append(f"=> /puzzle/clue/down/{num} {status} {num}. {text}")

            lines.extend(
                [
                    "",
                    "=> / Home",
                ]
            )

            return "\n".join(lines)

    @app.gemini("/puzzle/clue/{direction}/{num}")
    @require_certificate
    def view_clue(request: Request, direction: str, num: int):
        """View specific clue with current answer."""
        identity = get_identity(request)

        if direction.lower() not in ["across", "down"]:
            return "# Invalid Direction\n\n=> /puzzle Back to Puzzle"

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)
            puzzle = get_or_assign_todays_puzzle(session)

            if not puzzle:
                return "# No Puzzle Available\n\n=> / Home"

            config = request.app.state.config
            game = GameState.load_or_create(session, user, puzzle, config.puzzles_dir)

            clue_info = game.get_clue(direction, num)
            if not clue_info:
                return "# Clue Not Found\n\n=> /puzzle Back to Puzzle"

            clue_text = game.get_clue_text(direction, num)
            clue_id = f"{num}{direction[0].upper()}"
            is_solved = clue_id in game.solved_clues

            context = render_clue_context(
                game.puz_data,
                "".join(game.current_fill),
                direction,
                clue_info,
            )

            lines = [
                f"# {num} {direction.title()}",
                "",
                clue_text or "No clue text available",
                "",
                f"Length: {clue_info['len']} letters",
                "",
                "```",
                context,
                "```",
                "",
            ]

            if is_solved:
                lines.append("Status: Solved!")
            else:
                lines.append(f"=> /puzzle/answer/{direction}/{num} Enter Answer")

            lines.extend(
                [
                    f"=> /puzzle/clear/{direction}/{num} Clear Answer",
                    "",
                    "=> /puzzle Back to Puzzle",
                ]
            )

            return "\n".join(lines)

    @app.input(
        "/puzzle/answer/{direction}/{num}",
        prompt="Enter your answer (use SPACE for blanks):",
    )
    @require_certificate
    def submit_answer(request: Request, direction: str, num: int, query: str):
        """Process answer submission."""
        identity = get_identity(request)

        if direction.lower() not in ["across", "down"]:
            return "# Invalid Direction\n\n=> /puzzle Back to Puzzle"

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)
            puzzle = get_or_assign_todays_puzzle(session)

            if not puzzle:
                return "# No Puzzle Available\n\n=> / Home"

            config = request.app.state.config
            game = GameState.load_or_create(session, user, puzzle, config.puzzles_dir)

            is_correct, message = game.submit_answer(direction, num, query)
            game.save()

            lines = [
                "# Answer Submitted",
                "",
                f"Your answer: {query.upper()}",
                f"Result: {message}",
                "",
            ]

            if game.is_complete():
                lines.extend(
                    [
                        "PUZZLE COMPLETE! Congratulations!",
                        "",
                        "=> /leaderboard View Leaderboard",
                    ]
                )
            else:
                lines.append(f"=> /puzzle/clue/{direction}/{num} Back to Clue")

            lines.append("=> /puzzle Back to Puzzle")

            return "\n".join(lines)

    @app.gemini("/puzzle/clear/{direction}/{num}")
    @require_certificate
    def clear_answer(request: Request, direction: str, num: int):
        """Clear the answer for a specific clue."""
        identity = get_identity(request)

        if direction.lower() not in ["across", "down"]:
            return "# Invalid Direction\n\n=> /puzzle Back to Puzzle"

        with Session(request.app.state.engine) as session:
            user = get_or_create_user(session, identity.fingerprint)
            puzzle = get_or_assign_todays_puzzle(session)

            if not puzzle:
                return "# No Puzzle Available\n\n=> / Home"

            config = request.app.state.config
            game = GameState.load_or_create(session, user, puzzle, config.puzzles_dir)

            game.clear_answer(direction, num)
            game.save()

            return f"""# Answer Cleared

The answer for {num} {direction.title()} has been cleared.

=> /puzzle/clue/{direction}/{num} Back to Clue
=> /puzzle Back to Puzzle
"""
