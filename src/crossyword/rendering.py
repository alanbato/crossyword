"""ASCII crossword grid rendering."""

import puz

SUPERSCRIPT_DIGITS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
SUPERSCRIPT_CHARS = set("⁰¹²³⁴⁵⁶⁷⁸⁹")

# Black square character (Full Block)
BLACK_SQUARE = "▒"

# ANSI color codes
ANSI_RESET = "\033[0m"
ANSI_BORDER = "\033[36m"  # Cyan for borders (+, -, |)
ANSI_LETTER = "\033[32m"  # Green for filled letters
ANSI_NUMBER = "\033[33m"  # Yellow for clue numbers (superscripts)
ANSI_BLACK = "\033[36m"  # Cyan for black squares (█)


def to_superscript(num: int | str) -> str:
    """Convert a number to Unicode superscript characters."""
    return str(num).translate(SUPERSCRIPT_DIGITS)


def render_grid(puzzle: puz.Puzzle, current_fill: str) -> str:
    """
    Render crossword grid as ASCII art with superscript cell numbers.

    Format:
    +----+----+----+----+----+
    |¹H  |²E  |³L  | L  |⁴O  |
    +----+----+----+----+----+
    |⁵   |████|████|████|⁶   |
    +----+----+----+----+----+
    """
    width = puzzle.width
    height = puzzle.height
    numbering = puzzle.clue_numbering()

    number_map: dict[int, int] = {}
    for clue in numbering.across:
        number_map[clue["cell"]] = clue["num"]
    for clue in numbering.down:
        if clue["cell"] not in number_map:
            number_map[clue["cell"]] = clue["num"]

    lines = []
    cell_width = 4

    lines.append("+" + "+".join(["-" * cell_width] * width) + "+")

    for row in range(height):
        row_cells = []
        for col in range(width):
            idx = row * width + col
            cell = current_fill[idx] if idx < len(current_fill) else " "

            if cell == ".":
                row_cells.append(BLACK_SQUARE * cell_width)
            else:
                num = number_map.get(idx, "")
                letter = cell if cell not in ["-", " "] else " "

                if num:
                    sup = to_superscript(num)
                    cell_str = f"{sup}{letter}".ljust(cell_width)[:cell_width]
                else:
                    cell_str = f" {letter}".ljust(cell_width)[:cell_width]

                row_cells.append(cell_str)

        lines.append("|" + "|".join(row_cells) + "|")
        lines.append("+" + "+".join(["-" * cell_width] * width) + "+")

    return "\n".join(lines)


def render_clue_context(
    puzzle: puz.Puzzle, current_fill: str, direction: str, clue_info: dict
) -> str:
    """
    Render a focused view showing the current state of a word.

    For ACROSS: Current: _ A _ _ E
    For DOWN: Current: _/A/_/_/E (vertical display)
    """
    cell = clue_info["cell"]
    length = clue_info["len"]
    width = puzzle.width

    letters = []
    for i in range(length):
        if direction.lower() == "across":
            idx = cell + i
        else:
            idx = cell + (i * width)

        char = current_fill[idx] if idx < len(current_fill) else " "
        if char in ["-", " "]:
            letters.append("_")
        elif char == ".":
            letters.append(BLACK_SQUARE)
        else:
            letters.append(char)

    if direction.lower() == "across":
        return "Current: " + " ".join(letters)
    else:
        return "Current:\n" + "\n".join(letters)


def render_logo() -> str:
    """
    Render the Crossyword logo as ASCII art.

    Displays CROSSY horizontally with WORD vertically intersecting at O:
      W
    CROSSY
      R
      D
    """
    # Grid layout: 4 rows x 6 cols
    # Row 0: .  .  W  .  .  .
    # Row 1: C  R  O  S  S  Y
    # Row 2: .  .  R  .  .  .
    # Row 3: .  .  D  .  .  .
    grid = [
        [".", ".", "W", ".", ".", "."],
        ["C", "R", "O", "S", "S", "Y"],
        [".", ".", "R", ".", ".", "."],
        [".", ".", "D", ".", ".", "."],
    ]

    lines = []
    cell_width = 4

    lines.append("+" + "+".join(["-" * cell_width] * 6) + "+")

    for row in grid:
        row_cells = []
        for cell in row:
            if cell == ".":
                row_cells.append(BLACK_SQUARE * cell_width)
            else:
                cell_str = f" {cell}  "
                row_cells.append(cell_str)
        lines.append("|" + "|".join(row_cells) + "|")
        lines.append("+" + "+".join(["-" * cell_width] * 6) + "+")

    return "\n".join(lines)


def format_time(seconds: int) -> str:
    """Format seconds as human-readable time."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def _get_char_color(char: str) -> str | None:
    """Return the ANSI color code for a character, or None if uncolored."""
    if char in "+-|":
        return ANSI_BORDER
    elif char == BLACK_SQUARE:
        return ANSI_BLACK
    elif char.isupper():
        return ANSI_LETTER
    elif char in SUPERSCRIPT_CHARS:
        return ANSI_NUMBER
    return None


def apply_colors(ascii_art: str) -> str:
    """Apply ANSI color codes to ASCII crossword art.

    Colors:
    - Borders (+, -, |): Cyan
    - Letters (A-Z): Green
    - Clue numbers (superscript digits): Yellow
    - Black squares (█): Gray

    Batches consecutive same-colored characters for efficiency.
    """
    if not ascii_art:
        return ascii_art

    result = []
    current_color: str | None = None
    buffer: list[str] = []

    for char in ascii_art:
        color = _get_char_color(char)

        if color != current_color:
            # Flush buffer when color changes
            if buffer:
                if current_color:
                    result.append(f"{current_color}{''.join(buffer)}{ANSI_RESET}")
                else:
                    result.extend(buffer)
                buffer = []
            current_color = color

        buffer.append(char)

    # Flush remaining buffer
    if buffer:
        if current_color:
            result.append(f"{current_color}{''.join(buffer)}{ANSI_RESET}")
        else:
            result.extend(buffer)

    return "".join(result)
