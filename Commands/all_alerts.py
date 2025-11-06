from discord import Embed, app_commands
import discord
from taskDB import get_task, replace_task
from discord.ui import View, Button, Select, Modal, TextInput
import datetime
from collections import defaultdict
from api import HOWDY_API

class AllAlertsView(View):
    def __init__(self, interaction, user=None):
        super().__init__()
        self.interaction = interaction
        self.user = user or interaction.user
        self.can_edit = (interaction.user == self.user)
        self.alerts = self.alerts_counter(get_task("ALL"))
        self.current_page = 0
        self.embeds = self.all_alert_embed()
    
    def alerts_counter(self, users):
        out = defaultdict(int)
        for user in users:
            for alert in user['tasks']:
                if not alert['completed']:
                    key = (alert['name'], alert['terms'])
                    out[key] += 1
        return out
    
    def update_button_state(self):
        for child in self.children:
            if isinstance(child, Button) and child.custom_id == "Next":
                child.disabled = self.current_page == len(self.embeds) - 1
            elif isinstance(child, Button) and child.custom_id == "Prev":
                child.disabled = self.current_page == 0


    def all_alert_embed(self):
        alerts_per_page = 10
        pages = []
        def new_embed():
            return {
                "title": "All Alerts Ranking",
                "description": f"{len(self.alerts)} total alerts",
                "color": 0x580404,
                "timestamp": datetime.datetime.now().isoformat(),
                "author": {
                    "name": self.interaction.user.display_name,
                    "icon_url": self.interaction.user.display_avatar.url,
                },
                "fields": [],
            }

        
        current_embed = new_embed()

        for i, alert in enumerate(sorted(self.alerts.items(), key=lambda x: x[1], reverse=True)):
            if len(current_embed["fields"]) == alerts_per_page:
                pages.append(current_embed)
                current_embed = new_embed()

            current_embed["fields"].append({
                "name": f"{i+1}. {alert[0][0]} ({alert[1]} users)",
                "value": f"({HOWDY_API.term_codes_to_desc[alert[0][1]]})\n_ _",
                "inline": "false"
            })

        if current_embed["fields"]:
            pages.append(current_embed)

        if not pages:
            embed = new_embed()
            embed["fields"].append({
                "name": f"No alerts found",
                "value": "",
                "inline": "false"
            })
            pages.append(embed)
        
        for i in range(len(pages)):
            pages[i]["footer"] = {
                "text": f"Page {pages.index(pages[i])+1}/{len(pages)}",
            }
            pages[i] = Embed.from_dict(pages[i])
        
        return pages

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.blurple, custom_id="Prev")
    async def prev(self, interaction, button):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        self.current_page = max(0, self.current_page - 1)
        self.update_button_state()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page], 
            view=self,
        )

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple, custom_id="Next")
    async def next(self, interaction, button):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        self.current_page = min(len(self.embeds) - 1, self.current_page + 1)
        self.update_button_state()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page], 
            view=self,
        )


description = """
Check number of user subscribed to each alert.
"""

@app_commands.command(name='all_alerts', description=description)
async def all_alerts(interaction: discord.Interaction):
    my_alerts_page = AllAlertsView(interaction)
    await interaction.response.send_message("", embed=my_alerts_page.embeds[0], view=my_alerts_page)
    