import requests
import json


def get_all_terms():
    link = 'https://howdy.tamu.edu/api/all-terms'
    res = requests.get(link)
    if res.status_code != 200:
        raise Exception(f"Failed to fetch term data from {link}")
    try:
        return res.json()
    except:
        raise Exception(f"Failed to parse term data from {link}")

class_list = "https://howdy.tamu.edu/api/course-sections"

# terms_list={
#   "Spring 2024 - Galveston" : "202412",
#   "Spring 2024 - College Station" : "202411",
# }
terms_list = {res['STVTERM_DESC']: res['STVTERM_CODE'] for res in get_all_terms() if ('2025' in res['STVTERM_DESC'])}

class Classes:
  def __init__(self, terms) -> None:
    self.terms=terms_list[terms]
    self.classes = None
    self.refresh_classes()
    self.subject_code=sorted(set([x['SWV_CLASS_SEARCH_SUBJECT_DESC'] for x in self.classes]))
    self.display_name=terms

  def refresh_classes(self):
    response = requests.post(class_list, json={"startRow":0,"endRow":0,"termCode":self.terms,"publicSearch":"Y"})

    if response.status_code != 200:
      raise Exception(f"Failed to fetch class data for term {self.terms}")
    
    self.classes = response.json()
  
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
    return list(set(sorted(instructors)))
     
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

    for classes in self.classes:
      if classes['SWV_CLASS_SEARCH_CRN']==str(crn):
        return classes['STUSEAT_OPEN'] == 'Y'
      
    return False


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




# terms_object={
#     "202412" : Classes('Spring 2024 - Galveston'),
#     "202411" : Classes("Spring 2024 - College Station"),
# }

terms_object={res['STVTERM_CODE']: Classes(res['STVTERM_DESC']) for res in get_all_terms() if ('2025' in res['STVTERM_DESC'])}
