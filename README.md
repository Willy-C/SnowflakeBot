


# Snowflake Discord Bot

This is a small general-purpose bot that I am making for fun with features requested by friends who use it. It is mainly in my friends' and my own servers. This bot is made public but its invite URL is not advertised, use the `invite` command or contact me to get the invite URL.

## About
This bot is made with [discord.py](https://github.com/Rapptz/discord.py)

By default, the prefix is `%` but you can config the prefix on a per-server basis with the `prefix` command. You can also use `@Snowflake` as a prefix regardless of the server's prefix settings.

The name Snowflake does not actually have anything to do with discord's [Snowflake ID](https://discordapp.com/developers/docs/reference#snowflakes) format but instead, is a little joke within my friend group.

## What can it do?
A full list of commands and its corresponding documentation can be found via the `help` command on the bot or you can source dive this repo.

Here is a brief list of some of the things the bot can do:
 - Reaction Roles
 - Server Moderation
 - Get user and server info 
 - Evaluate Python code in chat
 - Help manage your notifications
 - Set timed reminders for yourself
 - Generate LaTeX as image in chat
 - Hot reload modules without restart
 - Use custom emojis across servers without Nitro
 - Stream music from Youtube, Twitch, Soundcloud, Mixer, Vimeo, etc with [Lavalink](https://github.com/Frederikam/Lavalink) 
 - and more...

## Future Features
Currently, I do not have a roadmap or a list of planned features, I just create new features when the idea comes. I am open to any feature requests, a lot of the bot's current features come from small inconveniences of discord and people wanting to make their discord experience better or just something that is fun to play with. 


## Note
There are a lot of parts that are not made by me and use external libraries or APIs or someone else's code.

Shoutout to these people for creating amazing libraries:
- [Danny/Rapptz](https://github.com/Rapptz) - [discord.py](https://github.com/Rapptz/discord.py) and a few other commands
- [Myst/EvieePy](https://github.com/EvieePy) - [Wavelink](https://github.com/PythonistaGuild/Wavelink) and pretty much all of the music playing
- [Devon/Gorialis](https://github.com/Gorialis) - [jishaku](https://github.com/Gorialis/jishaku)

## Requirements/Running your own instance

I would not recommend trying to host your own instance of this bot as some crucial parts are not public. Instead, use the `invite` command to get an invite URL to add to your server or send me a message. 

If you *really* want to run your own instance you would need the following:
- Python 3.7+
- discord.py >= 1.5
- A PostgreSQL database
- [asyncpg](https://github.com/MagicStack/asyncpg) for interacting with the database
- A [Lavalink](https://github.com/Frederikam/Lavalink) server for music playing
- The packages inside [`requirements.txt`](requirements.txt) for some commands

NOTE: the following steps are only a rough guideline, a lot of steps are left to the user to set up themselves. (eg. setting up Lavalink server)
1. Install dependencies:
`pip install -U -r requirements.txt`
2. A `config.py` with the following information:
```python
# These are required for the bot to run
BOT_TOKEN = '...' # Your bot token from discord
DBURI = 'postgresql://snowflake:password@host/snowflake' # Your PostgreSQL credentials

# The rest are optional, certain commands require external APIs:
GOOGLE_API_KEY = '...' # API key from Google
GOOGLE_CUSTOM_SEARCH_ENGINE = '...' # ID of your custom search engine from Google
DEEPAI_API_KEY = '...' # API Key from DeepAI
```
3. Create database tables
4. Run [`main.py`](main.py) and pray it works.
