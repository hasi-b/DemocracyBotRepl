import discord
import random
import os
import asyncio
from datetime import datetime
from discord.ext import tasks
from flask import Flask
from threading import Thread

# --- Keep-alive Web Server ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    thread = Thread(target=run_web)
    thread.start()

# --- Bot Setup ---
intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

# --- Topic Data ---
topics_by_time = {
    "Trend 1": [
        "Horses promise to ban mint chocolate ice cream after coming to power, eagles oppose",
        "Eagles promise to ban mismatched socks in public space, horses oppose",
        "Eagles demand male horses should always wear pants on public."
    ],
    "Trend 2": [
        'Eagle leader releases a statement, “Do we need freedom? Or do we need discipline?” Horses find this statement ridiculous.',
        "Horses put a legal notice to film studios to not show violence between animals, Eagles say it is state sponsored censorship",
        "Eagles demand that horses should be charged more for bus tickets."
    ],
    "Trend 3": [
        "The Horse claims that they will build schools open to all animals; the Eagle, however, believes schools should be separated by species.",
        "Horse claims It’s unfair that the bird family holds the management of all gemstones mine.",
        "To promote strong unity among birds, Eagles proposing a new law where all birds have to support their party, or they won't be officially recognised"
    ],
    "Trend 4": [
        "Eagles promise to bring high taxes for migratory birds, Horses claim it is unjust to mess with the natural order",
        "Horses seen having a secret meeting with the neighbouring country run by lions. Eagles call this a breach of public trust.",
        "Eagles issue arrest warrants for comedians who are joking about the party, claiming it destroys nationalistic pride"
    ],
    "Trend 5": [
        "Eagles want to impose mandatory military service to high schoolers. Horses call this unnecessary and a breach of freedom of choice",
        "Horse claims that the access to healthcare shouldn’t depend on one’s income. However Eagles claims that healthcare is a personal responsibility, not a government guarantee",
        "Eagles propose a unified Wildlands where only the state imposed religion will be accepted, Horses oppose this move and plans to abolish religion to bring equal rights."
    ]
}


# --- Globals ---
time_labels = list(topics_by_time.keys())
current_index = 0
post_channel = None
custom_interval = 5
game_running = False
active_threads = []  # Store active threads to close later

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# --- Slash Command: Start ---
@bot.slash_command(name="start", description="Start posting topics as separate threads")
async def start(
    ctx: discord.ApplicationContext,
    channel: discord.Option(discord.TextChannel, description="Channel to create threads in"),
    interval: discord.Option(int, description="Minutes between posts", default=5)
):
    global post_channel, current_index, custom_interval, game_running, active_threads

    if game_running:
        await ctx.respond("⚠️ Game is already running.", ephemeral=True)
        return

    post_channel = channel
    custom_interval = interval
    current_index = 0
    game_running = True
    active_threads = []  # Reset active threads

    await ctx.respond(f"▶️ Game started in {channel.mention} - each topic will create its own thread (every {interval} min)\n🏆 User with most reactions wins each round!")

    # Post the first topic immediately
    await post_next_topic()

    # Start the loop for subsequent posts with a delay
    if topic_loop.is_running():
        topic_loop.stop()

    # Start the loop after the interval delay
    asyncio.create_task(start_delayed_loop())

# --- Slash Command: Stop ---
@bot.slash_command(name="stop", description="Stop the game")
async def stop(ctx: discord.ApplicationContext):
    global game_running, active_threads

    if not game_running:
        await ctx.respond("❌ Game is not running.", ephemeral=True)
        return

    game_running = False
    if topic_loop.is_running():
        topic_loop.stop()

    # Close any remaining active thread
    if active_threads:
        await close_previous_thread_and_announce_winner()

    await ctx.respond("⏹️ Game stopped.")

# --- Post Logic ---
async def post_next_topic():
    global current_index, game_running, active_threads

    if not post_channel or not game_running:
        return

    # Close previous thread and announce winner (if not the first topic)
    if current_index > 0 and active_threads:
        await close_previous_thread_and_announce_winner()

    if current_index >= len(time_labels):
        # Close the last thread if we're done
        if active_threads:
            await close_previous_thread_and_announce_winner()
        await post_channel.send("✅ All topics have been posted. Game complete!")
        game_running = False
        if topic_loop.is_running():
            topic_loop.stop()
        return

    label = time_labels[current_index]
    topic = random.choice(topics_by_time[label])

    # Create a new thread for each time slot
    thread_name = f"{label}"

    try:
        new_thread = await post_channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.public_thread
        )

        # Store the thread for later closing
        active_threads.append(new_thread)

        # Post the topic as the first message in the thread
        await new_thread.send(f"🕒 **{label}** topic: **{topic}**\n\nDiscuss this topic here! React to messages you like! 👍")

    except discord.Forbidden:
        # Fallback to regular message if thread creation fails
        await post_channel.send(f"🕒 **{label}** topic: **{topic}** (Could not create thread)")
    except Exception as e:
        # Fallback to regular message if any other error occurs
        await post_channel.send(f"🕒 **{label}** topic: **{topic}** (Thread error: {str(e)})")

    current_index += 1

# --- Function to close thread and announce winner ---
async def close_previous_thread_and_announce_winner():
    global active_threads

    if not active_threads:
        return

    # Get the most recent thread (the one we want to close)
    thread_to_close = active_threads[-1]

    try:
        # Dictionary to store total reactions per user
        user_reaction_totals = {}
        user_message_counts = {}

        # Get all messages in the thread
        async for message in thread_to_close.history(limit=None):
            if message.author.bot:  # Skip bot messages
                continue

            user = message.author
            total_reactions = sum(reaction.count for reaction in message.reactions)

            # Add to user's total reaction count
            if user in user_reaction_totals:
                user_reaction_totals[user] += total_reactions
                user_message_counts[user] += 1
            else:
                user_reaction_totals[user] = total_reactions
                user_message_counts[user] = 1

        # Find the winner (user with most total reactions)
        winner_user = None
        max_reactions = 0

        for user, total_reactions in user_reaction_totals.items():
            if total_reactions > max_reactions:
                max_reactions = total_reactions
                winner_user = user

        # Announce winner if there is one
        if winner_user and max_reactions > 0:
            message_count = user_message_counts[winner_user]
            winner_text = f"🏆 **Winner**: {winner_user.mention} with {max_reactions} total reaction{'s' if max_reactions != 1 else ''}!"
            winner_text += f"\n📊 **Stats**: {message_count} message{'s' if message_count != 1 else ''} with an average of {max_reactions/message_count:.1f} reactions per message"
        else:
            winner_text = "🤷 No reactions in this round - no winner this time!"

        # Post winner announcement in the thread
        await thread_to_close.send(f"\n⏰ **Time's up!**\n{winner_text}\n\n🔒 This thread is now closed.")

        # Close the thread (archive and lock it)
        await thread_to_close.edit(archived=True, locked=True)

    except Exception as e:
        print(f"Error closing thread: {e}")
        # Try to at least send a closing message
        try:
            await thread_to_close.send("⏰ **Time's up!** 🔒 This thread is now closed.")
            await thread_to_close.edit(archived=True, locked=True)
        except:
            pass

# --- Helper function to start loop with delay ---
async def start_delayed_loop():
    await asyncio.sleep(custom_interval * 60)  # Wait for the interval
    if game_running:  # Check if game is still running
        topic_loop.change_interval(minutes=custom_interval)
        topic_loop.start()

# --- Topic Loop Task ---
@tasks.loop(minutes=5)  # Default interval, will be changed dynamically
async def topic_loop():
    if game_running:
        await post_next_topic()

# Ensure the loop doesn't start automatically when the bot starts
@topic_loop.before_loop
async def before_topic_loop():
    await bot.wait_until_ready()

# --- Run Bot ---
keep_alive()
bot.run(os.getenv("TOKEN"))