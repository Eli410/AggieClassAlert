from discord import Embed, app_commands
import discord
from taskDB import write_tasks
import datetime
from discord.ui import View, Button, Label, TextInput, Modal, Select
from api import HOWDY_API
import traceback
from zoneinfo import ZoneInfo
import io


class CRNSubmissionModal(Modal):
    term = Label(
        text="Select Term",
        component=Select(
            placeholder="Select Term",
            options = [discord.SelectOption(label=desc, value=code) for code, desc in HOWDY_API.term_codes_to_desc.items()][:25],
        ))
    
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

    def get_embed(self, syllabus_url):
        embed = {
            "title": f"{self.section['COURSE_TITLE']}\n{self.section['COURSE_NAME']}-{self.section['SECTION_NUMBER']} ({self.section['CRN']})",
            "description": f"{self.section['COURSE_DESCRIPTION']}\n",
            "fields": [
                {
                    "name": "Instructor",
                    "value": '\n'.join(f"[{instructor['NAME']}]({instructor.get('CV', '#')})\n" for instructor in (self.section.get('SWV_CLASS_SEARCH_INSTRCTR_JSON') or [])),
                    "inline": True,
                },
                {
                    "name": "Meeting Times",
                    "value": self.section['MEETING_MESSAGE'],
                    "inline": False,
                },
                {
                    "name": "Syllabus",
                    "value": f"[link]({syllabus_url})" if syllabus_url else "Not available",
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
                "text": f"{HOWDY_API.term_codes_to_desc[self.term.component.values[0]]}",
            },
        }
    
        return discord.Embed.from_dict(embed)
    
    async def on_submit(self, interaction):
        term = self.term.component.values[0]
        crn = self.crn.value
        print(f"Searching for CRN {crn} in term {term}")
        self.section = await HOWDY_API.get_section_details(term, crn)
        if not self.section:
            await interaction.response.send_message(content=f"# Invalid CRN for {term}!", ephemeral=True)
            return
        
        syllabus = await HOWDY_API.get_syllabus(term, crn)
        for instructor in self.section.get('SWV_CLASS_SEARCH_INSTRCTR_JSON'):
            cv = await HOWDY_API.get_instructor_cv(instructor.get('MORE'))
            fp = io.BytesIO(cv)
            fp.seek(0)
            cv_message = await self.interaction.client.SYLLABUS_CHANNEL.send(file=discord.File(fp, filename=f"CV_{instructor['NAME'].replace(' ', '_')}.pdf"))
            instructor['CV'] = cv_message.attachments[0].url
        if syllabus:
            fp = io.BytesIO(syllabus)
            fp.seek(0)
            syllabus = await self.interaction.client.SYLLABUS_CHANNEL.send(file=discord.File(fp, filename=f"Syllabus_{crn}.pdf"))
            syllabus_url = syllabus.attachments[0].url
        else:
            syllabus_url = None

        self.embed = self.get_embed(syllabus_url)
        view = CRNView(self.interaction, self)
        await interaction.response.send_message(embed=self.embed, view=view)

        
    async def on_error(self, interaction, error):
        trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        await interaction.client.ERROR_LOG_CHANNEL.send(f"Error in CRNSubmissionModal: ```{trace}```")
        await interaction.response.send_message(content="An error occurred while processing your request.\n(Check if the CRN or term is correct?)", ephemeral=True)



class CRNView(View):
    def __init__(self, interaction, modal):
        super().__init__()  
        self.interaction = interaction
        self.term = modal.term.component.values[0]
        self.section = [cls for cls in HOWDY_API.classes[self.term] if cls['SWV_CLASS_SEARCH_CRN'] == modal.crn.value][0]
        self.update_button()
        print(self.section)
    
    async def on_timeout(self):
        await self.interaction.edit_original_response(content="# Message timed out", view=None)
    
    def update_button(self):
        for child in self.children:
            if isinstance(child, Button) and child.custom_id == 'Add':
                child.disabled = self.section == None
                
    @discord.ui.button(label='Add', style=discord.ButtonStyle.blurple, custom_id='Add')
    async def Add(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        
        name = f"{self.section['SWV_CLASS_SEARCH_SUBJECT']} {self.section['SWV_CLASS_SEARCH_COURSE']}-{self.section['SWV_CLASS_SEARCH_SECTION']}"

        my_alerts = interaction.client.COMMANDS['my_alerts']
        if write_tasks(interaction.user.id, [(name, self.term, self.section['SWV_CLASS_SEARCH_CRN'])]):
            log = {
                "user_id": interaction.user.id,
                "time": datetime.datetime.now(ZoneInfo('US/Central')).strftime('%Y-%m-%d %H:%M:%S'),
                "term": self.term,
                "CRN": self.section['SWV_CLASS_SEARCH_CRN'],
            }
            await interaction.client.ALERT_CREATION_LOG_CHANNEL.send(f"```json\n{log}```")
            await interaction.response.send_message(content=f"Added {name} to your alert list! Check your alert with </{my_alerts.name}:{my_alerts.id}>", ephemeral=True)
        else:
            await interaction.response.send_message(content=f"Duplicated task! You already have this alert.", ephemeral=True)


description = """
search_by_crn command
"""

@app_commands.command(name='search_by_crn', description=description)
async def search_by_crn(interaction: discord.Interaction):
    modal = CRNSubmissionModal(interaction, "Search for a course by CRN", lambda x: None)
    await interaction.response.send_modal(modal)


@search_by_crn.error
async def search_error(interaction: discord.Interaction, error: Exception):
    await interaction.edit_original_response(content=f"An error occurred:\n```{error}```\nDid you use autocomplete?")
