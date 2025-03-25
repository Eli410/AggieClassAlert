from discord import Embed, app_commands
import discord
from taskDB import get_task, replace_task
import datetime
from discord.ui import View, Button, Select, Modal, TextInput


class ConfirmationModal(Modal):
    _ = TextInput(
                label='',
                placeholder="No input required, just click submit",
                required=False,
                )
    
    def __init__(self, interaction, title, on_submit_callback, on_submit_callback_args=None):
        super().__init__(title=title)
        self.interaction = interaction
        self.on_submit_callback = on_submit_callback
        self.on_submit_callback_args = on_submit_callback_args
    
    async def on_submit(self, interaction):
        self.on_submit_callback_args = [interaction] + (self.on_submit_callback_args or [])
        await self.on_submit_callback(*self.on_submit_callback_args)
        


class MyAlertsSelect(Select):
    def __init__(self, cb):
        super().__init__(
            placeholder="Select alerts to edit", 
            row=4,
            )
        self.cb = cb
    
    def add_option(self, *, label, value = ..., description = None, emoji = None, default = False):
        super().add_option(label=label, value=value, description=description, emoji=emoji, default=default)
        self.max_values = len(self.options)
    

    async def callback(self, interaction):
        await self.cb(self.values, interaction)

def my_alert_embed_select(alert_list, interaction):
    alerts_per_page = 10
    pages = []
    def new_embed():
        return {
            "title": "Your Alerts",
            "description": f"{len(alert_list)} alerts ({len([a for a in alert_list if not bool(a['completed'])])} active alerts)",
            "color": 0x580404,
            "timestamp": datetime.datetime.now().isoformat(),
            "author": {
                "name": interaction.user.display_name,
                "icon_url": interaction.user.display_avatar.url,
            },
            "fields": [],
        }

    
    sorted_alert_list = sorted(alert_list or [], key=lambda a: bool(a['completed']))
    current_embed = new_embed()

    for alert in sorted_alert_list:
        if len(current_embed["fields"]) == alerts_per_page:
            pages.append(current_embed)
            current_embed = new_embed()

        current_embed["fields"].append({
            "name": "",
            "value": f"{alert['name']} {'✅' if bool(alert['completed']) else '⏳'}",
            "inline": "false"
        })

    if current_embed["fields"]:
        pages.append(current_embed)

    if not pages:
        embed = new_embed()
        search_command = interaction.client.COMMANDS['search']
        embed["fields"].append({
            "name": f"No alerts found, use </{search_command.name}:{search_command.id}> to create one",
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

    

class MyAlertsMain(View):
    def __init__(self, interaction, change_view, can_edit):
        super().__init__()
        self.interaction = interaction
        self.change_view = change_view
        self.can_edit = can_edit
        self.current_page = 0
        self.embeds = my_alert_embed_select(get_task(self.interaction.user.id), self.interaction)
        self.update_button_state()

    def update_button_state(self):
        for child in self.children:
            if isinstance(child, Button) and child.custom_id == "Next":
                child.disabled = self.current_page == len(self.embeds) - 1
            elif isinstance(child, Button) and child.custom_id == "Prev":
                child.disabled = self.current_page == 0
            elif isinstance(child, Button) and child.custom_id == "Edit":
                if self.can_edit:
                    child.disabled = not get_task(self.interaction.user.id)
                else:
                    self.remove_item(child)

    async def reset(self):
        self.current_page = 0
        self.embeds = my_alert_embed_select(get_task(self.interaction.user.id), self.interaction)
        self.update_button_state()

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

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, custom_id="Edit", row=2)
    async def edit(self, interaction, button):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        await self.change_view("edit", interaction, "# Editing Alerts")
        
    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, Button) or isinstance(child, Select):
                child.disabled = True

        await self.change_view("main", self.interaction, "Message timed out")

class MyAlertsEdit(View):
    def __init__(self, interaction, change_view):
        super().__init__()
        self.interaction = interaction
        self.change_view = change_view
        self.current_page = 0
        self.selected_alerts = {}
        self.embeds = my_alert_embed_select(get_task(self.interaction.user.id), self.interaction)
        self.selects = self.get_selects()
        self.update_button_state()
        self.update_selects()
        
    def check_if_it_is_me(self, interaction):
        return interaction.user == self.interaction.user
    
    async def delete_all_alerts(self, interaction):
        tasks=get_task(self.interaction.user.id)
        for task in tasks:
            replace_task(self.interaction.user.id, task, None)  
        await self.change_view("main", interaction, f"{len(tasks)} alerts deleted")
    
    def update_button_state(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == "Delete Selected":
                child.disabled = not self.selected_alerts
            elif isinstance(child, discord.ui.Button) and child.custom_id == "Reactivate Selected":
                child.disabled = not self.selected_alerts
            elif isinstance(child, discord.ui.Button) and child.custom_id == "Delete All":
                child.disabled = not get_task(self.interaction.user.id)
            elif isinstance(child, Button) and child.custom_id == "Next":
                child.disabled = self.current_page == len(self.embeds) - 1
            elif isinstance(child, Button) and child.custom_id == "Prev":
                child.disabled = self.current_page == 0
    
    def update_selects(self):
        for child in self.children:
            if isinstance(child, Select):
                self.remove_item(child)
        
        if self.selects:
            self.add_item(self.selects[self.current_page])

    def update_embeds(self):
        for embed in self.embeds:
            embed.description = f"{len(self.selected_alerts)} alerts selected"
            for i, field in enumerate(embed.fields):
                
                if (field.value[:-2] or field.name[:-2]) in self.selected_alerts:
                    embed.set_field_at(i, name=field.value or field.name, value="", inline=False)
                else:
                    embed.set_field_at(i, name="", value=field.name or field.value, inline=False)
        

    def get_selects(self):
        selects = []
        for embed in self.embeds:
            select = MyAlertsSelect(self.selects_callback)
            for field in embed.fields:
                select.add_option(label=field.value, value=field.value)
            selects.append(select)
        
        return selects
    
    async def selects_callback(self, values=[], interaction=None):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        tasks = {task['name']: task for task in get_task(self.interaction.user.id)}
        for value in values:
            key = value[:-2]
            alert = tasks.get(key)
            if alert and alert['name'] not in self.selected_alerts:
                self.selected_alerts[alert['name']] = alert

        self.update_embeds()
        self.update_button_state()
        self.update_selects()
        if interaction:
            await interaction.response.edit_message(
                embed=self.embeds[self.current_page], 
                view=self,
            )




    async def reset(self):
        self.current_page = 0
        self.embeds = my_alert_embed_select(get_task(self.interaction.user.id), self.interaction)
        self.update_button_state()
        self.update_selects()
        self.selected_alerts = {}
        self.update_embeds()
        self.selects = self.get_selects()


    @discord.ui.button(label="Prev", style=discord.ButtonStyle.blurple, custom_id="Prev")
    async def prev(self, interaction, button):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        self.current_page = max(0, self.current_page - 1)
        self.update_button_state()
        self.update_selects()
        self.update_embeds()
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
        self.update_selects()
        self.update_embeds()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page], 
            view=self,
        )


    @discord.ui.button(label="Back", style=discord.ButtonStyle.primary, custom_id="Back", row=2)
    async def back(self, interaction, button):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        await self.change_view("main", interaction)

    @discord.ui.button(label="Delete Selected", style=discord.ButtonStyle.danger, custom_id="Delete Selected", row=2)
    async def delete(self, interaction, button):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        cnt = 0
        for task in self.selected_alerts.values():
            replace_task(self.interaction.user.id, task, None)
            cnt += 1
        
        await self.reset()
        await self.change_view("edit", interaction, f"{cnt} alerts deleted")

    @discord.ui.button(label="Reactivate Selected", style=discord.ButtonStyle.success, custom_id="Reactivate Selected", row=2)
    async def complete(self, interaction, button):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        cnt = 0
        for task in self.selected_alerts.values():
            new_task = task
            new_task['completed'] = False
            replace_task(self.interaction.user.id, task, new_task)
            cnt += 1

        await self.reset()
        await self.change_view("edit", interaction, f"{cnt} alerts reactivated")

    @discord.ui.button(label="Delete All", style=discord.ButtonStyle.danger, custom_id="Delete All", row=3)
    async def delete_all(self, interaction, button):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        await self.reset()
        await interaction.response.send_modal(ConfirmationModal(interaction, "Delete All Alerts?", on_submit_callback=self.delete_all_alerts))

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, Button) or isinstance(child, Select):
                child.disabled = True

        await self.change_view("edit", self.interaction, "Message timed out")

class MyAlertsView():
    def __init__(self, interaction, user = None):
        self.interaction = interaction
        self.user = user or interaction.user
        self.can_edit = (interaction.user == self.user)
        self.views = {}
        self.view = None
        self.initialise_views()
            
    
    def initialise_views(self):
        if self.user:
            self.interaction.user = self.user
        self.views["main"] = MyAlertsMain(self.interaction, self.change_view, can_edit = self.can_edit)
        self.views["edit"] = MyAlertsEdit(self.interaction, self.change_view)
        self.view = self.views["main"]
    
    async def change_view(self, view_name, interaction, message=None):
        self.view = self.views[view_name]
        await self.view.reset()
        if interaction.response.is_done():
            await interaction.edit_original_response(content=message, embed = self.view.embeds[0], view=self.view)
        else:
            await interaction.response.edit_message(content=message, embed = self.view.embeds[0], view=self.view)

description = """
View and manage your alerts.
"""

@app_commands.command(name='my_alerts', description=description)
async def my_alerts(interaction: discord.Interaction, user: discord.Member = None):
    my_alerts_page = MyAlertsView(interaction, user)
    await interaction.response.defer()
    await my_alerts_page.change_view("main", interaction)
    