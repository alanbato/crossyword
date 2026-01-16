"""Home page routes."""

from sqlmodel import Session
from xitzin import Request, Xitzin
from xitzin.auth import get_identity, optional_certificate

from ..daily import get_or_assign_todays_puzzle
from ..users import get_or_create_user


def register_routes(app: Xitzin) -> None:
    """Register home page routes."""

    @app.gemini("/")
    @optional_certificate
    def home(request: Request):
        """Home page with welcome and navigation."""
        identity = request.state.identity

        lines = [
            "# Crossyword",
            "",
            "Welcome to Crossyword - Daily crossword puzzles over Gemini!",
            "",
        ]

        if identity:
            with Session(request.app.state.engine) as session:
                user = get_or_create_user(session, identity.fingerprint)
                puzzle = get_or_assign_todays_puzzle(session)

                if user.display_name:
                    lines.append(f"Hello, {user.display_name}!")
                else:
                    lines.append(f"Hello, {identity.short_id}!")
                lines.append("")

                if puzzle:
                    lines.append(f"=> /puzzle Play Today's Puzzle: {puzzle.title}")
                else:
                    lines.append("No puzzle available today. Check back soon!")
        else:
            lines.extend(
                [
                    "To play, you'll need a client certificate for identification.",
                    "Most Gemini clients can generate one for you.",
                    "",
                    "=> /puzzle Play Today's Puzzle",
                ]
            )

        lines.extend(
            [
                "",
                "=> /leaderboard Today's Leaderboard",
                "=> /help How to Play",
                "",
                "---",
                "A Xitzin-powered Gemini capsule",
            ]
        )

        return "\n".join(lines)

    @app.gemini("/help")
    def help_page(request: Request):
        """How to play instructions."""
        return """# How to Play Crossyword

## Getting Started

1. Make sure your Gemini client has a client certificate enabled
2. Visit the puzzle page to see today's crossword
3. Select a clue (Across or Down) to view it
4. Enter your answer for that clue

## Entering Answers

* Answers are entered word-by-word
* Use SPACE to leave a cell empty if you're unsure
* Your progress is saved automatically

## Scoring

* Complete the puzzle to appear on the leaderboard
* Times are measured from when you first view the puzzle
* Faster times rank higher!

## Tips

* Start with clues you're confident about
* Crossing words can help confirm your answers
* The grid shows which cells are filled

=> / Back to Home
"""
