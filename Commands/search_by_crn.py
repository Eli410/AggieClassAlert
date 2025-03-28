from discord import Embed, app_commands
import discord
from taskDB import write_tasks
import datetime
from discord.ui import View, Button, Select, TextInput, Modal
from api import HOWDY_API
import traceback
from zoneinfo import ZoneInfo

class CRNSubmissionModal(Modal):
    crn = TextInput(
                label='CRN',
                placeholder="Enter CRN",
                required=True,
                )
    
    def __init__(self, interaction, title, on_submit_callback, on_submit_callback_args=None):
        super().__init__(title=title)
        self.interaction = interaction
        self.on_submit_callback = on_submit_callback
        self.on_submit_callback_args = on_submit_callback_args
        
    
    async def on_submit(self, interaction):
        self.on_submit_callback_args = [interaction] + (self.on_submit_callback_args + [self.crn.value] or [])
        await super().on_submit(interaction)
        await self.on_submit_callback(*self.on_submit_callback_args)

        
    async def on_error(self, interaction, error):
        trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        await interaction.client.ERROR_LOG_CHANNEL.send(f"Error in CRNSubmissionModal: ```{trace}```")
        await interaction.response.send_message(content="An error occurred while processing your request.\n(Check if the CRN or term is correct?)", ephemeral=True)



class CRNView(View):
    def __init__(self, interaction, term):
        super().__init__()  
        self.interaction = interaction
        self.term = term
        self.section = None
        self.embed = self.get_embed()
        self.update_button()

    def check_if_it_is_me(self, interaction):
        return False
    
    def get_embed(self):
        if self.section is None:
            embed = {
                "title": "Search for a course by CRN",
                "description": "Click Search to search for a course by CRN",
                "color": 0x580404,
                "timestamp": datetime.datetime.now().isoformat(),
                "author": {
                    "name": self.interaction.user.display_name,
                    "icon_url": self.interaction.user.display_avatar.url,
                },
                "footer": {
                    "text": f"{HOWDY_API.term_codes_to_desc[self.term]}",
                },
            }        
        else:
            embed = {
                "title": f"{self.section['COURSE_TITLE']}\n{self.section['COURSE_NAME']}-{self.section['SECTION_NUMBER']} ({self.section['CRN']})",
                "description": f"{self.section['COURSE_DESCRIPTION']}\n",
                "fields": [
                    {
                        "name": "Instructor",
                        "value": '\n'.join(f"[{instructor['NAME']}]({instructor['CV']})\n" for instructor in self.section['SWV_CLASS_SEARCH_INSTRCTR_JSON']),
                        "inline": True,
                    },
                    {
                        "name": "Meeting Times",
                        "value": self.section['MEETING_MESSAGE'],
                        "inline": False,
                    },
                    {
                        "name": "Syllabus",
                        "value": f"[link]({self.section['SYLLABUS']})",
                        "inline": True,
                    },
                ],
                "color": 0x580404,
                "timestamp": datetime.datetime.now().isoformat(),
                "author": {
                    "name": self.interaction.user.display_name,
                    "icon_url": self.interaction.user.display_avatar.url,
                },
                "footer": {
                    "text": f"Term: {self.term}",
                },
            }
        
        return discord.Embed.from_dict(embed)
    
    def update_button(self):
        for child in self.children:
            if isinstance(child, Button) and child.custom_id == 'Add':
                child.disabled = self.section == None
                
    async def search_callback(self, interaction, term, crn):
        # term_object=terms_object[terms_list[term]]
        self.section = await HOWDY_API.get_section_details(term, crn)
        if not self.section:
            await interaction.response.send_message(content=f"# Invalid CRN for {self.term}!", ephemeral=True)
            return
        self.embed = self.get_embed()
        self.update_button()

        await interaction.response.edit_message(embed=self.embed, view=self)

    @discord.ui.button(label='Add', style=discord.ButtonStyle.blurple, custom_id='Add')
    async def Add(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        
        name = f"{self.section['SUBJECT_CODE']} {self.section['COURSE_NUMBER']}-{self.section['SECTION_NUMBER']}"

        my_alerts = interaction.client.COMMANDS['my_alerts']
        if write_tasks(interaction.user.id, [(name, self.term, self.section['CRN'])]):
            log = {
                "user_id": interaction.user.id,
                "time": datetime.datetime.now(ZoneInfo('US/Central')).strftime('%Y-%m-%d %H:%M:%S'),
                "term": self.term,
                "CRN": self.section['CRN'],
            }
            await interaction.client.ALERT_CREATION_LOG_CHANNEL.send(f"```json\n{log}```")
            await interaction.response.send_message(content=f"Added {name} to your alert list! Check your alert with </{my_alerts.name}:{my_alerts.id}>", ephemeral=True)
        else:
            await interaction.response.send_message(content=f"Duplicated task! You already have this alert.", ephemeral=True)
    
    @discord.ui.button(label='Search', style=discord.ButtonStyle.blurple, custom_id='Search')
    async def Search(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        await interaction.response.send_modal(CRNSubmissionModal(interaction, "Search for a course by CRN", self.search_callback, [self.term]))


description = """
search_by_crn command
"""

@app_commands.command(name='search_by_crn', description=description)
async def search_by_crn(interaction: discord.Interaction, term: str):
    view = CRNView(interaction, term)
    await interaction.response.send_message("", embed=view.embed, view=view)

@search_by_crn.autocomplete('term')
async def term_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=desc, value=code)
        for code, desc in HOWDY_API.term_codes_to_desc.items() if current.lower() in desc.lower()
    ][:25]

@search_by_crn.error
async def search_error(interaction: discord.Interaction, error: Exception):
    await interaction.edit_original_response(content=f"An error occurred:\n```{error}```\nDid you use autocomplete?")
