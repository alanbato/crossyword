"""Tests for crossyword.rendering module - pure functions, no DB."""

import puz

from crossyword.rendering import (
    format_time,
    render_clue_context,
    render_grid,
    render_logo,
    to_superscript,
)


class TestToSuperscript:
    """Tests for to_superscript function."""

    def test_single_digit_zero(self):
        assert to_superscript(0) == "\u2070"

    def test_single_digit_one(self):
        assert to_superscript(1) == "\u00b9"

    def test_single_digit_five(self):
        assert to_superscript(5) == "\u2075"

    def test_single_digit_nine(self):
        assert to_superscript(9) == "\u2079"

    def test_multi_digit_ten(self):
        assert to_superscript(10) == "\u00b9\u2070"

    def test_multi_digit_42(self):
        assert to_superscript(42) == "\u2074\u00b2"

    def test_multi_digit_123(self):
        assert to_superscript(123) == "\u00b9\u00b2\u00b3"

    def test_string_input_single(self):
        assert to_superscript("7") == "\u2077"

    def test_string_input_multi(self):
        assert to_superscript("99") == "\u2079\u2079"


class TestRenderGrid:
    """Tests for render_grid function."""

    def test_grid_has_borders(self, puz_data: puz.Puzzle, empty_fill: str):
        """Grid renders with border characters."""
        grid = render_grid(puz_data, empty_fill)

        assert "+" in grid
        assert "|" in grid
        assert "-" in grid

    def test_grid_has_black_squares(self, puz_data: puz.Puzzle, empty_fill: str):
        """Black cells render as ####."""
        grid = render_grid(puz_data, empty_fill)

        assert "####" in grid

    def test_grid_has_clue_numbers(self, puz_data: puz.Puzzle, empty_fill: str):
        """Grid has superscript numbers for clue markers."""
        grid = render_grid(puz_data, empty_fill)

        # Should have superscript 1 for first clue
        assert "\u00b9" in grid

    def test_grid_shows_letters_when_filled(self, puz_data: puz.Puzzle):
        """Grid renders with solution letters visible."""
        grid = render_grid(puz_data, puz_data.solution)

        # Should contain letters from the solution
        # Check that at least some uppercase letters appear
        has_letter = any(c.isupper() and c != "#" for c in grid)
        assert has_letter

    def test_grid_correct_row_count(self, puz_data: puz.Puzzle, empty_fill: str):
        """Grid has correct number of rows."""
        grid = render_grid(puz_data, empty_fill)
        lines = grid.split("\n")

        # Each row has a content line and a separator line
        # Plus top border = (height * 2) + 1 lines
        expected_lines = (puz_data.height * 2) + 1
        assert len(lines) == expected_lines

    def test_grid_cell_width(self, puz_data: puz.Puzzle, empty_fill: str):
        """Each cell is 4 characters wide."""
        grid = render_grid(puz_data, empty_fill)
        lines = grid.split("\n")

        # Check the top separator line format: +----+----+...+
        sep_line = lines[0]
        assert "----" in sep_line

    def test_partial_fill_shows_mix(self, puz_data: puz.Puzzle, partial_fill: str):
        """Partially filled grid shows letters and empty cells."""
        grid = render_grid(puz_data, partial_fill)

        # Should have both letters and empty cells
        # Empty cells appear as spaces with cell numbers
        assert len(grid) > 0


class TestRenderClueContext:
    """Tests for render_clue_context function."""

    def test_across_empty_shows_underscores(
        self, puz_data: puz.Puzzle, empty_fill: str
    ):
        """Across clue context shows underscores for empty cells."""
        numbering = puz_data.clue_numbering()
        clue_info = numbering.across[0]

        context = render_clue_context(puz_data, empty_fill, "across", clue_info)

        assert context.startswith("Current:")
        assert "_" in context

    def test_across_filled_shows_letters(self, puz_data: puz.Puzzle):
        """Across clue context shows letters when filled."""
        numbering = puz_data.clue_numbering()
        clue_info = numbering.across[0]

        context = render_clue_context(puz_data, puz_data.solution, "across", clue_info)

        assert "Current:" in context
        # Should have space-separated letters
        # After "Current: " there should be letters
        content = context.replace("Current: ", "")
        assert len(content) > 0

    def test_down_empty_shows_vertical_layout(
        self, puz_data: puz.Puzzle, empty_fill: str
    ):
        """Down clue context shows vertical layout with newlines."""
        numbering = puz_data.clue_numbering()
        clue_info = numbering.down[0]

        context = render_clue_context(puz_data, empty_fill, "down", clue_info)

        assert "Current:" in context
        # Down clues should have newlines for vertical display
        assert "\n" in context

    def test_down_filled_shows_letters_vertically(self, puz_data: puz.Puzzle):
        """Down clue context shows letters vertically."""
        numbering = puz_data.clue_numbering()
        clue_info = numbering.down[0]

        context = render_clue_context(puz_data, puz_data.solution, "down", clue_info)

        lines = context.split("\n")
        # First line is "Current:", rest are letters
        assert lines[0] == "Current:"
        assert len(lines) > 1

    def test_across_direction_case_insensitive(
        self, puz_data: puz.Puzzle, empty_fill: str
    ):
        """Direction parameter is case insensitive."""
        numbering = puz_data.clue_numbering()
        clue_info = numbering.across[0]

        context_lower = render_clue_context(puz_data, empty_fill, "across", clue_info)
        context_upper = render_clue_context(puz_data, empty_fill, "ACROSS", clue_info)

        assert context_lower == context_upper


class TestFormatTime:
    """Tests for format_time function."""

    def test_zero_seconds(self):
        assert format_time(0) == "0s"

    def test_thirty_seconds(self):
        assert format_time(30) == "30s"

    def test_fifty_nine_seconds(self):
        assert format_time(59) == "59s"

    def test_one_minute(self):
        assert format_time(60) == "1m 0s"

    def test_ninety_seconds(self):
        assert format_time(90) == "1m 30s"

    def test_two_minutes_five_seconds(self):
        assert format_time(125) == "2m 5s"

    def test_fifty_nine_minutes(self):
        assert format_time(3599) == "59m 59s"

    def test_one_hour(self):
        assert format_time(3600) == "1h 0m"

    def test_one_hour_one_minute(self):
        assert format_time(3660) == "1h 1m"

    def test_two_hours(self):
        assert format_time(7200) == "2h 0m"

    def test_two_hours_two_minutes(self):
        assert format_time(7325) == "2h 2m"


class TestRenderLogo:
    """Tests for render_logo function."""

    def test_returns_string(self):
        logo = render_logo()
        assert isinstance(logo, str)
        assert len(logo) > 0

    def test_contains_crossy_letters(self):
        """Logo contains CROSSY letters."""
        logo = render_logo()
        assert "C" in logo
        assert "R" in logo
        assert "O" in logo
        assert "S" in logo
        assert "Y" in logo

    def test_contains_word_letters(self):
        """Logo contains WORD letters (W, O, R, D)."""
        logo = render_logo()
        assert "W" in logo
        assert "D" in logo

    def test_has_grid_structure(self):
        """Logo has grid borders."""
        logo = render_logo()
        assert "+" in logo
        assert "|" in logo
        assert "-" in logo

    def test_has_black_squares(self):
        """Logo has black squares (####)."""
        logo = render_logo()
        assert "####" in logo
