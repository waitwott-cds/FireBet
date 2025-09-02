import discord
import random
import asyncio
import sqlite3
import matplotlib.pyplot as plt
import io
import datetime
from discord.ext import commands, tasks

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="f.", intents=intents)
client.help_command = commands.MinimalHelpCommand()

# Global DogCoin price variable
current_price = 500.0


# --------------------------
# Database Initializations
# --------------------------

def initialize_database():
    """Initialize balance.db with fiat balance and DogCoin holdings."""
    with sqlite3.connect("balance.db") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS balance (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                holdings INTEGER DEFAULT 0
            )
        ''')
        conn.commit()


def initialize_crypto_db():
    """Initialize crypto.db with a prices table for DogCoin price history."""
    with sqlite3.connect("crypto.db") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prices (
                timestamp TEXT,
                price REAL,
                symbol TEXT
            )
        ''')
        cursor.execute("SELECT COUNT(*) FROM prices WHERE symbol = 'dogcoin'")
        count = cursor.fetchone()[0]
        if count == 0:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO prices (timestamp, price, symbol) VALUES (?, ?, ?)",
                           (timestamp, current_price, "dogcoin"))
            conn.commit()


initialize_database()
initialize_crypto_db()


# --------------------------
# Utility Functions for balance.db
# --------------------------

def get_balance(user_id):
    """Return the fiat balance for the given user."""
    with sqlite3.connect("balance.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM balance WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    return row[0] if row else 0


def get_holdings(user_id):
    """Return the DogCoin holdings for the given user."""
    with sqlite3.connect("balance.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT holdings FROM balance WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    return row[0] if row else 0


def update_balance(user_id, amount):
    """Update the fiat balance for a user by the given amount (can be negative)."""
    with sqlite3.connect("balance.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM balance WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        new_balance = round(max((row[0] + amount) if row else amount, 0), 2)
        if row:
            cursor.execute("UPDATE balance SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        else:
            cursor.execute("INSERT INTO balance (user_id, balance, holdings) VALUES (?, ?, ?)",
                           (user_id, new_balance, 0))
        conn.commit()


def update_holdings(user_id, amount):
    """Update the DogCoin holdings for a user by the given amount (can be negative)."""
    with sqlite3.connect("balance.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT holdings FROM balance WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        new_holdings = round(max((row[0] + amount) if row else amount, 0), 2)
        if row:
            cursor.execute("UPDATE balance SET holdings = ? WHERE user_id = ?", (new_holdings, user_id))
        else:
            cursor.execute("INSERT INTO balance (user_id, balance, holdings) VALUES (?, ?, ?)",
                           (user_id, 0, new_holdings))
        conn.commit()


# --------------------------
# Price History Functions (crypto.db)
# --------------------------

def get_price_history():
    """Fetch price history for DogCoin from crypto.db and limit to the last 30 data points."""
    with sqlite3.connect("crypto.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, price FROM prices WHERE symbol = 'dogcoin' ORDER BY timestamp ASC")
        data = cursor.fetchall()
    if len(data) > 30:
        data = data[-30:]
    return data


def plot_price_history():
    """Plot DogCoin price history with a black background, grid color #333333, and 0.5x marker size."""
    data = get_price_history()
    if not data:
        return None
    timestamps, prices = zip(*data)

    # Create figure and axes with a black background
    fig, ax = plt.subplots(figsize=(8, 4), facecolor='black')
    ax.set_facecolor('black')

    # Plot data with markersize set to 3 (approx. 0.5x the default size)
    ax.plot(timestamps, prices, marker='o', markersize=3, linestyle='-', color='b')

    # Set labels and title with white text
    ax.set_xlabel("Timestamp", color='white')
    ax.set_ylabel("Price (⬢)", color='white')
    ax.set_title("DogCoin Price History", color='white')
    ax.tick_params(axis='x', colors='white')
    ax.tick_params(axis='y', colors='white')

    # Add grid with specified color and linewidth
    ax.grid(True, color="#333333", linewidth=0.5)
    plt.xticks(rotation=45)

    # Save plot to a BytesIO buffer
    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=fig.get_facecolor(), bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


# --------------------------
# Background Task to Update Price
# --------------------------

@tasks.loop(seconds=60)
async def update_price_with_ai():
    """Simulate an AI-driven update to DogCoin price and record it in crypto.db with controlled adjustments."""
    global current_price
    with sqlite3.connect("crypto.db") as conn:
        cursor = conn.cursor()
        # Fetch the last 40 price entries
        cursor.execute("SELECT price FROM prices WHERE symbol = 'dogcoin' ORDER BY timestamp DESC LIMIT 40")
        data = cursor.fetchall()
        prices = [row[0] for row in data if row[0] is not None]

        # Calculate a relative trend rather than an absolute difference
        if len(prices) < 2 or prices[-1] == 0:
            recent_trend = 0
        else:
            recent_trend = (prices[0] - prices[-1]) / prices[-1]  # relative change
        # Use a smaller multiplier for the momentum factor
        momentum_factor = 0.001 * recent_trend
        # Random investor activity remains similar
        investor_activity = random.uniform(-0.03, 0.03)
        # Occasionally, a large trade impact is applied
        large_trade_impact = random.choice([0.02, -0.02, 0]) if random.random() < 0.1 else 0
        # Sum up adjustments
        adjustment = investor_activity + momentum_factor + large_trade_impact
        # Clamp the adjustment to avoid runaway growth (e.g., between -10% and +10%)
        adjustment = max(min(adjustment, 0.1), -0.1)
        # Update the price with the controlled adjustment
        new_price = max(round(current_price * (1 + adjustment), 2), 0.01)
        current_price = new_price
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO prices (timestamp, price, symbol) VALUES (?, ?, ?)",
                       (timestamp, current_price, "dogcoin"))
        conn.commit()

    print(f"[AI Bot] Updated price to {current_price} ⬢")


# --------------------------
# Bot Commands (All Responses as Embeds)
# --------------------------

@client.command(aliases=["bal", "wal"])  # Balance Alias
async def balance(ctx):
    """Display your fiat balance and DogCoin holdings."""
    user_id = ctx.author.id
    with sqlite3.connect("balance.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance, holdings FROM balance WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    fiat, holdings = (row if row else (0, 0))
    embed = discord.Embed(
        title=f"{ctx.author.name}'s Wallet",
        description=f"You have **{fiat} ⬢** and **{holdings} DogCoin**.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@client.command()
async def trade(ctx, action: str, amount: str):
    """
    Trade DogCoin at the current price.
    Usage: f.trade buy <amount> or f.trade sell <amount>
    Use 'max' or 'all' to trade your full capacity.
    """
    user_id = ctx.author.id
    with sqlite3.connect("balance.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance, holdings FROM balance WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    fiat = row[0] if row else 0
    holdings = row[1] if row else 0

    # trade shi fr
    if amount.lower() in ["max", "all"]:
        if action.lower() == "buy":
            raw_trade_amount = fiat / current_price
        elif action.lower() == "sell":
            raw_trade_amount = holdings
        else:
            embed = discord.Embed(
                description="Invalid action. Use **buy** or **sell**.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
    else:
        try:
            raw_trade_amount = float(amount)
        except ValueError:
            embed = discord.Embed(
                description="Invalid amount. Please specify a number, 'max', or 'all'.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

    # Round to 2 dec places
    trade_amount = round(max(raw_trade_amount, 0), 2)
    total_value = round(trade_amount * current_price, 2)

    if action.lower() == "buy":
        if fiat >= total_value and trade_amount > 0:
            update_balance(user_id, -total_value)
            update_holdings(user_id, trade_amount)
            new_fiat = round(fiat - total_value, 2)
            embed = discord.Embed(
                title="Purchase Successful",
                description=f"You bought **{trade_amount:.2f} DogCoin** for **{total_value:.2f} ⬢**.\nNew fiat balance: **{new_fiat:.2f} ⬢**.",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                description="Insufficient fiat balance to complete purchase.",
                color=discord.Color.red()
            )
    elif action.lower() == "sell":
        if holdings >= trade_amount and trade_amount > 0:
            update_holdings(user_id, -trade_amount)
            update_balance(user_id, total_value)
            new_fiat = round(fiat + total_value, 2)
            embed = discord.Embed(
                title="Sale Successful",
                description=f"You sold **{trade_amount:.2f} DogCoin** for **{total_value:.2f} ⬢**.\nNew fiat balance: **{new_fiat:.2f} ⬢**.",
                color=discord.Color.blue()
            )
        else:
            embed = discord.Embed(
                description="Insufficient DogCoin holdings to complete sale.",
                color=discord.Color.red()
            )
    else:
        embed = discord.Embed(
            description="Invalid action. Use **buy** or **sell**.",
            color=discord.Color.red()
        )

    await ctx.send(embed=embed)


@client.command()
async def price(ctx):
    """Display a graph of DogCoin price history."""
    history_image = plot_price_history()
    if history_image:
        embed = discord.Embed(
            title="DogCoin Price History",
            description="Below is the latest price history graph for DogCoin.",
            color=discord.Color.purple()
        )
        embed.set_image(url="attachment://price.png")
        await ctx.send(embed=embed, file=discord.File(history_image, "price.png"))
    else:
        embed = discord.Embed(
            description="No price history available for DogCoin.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)


@client.command()
async def work(ctx):
    """Earn a random amount of fiat ⬢ by working."""
    user_id = ctx.author.id
    earned = random.randint(1, 10)
    update_balance(user_id, earned)
    embed = discord.Embed(
        title="Work Completed",
        description=f"You worked hard and earned **{earned} ⬢**!\nUse `f.balance` to check your wallet.",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)


@client.command()
async def give(ctx, member: discord.Member, amount: int):
    """Give fiat ⬢ to another user."""
    user_id = ctx.author.id
    if amount <= 0:
        embed = discord.Embed(
            description="You cannot give negative or zero amounts of ⬢.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    if ctx.author.id != 753409302680699021:
        if get_balance(user_id) >= amount:
            update_balance(user_id, -amount)
            update_balance(member.id, amount)
            embed = discord.Embed(
                description=f"You gave **{amount} ⬢** to {member.mention}!",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                description="You don't have enough ⬢ to give that amount.",
                color=discord.Color.red()
            )
    else:
        update_balance(member.id, amount)
        embed = discord.Embed(
            description=f"The developer has granted **{amount} ⬢** to {member.mention}. Please express words of gratitude proceeding this message.",
            color=discord.Color.yellow()
        )
    await ctx.send(embed=embed)


@client.command()
async def ping(ctx):
    """Show the bot's latency."""
    latency = round(client.latency * 1000, 2)
    embed = discord.Embed(
        title="Pong! 🏓",
        description=f"Latency is **{latency}ms**.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)


@client.event
async def on_ready():
    update_price_with_ai.start()
    members = sum(guild.member_count for guild in client.guilds) - len(client.guilds)
    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{members} users in {len(client.guilds)} servers! | f.help"
        )
    )
    print("⚙️ | Bot is running")

client.run(token)
