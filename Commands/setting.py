from discord import Embed, app_commands
import discord
from discord.ui import View, Button, Select, Modal, TextInput
import datetime
from userSettings import USER_PREFERENCES


class SettingView(View):
    def __init__(self, interaction, user=None):
        super().__init__()
        self.interaction = interaction
        self.preference = USER_PREFERENCES
        self.embed = self.setting_embed()
        self.update_buttons()

    def get_settings(self):
        return self.preference.get_user_settings(self.interaction.user.id)

    def setting_embed(self):
        embed = {
            "title": "Settings",
            "description": "Configure your settings and preferences for the bot.",
            "color": 0x580404,
            "timestamp": datetime.datetime.now().isoformat(),
            "author": {
                "name": self.interaction.user.display_name,
                "icon_url": self.interaction.user.display_avatar.url,
            },
            "fields": [],
        }
        settings = self.get_settings()

        embed["fields"].append({
            "name": "Alert method",
            "value": "DM" if settings['DM'] else "in <#1229476856995254342>",
            "inline": False,
        })

        reg_time_value = f"{'\n'.join(settings['reg_time'])}" if settings['reg_time'] else "None"
        embed["fields"].append({
            "name": "Registration Times",
            "value": reg_time_value,
            "inline": False,
        })

        return discord.Embed.from_dict(embed)
        
    def update_buttons(self):
        settings = self.get_settings()
        if settings['DM']:
            for button in self.children:
                if button.custom_id == "change_dm":
                    button.label = "Alert me in server"
                    button.style = discord.ButtonStyle.primary
                if button.custom_id == "test_dm":
                    button.disabled = False
        else:
            for button in self.children:
                if button.custom_id == "change_dm":
                    button.label = "DM me"
                    button.style = discord.ButtonStyle.primary
                if button.custom_id == "test_dm":
                    button.disabled = True

    @discord.ui.button(label="1", style=discord.ButtonStyle.success, custom_id="change_dm")
    async def change_dm(self, interaction, button):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        
        settings = self.get_settings()
        settings['DM'] = not settings['DM']
        self.preference.update_user_setting(self.interaction.user.id, 'DM', settings['DM'])
        self.embed = self.setting_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=self.embed, view=self)
    
    @discord.ui.button(label="DM test", style=discord.ButtonStyle.primary, custom_id="test_dm")
    async def test_dm(self, interaction, button):
        settings = self.get_settings()
        if settings['DM']:
            embed = discord.Embed(title="Test DM", description="This is a test DM from the bot.", color=0x580404)
            try:
                await interaction.user.send(embed=embed)
            except discord.Forbidden:
                await interaction.response.send_message("I cannot send you DMs. Please check your settings.", ephemeral=True)
                return
            await interaction.response.send_message("Test DM sent!", ephemeral=True)
        else:
            await interaction.response.send_message("You have disabled DM notifications.", ephemeral=True)
        
    @discord.ui.button(label="Add Registration Time", style=discord.ButtonStyle.primary, custom_id="add_reg_time", row = 2, disabled=True)
    async def add_reg_time(self, interaction, button):
        modal = Modal(title="Add Registration Time")
        modal.add_item(TextInput(label="From", placeholder="e.g. 04/14/2025 05:00 AM", required=True, max_length=100))
        modal.add_item(TextInput(label="To", placeholder="e.g. 04/14/2025 05:00 AM", required=True, max_length=100))
        
        async def on_submit(modal_interaction):
            for child in modal.children:
                if child.label == "From":
                    from_time = child.value
                elif child.label == "To":
                    to_time = child.value
            if not from_time or not to_time:
                await modal_interaction.response.send_message("Please fill in both fields.", ephemeral=True)
                return
        
            try:
                reg_time = f"{from_time} - {to_time}"
                from_time = datetime.datetime.strptime(from_time, "%m/%d/%Y %I:%M %p")
                to_time = datetime.datetime.strptime(to_time, "%m/%d/%Y %I:%M %p")
            except ValueError:
                await modal_interaction.response.send_message("Invalid date format. Please use MM/DD/YYYY HH:MM AM/PM.", ephemeral=True)
                return
            
            if from_time >= to_time:
                await modal_interaction.response.send_message("The 'From' time must be earlier than the 'To' time.", ephemeral=True)
                return
            
            settings = self.get_settings()
            settings['reg_time'].append(reg_time)
            self.preference.update_user_setting(self.interaction.user.id, 'reg_time', settings['reg_time'])
            self.embed = self.setting_embed()
            await modal_interaction.response.send_message(embed=self.embed, view=self)
        
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Remove Registration Time", style=discord.ButtonStyle.danger, custom_id="remove_reg_time", row = 2, disabled=True)
    async def remove_reg_time(self, interaction, button):
        settings = self.get_settings()

        modal = Modal(title="Remove Registration Time")
        selections = Select(placeholder="Select a registration time to remove", min_values=1, max_values=len(settings['reg_time']))
        for reg_time in settings['reg_time']:
            selections.add_option(label=reg_time, value=reg_time)
        modal.add_item(selections)

        async def on_submit(modal_interaction):
            selected_times = modal_interaction.data['values']
            for reg_time in selected_times:
                settings['reg_time'].remove(reg_time)
            self.preference.update_user_setting(self.interaction.user.id, 'reg_time', settings['reg_time'])
            self.embed = self.setting_embed()
            await modal_interaction.response.send_message(embed=self.embed, view=self)
        
        modal.on_submit = on_submit
        await interaction.response.send_modal(modal)

    
        
    
    
    
    
    async def on_timeout(self):
        await self.interaction.edit_original_response(content="# Message timed out", view=None)


    async def send_initial_response(self):
        await self.interaction.response.send_message(embed=self.embed, view=self)


description = """
Configure your settings and preferences for the bot.
"""

@app_commands.command(name='setting', description=description)
async def setting(interaction: discord.Interaction):
    view = SettingView(interaction)
    await view.send_initial_response()
