#!/usr/bin/env python3
"""
Valkyrie Bot Launcher for Chigwell Telegram MCP
===============================================
Integrerer C2 Bot og Verify Bot med ALIVE beskeder.
Kører sammen med MCP serveren.
"""

import os
import sys
import json
import time
import random
import asyncio
import logging
import threading
from datetime import datetime
from dotenv import load_dotenv

# Load env først
load_dotenv()

# Tilføj parent directory til path for at importere main
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telethon import TelegramClient, events
from telethon.sessions import StringSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('valkyrie_launcher')

# API credentials
API_ID = int(os.getenv('TELEGRAM_API_ID', '35327630'))
API_HASH = os.getenv('TELEGRAM_API_HASH', 'b09b69c34972ce0fe7fdd43ff18bde21')
SESSION_NAME = os.getenv('TELEGRAM_SESSION_NAME', 'valkyrie_session')
ALIVE_CHAT_ID = os.getenv('ALIVE_CHAT_ID', '')

# Bot states
bots_status = {
    'c2': {'running': False, 'started': None, 'beacons': 0},
    'verify': {'running': False, 'started': None, 'verified': 0, 'blocked': 0}
}

pending_verifications = {}


def generate_captcha():
    """Generate simple math CAPTCHA."""
    a = random.randint(1, 10)
    b = random.randint(1, 10)
    answer = a + b
    return f"{a} + {b}", str(answer)


async def send_alive_message(client, bot_type, extra_info=None):
    """Send ALIVE message when bot starts."""
    if not ALIVE_CHAT_ID:
        logger.info(f"ALIVE_CHAT_ID not set, skipping alive message for {bot_type}")
        return False
    
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if bot_type == 'c2':
            msg = f"""
🤖 **C2 BOT ALIVE** ✅

📅 Started: {now}
🔧 Server: localhost:5000
📊 Session: {SESSION_NAME}
🆔 Status: **ONLINE AND LISTENING**

Ready to receive beacons from deployed payloads.
"""
        elif bot_type == 'verify':
            msg = f"""
✅ **VERIFICATION BOT ALIVE** 🤖

📅 Started: {now}
⏱️ Timeout: 120s
🆔 Status: **READY TO VERIFY**

New members will receive CAPTCHA challenges automatically.
"""
        else:
            msg = f"""
🚀 **VALKYRIE BOT ALIVE** 🔥

📅 Started: {now}
🤖 Type: {bot_type}
🆔 Status: **ONLINE**
"""
        
        if extra_info:
            msg += f"\n📋 Info: {extra_info}"
        
        await client.send_message(int(ALIVE_CHAT_ID), msg)
        logger.info(f"✅ ALIVE message sent for {bot_type} to {ALIVE_CHAT_ID}")
        return True
    except Exception as e:
        logger.error(f"Failed to send alive message for {bot_type}: {e}")
        return False


async def run_c2_bot():
    """Run C2 Bot for receiving beacons."""
    logger.info("🚀 Starting C2 Bot...")
    
    client = TelegramClient(f"{SESSION_NAME}_c2", API_ID, API_HASH)
    
    try:
        await client.start()
        me = await client.get_me()
        logger.info(f"✅ C2 Bot connected as {me.first_name}")
        
        bots_status['c2']['running'] = True
        bots_status['c2']['started'] = datetime.now()
        
        # Send ALIVE message
        await send_alive_message(client, 'c2')
        
        @client.on(events.NewMessage(pattern='/c2_status'))
        async def status_handler(event):
            uptime = datetime.now() - bots_status['c2']['started']
            await event.reply(f"""
📊 **C2 Bot Status**

⏱️ Uptime: {uptime}
🎯 Beacons: {bots_status['c2']['beacons']}
🟢 Status: ONLINE
""")
        
        @client.on(events.NewMessage(pattern='/alive'))
        async def alive_handler(event):
            await send_alive_message(client, 'c2')
            await event.reply("✅ ALIVE message resent!")
        
        @client.on(events.NewMessage(pattern='/beacon'))
        async def beacon_simulator(event):
            """Simulate a beacon for testing."""
            bots_status['c2']['beacons'] += 1
            await send_alive_message(client, 'c2', f"Beacon #{bots_status['c2']['beacons']} received")
            await event.reply(f"✅ Simulated beacon #{bots_status['c2']['beacons']}")
        
        logger.info("🎯 C2 Bot listening for commands (/c2_status, /alive, /beacon)")
        
        # Keep running
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"C2 Bot error: {e}")
    finally:
        bots_status['c2']['running'] = False
        await client.disconnect()


async def run_verify_bot():
    """Run Verification Bot for group member verification."""
    logger.info("🚀 Starting Verification Bot...")
    
    client = TelegramClient(f"{SESSION_NAME}_verify", API_ID, API_HASH)
    
    try:
        await client.start()
        me = await client.get_me()
        logger.info(f"✅ Verify Bot connected as {me.first_name}")
        
        bots_status['verify']['running'] = True
        bots_status['verify']['started'] = datetime.now()
        
        # Send ALIVE message
        await send_alive_message(client, 'verify')
        
        @client.on(events.ChatAction)
        async def chat_action_handler(event):
            """Handle new members joining."""
            if event.user_joined or event.user_added:
                user_id = event.user_id
                logger.info(f"New user joined: {user_id}")
                
                # Generate CAPTCHA
                challenge, answer = generate_captcha()
                pending_verifications[user_id] = {
                    'challenge': challenge,
                    'answer': answer,
                    'timestamp': datetime.now()
                }
                
                try:
                    msg = f"""
🛡️ **VERIFICATION REQUIRED** 🛡️

To join the group, solve this:

**What is {challenge}?**

⏱️ You have 120 seconds to reply with the number.
"""
                    await client.send_message(user_id, msg)
                    
                    # Start timeout
                    asyncio.create_task(verification_timeout(client, user_id))
                except Exception as e:
                    logger.error(f"Failed to send verification: {e}")
        
        @client.on(events.NewMessage)
        async def message_handler(event):
            """Handle verification responses."""
            if event.is_private:
                user_id = event.sender_id
                
                if user_id in pending_verifications:
                    user_answer = event.message.text.strip()
                    correct = pending_verifications[user_id]['answer']
                    
                    if user_answer == correct:
                        del pending_verifications[user_id]
                        bots_status['verify']['verified'] += 1
                        await event.reply("✅ **Verified!** You can now participate.")
                        logger.info(f"User {user_id} verified")
                    else:
                        await event.reply("❌ Wrong! Try again with a new challenge.")
                        # New challenge
                        challenge, answer = generate_captcha()
                        pending_verifications[user_id] = {
                            'challenge': challenge,
                            'answer': answer,
                            'timestamp': datetime.now()
                        }
                        await client.send_message(user_id, f"New challenge: What is {challenge}?")
        
        @client.on(events.NewMessage(pattern='/verify_status'))
        async def status_handler(event):
            uptime = datetime.now() - bots_status['verify']['started']
            await event.reply(f"""
📊 **Verify Bot Status**

⏱️ Uptime: {uptime}
✅ Verified: {bots_status['verify']['verified']}
❌ Blocked: {bots_status['verify']['blocked']}
⏳ Pending: {len(pending_verifications)}
🟢 Status: ONLINE
""")
        
        @client.on(events.NewMessage(pattern='/alive'))
        async def alive_handler(event):
            await send_alive_message(client, 'verify')
            await event.reply("✅ ALIVE message resent!")
        
        logger.info("🛡️ Verification Bot watching for new members")
        
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"Verify Bot error: {e}")
    finally:
        bots_status['verify']['running'] = False
        await client.disconnect()


async def verification_timeout(client, user_id):
    """Handle verification timeout."""
    await asyncio.sleep(120)
    
    if user_id in pending_verifications:
        del pending_verifications[user_id]
        bots_status['verify']['blocked'] += 1
        try:
            await client.send_message(user_id, "❌ Timeout! You were blocked.")
        except:
            pass


async def run_all_bots():
    """Run all bots concurrently."""
    logger.info("🚀 Starting ALL Valkyrie Bots...")
    
    # Run both bots concurrently
    await asyncio.gather(
        run_c2_bot(),
        run_verify_bot(),
        return_exceptions=True
    )


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Valkyrie Bot Launcher')
    parser.add_argument('--c2', action='store_true', help='Run only C2 bot')
    parser.add_argument('--verify', action='store_true', help='Run only Verify bot')
    parser.add_argument('--all', action='store_true', help='Run all bots (default)')
    
    args = parser.parse_args()
    
    try:
        if args.c2:
            asyncio.run(run_c2_bot())
        elif args.verify:
            asyncio.run(run_verify_bot())
        else:
            # Run all bots
            asyncio.run(run_all_bots())
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down bots...")


if __name__ == '__main__':
    main()
