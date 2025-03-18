ALL_TERMS_URL = 'https://howdy.tamu.edu/api/all-terms'
CLASS_LIST_URL = 'https://howdy.tamu.edu/api/course-sections'

import requests 
import aiohttp
import asyncio
import json
import datetime
from CustomHelpers import recursive_parse_json

class Howdy_API:
    def __init__(self):
        self.terms = self.get_all_terms()
        self.term_codes_to_desc = {term['STVTERM_CODE']: term['STVTERM_DESC'] for term in self.terms}
        self.classes = {term['STVTERM_CODE']: self.get_classes(term['STVTERM_CODE']) for term in self.terms}
        print(f"Howdy API initialized, loaded the following terms: \n{'\n'.join([f'{term["STVTERM_DESC"]} ({term["STVTERM_CODE"]})' for term in self.terms])}\n")

    def get_all_terms(current=True):
        res = requests.get(ALL_TERMS_URL)
        if res.status_code != 200:
            raise Exception(f"Failed to fetch term data from {ALL_TERMS_URL}")
        try:
            if current:
                current_year = (datetime.datetime.now().year)
                return [term for term in res.json() if str(current_year) in term['STVTERM_CODE'] or str(current_year+1) in term['STVTERM_CODE']]
            else:
                return res.json()
        except:
            raise Exception(f"Failed to parse term data from {ALL_TERMS_URL}")



    def get_classes(self, term_code):
        res = requests.post(CLASS_LIST_URL, json={"termCode":term_code})
        if res.status_code != 200:
            raise Exception(f"Failed to fetch class data from {CLASS_LIST_URL}")
        try:
            return res.json()
        except:
            raise Exception(f"Failed to parse class data from {CLASS_LIST_URL}")

    def get_term_general_info(self, term_code):
        class_list = set()
        for c in self.classes[term_code]:
            class_list.add((c['SWV_CLASS_SEARCH_SUBJECT'], c['SWV_CLASS_SEARCH_COURSE']))
        return sorted(class_list, key=lambda x: (x[0], x[1]))
    

    def filter_by_instructor(self, term_code, instructor):
        CV = None
        out = []
        for c in self.classes[term_code]:
            if c['SWV_CLASS_SEARCH_INSTRCTR_JSON'] is not None:
                instructors = recursive_parse_json(c['SWV_CLASS_SEARCH_INSTRCTR_JSON'])
                for i in instructors:
                    if instructor == i['NAME']:
                        out.append(c)
                        if i['HAS_CV'] == 'Y':
                            CV = f'https://compass-ssb.tamu.edu/pls/PROD/bwykfupd.p_showdoc?doctype_in=CV&pidm_in={i['MORE']}'
                        break
        # grades = self.get_grade_distribution(c['SWV_CLASS_SEARCH_SUBJECT'], c['SWV_CLASS_SEARCH_COURSE'], instructor)
        # print(grades)
        return out, CV

    def filter_by_course(self, term_code, course):
        major, number = course.split(' ')
        out = []
        for c in self.classes[term_code]:
            if c['SWV_CLASS_SEARCH_SUBJECT'] == major and c['SWV_CLASS_SEARCH_COURSE'] == number:
                out.append(c)

        return sorted(out, key=lambda x: x['STUSEAT_OPEN'] == 'Y')
    
    def get_all_instructors(self, term_code):
        out = set()
        for c in self.classes[term_code]:
            if c['SWV_CLASS_SEARCH_INSTRCTR_JSON'] is not None:
                instructors = recursive_parse_json(c['SWV_CLASS_SEARCH_INSTRCTR_JSON'])
                for i in instructors:
                    out.add(i['NAME'])
        return sorted(out)

    async def get_section_details(self, term_code: str, crn: str) -> dict:
        error = []

        links = {
            "Section attributes"             : 'https://howdy.tamu.edu/api/section-attributes',
            "Section prereqs"                : 'https://howdy.tamu.edu/api/section-prereqs',
            "Bookstore links"                : 'https://howdy.tamu.edu/api/section-bookstore-links',
            "Meeting times with profs"       : 'https://howdy.tamu.edu/api/section-meeting-times-with-profs',
            "Section program restrictions"   : 'https://howdy.tamu.edu/api/section-program-restrictions',
            "Section college restrictions"   : 'https://howdy.tamu.edu/api/section-college-restrictions',
            "Level restrictions"             : 'https://howdy.tamu.edu/api/section-level-restrictions',
            "Degree restrictions"            : 'https://howdy.tamu.edu/api/section-degree-restrictions',
            "Major restrictions"             : 'https://howdy.tamu.edu/api/section-major-restrictions',
            "Minor restrictions"             : 'https://howdy.tamu.edu/api/section-minor-restrictions',
            "Concentrations restrictions"    : 'https://howdy.tamu.edu/api/section-concentrations-restrictions',
            "Field of study restrictions"    : 'https://howdy.tamu.edu/api/section-field-of-study-restrictions',
            "Department restrictions"        : 'https://howdy.tamu.edu/api/section-department-restrictions',
            "Cohort restrictions"            : 'https://howdy.tamu.edu/api/section-cohort-restrictions',
            "Student attribute restrictions" : 'https://howdy.tamu.edu/api/section-student-attribute-restrictions',
            "Classification restrictions"    : 'https://howdy.tamu.edu/api/section-classifications-restrictions',
            "Campus restrictions"            : 'https://howdy.tamu.edu/api/section-campus-restrictions',
        }

        general_info_link = f"https://howdy.tamu.edu/api/course-section-details?term={term_code}&subject=&course=&crn={crn}"
        # Fetch general info
            
        async def fetch_all():
            out = {}
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(general_info_link) as response:
                        # Howdy still returns 200 for some reason if the response is invalid kms
                        general_info = await response.json()
                        if not general_info:
                            error.append(f"Failed to fetch general info from {general_info_link}")
                            return {}
                        else:
                            general_info['COURSE_NAME'] = f"{general_info['DEPT']} {general_info['COURSE_NUMBER']}"
                        out.update(general_info)
                except Exception as e:
                    error.append(f"Exception when fetching general info: {e}")
                    out = {}
                    
            async with aiohttp.ClientSession() as session:

                # Define async tasks for each link
                async def fetch_data(key, link):
                    try:
                        async with session.post(
                            link,
                            json={
                                "term": term_code,
                                "subject": None,
                                "course": None,
                                "crn": crn,
                            },
                        ) as res:
                            if res.status != 200:
                                error.append(f"Failed to fetch {key} data from {link}")
                                data = {}
                            else:
                                text = await res.text()
                                data = recursive_parse_json(text)
                            out["OTHER_ATTRIBUTES"][key] = data
                    except Exception as exc:
                        error.append(f"{key} generated an exception: {exc}")
                        out["OTHER_ATTRIBUTES"][key] = {}

                is_valid_section = len(out) > 0

                if is_valid_section:
                    out['OTHER_ATTRIBUTES'] = {}
                    tasks = [fetch_data(key, link) for key, link in links.items()]
                    await asyncio.gather(*tasks)
                    out['SYLLABUS'] = f"https://compass-ssb.tamu.edu/pls/PROD/bwykfupd.p_showdoc?doctype_in=SY&crn_in={crn}&termcode_in={term_code}"
                    if out["OTHER_ATTRIBUTES"]['Meeting times with profs'] and out['OTHER_ATTRIBUTES']['Meeting times with profs']['SWV_CLASS_SEARCH_INSTRCTR_JSON']:
                        instructor_info = out["OTHER_ATTRIBUTES"]['Meeting times with profs']['SWV_CLASS_SEARCH_INSTRCTR_JSON'][0]
                        out['INSTRUCTOR'] = instructor_info['NAME'].rstrip(' (P)')
                        instructor_info['CV'] = f'https://compass-ssb.tamu.edu/pls/PROD/bwykfupd.p_showdoc?doctype_in=CV&pidm_in={instructor_info['MORE']}'
                    else:
                        out['INSTRUCTOR'] = 'Not assigned'
                    
            return out

        # Run the async fetch_all function in the event loop
        out = await fetch_all()

        out.update(out['OTHER_ATTRIBUTES'])
        del out['OTHER_ATTRIBUTES']
        out.update(out['Meeting times with profs'])
        del out['Meeting times with profs']

        # Parse SWV_CLASS_SEARCH_JSON_CLOB into a readable message
        if "SWV_CLASS_SEARCH_JSON_CLOB" in out and isinstance(out["SWV_CLASS_SEARCH_JSON_CLOB"], list):
            meeting_parts = []
            for meeting in out["SWV_CLASS_SEARCH_JSON_CLOB"]:
                # Compile all day abbreviations that are set
                days = [meeting[day] for day in [
                    "SSRMEET_SUN_DAY", "SSRMEET_MON_DAY", "SSRMEET_TUE_DAY",
                    "SSRMEET_WED_DAY", "SSRMEET_THU_DAY", "SSRMEET_FRI_DAY",
                    "SSRMEET_SAT_DAY"
                ] if meeting.get(day)]
                day_str = "".join(days) if days else "N/A"
                time_str = f"{meeting.get('SSRMEET_BEGIN_TIME', 'N/A')} - {meeting.get('SSRMEET_END_TIME', 'N/A')}"
                location_str = f"{meeting.get('SSRMEET_BLDG_CODE', 'N/A')} {meeting.get('SSRMEET_ROOM_CODE', 'N/A')}"
                mtyp = meeting.get("SSRMEET_MTYP_CODE", "N/A")
                meeting_parts.append(f"{mtyp}: {day_str} {time_str} at {location_str}")
            out["MEETING_MESSAGE"] = "\n".join(meeting_parts)

        out['ERRORS'] = error
            
        return out
    
    def get_availability(self):
        out = {}

        for term in self.terms:
            t = {}
            for c in self.get_classes(term['STVTERM_CODE']):
                t[c['SWV_CLASS_SEARCH_CRN']] = c['STUSEAT_OPEN'] == 'Y'
            
            out[term['STVTERM_CODE']] = t

        return out
    
    def get_grade_distribution(self, dept, number, prof=None):
        url = "https://anex.us/grades/getData/"
        data = {
            "dept": dept,
            "number": number
        }
        response = requests.post(url, data=data)
        print(response.text)
        print(dept, number, prof)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch grade distribution data from {url}")
        
        try:
            classes = response.json()['classes']
        except:
            return []

        if not prof:
            return classes
        else:
            first, last = prof.split(' ')[0], prof.split(' ')[-1]
            out = []
            for c in classes:
                l, f_init = c['prof'].split(' ')[0], c['prof'].split(' ')[1]
                if l.lower() == last.lower() and f_init[0].lower() == first[0].lower():
                    out.append(c)
            return out


HOWDY_API = Howdy_API()

if __name__ == '__main__':
    term = '202511'
    crn = '30835'
    res = HOWDY_API.classes[term]
    with open('example.json', 'w') as f:
        json.dump(res, f, indent=4)
