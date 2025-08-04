import re
import os
import json
import asyncio
from telethon import TelegramClient, events

# ─── Credentials & IDs ───────────────────────────────────────────────────
API_ID         = 14189195
API_HASH       = "62dc7fdfa467ec25fbb1fd59ccee3013"
BOT_TOKEN      = "8394101555:AAGmvSqa4RHzHzvr9OLbvPE4NqcN6KEi1J4"
USER_SESSION   = "user_session"         # Your user account session
BOT_SESSION    = "bot_session"          # Bot session
SOURCE_CHAT_ID = -1002252838990         # the chat to scrape (same for everyone)

# ─── Pattern for extracting codes ────────────────────────────────────────
CODE_PATTERN   = re.compile(r"\b\d{16}\|\d{2}\|\d{4}\|\d{3,4}\b")

# ─── User state file to remember last seen message ID per user ───────────
USER_STATE_FILE = "user_states.json"

# ─── Max chars per Telegram message ──────────────────────────────────────
MAX_LEN = 4000

# Initialize both clients
user_client = TelegramClient(USER_SESSION, API_ID, API_HASH)  # For scraping
bot_client = TelegramClient(BOT_SESSION, API_ID, API_HASH)    # For bot commands

def load_user_states():
    """Load all user states from file."""
    if not os.path.exists(USER_STATE_FILE):
        return {}
    try:
        with open(USER_STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_user_states(states):
    """Save all user states to file."""
    with open(USER_STATE_FILE, "w") as f:
        json.dump(states, f, indent=2)

def get_user_last_id(user_id):
    """Get the last scraped message ID for a specific user."""
    states = load_user_states()
    return states.get(str(user_id), 0)

def set_user_last_id(user_id, msg_id):
    """Set the last scraped message ID for a specific user."""
    states = load_user_states()
    states[str(user_id)] = msg_id
    save_user_states(states)

async def send_codes(event, codes):
    """Send codes to user, splitting into multiple messages if needed."""
    if not codes:
        await event.reply("⚠️ No matching found.")
        return

    # Format codes nicely
    formatted_codes = []
    for i, code in enumerate(codes, 1):
        formatted_codes.append(f"{i}. `{code}`")

    block = "\n".join(formatted_codes)

    if len(block) <= MAX_LEN:
        await event.reply(f"🎯 **Found {len(codes)}:**\n\n{block}")
    else:
        # Split into chunks
        chunks = []
        current_chunk = f"🎯 **Found {len(codes)}:**\n\n"

        for line in formatted_codes:
            if len(current_chunk + line + "\n") > MAX_LEN:
                chunks.append(current_chunk.strip())
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        for chunk in chunks:
            await event.reply(chunk)

@bot_client.on(events.NewMessage(pattern=r'^/start$'))
async def start_command(event):
    """Welcome message for new users."""
    welcome_msg = """
🤖 **Welcome to the Code Scraper Bot!**

Available commands:
• `/scr <number>`
• `/scr new`
• `/help`

Made by @LeVetche
    """
    await event.reply(welcome_msg)

@bot_client.on(events.NewMessage(pattern=r'^/help$'))
async def help_command(event):
    """Help message."""
    help_msg = """
📖 **How to use this bot:**

**Commands:**
• `/scr <number>`
• `/scr new`
• `/stats`

Made by @LeVetche
    """
    await event.reply(help_msg)

@bot_client.on(events.NewMessage(pattern=r'^/scr\s+(\d+)$'))
async def scrape_n_codes(event):
    """Handle /scr N command - get last N approved codes."""
    user_id = event.sender_id
    n = int(event.pattern_match.group(1))

    # Limit to prevent abuse
    if n > 50:
        await event.reply("⚠️ Maximum 50 codes per request. Please use a smaller number.")
        return

    if n <= 0:
        await event.reply("⚠️ Please enter a positive number.")
        return

    try:
        await event.reply("🔍 Searching...")

        # Use user client to get messages from the source chat
        messages = await user_client.get_messages(SOURCE_CHAT_ID, limit=2000)
        codes = []
        highest_id = 0

        for msg in messages:
            text = msg.message or ""
            if "Approved" in text:
                found_codes = CODE_PATTERN.findall(text)
                for code in found_codes:
                    if len(codes) < n:
                        codes.append(code)
                if found_codes and msg.id > highest_id:
                    highest_id = msg.id

            if len(codes) >= n:
                break

        # Update user's last scraped ID
        if highest_id:
            set_user_last_id(user_id, highest_id)

        await send_codes(event, codes)
        print(f"📤 User {user_id}: /scr {n} → sent {len(codes)} codes")

    except Exception as e:
        await event.reply(f"❌ Error occurred: {str(e)}")
        print(f"Error in scrape_n_codes: {e}")

@bot_client.on(events.NewMessage(pattern=r'^/scr\s+new$'))
async def scrape_new_codes(event):
    """Handle /scr new command - get new codes since last scrape."""
    user_id = event.sender_id
    last_id = get_user_last_id(user_id)

    if last_id == 0:
        await event.reply("ℹ️ No previous scrape found for your account.\nFirst use `/scr <number>` to initialize your tracking.")
        return

    try:
        await event.reply("🔍 Searching...")

        # Use user client to get messages newer than user's last scraped ID
        messages = await user_client.get_messages(SOURCE_CHAT_ID, min_id=last_id, limit=500)
        codes = []
        new_last_id = last_id

        # Process from oldest to newest
        for msg in reversed(messages):
            text = msg.message or ""
            if "Approved" in text:
                found_codes = CODE_PATTERN.findall(text)
                if found_codes:
                    codes.extend(found_codes)
                    new_last_id = max(new_last_id, msg.id)

        # Update user's last scraped ID if we found new messages
        if new_last_id != last_id:
            set_user_last_id(user_id, new_last_id)

        if not codes:
            await event.reply("✅ No new found since your last scrape.")
        else:
            await send_codes(event, codes)

        print(f"📤 User {user_id}: /scr new → sent {len(codes)} new codes")

    except Exception as e:
        await event.reply(f"❌ Error occurred: {str(e)}")
        print(f"Error in scrape_new_codes: {e}")

@bot_client.on(events.NewMessage(pattern=r'^/stats$'))
async def user_stats(event):
    """Show user's scraping statistics."""
    user_id = event.sender_id
    last_id = get_user_last_id(user_id)

    if last_id == 0:
        stats_msg = "📊 **Your Statistics:**\n\n• No scrapes performed yet\n• Use `/scr <number>` to get started!"
    else:
        stats_msg = f"📊 **Your Statistics:**\n\n• Last scraped message ID: `{last_id}`\n• Use `/scr new` to get codes since your last scrape"

    await event.reply(stats_msg)

async def main():
    """Start both clients."""
    print("🤖 Starting hybrid scraper bot...")

    # Start user client first (for scraping)
    print("🔑 Starting user session...")
    await user_client.start()
    user_me = await user_client.get_me()
    print(f"✅ User session active: {user_me.first_name} (@{user_me.username or 'no username'})")

    # Start bot client (for commands)
    print("🤖 Starting bot session...")
    await bot_client.start(bot_token=BOT_TOKEN)
    bot_me = await bot_client.get_me()
    print(f"✅ Bot started: @{bot_me.username}")

    print("=" * 50)
    print(f"🎯 Setup Complete!")
    print(f"📱 Bot: @{bot_me.username}")
    print(f"👤 Scraper: {user_me.first_name}")
    print(f"💬 Source Chat: {SOURCE_CHAT_ID}")
    print("👥 Ready to serve multiple users...")
    print("⏳ Waiting for /scr commands...")
    print("=" * 50)

    # Keep both clients running
    await bot_client.run_until_disconnected()

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 HYBRID TELEGRAM CODE SCRAPER BOT")
    print("   Bot handles commands, User account scrapes")
    print("=" * 60)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
