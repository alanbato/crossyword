# Crossyword

Daily crossword puzzles over the Gemini protocol, built with [Xitzin](https://github.com/alanbato/xitzin).

## Features

- **Daily puzzles** - A new crossword puzzle every day
- **Certificate-based auth** - Progress tied to your Gemini client certificate
- **Persistent progress** - Your answers are saved automatically
- **Leaderboards** - Compete for the fastest completion times
- **ASCII grid display** - Clean text-based crossword rendering

## Installation

Requires Python 3.14+.

```bash
git clone https://github.com/alanbato/crossyword.git
cd crossyword
uv sync
```

## Adding Puzzles

Crossyword reads `.puz` files from the `puzzles/` directory. You can use [xword-dl](https://github.com/thisisparker/xword-dl) to download puzzles from various sources:

```bash
# Install xword-dl
uv tool install xword-dl

# Download puzzles (examples)
xword-dl nd                    # Newsday
xword-dl usa                   # USA Today
xword-dl uni --date 1/15/2025  # Universal by date

# Move to puzzles directory
mv *.puz puzzles/
```

Puzzles are automatically imported when the server starts.

## Running

```bash
uv run crossyword
```

The server starts on `gemini://localhost:1965` with auto-generated TLS certificates.

### Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CROSSYWORD_HOST` | `localhost` | Server host |
| `CROSSYWORD_PORT` | `1965` | Server port |
| `CROSSYWORD_DATABASE_URL` | `sqlite:///./crossyword.db` | Database URL |
| `CROSSYWORD_PUZZLES_DIR` | `./puzzles` | Puzzles directory |
| `CROSSYWORD_CERTFILE` | (auto) | TLS certificate path |
| `CROSSYWORD_KEYFILE` | (auto) | TLS key path |

## Playing

1. Connect with a Gemini client (Lagrange, Kristall, Amfora, etc.)
2. Enable a client certificate for identification
3. Navigate to today's puzzle
4. Select clues and enter answers word-by-word
5. Complete the puzzle to appear on the leaderboard

## Routes

| Route | Description |
|-------|-------------|
| `/` | Home page |
| `/puzzle` | Today's puzzle with grid and all clues |
| `/puzzle/clue/{direction}/{num}` | View and answer a specific clue |
| `/leaderboard` | Today's leaderboard |
| `/profile` | Your stats and history |
| `/help` | How to play |

## Tech Stack

- [Xitzin](https://github.com/alanbato/xitzin) - Gemini framework
- [puzpy](https://github.com/alexdej/puzpy) - .puz file parsing
- [SQLModel](https://sqlmodel.tiangolo.com/) - Database ORM

## License

MIT
