import json

def get_task(user_id):
    try:
      with open('tasks.json', 'r') as file:
        data = json.load(file)
    except FileNotFoundError:
        data = []

    if user_id == "ALL":
      return data
    
    user = next((item for item in data if item['user_id'] == user_id), None)

    if user is None:
        user = {"user_id": user_id, "tasks": []}
        data.append(user)
        with open('tasks.json', 'w') as file:
            json.dump(data, file, indent=4)
    else:
        return user['tasks']


def write_tasks(user_id, tasks):
    try:
        with open('tasks.json', 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        data = []

    user = next((item for item in data if item['user_id'] == user_id), None)

    if user is None:
        user = {"user_id": user_id, "tasks": []}
        data.append(user)

    for name, term, CRN in tasks:
        task = {"name": name, "terms": term, "CRN": CRN, "completed": False}
        # Check if task already exists
        for existing_task in user["tasks"]:
            if existing_task["terms"] == term and existing_task["CRN"] == CRN:
                if existing_task['completed']:
                    replace_task(user_id, existing_task, task)
                    return True
                else:
                    return False

        user["tasks"].append(task)
        
        

    with open('tasks.json', 'w') as file:
        json.dump(data, file, indent=4)
    
    return True

def replace_task(user_id, old_task, new_task=None):
    try:
        with open('tasks.json', 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        data = []

    user_tasks = next((item for item in data if item['user_id'] == user_id), None)

    if user_tasks is not None:
        for i, task in enumerate(user_tasks['tasks']):
            if task['name'] == old_task['name']:
                if new_task is not None:
                    user_tasks['tasks'][i] = new_task
                else:
                    del user_tasks['tasks'][i]
                break

        with open('tasks.json', 'w') as file:
            json.dump(data, file, indent=4)   
