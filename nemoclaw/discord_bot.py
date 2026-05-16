from __future__ import annotations

import io
import os
from pathlib import Path

import discord
import httpx
from discord import app_commands

from nemoclaw.config import get_settings, load_defaults


class NemoclawBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.api = get_settings().api_base

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"Nemoclaw Discord bot logged in as {self.user}")


bot = NemoclawBot()


@bot.tree.command(name="job", description="Submit a CAE job")
@app_commands.describe(description="What to optimize or analyze", stl="Optional STL attachment")
async def cmd_job(
    interaction: discord.Interaction,
    description: str,
    stl: discord.Attachment | None = None,
):
    await interaction.response.defer(thinking=True)
    files = {}
    if stl:
        files["file"] = (stl.filename, await stl.read(), "application/octet-stream")
    data = {"user_request": description}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{bot.api}/jobs", data=data, files=files or None)
        resp.raise_for_status()
        payload = resp.json()
    await interaction.followup.send(
        f"Job `{payload['job_id']}` submitted (status: {payload['status']}). Use `/status {payload['job_id']}`."
    )


@bot.tree.command(name="status", description="Job status")
@app_commands.describe(job_id="Job id")
async def cmd_status(interaction: discord.Interaction, job_id: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{bot.api}/jobs/{job_id}")
        if resp.status_code == 404:
            await interaction.response.send_message("Job not found.", ephemeral=True)
            return
        data = resp.json()
    passes = data.get("passes", [])
    last = passes[-1] if passes else {}
    metrics = last.get("metrics", {})
    await interaction.response.send_message(
        f"**{job_id}** — `{data['status']}` stage `{data['stage']}`\n"
        f"Stop: {data.get('stop_reason')}\n"
        f"Artifacts: {', '.join(data.get('artifacts', [])) or 'none'}\n"
        f"Last metrics: {metrics}"
    )


@bot.tree.command(name="stop", description="Cancel a job")
@app_commands.describe(job_id="Job id")
async def cmd_stop(interaction: discord.Interaction, job_id: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(f"{bot.api}/jobs/{job_id}/cancel")
    await interaction.response.send_message(f"Cancel requested for `{job_id}`.")


@bot.tree.command(name="limits", description="Show optimization limits")
async def cmd_limits(interaction: discord.Interaction):
    d = load_defaults().get("optimization", {})
    await interaction.response.send_message(
        f"max_passes={d.get('max_passes')}, parallel_candidates={d.get('parallel_candidates')}, "
        f"convergence={d.get('convergence')}"
    )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not message.content.startswith("!nemoclaw"):
        return
    desc = message.content.replace("!nemoclaw", "", 1).strip()
    if not desc:
        return
    await message.channel.send("Submitting job…")
    files = {}
    if message.attachments:
        att = message.attachments[0]
        data = await att.read()
        files["file"] = (att.filename, data, "application/octet-stream")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{bot.api}/jobs",
            data={"user_request": desc},
            files=files or None,
        )
        job = resp.json()
    await message.channel.send(f"Job `{job['job_id']}` started.")


def main():
    token = get_settings().discord_bot_token or os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise SystemExit("DISCORD_BOT_TOKEN not set")
    bot.run(token)


if __name__ == "__main__":
    main()
