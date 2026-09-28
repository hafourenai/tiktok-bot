import logging
from datetime import datetime, timezone

import discord

from voice_stats import VoiceStatsStore


logger = logging.getLogger(__name__)


class DiscordVoiceMonitor(discord.Client):
    def __init__(self, store: VoiceStatsStore, guild_id: int | None) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.voice_states = True
        intents.members = True
        super().__init__(intents=intents, reconnect=True)
        self.store = store
        self.guild_id = guild_id

    def _monitored(self, guild: discord.Guild | None) -> bool:
        return bool(guild and (self.guild_id is None or guild.id == self.guild_id))

    async def on_ready(self) -> None:
        logger.info("Discord voice monitor connected as %s", self.user)
        now = datetime.now(timezone.utc)
        for guild in self.guilds:
            if not self._monitored(guild):
                continue
            connected = {
                member.id: member
                for channel in guild.voice_channels
                for member in channel.members
                if not member.bot
            }
            for session in self.store.active_sessions(guild.id):
                member = connected.get(session["user_id"])
                if not member or not member.voice or not member.voice.channel:
                    self.store.close_session(guild.id, session["user_id"], now)
                    logger.info("[VOICE] Closed stale session for %s during sync", session["username"])
                elif member.voice.channel.id != session["channel_id"]:
                    self.store.close_session(guild.id, member.id, now)
                    self.store.start_session(guild.id, member.id, member.display_name, member.voice.channel.id, member.voice.channel.name, now)
                    logger.info("[VOICE] Recovered move for %s", member.display_name)
            for member in connected.values():
                channel = member.voice.channel
                self.store.start_session(guild.id, member.id, member.display_name, channel.id, channel.name, now)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if not self._monitored(member.guild) or member.bot or before.channel == after.channel:
            return
        now = datetime.now(timezone.utc)
        if before.channel:
            self.store.close_session(member.guild.id, member.id, now)
            if after.channel:
                logger.info("[VOICE] %s moved %s -> %s", member.display_name, before.channel.name, after.channel.name)
            else:
                logger.info("[VOICE] %s left %s", member.display_name, before.channel.name)
        if after.channel:
            self.store.start_session(member.guild.id, member.id, member.display_name, after.channel.id, after.channel.name, now)
            if not before.channel:
                logger.info("[VOICE] %s joined %s", member.display_name, after.channel.name)
