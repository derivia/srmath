#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os
import click
import math
from pathlib import Path
from typing import List, Optional, Tuple
import questionary
import rich
import random
from rich.console import Console
from rich.table import Table
from dataclasses import dataclass
from rich.markdown import Markdown
import textwrap
from datetime import datetime, timedelta
import configparser


def adapt_datetime(dt: datetime) -> str:
    return dt.isoformat() if dt else None


def convert_datetime(s: bytes) -> Optional[datetime]:
    return datetime.fromisoformat(s.decode()) if s else None


sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)


@dataclass
class Question:
    id: Optional[int]
    book: str
    page: int
    content: str
    answer: str
    difficulty: float = 0.3
    stability: float = 0.0
    last_review: Optional[datetime] = None
    due_date: Optional[datetime] = None


class StudyDB:
    def __init__(self):
        self.db_path = Path.home() / ".math_study.db"
        self.conn = sqlite3.connect(
            str(self.db_path), detect_types=sqlite3.PARSE_DECLTYPES
        )
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY,
                book TEXT NOT NULL,
                page INTEGER NOT NULL,
                content TEXT NOT NULL,
                answer TEXT NOT NULL,
                difficulty REAL DEFAULT 0.3,
                stability REAL DEFAULT 0.0,
                last_review timestamp,
                due_date timestamp
            );

            CREATE TABLE IF NOT EXISTS question_history (
                id INTEGER PRIMARY KEY,
                question_id INTEGER NOT NULL,
                difficulty REAL NOT NULL,  -- Changed from TEXT to REAL
                review_date timestamp NOT NULL,
                FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_due_date ON questions(due_date);
            CREATE INDEX IF NOT EXISTS idx_question_history ON question_history(question_id);
        """
        )
        self.conn.commit()

    def reset_db(self):
        self.conn.executescript(
            """
            DROP TABLE IF EXISTS question_history;
            DROP TABLE IF EXISTS questions;
        """
        )
        self.init_db()

    def create_question(self, question: Question) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO questions (book, page, content, answer, due_date)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                question.book,
                question.page,
                question.content,
                question.answer,
                datetime.now(),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_question(self, question_id: int) -> Optional[Question]:
        row = self.conn.execute(
            "SELECT * FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
        return Question(**dict(row)) if row else None

    def get_questions(self, limit: int) -> List[Question]:
        if limit is not None:
            rows = self.conn.execute(
                "SELECT * FROM questions LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM questions").fetchall()
        return [Question(**dict(row)) for row in rows] if rows else None

    def update_question(self, question: Question):
        self.conn.execute(
            """
            UPDATE questions
            SET book = ?, page = ?, content = ?, answer = ?, difficulty = ?,
                stability = ?, last_review = ?, due_date = ?
            WHERE id = ?
        """,
            (
                question.book,
                question.page,
                question.content,
                question.answer,
                question.difficulty,
                question.stability,
                question.last_review,
                question.due_date,
                question.id,
            ),
        )
        self.conn.commit()

    def get_due_questions(self, limit: Optional[int] = None) -> List[Question]:
        query = """
            SELECT * FROM questions
            WHERE due_date <= ? OR due_date IS NULL
            ORDER BY due_date ASC NULLS FIRST
        """
        if limit:
            query += f" LIMIT {limit}"

        rows = self.conn.execute(query, (datetime.now(),)).fetchall()
        return [Question(**dict(row)) for row in rows]

    def delete_history(self, question_id: Optional[int] = None):
        if question_id:
            self.conn.execute(
                """
                UPDATE questions
                SET difficulty = 0.3, stability = 0.0, last_review = NULL, due_date = ?
                WHERE id = ?
            """,
                (datetime.now(), question_id),
            )
            self.conn.execute(
                "DELETE FROM question_history WHERE question_id = ?", (question_id,)
            )
        else:
            self.conn.execute(
                """
                UPDATE questions
                SET difficulty = 0.3, stability = 0.0, last_review = NULL, due_date = ?
            """,
                (datetime.now(),),
            )
            self.conn.execute("DELETE FROM question_history")
        self.conn.commit()

    def get_question_status(self, question_id: int) -> List[Tuple[str, datetime]]:
        rows = self.conn.execute(
            "SELECT difficulty, review_date FROM question_history WHERE question_id = ? ORDER BY review_date DESC",
            (question_id,),
        ).fetchall()
        difficulty_map = {1.0: "again", 2.0: "hard", 3.0: "good", 4.0: "easy"}
        return [
            (
                difficulty_map.get(
                    float(row["difficulty"]),
                    "unknown",
                ),
                row["review_date"],
            )
            for row in rows
        ]


class FSRS:
    def __init__(self):
        self.w = [0.4, 0.6, 2.4, 5.8, 4.93, 0.94, 0.86, 0.01, 1.49, 0.14, 0.94]
        self.difficulty_map = {1: "again", 2: "hard", 3: "good", 4: "easy"}

    def compute_next_review(
        self, q: Question, difficulty: str
    ) -> Tuple[float, float, datetime]:
        rating_map = {"again": 1, "hard": 2, "good": 3, "easy": 4}
        rating = rating_map[difficulty]

        new_difficulty = self._update_difficulty(q.difficulty, rating)
        new_stability = self._update_stability(q.stability, rating, new_difficulty)

        interval = self._calculate_interval(new_stability, new_difficulty, rating)
        next_date = datetime.now() + timedelta(days=interval)

        return (
            float(rating),
            new_stability,
            next_date,
        )

    def _update_difficulty(self, difficulty: float, rating: int) -> float:
        if rating == 1:
            return difficulty + self.w[0] * (1 - difficulty)
        elif rating == 4:
            return difficulty + self.w[0] * (0 - difficulty)
        else:
            return difficulty + self.w[0] * (1 / rating - 1)

    def _update_stability(
        self, stability: float, rating: int, difficulty: float
    ) -> float:
        if rating == 1:
            return self.w[1]
        new_stability = stability * (
            1
            + math.exp(self.w[2])
            * (11 - rating)
            * math.pow(stability + 1, -self.w[3])
            * math.exp((1 - difficulty) * self.w[4])
        )
        return max(self.w[1], new_stability)

    def _calculate_interval(
        self, stability: float, difficulty: float, rating: int
    ) -> float:
        base_interval = stability * math.exp((1 - stability) * self.w[5])
        if rating == 4:
            return base_interval * 1.3
        elif rating == 2:
            return base_interval * 0.8
        elif rating == 1:
            return 0 # again should run on the same day
        else:
            return base_interval


class StudyApp:
    def __init__(self):
        self.db = StudyDB()
        self.fsrs = FSRS()
        self.console = Console()
        self.config = self._load_config()

    def _load_config(self):
        config_path = Path.home() / ".srmath.conf"
        config = configparser.ConfigParser()
        if not config_path.exists():
            config["DEFAULT"] = {
                "questions_due_per_day": "10",
                "datetime_format": "%Y-%m-%d",  # Default format
            }
            with open(config_path, "w") as f:
                config.write(f)
        config.read(config_path)
        return config

    def get_due_limit(self):
        return int(self.config["DEFAULT"]["questions_due_per_day"])

    def get_datetime_format(self):
        return self.config["DEFAULT"].get("datetime_format", "%Y-%m-%d")

    def show_due_questions(self, limit: Optional[int] = None):
        questions = self.db.get_due_questions(limit)
        if not questions:
            self.console.print("[yellow]No questions due today![/yellow]")
            return

        table = Table(show_header=True)
        table.add_column("ID")
        table.add_column("Book")
        table.add_column("Page")
        table.add_column("Question")
        table.add_column("Due Date")

        datetime_format = self.get_datetime_format()

        for q in questions:
            due_date = q.due_date.strftime(datetime_format) if q.due_date else "New"
            table.add_row(
                str(q.id),
                q.book,
                str(q.page),
                q.content[:50] + "..." if len(q.content) > 50 else q.content,
                str(due_date),
            )

        self.console.print(table)

    def mark_done(self, question_id: int, difficulty: str):
        q = self.db.get_question(question_id)
        if not q:
            self.console.print(f"[red]Question {question_id} not found[/red]")
            return

        difficulty_float, stability, next_date = self.fsrs.compute_next_review(
            q, difficulty
        )

        q.difficulty = difficulty_float
        q.stability = stability
        q.last_review = datetime.now()
        q.due_date = next_date

        self.db.conn.execute(
            "INSERT INTO question_history (question_id, difficulty, review_date) VALUES (?, ?, ?)",
            (question_id, difficulty_float, datetime.now()),
        )

        self.db.update_question(q)
        self.console.print(
            f"[green]Next review: {next_date.strftime(self.get_datetime_format())}[/green]"
        )

    def reset_database(self):
        if questionary.confirm(
            "Are you sure you want to reset the database? This will delete all questions and progress."
        ).ask():
            self.db.reset_db()
            self.console.print("[green]Database has been reset successfully[/green]")
        else:
            self.console.print("Database reset cancelled")

    def show_question(self, question_id: int):
        q = self.db.get_question(question_id)
        if not q:
            self.console.print(f"[red]Question {question_id} not found[/red]")
            return

        datetime_format = self.get_datetime_format()

        self.console.print(f"[bold]====================================[/bold]")
        self.console.print(f"From: {q.book}, Page: {q.page}")
        self.console.print(
            f"Due date {q.due_date.strftime(datetime_format) if q.due_date else 'New'}"
        )
        self.console.print(f"\n{q.content}\n")

        history = self.db.get_question_status(question_id)
        if history:
            self.console.print("\n[bold]Review History[/bold]")
            for difficulty, review_date in history:
                formatted_review_date = review_date.strftime(datetime_format)
                self.console.print(
                    f"{difficulty.capitalize()} on {formatted_review_date}"
                )

    def show_questions_duedate(self, limit: Optional[int] = None):
        qs = self.db.get_questions(limit)
        datetime_format = self.get_datetime_format()

        for q in qs:
            self.console.print(
                f"From: {q.book}, Page: {q.page} - Due date: {q.due_date.strftime(datetime_format) if q.due_date else 'New'}"
            )
            self.console.print(f"{q.content}")

    def show_answer(self, question_id: int):
        q = self.db.get_question(question_id)
        if not q:
            self.console.print(f"[red]Question {question_id} not found[/red]")
            return

        self.console.print(f"\n[bold]Answer to Question {q.id}[/bold]")
        self.console.print(f"{q.answer}\n")

    def prompt_to_show_answer(self):
        return questionary.confirm("Show answer?").ask()

    def create_question(self):
        book = questionary.text("Book title:").ask()
        page = questionary.text("Page number:", validate=lambda x: x.isdigit()).ask()
        content = questionary.text("Question content:").ask()
        answer = questionary.text("Answer/Solution:").ask()

        q = Question(id=None, book=book, page=int(page), content=content, answer=answer)

        question_id = self.db.create_question(q)
        self.console.print(f"[green]Created question {question_id}[/green]")

    def edit_question(self, question_id: int):
        q = self.db.get_question(question_id)
        if not q:
            self.console.print(f"[red]Question {question_id} not found[/red]")
            return

        book = questionary.text("Book title:", default=q.book).ask()
        page = questionary.text("Page number:", default=str(q.page)).ask()
        content = questionary.text("Question content:", default=q.content).ask()
        answer = questionary.text("Answer/Solution:", default=q.answer).ask()

        q.book = book
        q.page = int(page)
        q.content = content
        q.answer = answer

        self.db.update_question(q)
        self.console.print(f"[green]Updated question {question_id}[/green]")

    def delete_history(self, question_id: Optional[int] = None):
        if question_id:
            self.db.delete_history(question_id)
            self.console.print(
                f"[green]History deleted for question {question_id}[/green]"
            )
        else:
            self.db.delete_history()
            self.console.print("[green]History deleted for all questions[/green]")

    def prompt_difficulty(self, question_id: int):
        if (
            self.db.get_question(question_id).last_review
            and self.db.get_question(question_id).last_review.date()
            == datetime.now().date()
        ):
            self.console.print(
                "[yellow]This question has already been reviewed today.[/yellow]"
            )
            return

        difficulty = (
            questionary.select(
                "How difficult was this question?",
                choices=[
                    "again - Need to review this again today",
                    "hard - That was difficult",
                    "good - Got it right",
                    "easy - Too easy",
                ],
            )
            .ask()
            .split(" - ")[0]
        )

        self.mark_done(question_id, difficulty)

    def mark_due_questions(self):
        limit = self.get_due_limit()
        questions = self.db.get_due_questions(limit)
        if not questions:
            self.console.print("[yellow]No questions due today![/yellow]")
            return

        random.shuffle(questions)
        for q in questions:
            self.show_question(q.id)
            if self.prompt_to_show_answer():
                self.show_answer(q.id)
            self.prompt_difficulty(q.id)


@click.group()
def cli():
    """Math Study SRS - A spaced repetition system for studying mathematics"""
    pass


@cli.command()
@click.option("--limit", "-l", type=int, help="Limit the number of questions shown")
def list(limit):
    """Show today's due questions"""
    StudyApp().show_due_questions(limit)


@cli.command()
@click.argument("question_id", type=int)
def question(question_id):
    """Show a specific question"""
    StudyApp().show_question(question_id)


@cli.command()
@click.option("--limit", "-l", type=int, help="Limit the number of questions shown")
def all_questions(limit):
    """Show all questions due date"""
    StudyApp().show_questions_duedate(limit)


@cli.command()
@click.argument("question_id", type=int)
def answer(question_id):
    """Show the answer to a specific question"""
    StudyApp().show_answer(question_id)


@cli.command()
@click.argument("question_id", type=int)
def edit(question_id):
    """Edit a question"""
    StudyApp().edit_question(question_id)


@cli.command()
def create():
    """Create a new question"""
    StudyApp().create_question()


@cli.command()
def reset():
    """Reset the database (delete all questions and progress)"""
    StudyApp().reset_database()


@cli.command()
@click.option("--all", is_flag=True, help="Delete history for all questions")
@click.argument("question_id", type=int, required=False)
def delete_history(question_id, all):
    """Delete history for a specific question or all questions"""
    StudyApp().delete_history(question_id if not all else None)


@cli.command()
def review():
    """Mark today's due questions as reviewed"""
    StudyApp().mark_due_questions()


if __name__ == "__main__":
    cli()
