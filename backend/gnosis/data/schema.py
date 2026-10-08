"""The database schema (ADR 0002): what the tables are. Changes to it are
made only through a new Alembic migration (backend/migrations/versions/);
tests check the migrated database matches this file.

Identity and access: users, identities, credentials, sessions, roles,
permissions, invites. Learning: settings, goals, study days and the lesson
slots of each day, with their content, chat, quiz, review cards, mastery
evidence, practice items and explanation as rows of their own. Operations:
usage, signals, audit log.

JSON columns hold only what is a document by nature: a question with its
options, a goal's path, a reading plan, a setup draft, preferences."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Column, Date, DateTime, Float, ForeignKey, Identity,
                        Index, Integer, MetaData, PrimaryKeyConstraint, Table, Text, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB, UUID

NAMING = {"ix": "ix_%(table_name)s_%(column_0_N_name)s", "uq": "uq_%(table_name)s_%(column_0_N_name)s",
          "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_N_name)s",
          "pk": "pk_%(table_name)s"}
metadata = MetaData(naming_convention=NAMING)


def _created():
    return Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())


def _user_fk(**kw):
    return Column("user_id", UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, **kw)


# ---------------------------------------------------------------- identity
users = Table(
    "users", metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("legacy_id", Text, unique=True),            # the id in the system the account came from (Supabase)
    Column("email", Text, unique=True),                 # lower-case
    Column("display_name", Text, nullable=False, server_default=""),
    Column("avatar_url", Text, nullable=False, server_default=""),
    Column("status", Text, nullable=False, server_default="active"),
    _created(),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_seen_at", DateTime(timezone=True)),
    CheckConstraint("status in ('active', 'suspended', 'deleted')", name="status"),
    CheckConstraint("email = lower(email)", name="email_lower"),
)

identities = Table(
    "identities", metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    _user_fk(),
    Column("provider", Text, nullable=False),           # 'google', 'email', later others
    Column("subject", Text, nullable=False),            # the provider's stable id for the person
    Column("email", Text),
    _created(),
    UniqueConstraint("provider", "subject"),
    Index("ix_identities_user_id", "user_id"),
)

credentials = Table(
    "credentials", metadata,
    Column("user_id", UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("password_hash", Text, nullable=False),
    Column("algorithm", Text, nullable=False),          # 'argon2id'; 'bcrypt' for hashes imported as they were
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("algorithm in ('argon2id', 'bcrypt')", name="algorithm"),
)

sessions = Table(
    "sessions", metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")),
    _user_fk(),
    Column("token_hash", Text, nullable=False, unique=True),   # sha-256 of the cookie value; the value is never stored
    _created(),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    Column("ip", Text),
    Column("user_agent", Text),
    Index("ix_sessions_user_id", "user_id"),
)

roles = Table(
    "roles", metadata,
    Column("name", Text, primary_key=True),
    Column("description", Text, nullable=False, server_default=""),
    Column("builtin", Boolean, nullable=False, server_default=text("false")),
)

permissions = Table(
    "permissions", metadata,
    Column("name", Text, primary_key=True),             # 'users.read', 'users.suspend', 'content.edit', …
    Column("description", Text, nullable=False, server_default=""),
)

role_permissions = Table(
    "role_permissions", metadata,
    Column("role", Text, ForeignKey("roles.name", ondelete="CASCADE"), nullable=False),
    Column("permission", Text, ForeignKey("permissions.name", ondelete="CASCADE"), nullable=False),
    PrimaryKeyConstraint("role", "permission"),
)

user_roles = Table(
    "user_roles", metadata,
    _user_fk(),
    Column("role", Text, ForeignKey("roles.name", ondelete="CASCADE"), nullable=False),
    _created(),
    PrimaryKeyConstraint("user_id", "role"),
)

invites = Table(
    "invites", metadata,
    Column("email", Text, primary_key=True),
    Column("note", Text, nullable=False, server_default=""),
    Column("invited_by", UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")),
    _created(),
    CheckConstraint("email = lower(email)", name="email_lower"),
)

# ---------------------------------------------------------------- her setup
user_settings = Table(
    "user_settings", metadata,
    Column("user_id", UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("units_per_day", Integer, nullable=False),
    Column("reading_enabled", Boolean, nullable=False, server_default=text("false")),
    Column("onboarding", JSONB),                         # a setup in progress (a draft: a document)
    Column("onboarded_at", Text),                        # as the app wrote it (ISO time)
    Column("updated_at", Text),
)

user_subjects = Table(                                   # her subjects and goals, in their turn order
    "user_subjects", metadata,
    _user_fk(),
    Column("subject", Text, nullable=False),
    Column("position", Integer, nullable=False),
    PrimaryKeyConstraint("user_id", "subject"),
)

subject_levels = Table(                                  # her starting level per subject (kept for ones taken out)
    "subject_levels", metadata,
    _user_fk(),
    Column("subject", Text, nullable=False),
    Column("level", Text),
    PrimaryKeyConstraint("user_id", "subject"),
)

goals = Table(
    "goals", metadata,
    _user_fk(),
    Column("id", Text, nullable=False),                  # 'g-' + 8 hex (the subject id of a goal)
    Column("path", JSONB, nullable=False),               # the designed path (coach/paths.py)
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    PrimaryKeyConstraint("user_id", "id"),
)

preferences = Table(
    "preferences", metadata,
    Column("user_id", UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("data", JSONB, nullable=False),               # coach/prefs.py (reminders, light day, practice set)
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

reading_books = Table(
    "reading_books", metadata,
    _user_fk(),
    Column("id", Text, nullable=False),
    Column("data", JSONB, nullable=False),               # coach/books.py: the plan and its days (to be split in a later step)
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    PrimaryKeyConstraint("user_id", "id"),
)

# ---------------------------------------------------------------- learning
study_days = Table(                                      # one day of one subject (was learning_entries)
    "study_days", metadata,
    _user_fk(),
    Column("day", Date, nullable=False),
    Column("subject", Text, nullable=False),
    Column("session_number", Integer, nullable=False),
    Column("level", Text, nullable=False, server_default=""),
    Column("completed", Boolean, nullable=False, server_default=text("false")),
    Column("title", Text, nullable=False, server_default=""),
    Column("followup_question", Text, nullable=False, server_default=""),
    Column("reflection", Text, nullable=False, server_default=""),
    # days from before lessons were split into slots kept their one lesson here
    Column("legacy_lesson", Text, nullable=False, server_default=""),
    Column("legacy_kickoff", Text, nullable=False, server_default=""),
    Column("legacy_followups", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    PrimaryKeyConstraint("user_id", "day", "subject"),
    Index("ix_study_days_user_id_subject", "user_id", "subject"),
)

day_lessons = Table(                                     # a lesson planned on a day (a slot)
    "day_lessons", metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    _user_fk(),
    Column("day", Date, nullable=False),
    Column("subject", Text, nullable=False),
    Column("lesson_no", Integer, nullable=False),
    Column("position", Integer, nullable=False),
    Column("title", Text, nullable=False, server_default=""),
    Column("unit", Text, nullable=False, server_default=""),
    Column("completed", Boolean, nullable=False, server_default=text("false")),
    Column("from_day", Date),                            # a link to the day the lesson was written
    Column("passed_on", Date),                           # passed on a later day than written
    Column("tracks_cards", Boolean, nullable=False, server_default=text("false")),     # made since review began
    Column("tracks_evidence", Boolean, nullable=False, server_default=text("false")),  # made since mastery began
    UniqueConstraint("user_id", "day", "subject", "lesson_no"),
    Index("ix_day_lessons_user_id_subject_lesson_no", "user_id", "subject", "lesson_no"),
)

lesson_contents = Table(
    "lesson_contents", metadata,
    Column("slot_id", BigInteger, ForeignKey("day_lessons.id", ondelete="CASCADE"), primary_key=True),
    Column("kickoff", Text, nullable=False, server_default=""),
    Column("body", Text, nullable=False, server_default=""),     # the generated lesson
)

lesson_messages = Table(                                 # her questions to the coach and its answers
    "lesson_messages", metadata,
    Column("slot_id", BigInteger, ForeignKey("day_lessons.id", ondelete="CASCADE"), nullable=False),
    Column("position", Integer, nullable=False),
    Column("role", Text, nullable=False),
    Column("content", Text, nullable=False),
    PrimaryKeyConstraint("slot_id", "position"),
    CheckConstraint("role in ('user', 'assistant')", name="role"),
)

quizzes = Table(                                         # a lesson's current quiz
    "quizzes", metadata,
    Column("slot_id", BigInteger, ForeignKey("day_lessons.id", ondelete="CASCADE"), primary_key=True),
    Column("quiz_key", Text, nullable=False),
    Column("submitted", Boolean, nullable=False),
    Column("score", Integer),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("best", Integer),
    Column("draft", JSONB),                              # answers given so far, before submitting
)

quiz_questions = Table(
    "quiz_questions", metadata,
    Column("slot_id", BigInteger, ForeignKey("quizzes.slot_id", ondelete="CASCADE"), nullable=False),
    Column("position", Integer, nullable=False),
    Column("kind", Text, nullable=False),                # choice, scenario, blank, order, match, short, apply
    Column("from_lesson", Integer),                      # a question on an earlier lesson (not scored)
    Column("body", JSONB, nullable=False),               # the question as asked: options, key, why…
    Column("answer", JSONB),                             # her submitted answer
    Column("mark", Float),                               # 0..1; null while a written answer awaits marking
    Column("feedback", Text),
    PrimaryKeyConstraint("slot_id", "position"),
)

review_cards = Table(
    "review_cards", metadata,
    Column("slot_id", BigInteger, ForeignKey("day_lessons.id", ondelete="CASCADE"), nullable=False),
    Column("position", Integer, nullable=False),
    Column("card_id", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("front", Text, nullable=False),
    Column("back", Text, nullable=False),
    Column("box", Integer, nullable=False),
    Column("due", Date, nullable=False),
    Column("added", Date, nullable=False),
    Column("last", Date),
    Column("reviews", Integer, nullable=False),
    Column("lapses", Integer, nullable=False),
    Column("paused", Boolean, nullable=False),
    Column("card_topic", Text),
    Column("card_lesson_no", Integer),
    Column("example", Text),
    Column("question", JSONB),
    PrimaryKeyConstraint("slot_id", "card_id"),
    Index("ix_review_cards_due", "due"),
)

review_card_removals = Table(
    "review_card_removals", metadata,
    Column("slot_id", BigInteger, ForeignKey("day_lessons.id", ondelete="CASCADE"), nullable=False),
    Column("card_id", Text, nullable=False),
    PrimaryKeyConstraint("slot_id", "card_id"),
)

mastery_evidence = Table(
    "mastery_evidence", metadata,
    Column("slot_id", BigInteger, ForeignKey("day_lessons.id", ondelete="CASCADE"), nullable=False),
    Column("evidence_id", Text, nullable=False),
    Column("position", Integer, nullable=False),
    Column("day", Date, nullable=False),
    Column("kind", Text, nullable=False),
    Column("score", Float, nullable=False),
    PrimaryKeyConstraint("slot_id", "evidence_id"),
    CheckConstraint("score >= 0 and score <= 1", name="score"),
)

practice_items = Table(
    "practice_items", metadata,
    Column("slot_id", BigInteger, ForeignKey("day_lessons.id", ondelete="CASCADE"), nullable=False),
    Column("position", Integer, nullable=False),
    Column("body", JSONB, nullable=False),
    PrimaryKeyConstraint("slot_id", "position"),
)

explanations = Table(
    "explanations", metadata,
    Column("slot_id", BigInteger, ForeignKey("day_lessons.id", ondelete="CASCADE"), primary_key=True),
    Column("at", Text, nullable=False),
    Column("text", Text, nullable=False),
    Column("feedback", JSONB),
    Column("reply", Text),
    Column("reply_feedback", JSONB),
)

# ---------------------------------------------------------------- operations
ai_usage = Table(
    "ai_usage", metadata,
    _user_fk(),
    Column("day", Date, nullable=False),
    Column("request_count", Integer, nullable=False, server_default="0"),
    Column("token_count", Integer, nullable=False, server_default="0"),
    PrimaryKeyConstraint("user_id", "day"),
)

usage_events = Table(
    "usage_events", metadata,
    _user_fk(),
    Column("day", Date, nullable=False),
    Column("event", Text, nullable=False),
    Column("count", Integer, nullable=False, server_default="1"),
    PrimaryKeyConstraint("user_id", "day", "event"),
)

learning_signals = Table(
    "learning_signals", metadata,
    _user_fk(),
    Column("day", Date, nullable=False),
    Column("event", Text, nullable=False),
    Column("count", Integer, nullable=False, server_default="1"),
    PrimaryKeyConstraint("user_id", "day", "event"),
)

audit_log = Table(                                       # append-only: who did what to what, when, from where
    "audit_log", metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("actor_user_id", UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")),
    Column("action", Text, nullable=False),
    Column("target_type", Text),
    Column("target_id", Text),
    Column("ip", Text),
    Column("details", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Index("ix_audit_log_at", "at"),
)

# the roles and permissions every installation starts with (migration 0001 seeds them)
BUILTIN_ROLES = {
    "user": "A learner",
    "staff": "Can see users and learning data to help them",
    "editor": "Can edit courses, lessons and knowledge",
    "moderator": "Can review and act on user content",
    "admin": "Can manage users, invites, content and configuration",
    "super_admin": "Everything, including roles and system configuration",
}
BUILTIN_PERMISSIONS = {
    "users.read": "See users and their profiles",
    "users.update": "Change a user's profile or status",
    "users.suspend": "Suspend or reactivate an account",
    "users.delete": "Delete an account and its data",
    "roles.assign": "Give or take a role",
    "invites.manage": "Add or remove invitations",
    "learning.read": "See learning progress (support)",
    "content.edit": "Edit courses, lessons and knowledge",
    "insights.read": "See the product's numbers",
    "ai.config.edit": "Change AI models, prompts and limits",
    "system.config.edit": "Change system configuration",
    "audit.read": "Read the audit log",
}
ROLE_GRANTS = {
    "user": [],
    "staff": ["users.read", "learning.read"],
    "editor": ["content.edit"],
    "moderator": ["users.read", "users.suspend"],
    "admin": ["users.read", "users.update", "users.suspend", "invites.manage", "learning.read", "content.edit",
              "insights.read", "audit.read"],
    "super_admin": sorted(BUILTIN_PERMISSIONS),
}
