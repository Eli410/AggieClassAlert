from discord import Embed, app_commands
import discord
from taskDB import write_tasks
import datetime
from discord.ui import View, Button, Select, TextInput, Modal
from api import HOWDY_API
import traceback
from typing import List
from CustomHelpers import parse_meeting_info
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

class InstructorViewSelect(Select):
    def __init__(self, cb):
        super().__init__(
            placeholder="Select a section", 
            )
        self.cb = cb
    
    def add_option(self, *, label, value = ..., description = None, emoji = None, default = False):
        super().add_option(label=label, value=value, description=description, emoji=emoji, default=default)
        self.max_values = len(self.options)
    

    async def callback(self, interaction):
        await self.cb(self.values, interaction)

class SearchInstructorView(View):
    def __init__(self, interaction, term, instructor):
        super().__init__()
        self.term = term
        self.instructor = instructor
        self.interaction = interaction
        self.section = None
        self.current_page = 0
        self.class_list, self.CV = HOWDY_API.filter_by_instructor(term, instructor)
        self.embeds, self.selects = self.get_embeds_and_selects()
        self.update_button()
        self.update_selects()

    async def select_callback(self, values, interaction):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        success, failure = [], []
        raw = []
        for arg in values:
            term, crn = arg.split('-')
            section_details = await HOWDY_API.get_section_details(term, crn)
            name = f"{section_details['SUBJECT_CODE']} {section_details['COURSE_NUMBER']}-{section_details['SECTION_NUMBER']}"
            if write_tasks(interaction.user.id, [(name, self.term, crn)]):
                success.append(name)
                raw.append((name, self.term, crn))
            else:
                failure.append(name)
        
        message = ""
        if success:
            message += f"Added the following sections to your watchlist:\n- {'\n- '.join(success)}"
        if failure:
            message += f"\nThe following alerts are already in your alert list:\n- {'\n- '.join(failure)}"
        
        await interaction.response.send_message(content=message or "Error", ephemeral=True)
        log = [{
                "user_id": interaction.user.id,
                "time": datetime.datetime.now(ZoneInfo('US/Central')).strftime('%Y-%m-%d %H:%M:%S'),
                "term": term,
                "CRN": crn,
            } for name, term, crn in raw]
        await interaction.client.ALERT_CREATION_LOG_CHANNEL.send(f"```json\n{log}```")
        

    def get_embeds_and_selects(self):
        class_per_page = 10
        prof = f"[{self.instructor}]({self.CV})" if self.CV else self.instructor
        new_embed = lambda: discord.Embed.from_dict({
            "description": f"**Search results for {prof} ({len(self.class_list)} results)**",
            "color": 0x580404,
            "timestamp": datetime.datetime.now().isoformat(),
            "author": {
                "name": self.interaction.user.display_name,
                "icon_url": self.interaction.user.display_avatar.url,
            },
        })
        new_select = lambda: InstructorViewSelect(self.select_callback)

        pages = []
        selects = []

        for i in range(len(self.class_list)):
            cls = self.class_list[i]
            meeting_info = parse_meeting_info(cls['SWV_CLASS_SEARCH_JSON_CLOB'])
            if i % class_per_page == 0:
                pages.append(new_embed())
                selects.append(new_select())

            pages[-1].add_field(
                name=f"{cls['SWV_CLASS_SEARCH_SUBJECT']}-{cls['SWV_CLASS_SEARCH_COURSE']}-{cls['SWV_CLASS_SEARCH_SECTION']} ({cls['SWV_CLASS_SEARCH_CRN']}) ({cls['SWV_CLASS_SEARCH_TITLE']}) {'🟢' if cls['STUSEAT_OPEN'] == 'Y' else '🔴'}", 
                value=f"{meeting_info.get('Lecture', '')}\n{meeting_info.get('Laboratory', '')}", 
                inline=False)
            
            selects[-1].add_option(
                label=f"{cls['SWV_CLASS_SEARCH_SUBJECT']}-{cls['SWV_CLASS_SEARCH_COURSE']}-{cls['SWV_CLASS_SEARCH_SECTION']} ({cls['SWV_CLASS_SEARCH_TITLE']})",
                value=f"{cls['SWV_CLASS_SEARCH_TERM']}-{cls['SWV_CLASS_SEARCH_CRN']}",
            )
        
        for i in range(len(pages)):
            pages[i].set_footer(text=f"{HOWDY_API.term_codes_to_desc[self.term]}\n(Page {i+1}/{len(pages)})")
        
        return pages, selects


    def update_button(self):
        for child in self.children:
            if isinstance(child, Button) and child.custom_id == "Next":
                child.disabled = self.current_page == len(self.embeds) - 1
            elif isinstance(child, Button) and child.custom_id == "Prev":
                child.disabled = self.current_page == 0
    
    def update_selects(self):
        for child in self.children:
            if isinstance(child, InstructorViewSelect):
                self.remove_item(child)

        if self.selects:
            self.add_item(self.selects[self.current_page])
        
    async def update_embeds(self):
        if self.embeds:
            await self.interaction.edit_original_response(embed = self.embeds[self.current_page], view=self)

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.blurple, custom_id="Prev")
    async def prev(self, interaction, button):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return

        self.current_page = max(0, self.current_page - 1)
        self.update_selects()
        await self.update_embeds()
        self.update_button()
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
        self.update_selects()
        await self.update_embeds()
        self.update_button()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page], 
            view=self,
        )

    @discord.ui.button(label="Select all", style=discord.ButtonStyle.green, custom_id="SelectAll")
    async def select_all(self, interaction, button):
        if self.interaction.user != interaction.user:
            command = interaction.client.COMMANDS[self.interaction.command.name]
            await interaction.response.send_message(content=f"This is not your embed! Run the command </{command.name}:{command.id}>", ephemeral=True)
            return
        
        all_values = [option.value for option in self.selects[self.current_page].options]
        await self.select_callback(all_values, interaction)



description = "Search for a course by instructor"

@app_commands.command(name='search_by_instructor', description=description)
async def search_by_instructor(interaction: discord.Interaction, term: str, instructor: str):
    await interaction.response.defer(ephemeral=False, thinking=True)
    view = SearchInstructorView(interaction, term, instructor)
    await interaction.edit_original_response(view=view, embed=view.embeds[0])
    

@search_by_instructor.autocomplete("term")
async def term_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:    
    return [
        app_commands.Choice(name=desc, value=code)
        for code, desc in HOWDY_API.term_codes_to_desc.items()
        if current.lower() in desc.lower()
    ][:25]

@search_by_instructor.autocomplete("instructor")
async def instructor_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    similar = lambda a, b: SequenceMatcher(None, a.lower(), b.lower()).ratio()

    term = interaction.data["options"][0]["value"]
    matches = sorted(HOWDY_API.get_all_instructors(term), key=lambda instructor: similar(current, instructor), reverse=True)[:10]
    return [app_commands.Choice(name=match, value=match) for match in matches]

@search_by_instructor.error
async def search_by_instructor_error(interaction: discord.Interaction, error: Exception):
    await interaction.followup.send(f"An error occurred:\n ```{error}```\nIt is likely that you did not use auto-fill for the arguments.", ephemeral=True)
    await interaction.client.ERROR_LOG_CHANNEL.send(f"```{error}\n{traceback.format_exc()}```")