# AggieClassAlert
A Discord bot that alerts the user when a class section opens up

Invite: https://discord.gg/mwpYwbbnhV

You interface with the bot through slash commands, buttons and drop-down menus, here are the commands that the bot currently has:

1. `/my_alerts`: This command does not take any argument, it displays the alerts you currently have setup, whether it is completed or ongoing. This is also where you edit or delete an alert

2. `/search`: This is the main search command for you to find a section and setup an alert, it takes 3 **required** arguments: 
 - `term`: The term of the classes you are looking for. e.g. (Fall 2024 - College Station)
 - `subject`: The 4 letter code or major names that your class is in. e.g. (CSCE - Computer Sci & Engr)
 - `course_number`: The course number for the class you are looking for. e.g. (221 - DATA STRUC & ALGORITHMS)

3. `/search_by_instructor`: This is another way to search for a section of a class, this time by instructor, it takes 2 **required** arguments:
 - `term`: same as above
 - `instructor`: The name of the instructor you would like to search for.

4. `/status`: This just pings the bot.

Once you searched for a class, an embed with all the sections will show up, you can use the button to toggle between full and available sections, the use the drop-down menu to select a spacific section, the embed should reflect your selection by listing only that section, then you can use the drop-down menu again to select the type of alert you would like to setup.

## Notes:
1. All the arguments have auto-fill, to ensure you entered the correct arguments, start typing out the argument and discord will automatically return the search result for the closest result, the use **TAB** key or click on the argument.

2. The bot will notify you in the #alert channel in the discord server
