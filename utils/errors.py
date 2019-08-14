import discord
from discord.ext import commands

class NoBlacklist(commands.CheckFailure):
    def __init__(self, message=None):
        super().__init__(message or 'You are blacklisted and cannot use this bot.')

