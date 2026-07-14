#!/usr/bin/env python3
"""
Telegram Session String Generator

This script generates a session string that can be used for Telegram authentication
with the Telegram MCP server. The session string allows for portable authentication
without storing session files.

Usage:
    python session_string_generator.py

Requirements:
    - telethon
    - python-dotenv

Note on ID Formats:
When using the MCP server, please be aware that all `chat_id` and `user_id`
parameters support integer IDs, string representations of IDs (e.g., "123456"),
and usernames (e.g., "@mychannel").
"""

import asyncio
import io
import os
import re
import sys
import webbrowser
from pathlib import Path
from typing import List, Tuple

from dotenv import load_dotenv
from telethon import errors
from telethon.sessions import StringSession
from telethon.sync import TelegramClient

load_dotenv()


def _qr_login(client: TelegramClient) -> None:
    import qrcode

    qr = client.qr_login()

    print("\n----- QR Code Login -----\n")

    qr_obj = qrcode.QRCode(border=1)
    qr_obj.add_data(qr.url)
    qr_obj.make(fit=True)
    f = io.StringIO()
    qr_obj.print_ascii(out=f, invert=True)
    print(f.getvalue())

    print("Scan the QR code above with your Telegram app:")
    print("  Open Telegram > Settings > Devices > Link Desktop Device\n")
    print(f"Or open this link on a device where you're logged in:\n  {qr.url}\n")
    print(f"Expires at: {qr.expires.strftime('%H:%M:%S')}")
    print("Waiting for you to scan...")

    try:
        client.loop.run_until_complete(qr.wait(timeout=120))
    except asyncio.TimeoutError:
        print("\nQR code expired. Please try again.")
        client.disconnect()
        sys.exit(1)
    except errors.SessionPasswordNeededError:
        pw = input("\nTwo-factor authentication enabled. Please enter your password: ")
        client.sign_in(password=pw)


def _phone_login(client: TelegramClient, phone: str = "") -> None:
    if not phone:
        phone = input("Please enter your phone (or bot token): ").strip()

    try:
        client.send_code_request(phone)
    except errors.FloodWaitError as e:
        print(f"\nFlood wait error; you must wait {e.seconds} seconds before trying again.")
        client.disconnect()
        sys.exit(1)
    except errors.PhoneNumberInvalidError:
        print("\nThe phone number is invalid.")
        client.disconnect()
        sys.exit(1)
    except Exception as e:
        print(f"\nError sending code: {e}")
        client.disconnect()
        sys.exit(1)

    code = input("\nPlease enter the code you received: ")
    try:
        client.sign_in(phone, code)
    except errors.SessionPasswordNeededError:
        pw = input("Two-factor authentication enabled. Please enter your password: ")
        client.sign_in(password=pw)


def _choose_login_method() -> str:
    print("Choose login method:")
    print("  1) QR code login (recommended -- scan from your Telegram app)")
    print("  2) Phone number + verification code")
    return input("\nEnter 1 or 2 [default: 1]: ").strip() or "1"


def _normalize_label(label: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", label.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "default"


def _session_env_key(label: str) -> str:
    normalized_label = _normalize_label(label)
    if normalized_label == "default":
        return "TELEGRAM_SESSION_STRING"
    return f"TELEGRAM_SESSION_STRING_{normalized_label}"


def _set_env_var(env_path: Path, key: str, value: str) -> None:
    line = f"{key}={value}\n"
    env_contents = env_path.read_text().splitlines(keepends=True) if env_path.exists() else []

    for index, existing_line in enumerate(env_contents):
        if existing_line.startswith(f"{key}="):
            env_contents[index] = line
            break
    else:
        env_contents.append(line)

    env_path.write_text("".join(env_contents))


def _update_env_file(
    session_string: str,
    env_path: Path,
    label: str = "",
) -> None:
    _set_env_var(env_path, _session_env_key(label), session_string)


def _prompt_for_api_credentials() -> Tuple[int, str]:
    """Guide the user through obtaining TELEGRAM_API_ID / TELEGRAM_API_HASH.

    Opens https://my.telegram.org/apps in the default browser and walks the
    user through creating an application, then prompts them to paste the
    resulting credentials. Returns a validated (api_id, api_hash) pair.
    """
    apps_url = "https://my.telegram.org/apps"

    print("\n----- Telegram API Credentials Setup -----\n")
    print("You need a TELEGRAM_API_ID and TELEGRAM_API_HASH to continue.")
    print("Follow these steps:")
    print(f"  1) Log in at {apps_url} with your phone number.")
    print("  2) Open 'API development tools'.")
    print("  3) Create an application (any title/short name; platform 'Desktop').")
    print("  4) Copy the 'App api_id' and 'App api_hash' values shown.\n")

    if input("Open the page in your browser now? (Y/n): ").strip().lower() != "n":
        try:
            webbrowser.open(apps_url)
        except Exception as e:
            print(f"Could not open a browser automatically: {e}")
            print(f"Please open {apps_url} manually.")

    while True:
        api_id_raw = input("\nEnter your TELEGRAM_API_ID: ").strip()
        try:
            api_id = int(api_id_raw)
        except ValueError:
            print("API ID must be an integer. Please try again.")
            continue

        api_hash = input("Enter your TELEGRAM_API_HASH: ").strip()
        if not api_hash:
            print("API hash cannot be empty. Please try again.")
            continue

        return api_id, api_hash


def _resolve_api_credentials() -> Tuple[int, str]:
    api_id_raw = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")

    if api_id_raw and api_hash:
        try:
            return int(api_id_raw), api_hash
        except ValueError:
            print("Warning: TELEGRAM_API_ID is not a valid integer; re-entering.")

    api_id, api_hash = _prompt_for_api_credentials()

    save = (
        input("\nSave these credentials to your .env file for next time? (Y/n): ").strip().lower()
    )
    if save != "n":
        try:
            env_path = Path(".env")
            _set_env_var(env_path, "TELEGRAM_API_ID", str(api_id))
            _set_env_var(env_path, "TELEGRAM_API_HASH", api_hash)
            print(".env file updated with API credentials.")
        except Exception as e:
            print(f"Could not update .env file: {e}")

    return api_id, api_hash


def _authenticate_account(
    api_id: int,
    api_hash: str,
    label: str,
    method: str,
    phone: str = "",
) -> str:
    client = TelegramClient(StringSession(), api_id, api_hash)
    client.connect()

    try:
        if not client.is_user_authorized():
            if method == "1":
                _qr_login(client)
            else:
                _phone_login(client, phone)

        session_string = StringSession.save(client.session)
        print("\nAuthentication successful!")
        print("\n----- Session String -----")
        print(f"\n{session_string}\n")
        print(f"Environment key: {_session_env_key(label)}")
        return session_string
    finally:
        client.disconnect()


def _single_account_flow(api_id: int, api_hash: str) -> Tuple[str, str]:
    print("This script will generate a session string for your Telegram account.")
    print("The generated session string can be added to your .env file.")
    print(
        "\nYour credentials will NOT be stored on any server and are only used for local authentication.\n"
    )

    method = _choose_login_method()
    label = ""
    session_string = _authenticate_account(api_id, api_hash, label, method)
    return label, session_string


def _multi_account_flow(api_id: int, api_hash: str) -> List[Tuple[str, str]]:
    sessions: List[Tuple[str, str]] = []

    print("\nLet's set up your Telegram accounts one at a time.")
    print("For each account I'll ask for the phone number, then guide you")
    print("through entering the login code Telegram sends you.\n")

    while True:
        account_no = len(sessions) + 1
        print(f"\n===== Account {account_no} =====")

        phone = input("Phone number in international format (e.g. +4512345678): ").strip()

        label = input("Label for this account [blank = auto-name]: ").strip()
        if not label:
            label = f"account_{account_no}"

        print("\nHow do you want to log in to this account?")
        method = _choose_login_method()

        try:
            session_string = _authenticate_account(api_id, api_hash, label, method, phone)
            sessions.append((label, session_string))
        except Exception as e:
            print(f"\nCould not authenticate this account: {e}")
            retry = input("Try this account again? (y/N): ").strip().lower()
            if retry == "y":
                continue

        another = input("\nAdd another account? (y/N): ").strip().lower()
        if another != "y":
            break

    return sessions


def main() -> None:
    print("\n----- Telegram Session String Generator -----\n")

    API_ID, API_HASH = _resolve_api_credentials()

    multi_account = (
        input("Generate session strings for multiple accounts? (y/N): ").strip().lower()
    )

    try:
        if multi_account == "y":
            sessions = _multi_account_flow(API_ID, API_HASH)
        else:
            sessions = [_single_account_flow(API_ID, API_HASH)]

        if not sessions:
            print("No accounts were authenticated.")
            return

        print("\nIMPORTANT: Keep these strings private and never share them with anyone!")

        choice = input(
            "\nWould you like to automatically update your .env file with these session strings? (y/N): "
        )
        if choice.lower() == "y":
            try:
                env_path = Path(".env")
                for label, session_string in sessions:
                    _update_env_file(session_string, env_path, label)

                print("\n.env file updated successfully!")
            except Exception as e:
                print(f"\nError updating .env file: {e}")
                print("Please manually add the session strings to your .env file.")

    except Exception as e:
        print(f"\nError: {e}")
        print("Failed to generate session string. Please try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
