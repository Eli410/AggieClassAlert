import discord
import time
from task_db import get_task, replace_task
from discord.ext import tasks
from channels import *

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = int(time.time())
        self.tree = discord.app_commands.CommandTree(self)
        self.LOG_CHANNEL = None
        
    async def setup_hook(self) -> None:
        # start the task to run in the background
        # self.my_background_task.start()
        pass

    async def on_ready(self):
        self.LOG_CHANNEL = self.get_channel(LOG_CHANNEL)
        self.COMMANDS = await self.tree.fetch_commands()
        self.COMMANDS = {command.name: command for command in self.COMMANDS}

        await self.tree.sync()
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')


    async def check_availability_and_notify(self, user, alert, term_obj, task, alert_channel):
        name, terms, CRN, comp, value, completed = alert['name'], alert['terms'], alert['CRN'], alert['comp'], alert['value'], alert['completed']
        if completed:
            return 0

        isOpen = await term_obj.get_availability(CRN)

        if isOpen:
            embed=discord.Embed(title=f"Alert triggered", description=f"{name}", color=discord.Color.green())
            embed.set_author(name=user.name, icon_url=user.display_avatar.url)
            embed.set_footer(text=term_obj.display_name)

            await alert_channel.send(f'<@{user.id}> Here is your alert: ', embed=embed)
                
            alert['completed'] = True
            replace_task(task['user_id'], alert, alert)  # Update the task as completed

            return 1
        
        return 0
    
    # @tasks.loop(seconds=60)  # task runs every 60 seconds
    # async def my_background_task(self):
    #     try:
    #         start = time.time()
    #         await self.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name='Checking sections...'))
    #         tasks_all = get_task("ALL")
    #         alert_channel = self.get_channel(1229476856995254342)
    #         for obj in terms_object.values():
    #             obj.refresh_classes()

    #         alert_tasks = []
    #         for task in tasks_all:
    #             user = self.get_user(task['user_id'])
    #             for alert in task['tasks']:
    #                 if not alert['completed']:
    #                     term_obj = terms_object[alert['terms']]
    #                     alert_tasks.append(self.check_availability_and_notify(user, alert, term_obj, task, alert_channel))

    #         result = await asyncio.gather(*alert_tasks)
    #         elapsed = time.time() - start
    #         game = discord.CustomActivity(
    #             name=f'Just checked {len(alert_tasks)} sections and notified {sum(result)} users in {elapsed:.2f} seconds'
    #         )
    #         await self.change_presence(status=discord.Status.idle, activity=game)
    #     except Exception as e:
    #         print(f"Error in my_background_task: {e}")
    #         os.execv(sys.executable, [sys.executable] + sys.argv)
    

    # @my_background_task.before_loop
    # async def before_my_task(self):
    #     await self.wait_until_ready()  # wait until the bot logs in
