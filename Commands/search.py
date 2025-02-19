from discord import app_commands
import discord
from taskDB import write_tasks
import datetime
from discord.ui import View, Button, Select
from api import HOWDY_API
from typing import List
from CustomHelpers import parse_meeting_info, parse_prof

class SearchViewSelect(Select):
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



class SearchView(View):
    def __init__(self, interaction: discord.Interaction, term, course):
        super().__init__()
        self.term = term
        self.course = course
        self.interaction = interaction
        self.section = None
        self.current_page = 0
        self.class_list = HOWDY_API.filter_by_course(term, course)
        self.embeds, self.selects = self.get_embeds_and_selects()
        self.update_button()
        self.update_selects()
        
    async def select_callback(self, values, interaction):
        success, failure = [], []
        for arg in values:
            term, crn = arg.split('-')
            section_details = await HOWDY_API.get_section_details(term, crn)
            name = f"{section_details['SUBJECT_CODE']} {section_details['COURSE_NUMBER']}-{section_details['SECTION_NUMBER']}"
            if write_tasks(interaction.user.id, [(name, self.term, crn)]):
                success.append(name)
            else:
                failure.append(name)
        
        message = ""
        if success:
            message += f"Added the following sections to your watchlist:\n- {'\n- '.join(success)}"
        if failure:
            message += f"\nThe following alerts are already in your alert list:\n- {'\n- '.join(failure)}"
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(content=message or "Error", ephemeral=True)
        

    def get_embeds_and_selects(self):
        class_per_page = 10
        new_embed = lambda: discord.Embed.from_dict({
            "description": f"**Search results for {self.course} ({cls['SWV_CLASS_SEARCH_TITLE']})**\n({len(self.class_list)} results)",
            "color": 0x580404,
            "timestamp": datetime.datetime.now().isoformat(),
            "author": {
                "name": self.interaction.user.display_name,
                "icon_url": self.interaction.user.display_avatar.url,
            },
        })
        new_select = lambda: SearchViewSelect(self.select_callback)

        pages = []
        selects = []
        
        for i in range(len(self.class_list)):
            cls = self.class_list[i]
            meeting_info = parse_meeting_info(cls['SWV_CLASS_SEARCH_JSON_CLOB'])
            prof = parse_prof(cls['SWV_CLASS_SEARCH_INSTRCTR_JSON'])
            if i % class_per_page == 0:
                pages.append(new_embed())
                selects.append(new_select())

            lab_field = f"Lab: {meeting_info['Laboratory']}\n" if meeting_info.get('Laboratory') else ""
            pages[-1].add_field(
                name=f"{cls['SWV_CLASS_SEARCH_SUBJECT']}-{cls['SWV_CLASS_SEARCH_COURSE']}-{cls['SWV_CLASS_SEARCH_SECTION']} ({cls['SWV_CLASS_SEARCH_CRN']}) {'🟢' if cls['STUSEAT_OPEN'] == 'Y' else '🔴'}",
                value=f"Lecture: {meeting_info['Lecture']}\n\
                        {lab_field}\
                        {', '.join([f'[{p[0]}]({p[1]})' if p[1] else f"**{p[0]}**" for p in prof])}\n\
                        [Syllabus](https://compass-ssb.tamu.edu/pls/PROD/bwykfupd.p_showdoc?doctype_in=SY&crn_in={cls['SWV_CLASS_SEARCH_CRN']}&termcode_in={cls['SWV_CLASS_SEARCH_TERM']})",
                inline=False)
            
            selects[-1].add_option(
                label=f"{cls['SWV_CLASS_SEARCH_SUBJECT']}-{cls['SWV_CLASS_SEARCH_COURSE']}-{cls['SWV_CLASS_SEARCH_SECTION']} ({cls['SWV_CLASS_SEARCH_TITLE']}) {'🟢' if cls['STUSEAT_OPEN'] == 'Y' else '🔴'}",
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
            if isinstance(child, SearchViewSelect):
                self.remove_item(child)

        if self.selects:
            self.add_item(self.selects[self.current_page])
        
    async def update_embeds(self):
        if self.embeds:
            await self.interaction.edit_original_response(embed = self.embeds[self.current_page], view=self)

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.blurple, custom_id="Prev")
    async def prev(self, interaction, button):
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
        all_values = [option.value for option in self.selects[self.current_page].options]
        await self.select_callback(all_values, interaction)



@app_commands.command(name='search')
async def search(interaction: discord.Interaction, term: str, course: str):
    await interaction.response.defer(ephemeral=False, thinking=True)
    view = SearchView(interaction, term, course)
    await interaction.edit_original_response(view=view, embed=view.embeds[0])
    

@search.autocomplete('term')
async def term_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=desc, value=code)
        for code, desc in HOWDY_API.term_codes_to_desc.items() if current.lower() in desc.lower()
    ][:25]

@search.autocomplete('course')
async def class_autocomplete(interaction: discord.Interaction, current: str):
    if not current:
        return []
    current = current.strip()
    term = interaction.data['options'][0]['value']
    classes = HOWDY_API.get_term_general_info(term)
    choices = []
    for cls in classes:
        candidate = f"{cls[0]} {cls[1]}"
        if current.lower() in candidate.lower():
            choices.append(app_commands.Choice(name=candidate, value=candidate))
            if len(choices) == 10:
                break
            
    return choices
