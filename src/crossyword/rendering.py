"""ASCII crossword grid rendering."""

import puz

SUPERSCRIPT_DIGITS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


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
    |⁵   |####|####|####|⁶   |
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
                row_cells.append("#" * cell_width)
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
            letters.append("#")
        else:
            letters.append(char)

    if direction.lower() == "across":
        return "Current: " + " ".join(letters)
    else:
        return "Current:\n" + "\n".join(letters)


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
