import aiohttp
from bs4 import BeautifulSoup
import requests
import json



class_list = "https://howdy.tamu.edu/api/course-sections"


terms_list={
  "Fall 2024 - Galveston" : "202432",
  "Fall 2024 - College Station" : "202431",
  "Summer 2024 - Galveston" : "202422",
  "Summer 2024 - College Station" : "202421",
}


class Classes:
  def __init__(self, terms) -> None:
    self.terms=terms_list[terms]
    self.classes = requests.post(class_list, json={"startRow":0,"endRow":0,"termCode":terms_list[terms],"publicSearch":"Y"}).json()
    self.subject_code=sorted(set([x['SWV_CLASS_SEARCH_SUBJECT_DESC'] for x in self.classes]))
    self.display_name=terms


  def get_all_classes(self, subject_code):
    return [x for x in self.classes if x['SWV_CLASS_SEARCH_SUBJECT_DESC']==subject_code]

  def get_all_sections(self, subject_code, section):
    return [x for x in self.classes if (x['SWV_CLASS_SEARCH_SUBJECT_DESC']==subject_code and x['SWV_CLASS_SEARCH_COURSE']==section)]

  def get_all_instructors(self):
    instructors=[]
    for class_ in self.classes:
      instructor=json.loads(class_['SWV_CLASS_SEARCH_INSTRCTR_JSON']) if class_['SWV_CLASS_SEARCH_INSTRCTR_JSON'] else [{'NAME' : "None"}]
      for i in instructor:
        instructors.append(i['NAME'])
    return sorted(set(instructors))
     
  def search(self, subject_code, section=None):
    out=[]
    for classes in self.classes:
      if section:
        if classes['SWV_CLASS_SEARCH_SUBJECT_DESC']==subject_code and classes['SWV_CLASS_SEARCH_COURSE']==section:
          # seats, waitlist=self.get_availability(classes['SWV_CLASS_SEARCH_CRN'])
          # classes['Availability']=f"{seats['Available']}/{seats['Capacity']}"
          out.append(classes)
      else:
        if classes['SWV_CLASS_SEARCH_SUBJECT_DESC']==subject_code:
          # seats, waitlist=self.get_availability(classes['SWV_CLASS_SEARCH_CRN'])
          # classes['Availability']=f"{seats['Available']}/{seats['Capacity']}"
          out.append(classes)

    return out

  def search_by_instructor(self, instructor):
    out=[]
    for classes in self.classes:
      instructor_=json.loads(classes['SWV_CLASS_SEARCH_INSTRCTR_JSON']) if classes['SWV_CLASS_SEARCH_INSTRCTR_JSON'] else [{'NAME' : "None"}]
      for i in instructor_:
        if i['NAME']==instructor:
          out.append(classes)
    return out

  def search_by_crn(self, crn):
    for classes in self.classes:
      if classes['SWV_CLASS_SEARCH_CRN']==str(crn):
        return classes

  async def get_availability(self, crn):
    url = f"https://compass-ssb.tamu.edu/pls/PROD/bwykschd.p_disp_detail_sched?term_in={self.terms}&crn_in={crn}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                text = await response.text()
                soup = BeautifulSoup(text, 'html.parser')
                paragraphs = soup.find_all('table')
            else:
                print("Failed to retrieve the webpage. Status code:", response.status)

    a = [p.get_text() for p in paragraphs if 'Remaining' in p.get_text()]
    try:
      a = a[-1].split('\n')
      x = a.index('Seats')
    except:
      return {'Capacity': -1, 'Taken': -1, 'Available': -1}

    return {'Capacity': a[x+1], 'Taken': a[x+2], 'Available': a[x+3]}
    

  def search_by_crn(self, crn):
    for classes in self.classes:
      if classes['SWV_CLASS_SEARCH_CRN']==str(crn):
        return classes
      
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

    for name, term, CRN, comp, value in tasks:
        task = {"name": name, "terms": term, "CRN": CRN, "comp": comp, "value": value, "completed": False}
        # Check if task already exists
        for existing_task in user["tasks"]:
            if existing_task["terms"] == term and existing_task["CRN"] == CRN and existing_task["comp"] == comp and existing_task["value"] == value:
                if existing_task['completed']:
                    replace_task(user_id, existing_task, task)
                    return True
                else:
                    return False
        # is_duplicate = any(existing_task["terms"] == term and existing_task["CRN"] == CRN and 
                          #  existing_task["comp"] == comp and existing_task["value"] == value
                          #  for existing_task in user["tasks"])

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



terms_object={
    "202432" : Classes('Fall 2024 - Galveston'),
    "202431" : Classes("Fall 2024 - College Station"), 
    "202422" : Classes('Summer 2024 - Galveston'),
    "202421" : Classes("Summer 2024 - College Station")
}

