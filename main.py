import json
import discord
from discord import app_commands, ButtonStyle, SelectOption, AllowedMentions, CustomActivity
from discord.interactions import Interaction
from discord.ui import Button, View, Modal, Select, TextInput
import time
from discord.ext import tasks
from typing import List
import ast
from class_notification import terms_list, terms_object, get_task, write_tasks, replace_task
import datetime
import pytz
import itertools
import asyncio
from functools import wraps


class MyModal(Modal):
    def __init__(self, components, callback_func=None, callback_func_arg=None, **kwargs):
        super().__init__(**kwargs)
        for field in components:
            self.add_item(field)
        
        self.callback_func = callback_func
        self.callback_func_arg = callback_func_arg

    async def on_submit(self, interaction: discord.Interaction):
        if self.callback_func:
            if self.callback_func_arg:
                await self.callback_func(interaction, self.callback_func_arg)
            else:
                await self.callback_func(interaction)

    

class MyView(View):
    def __init__(self, components, callback_func=None, callback_func_arg=None, **kwargs):
        super().__init__(**kwargs)
        self.func=callback_func
        self.arg=callback_func_arg
        if components!=None:
            for component in components:
                self.add_item(component)
        
    async def on_timeout(self):
        if self.func!=None:
            if self.arg!=None:
                await self.func(*self.arg)
            else:
                await self.func()
        else:
            return
    


class MyButton(Button):
    def __init__(self, callback=None, callback_arg=None, **kwargs):
        super().__init__(**kwargs)
        self.cb=callback
        self.cb_arg=callback_arg
        
    async def callback(self, interaction):
        if self.cb_arg:
            await self.cb(interaction, self.cb_arg)
        else:
            await self.cb(interaction)
    
    def disable(self):
        self.disabled=True

class MyTextInput(TextInput):
    def __init__(self, callback=None, callback_arg=None, **kwargs):
        super().__init__(**kwargs)
        self.cb=callback
        self.cb_arg=callback_arg
        # self.on_submit=on_submit
        # self.on_submit_arg=on_submit_arg
    async def callback(self, interaction):
        if self.cb_arg:
            await self.cb(interaction, self.cb_arg)
        else:
            await self.cb(interaction)
    
    async def on_submit(self, interaction):
        if self.on_submit:
            if self.on_submit_arg:
                await self.on_submit(interaction, self.on_submit_arg)
            await self.on_submit(interaction)
        
    def disable(self):
        self.disabled=True

class MySelect(Select):
    def __init__(self, callback=None, callback_arg=None, **kwargs):
        super().__init__(**kwargs)
        self.cb=callback
        self.cb_arg=callback_arg
        
    async def callback(self, interaction):
        if self.cb_arg:
            await self.cb(interaction, self.values, self.cb_arg)
        else:
            await self.cb(interaction, self.values)

    
    def set_callback(self, cb):
        self.cb=cb
    
    def set_cb_arg(self, arg):
        self.cb_arg=arg

    def disable(self):
        self.disabled=True

    def change_placeholder(self, new):
        self.placeholder=new

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # an attribute we can access from our task
        self.counter = 0

    async def setup_hook(self) -> None:
        # start the task to run in the background
        self.my_background_task.start()

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def check_availability_and_notify(self, user, alert, term_obj, task, alert_channel):
        name, terms, CRN, comp, value, completed = alert['name'], alert['terms'], alert['CRN'], alert['comp'], alert['value'], alert['completed']
        if completed:
            return

        seats = await term_obj.get_availability(CRN)

        if seats['Available'] == '-1' and seats['Capacity'] == '-1' and seats['Taken'] == '-1':
            embed=discord.Embed(title=f"Error getting availability for", description=f"{name}", color=discord.Color.red())
            embed.set_author(name=user.name, icon_url=user.display_avatar.url)
            embed.set_footer(text=term_obj.display_name)
            client.get_user(385627167259623435).send(embed=embed)
            return

        trigger = False
        if comp == '>' and int(seats['Available']) > int(value):
            trigger = True
        elif comp == '=' and int(seats['Available']) == int(value):
            trigger = True

        if trigger:
            embed=discord.Embed(title=f"Alert triggered", description=f"{name}", color=discord.Color.green())
            embed.set_author(name=user.name, icon_url=user.display_avatar.url)
            embed.set_footer(text=term_obj.display_name)

            try:
                await user.send(embed=embed)
            except discord.Forbidden:
                await alert_channel.send(f'<@{user.id}> I am not able to message you, here is your alert: ', embed=embed)
                
            alert['completed'] = True
            replace_task(task['user_id'], alert, alert)  # Update the task as completed


    @tasks.loop(seconds=60)  # task runs every 60 seconds
    async def my_background_task(self):
        await self.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.watching, name="for available seats"))
        tasks = get_task("ALL")
        alert_channel = self.get_channel(1229476856995254342)

        # Prepare tasks for all alerts
        alert_tasks = []
        for task in tasks:
            user = self.get_user(task['user_id'])
            for alert in task['tasks']:
                if not alert['completed']:
                    term_obj = terms_object[alert['terms']]
                    alert_tasks.append(self.check_availability_and_notify(user, alert, term_obj, task, alert_channel))

        # Run all tasks concurrently
        await asyncio.gather(*alert_tasks)

        # Update status after all tasks have completed
        next_check_time = datetime.datetime.now(pytz.timezone('America/Chicago')) + datetime.timedelta(seconds=60)
        await self.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.watching, name=f"Again at CDT {next_check_time.strftime('%H:%M:%S')}"))


    @my_background_task.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()  # wait until the bot logs in

def check_user_auth(original_interaction):
    async def decorator(func):
        @wraps(func)
        async def wrapper(interaction, *args, **kwargs):
            if interaction.user.id != original_interaction.user.id:
                await interaction.response.send_message("**Don't mess with other people's stuff!**", ephemeral=True)
                return
            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator


async def create_alert(interaction, arg, original_interaction):
    user_id=interaction.user.id
    if interaction.user.id!=original_interaction.user.id:
        await interaction.response.send_message("**Don't mess with other people's stuff!**", ephemeral=True)
        return
    
    embed=discord.Embed(color=discord.Color.green())
    embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
    embed.set_footer(text=original_interaction.message.embeds[0].footer.text)
    
    arg=[ast.literal_eval(x) for x in arg]
    cnt=0
    for term, crn, op, val in arg:
        class_=terms_object[str(term)].search_by_crn(crn)
        name=f"Alert me when seats in {class_['SWV_CLASS_SEARCH_SUBJECT']} {class_['SWV_CLASS_SEARCH_COURSE']}-{class_['SWV_CLASS_SEARCH_SECTION']} {op} {val}"

        success=write_tasks(user_id, [(name, term, crn, op, val)])
        if not success:
            name+=" **(Duplicate)**"
        else:
            cnt+=1
        embed.add_field(name=name, value="_ _", inline=False)
        
    embed.title=f"{cnt} alerts created."
    embed.description="Use `/my_alerts` to view and edit your alerts."
    if cnt!=len(arg):
        embed.description+="\n**Some alerts were not created due to duplicates.**"
    await interaction.response.edit_message(embed=embed, view=None)


async def switch_embed(interatction, arg):
    if interatction.user.id!=arg.user.id:
        await interatction.response.send_message("**Don't mess with other people's stuff!**", ephemeral=True)
        return
    
    buttons=[MyButton(style=ButtonStyle.green, label="Next page", callback=switch_embed, callback_arg=arg)]

    view=MyView(components=buttons+[next(arg.extras['select_iterator'])])
    await interatction.response.edit_message(embed=next(arg.extras['embed_iterator']), view=view)



async def alert_setup(interaction, arg, original_interaction):
    if interaction.user.id!=original_interaction.user.id:
        await interaction.response.send_message("**Don't mess with other people's stuff!**", ephemeral=True)
        return
    selections=[]
    embed=interaction.message.embeds[0]
    new_embed=discord.Embed(color=embed.color)

    if arg=='All':
        pass
    else:
        arg=[ast.literal_eval(x) for x in arg]
        # arg=ast.literal_eval(arg)
        new_embed.title=embed.title
        new_embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        for term, crn in arg:
            class_=terms_object[str(term)].search_by_crn(crn)
            selections.append(SelectOption(label=f"Alert me when seats in {class_['SWV_CLASS_SEARCH_SUBJECT']} {class_['SWV_CLASS_SEARCH_COURSE']}-{class_['SWV_CLASS_SEARCH_SECTION']} > 0", value=f"('{term}','{crn}','>','0')"))
            for field in embed.fields:
                if field.name==f"Section: {class_['SWV_CLASS_SEARCH_SECTION']} ({class_['Availability']})":
                    new_embed.add_field(name=field.name, value=field.value, inline=False)
                    break
            else:
                new_embed=embed
            new_embed.set_footer(text=embed.footer.text)

        new_embed.description=f"Selected {len(selections)} sections."

    selections=[MySelect(options=selections, placeholder="Select alert type", callback=create_alert, callback_arg=(interaction), max_values=len(selections))]
    view=MyView(components=selections)
    await interaction.response.edit_message(view=view, embed=new_embed)

def build_embed(interaction, fields, title, description, footer, inline=True, field_per_embed=25):
    embed=discord.Embed(title=title, color=discord.Color.green())
    embeds=[]

    for field in fields:
        if len(embed.fields)==field_per_embed:
            embeds.append(embed)
            embed=discord.Embed(title=title, description=description, color=discord.Color.green())
        embed.add_field(name=field[0], value=field[1], inline=inline)
        if len(embed)>6000:
            embed.remove_field(len(embed.fields)-1)
            embeds.append(embed)
            embed=discord.Embed(title=title, description=description, color=discord.Color.green())

    embeds.append(embed)
    for embed in embeds:
        if description=="":
            embed.description=f"Showing page {embeds.index(embed)+1}/{len(embeds)}, {len(fields)} results in total."
        else:
            embed.description=description
        
        if footer=="":
            embed.set_footer(text=f"Showing page {embeds.index(embed)+1}/{len(embeds)}, {len(fields)} results in total.")
        else:
            embed.set_footer(text=footer)
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)

    return embeds

def build_select_from_embed(selects, embeds):
    grouped_selects=[]
    for embed in embeds:
        select=[]
        for field in embed.fields:
            for select_ in selects:
                if select_.label.split(' ')[1].split('-')[1] in field.name:
                    select.append(SelectOption(label=select_.label, value=select_.value))
                    break
        grouped_selects.append(select)

    return grouped_selects













intents = discord.Intents.default()
intents.members = True
intents.message_content=True

client = MyClient(intents=intents, allowed_mentions=AllowedMentions(everyone=False, users=True, roles=True, replied_user=True))
tree = app_commands.CommandTree(client)



@tree.command(name='sync', description='Owner only', guild=discord.Object(id=705127855251652720))
async def sync(interaction: discord.Interaction, server_id:str=None):
    if interaction.user.id == 385627167259623435:
        if server_id is not None:
            await tree.sync(guild=discord.Object(id=int(server_id)))
            print('Command tree synced.')
            await interaction.response.send_message('Command tree synced', ephemeral=True)
        await tree.sync()
        print('Command tree synced.')
        await interaction.response.send_message('Command tree synced', ephemeral=True)
    else:
        await interaction.response.send_message('You must be the owner to use this command!', ephemeral=True)


@tree.command(name='status',description='General status of the bot.')
async def status(interaction):
    t=time.monotonic()
    await interaction.response.send_message('Online!')
    await interaction.edit_original_response(content='Online! Ping: **'+str(round(time.monotonic()-t,3))+'** seconds')





@tree.command(name='search')
async def search(interaction: discord.Interaction, term: str, subject: str, course_number: str):

    async def process_class(class_, term_object):
        instructor = json.loads(class_['SWV_CLASS_SEARCH_INSTRCTR_JSON']) if class_['SWV_CLASS_SEARCH_INSTRCTR_JSON'] else [{'NAME': "None"}]
        try:
            seats = await term_object.get_availability(class_['SWV_CLASS_SEARCH_CRN'])
        except:
            seats = {'Capacity': '-1', 'Taken': '-1', 'Available': '-1'}

        class_['Availability'] = f"{seats['Available']}/{seats['Capacity']}"
        
        lec = None
        lab = None
        meet_time = json.loads(class_['SWV_CLASS_SEARCH_JSON_CLOB'])
        
        for meet in meet_time:
            if meet['SSRMEET_MTYP_CODE'] == 'Lecture':
                lec = f"Lecture: {''.join(value for key, value in meet.items() if key.endswith('_DAY') and value is not None)} {meet['SSRMEET_BEGIN_TIME']+'-'+meet['SSRMEET_END_TIME'] if meet['SSRMEET_BEGIN_TIME'] else ''} {meet['SSRMEET_BLDG_CODE'] if meet['SSRMEET_BLDG_CODE'] else ''} {meet['SSRMEET_ROOM_CODE'] if meet['SSRMEET_ROOM_CODE'] else ''}"
            elif meet['SSRMEET_MTYP_CODE'] == 'Laboratory':
                lab = f"Lab: {''.join(value for key, value in meet.items() if key.endswith('_DAY') and value is not None)} {meet['SSRMEET_BEGIN_TIME']+'-'+meet['SSRMEET_END_TIME'] if meet['SSRMEET_BEGIN_TIME'] else ''} {meet['SSRMEET_BLDG_CODE'] if meet['SSRMEET_BLDG_CODE'] else ''} {meet['SSRMEET_ROOM_CODE'] if meet['SSRMEET_ROOM_CODE'] else ''}"
        
        fields.append((f"Section: {class_['SWV_CLASS_SEARCH_SECTION']} ({class_['Availability']})", f"Instructor: {' and '.join([x['NAME'] for x in instructor])}\n{lec if lec else ''}\n{lab if lab else ''}"))
        selects.append(SelectOption(label=f"{class_['SWV_CLASS_SEARCH_SUBJECT']} {class_['SWV_CLASS_SEARCH_COURSE']}-{class_['SWV_CLASS_SEARCH_SECTION']} {' and '.join([x['NAME'] for x in instructor])} ({class_['Availability']})", value=f"('{class_['SWV_CLASS_SEARCH_TERM']}','{class_['SWV_CLASS_SEARCH_CRN']}')"))

    async def switch_embed(interatction, arg):
        if interatction.user.id!=arg.user.id:
            await interatction.response.send_message("**Don't mess with other people's stuff!**", ephemeral=True)
            return
        view=MyView(components=buttons+[next(arg.extras['select_iterator'])])
        await interatction.response.edit_message(embed=next(arg.extras['embed_iterator']), view=view)



    await interaction.response.defer()
    term_object=terms_object[terms_list[term]]
    classes=term_object.search(subject, course_number.split(' - ')[0].strip())
    fields=[]
    selects=[]

    tasks = [process_class(class_, term_object) for class_ in classes]
    await asyncio.gather(*tasks)


    embeds=build_embed(interaction, fields, f"Search results for {subject}, {course_number}", "", term, field_per_embed=9)
    selects=build_select_from_embed(selects, embeds)
    my_selects=[]
    for select in selects:
        my_selects.append(MySelect(options=select, placeholder="Select section", callback=alert_setup, callback_arg=(interaction), max_values=len(select)))

    embed_iterator = itertools.cycle(embeds)
    select_iterator = itertools.cycle(my_selects)
    if len(embeds)==1:
        buttons=[]
    else:
        buttons=[MyButton(style=ButtonStyle.green, label="Next page", callback=switch_embed, callback_arg=interaction)]
    view=MyView(components=buttons+[next(select_iterator)])
    interaction.extras['embed_iterator']=embed_iterator
    interaction.extras['select_iterator']=select_iterator

    await interaction.followup.send(embed=next(embed_iterator), view=view)


@search.autocomplete('term')
async def term_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    terms = list(terms_list.keys())
    return [
        app_commands.Choice(name=term, value=term)
        for term in terms if current.lower() in term.lower()
    ]

@search.autocomplete('subject')
async def subject_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    term=interaction.data['options'][0]['value']
    term_code=terms_list[term]
    term=terms_object[term_code]
    subjects_list=sorted(list(set([x['SWV_CLASS_SEARCH_SUBJECT_DESC'] for x in term.classes])))
    return [
        app_commands.Choice(name=subject, value=subject)
        for subject in subjects_list if current.lower() in subject.lower()
    ]

@search.autocomplete('course_number')
async def course_number_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    term=interaction.data['options'][0]['value']
    term_code=terms_list[term]
    term=terms_object[term_code]
    class_=interaction.data['options'][1]['value']
    sections_list=sorted(list(set([f"{x['SWV_CLASS_SEARCH_COURSE']} - {x['SWV_CLASS_SEARCH_TITLE']}" for x in term.classes if x['SWV_CLASS_SEARCH_SUBJECT_DESC']==class_])))
    return [
        app_commands.Choice(name=section, value=section)
        for section in sections_list if current.lower() in section.lower()
    ]

@search.error
async def search_error(interaction, error):
    if interaction.response.is_done():
        await interaction.edit_original_response(content=f'An error occured, please try again. Maybe you entered the wrong arguments, make sure to use the auto complete.\nError: ```{error}```')
    else:
        await interaction.response.send_message(f'An error occured, please try again. Maybe you entered the wrong arguments, make sure to use the auto complete.\nError: ```{error}```')

@tree.command(name='my_alerts')
async def my_alerts(interaction: discord.Interaction):

    def build_select_from_embed(selects, embeds):
        grouped_selects=[]
        for embed in embeds:
            select=[]
            for field in embed.fields:
                for select_ in selects:
                    if select_.label == field.name:
                        select.append(SelectOption(label=select_.label, value=select_.value))
                        break
            grouped_selects.append(select)

        return grouped_selects
    
    async def main_menu(interaction):
        user_id=interaction.user.id
        tasks=get_task(user_id)
        fields=[]
        # embed=discord.Embed(title="Your alerts", color=discord.Color.green())
        # embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        select=[]
        if tasks:
            for task in tasks:
                fields.append((task['name'], f"Status: **{('Completed' if bool(task['completed']) else 'Ongoing')}**"))
                select.append(SelectOption(label=task['name'], value=task['name']))
        else:
            fields.append(("You have no alerts set up.", "Use the `/search` command to set up alerts."))
        
        embeds=build_embed(interaction, fields, "Your alerts", " ", "", inline=True, field_per_embed=6)
        

        selects=build_select_from_embed(select, embeds)
        my_selects=[]
        for select in selects:
            my_selects.append(MySelect(options=select+[SelectOption(label="All", value="All")], placeholder="Select alert to edit", callback=handel_alert_edit, callback_arg=interaction))
        select_iterator = itertools.cycle(my_selects)

        if len(embeds)==1:
            buttons=[]
            if len(select)==0:
                view=None
            else:
                view=MyView(components=[next(select_iterator)])
        else:
            buttons=[MyButton(style=ButtonStyle.green, label="Next page", callback=switch_embed, callback_arg=interaction)]
            embed_iterator = itertools.cycle(embeds)
            view=MyView(components=buttons+[next(select_iterator)])
            interaction.extras['embed_iterator']=embed_iterator
            interaction.extras['select_iterator']=select_iterator

        if interaction:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=(next(embed_iterator) if len(embeds)>1 else embeds[0]), view=view)
            else:
                await interaction.response.send_message(embed=(next(embed_iterator) if len(embeds)>1 else embeds[0]), view=view)


    async def handel_alert_edit(interaction, arg, original_interaction):
        if interaction.user.id!=original_interaction.user.id:
            await interaction.response.send_message("**Don't mess with other people's stuff!**", ephemeral=True)
            return
        
        action=arg[0]
        user_id=interaction.user.id
        tasks=get_task(user_id)
        if action=='All':
            tasks=get_task(user_id)
        else:
            tasks=get_task(user_id)
            task=None
            for _ in tasks:
                if _['name']==action:
                    task=_
                    break

        
        async def edit_alert(interaction, arg):
            await interaction.response.defer()
            if interaction.user.id!=original_interaction.user.id:
                await interaction.response.send_message("**Don't mess with other people's stuff!**", ephemeral=True)
                return
            arg=arg[0]
            if arg=="Delete":
                task = next((_ for _ in tasks if _['name'] == action), None)
                replace_task(user_id, task, None)
                await original_interaction.edit_original_response(content="Alert deleted.", embed=None, view=None)
                await main_menu(original_interaction)

            elif arg=="False":
                task = next((_ for _ in tasks if _['name'] == action), None)
                new_task=task
                new_task['completed']=False
                replace_task(user_id, task, new_task)
                await original_interaction.edit_original_response(content="Alert marked as ongoing.", embed=None, view=None)
                await main_menu(original_interaction)
            
            elif arg=="Delete All":
                for task in tasks:
                    replace_task(user_id, task, None)   
                await original_interaction.edit_original_response(content="All alerts deleted.", embed=None, view=None)
                await main_menu(original_interaction)
            
            elif arg=="False All":
                for task in tasks:
                    new_task=task
                    new_task['completed']=False
                    replace_task(user_id, task, new_task)
                await original_interaction.edit_original_response(content="All alerts marked as ongoing.", embed=None, view=None)
                await main_menu(original_interaction)

        new_embed=discord.Embed(title="Editing Alert", color=discord.Color.green())
        new_embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)


        for embed in interaction.message.embeds:
            for field in embed.fields:
                if action=="All":
                    new_embed.add_field(name=field.name, value=field.value, inline=False)
                else:
                    if field.name==action:
                        new_embed.add_field(name=field.name, value=field.value, inline=False)
                        break
                    
        if action=="All":
            select=[]
            select.append(SelectOption(label="Delete All", value="Delete All"))
            select.append(SelectOption(label="Mark All as Ongoing", value="False All"))
            
        else:

            select=[SelectOption(label="Delete Alert", value="Delete")]
            if task['completed']:
                select.append(SelectOption(label="Mark as Ongoing", value="False"))


        select=MyView(components=[MySelect(options=select, placeholder="Select actions", callback=edit_alert)])
        await interaction.response.edit_message(embed=new_embed, view=select)
    
    await main_menu(interaction)
    

@tree.command(name='search_by_instructor')
async def search_by_instructor(interaction: discord.Interaction, term: str, instructor: str):
    

    await interaction.response.defer()
    async def process_class(class_, term_object):
        instructor = json.loads(class_['SWV_CLASS_SEARCH_INSTRCTR_JSON']) if class_['SWV_CLASS_SEARCH_INSTRCTR_JSON'] else [{'NAME': "None"}]        
        try:
            seats = await term_object.get_availability(class_['SWV_CLASS_SEARCH_CRN'])
        except:
            seats = {'Capacity': '-1', 'Taken': '-1', 'Available': '-1'}

        class_['Availability'] = f"{seats['Available']}/{seats['Capacity']}"
        
        lec = None
        lab = None
        meet_time = json.loads(class_['SWV_CLASS_SEARCH_JSON_CLOB'])
        
        for meet in meet_time:
            if meet['SSRMEET_MTYP_CODE'] == 'Lecture':
                lec = f"Lecture: {''.join(value for key, value in meet.items() if key.endswith('_DAY') and value is not None)} {meet['SSRMEET_BEGIN_TIME']+'-'+meet['SSRMEET_END_TIME'] if meet['SSRMEET_BEGIN_TIME'] else ''} {meet['SSRMEET_BLDG_CODE'] if meet['SSRMEET_BLDG_CODE'] else ''} {meet['SSRMEET_ROOM_CODE'] if meet['SSRMEET_ROOM_CODE'] else ''}"
            elif meet['SSRMEET_MTYP_CODE'] == 'Laboratory':
                lab = f"Lab: {''.join(value for key, value in meet.items() if key.endswith('_DAY') and value is not None)} {meet['SSRMEET_BEGIN_TIME']+'-'+meet['SSRMEET_END_TIME'] if meet['SSRMEET_BEGIN_TIME'] else ''} {meet['SSRMEET_BLDG_CODE'] if meet['SSRMEET_BLDG_CODE'] else ''} {meet['SSRMEET_ROOM_CODE'] if meet['SSRMEET_ROOM_CODE'] else ''}"
        
        fields.append((f"Section: {class_['SWV_CLASS_SEARCH_SECTION']} ({class_['Availability']})", f"Instructor: {' and '.join([x['NAME'] for x in instructor])}\n{lec if lec else ''}\n{lab if lab else ''}"))
        selects.append(SelectOption(label=f"{class_['SWV_CLASS_SEARCH_SUBJECT']} {class_['SWV_CLASS_SEARCH_COURSE']}-{class_['SWV_CLASS_SEARCH_SECTION']} {' and '.join([x['NAME'] for x in instructor])} ({class_['Availability']})", value=f"('{class_['SWV_CLASS_SEARCH_TERM']}','{class_['SWV_CLASS_SEARCH_CRN']}')"))

    term_object=terms_object[terms_list[term]]
    classes=term_object.search_by_instructor(instructor)
    fields=[]
    selects=[]

    tasks = [process_class(class_, term_object) for class_ in classes]
    await asyncio.gather(*tasks)


    embeds=build_embed(interaction, fields, f"Search results for {instructor}", "", term, field_per_embed=9)
    selects=build_select_from_embed(selects, embeds)
    my_selects=[]
    for select in selects:
        my_selects.append(MySelect(options=select, placeholder="Select section", callback=alert_setup, callback_arg=(interaction)))

    embed_iterator = itertools.cycle(embeds)
    select_iterator = itertools.cycle(my_selects)
    if len(embeds)==1:
        buttons=[]
    else:
        buttons=[MyButton(style=ButtonStyle.green, label="Next page", callback=switch_embed, callback_arg=interaction)]
    view=MyView(components=buttons+[next(select_iterator)])
    interaction.extras['embed_iterator']=embed_iterator
    interaction.extras['select_iterator']=select_iterator

    await interaction.followup.send(embed=next(embed_iterator), view=view)
@search_by_instructor.autocomplete('term')
async def term_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    terms = list(terms_list.keys())
    return [
        app_commands.Choice(name=term, value=term)
        for term in terms if current.lower() in term.lower()
    ]

@search_by_instructor.autocomplete('instructor')
async def instructor_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    term=interaction.data['options'][0]['value']
    term_code=terms_list[term]
    term=terms_object[term_code]
    instructors_list=term.get_all_instructors()
    return [
        app_commands.Choice(name=instructor, value=instructor)
        for instructor in instructors_list if current.lower() in instructor.lower()
    ]

@tree.command(name='search_by_crn')
async def search_by_crn(interaction: discord.Interaction, term: str, crn: str):
    term_object=terms_object[terms_list[term]]
    class_=term_object.search_by_crn(crn)
    embed=discord.Embed(title=f"Search results for {crn}", color=discord.Color.green())
    instructor=json.loads(class_['SWV_CLASS_SEARCH_INSTRCTR_JSON']) if class_['SWV_CLASS_SEARCH_INSTRCTR_JSON'] else [{'NAME' : "None"}]
    seats= await term_object.get_availability(crn)
    class_['Availability']=f"{seats['Available']}/{seats['Capacity']}"
    lec=None
    lab=None
    meet_time=json.loads(class_['SWV_CLASS_SEARCH_JSON_CLOB'])

    for meet in meet_time:
        if meet['SSRMEET_MTYP_CODE']=='Lecture':
            lec=f"Lecture: {''.join(value for key, value in meet.items() if key.endswith('_DAY') and value is not None)} {meet['SSRMEET_BEGIN_TIME']+'-'+meet['SSRMEET_END_TIME'] if meet['SSRMEET_BEGIN_TIME'] else ''} {meet['SSRMEET_BLDG_CODE'] if meet['SSRMEET_BLDG_CODE'] else ''} {meet['SSRMEET_ROOM_CODE'] if meet['SSRMEET_ROOM_CODE'] else ''}"
        elif meet['SSRMEET_MTYP_CODE']=='Laboratory':
            lab=f"Lab: {''.join(value for key, value in meet.items() if key.endswith('_DAY') and value is not None)} {meet['SSRMEET_BEGIN_TIME']+'-'+meet['SSRMEET_END_TIME'] if meet['SSRMEET_BEGIN_TIME'] else ''} {meet['SSRMEET_BLDG_CODE'] if meet['SSRMEET_BLDG_CODE'] else ''} {meet['SSRMEET_ROOM_CODE'] if meet['SSRMEET_ROOM_CODE'] else ''}"
    embed.add_field(name=f"{class_['SWV_CLASS_SEARCH_SUBJECT']} {class_['SWV_CLASS_SEARCH_COURSE']}-{class_['SWV_CLASS_SEARCH_SECTION']} ({class_['Availability']})", value=f"Instructor: { ' and '.join([x['NAME'] for x in instructor]) }\n{lec if lec else ''}\n{lab if lab else ''}", inline=True)
    select=[SelectOption(label=f"{class_['SWV_CLASS_SEARCH_SUBJECT']} {class_['SWV_CLASS_SEARCH_COURSE']}-{class_['SWV_CLASS_SEARCH_SECTION']} { ' and '.join([x['NAME'] for x in instructor]) } ({class_['Availability']})", value=f"{class_['SWV_CLASS_SEARCH_TERM']},{class_['SWV_CLASS_SEARCH_CRN']}")]
    select=[MySelect(options=select, placeholder="Select section", callback=alert_setup, callback_arg=(interaction))]
    embed.set_footer(text=term)
    await interaction.response.send_message(embed=embed, view=MyView(components=select))

@search_by_crn.autocomplete('term')
async def term_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    terms = list(terms_list.keys())
    return [
        app_commands.Choice(name=term, value=term)
        for term in terms if current.lower() in term.lower()
    ]

    



client.run("Token")
