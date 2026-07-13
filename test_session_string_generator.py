from pathlib import Path

from session_string_generator import (
    _normalize_label,
    _session_env_key,
    _set_env_var,
    _update_env_file,
)


def test_normalize_label_defaults_to_default():
    assert _normalize_label("") == "default"


def test_session_env_key_uses_label_suffix():
    expected = "TELEGRAM_SESSION_STRING_primary_phone"
    assert _session_env_key("Primary Phone") == expected


def test_update_env_file_replaces_and_appends(tmp_path):
    env_path = Path(tmp_path) / ".env"
    env_path.write_text(
        "TELEGRAM_SESSION_STRING=old\nOTHER=value\n",
        encoding="utf-8",
    )

    _update_env_file("new-session", env_path)
    _update_env_file("work-session", env_path, "Work Account")

    assert env_path.read_text(encoding="utf-8") == (
        "TELEGRAM_SESSION_STRING=new-session\n"
        "OTHER=value\n"
        "TELEGRAM_SESSION_STRING_work_account=work-session\n"
    )


def test_set_env_var_creates_and_updates(tmp_path):
    env_path = Path(tmp_path) / ".env"

    _set_env_var(env_path, "TELEGRAM_API_ID", "12345")
    _set_env_var(env_path, "TELEGRAM_API_HASH", "abcdef")
    _set_env_var(env_path, "TELEGRAM_API_ID", "67890")

    assert env_path.read_text(encoding="utf-8") == (
        "TELEGRAM_API_ID=67890\n" "TELEGRAM_API_HASH=abcdef\n"
    )
