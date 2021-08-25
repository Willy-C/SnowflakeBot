import discord
from discord.ext import commands
from collections import defaultdict
from datetime import datetime


class InviteTracker(commands.Cog, name='Invites'):
    def __init__(self, bot):
        self.bot = bot
        self.cached_invites = defaultdict(lambda: defaultdict(int))
        bot.loop.create_task(self.get_guild_invites())

    async def get_guild_invites(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            if not guild.me.guild_permissions.manage_guild:
                continue
            try:
                invites = await guild.invites()
            except discord.HTTPException:
                continue
            if not invites:
                continue
            self.cached_invites[guild.id] = defaultdict(int, {invite.code: invite.uses for invite in invites})

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        self.cached_invites[invite.guild.id][invite.code]
        # defaultdict handles everything

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        del self.cached_invites[invite.guild.id][invite.code]
        if not self.cached_invites[invite.guild.id]:
            del self.cached_invites[invite.guild.id]

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.guild.me.guild_permissions.manage_guild or member.guild.id not in self.cached_invites:
            return

        invites = await member.guild.invites()
        inviter = None
        for invite in invites:
            if invite.uses > self.cached_invites[member.guild.id][invite.code]:
                inviter = invite.inviter
            self.cached_invites[member.guild.id][invite.code] = invite.uses
        if inviter is None:
            return  # mystery
        modcog = self.bot.get_cog('Mod')
        config = await modcog.get_mod_config(member.guild.id)
        if config is None:
            return

        invite_channel = member.guild.get_channel(config.get('invite_ch'))
        if invite_channel is not None:
            e = discord.Embed(title='Invite Tracker',
                              color=discord.Colour.dark_purple(),
                              timestamp=datetime.utcnow())
            e.set_author(icon_url=member.display_avatar.url, name=member)
            e.add_field(name='ID', value=member.id)
            e.add_field(name='Joined with invite created by:', value=f'{inviter.mention} (ID: {inviter.id})')
            await invite_channel.send(embed=e)

    def prettify_invites(self):
        """Converts our nested defaultdicts to dicts for print"""
        return {k: dict(v) if isinstance(v, defaultdict) else v for (k, v) in self.cached_invites.items()}


def setup(bot):
    bot.add_cog(InviteTracker(bot))
