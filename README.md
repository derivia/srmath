# SRMath

SRMath is a spaced repetition system to help students efficiently study by
managing questions and review cycles.
It is intended for math review studies, but can be used for other topics.

## Features

- Create, edit, and delete questions
- Track review history and due dates
- Automatically schedule reviews with spaced repetition
- Customize datetime format
- Purge database of all questions and history

## Installation

1. Clone the repo:
    ```bash
    git clone https://github.com/derivia/srmath.git
    cd srmath
    ```

2. Set up virtual environment:
    ```bash
    python3 -m venv .venv_srmath
    ```

3. Activate the environment:
    - On Linux/macOS:
        ```bash
        source .venv_srmath/bin/activate
        ```
    - On Windows:
        ```bash
        .venv_srmath\Scripts\activate
        ```

4. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

The `.srmath.conf` file is used for settings like questions per day and datetime
format.

### Example `.srmath.conf`:

```ini
[DEFAULT]
questions_due_per_day = 10
datetime_format = %d/%m/%Y
```

## Commands

### `list`
Show today's due questions:
```bash
python srmath.py list --limit 5
```

### `question <id>`
Show details of a specific question:
```bash
python srmath.py question 2
```

### `answer <id>`
Show the answer for a specific question:
```bash
python srmath.py answer 2
```

### `edit <id>`
Edit an existing question:
```bash
python srmath.py edit 2
```

### `create`
Create a new question:
```bash
python srmath.py create
```

### `reset`
Reset the database (delete all data):
```bash
python srmath.py reset
```

### `delete_history <id>`
Delete history for a specific question:
```bash
python srmath.py delete_history 2
```

### `mark`
Start reviweing due questions for today:
```bash
python srmath.py mark
```

## How It Works

The app uses a spaced repetition algorithm to schedule question reviews. The
interval between reviews increases as you get questions right.

### Review Feedback Options:

- **again**: Review again today
- **hard**: Question was difficult
- **good**: Correct answer
- **easy**: Question was too easy

## Backlog

Improvements for future versions:

- [ ] Separate code into multiple files
- [ ] Allow easy global installation
- [ ] Import/Export Features
- [ ] Search functionality

## License

MIT License - see the [LICENSE](LICENSE) file for details.
