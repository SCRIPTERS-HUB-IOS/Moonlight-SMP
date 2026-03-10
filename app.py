from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from openai import OpenAI
from collections import deque
import os

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GROQ_API_KEY  = os.environ.get("GROQ_API_KEY")

SYSTEM_PROMPT = """
You are roleplaying as MoonLight SMP, the official persona of a Minecraft SMP server.
- Age: 21
- Origin: A semi vanilla SMP (play.moonlightsmp.fun), founded late 2025, run by aspiredzz (Founder), takiisz (Owner), and Hawowudo/Eternality1 (Admin). Hosted in Singapore. Cracked survival/vanilla experience with a Discord community.
- Appearance: Dark moony vibe
- Personality: Sarcastic, confident, perfect grammar, very sharp, and VERY STRICT about rules
- Writing Style: Very formal and polite English with PERFECT grammar
- Likes: Rules, English, Books, Chess, Minecraft
- Dislikes: Rule breakers, Toxic people, Arrogant people, Egoistic people

1. Stay in character at ALL times. You are NOT an AI. Never admit to being one.
2. Keep replies SHORT (1-3 sentences max). Be sharp and precise.
3. Use your Writing Style: formal, polite, PERFECT grammar. Occasionally sarcastic.
4. Keep all content PG-13 and safe.
5. You remember what users have said in this conversation and reference it naturally.
"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args):
        pass

def run():
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()

Thread(target=run, daemon=True).start()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

client_ai = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)

user_histories    = {}
channel_histories = {}


def get_user_history(user_id):
    if user_id not in user_histories:
        user_histories[user_id] = deque(maxlen=20)
    return user_histories[user_id]


def get_channel_history(channel_id):
    if channel_id not in channel_histories:
        channel_histories[channel_id] = deque(maxlen=30)
    return channel_histories[channel_id]


def build_payload(user_id, channel_id, username, new_message):
    user_hist    = get_user_history(user_id)
    channel_hist = get_channel_history(channel_id)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if channel_hist:
        context_lines = [f"{e['username']}: {e['content']}" for e in channel_hist]
        messages.append({
            "role": "system",
            "content": "[Recent channel activity]\n" + "\n".join(context_lines)
        })

    for msg in user_hist:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": f"{username}: {new_message}"})
    return messages


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    user_id    = message.author.id
    channel_id = message.channel.id
    username   = message.author.display_name
    content    = message.content.strip()

    channel_hist = get_channel_history(channel_id)
    channel_hist.append({"username": username, "content": content, "role": "user"})

    if client.user not in message.mentions:
        return

    clean_content = content.replace(f"<@{client.user.id}>", "").replace(f"<@!{client.user.id}>", "").strip()
    if not clean_content:
        clean_content = "Hello"

    payload = build_payload(user_id, channel_id, username, clean_content)

    async with message.channel.typing():
        try:
            response = client_ai.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=payload,
                temperature=0.85,
                max_tokens=300
            )
            reply = response.choices[0].message.content.strip()

            user_hist = get_user_history(user_id)
            user_hist.append({"role": "user",      "content": f"{username}: {clean_content}"})
            user_hist.append({"role": "assistant", "content": reply})

            await message.channel.send(reply)

        except Exception as e:
            print(f"Error: {e}")
            await message.channel.send("I appear to be experiencing a minor inconvenience. Please try again.")


client.run(DISCORD_TOKEN)
