import json


async def check_permission(new, old):
    if old.user != new.user:
        command = old.client.COMMANDS[new.command.name]
        await new.response.send_message(content=f"This is not your search! Run the command </{command.name}:{command.id}>", ephemeral=True)
        return False
    return True

def recursive_parse_json(json_str):
    try:
        # Try parsing the string as JSON
        parsed = json.loads(json_str)
        
        # If it's a dictionary, recursively parse its values
        if isinstance(parsed, dict):
            return {k: recursive_parse_json(v) for k, v in parsed.items()}
        # If it's a list, recursively parse each element
        elif isinstance(parsed, list):
            return [recursive_parse_json(element) for element in parsed]
        else:
            return parsed
    except (json.JSONDecodeError, TypeError):
        # If parsing fails, return the original string
        return json_str
    

def parse_meeting_info(out):
    out = recursive_parse_json(out)
    meeting_parts = {}
    for meeting in out:
        days = [meeting[day] for day in [
            "SSRMEET_SUN_DAY", "SSRMEET_MON_DAY", "SSRMEET_TUE_DAY",
            "SSRMEET_WED_DAY", "SSRMEET_THU_DAY", "SSRMEET_FRI_DAY",
            "SSRMEET_SAT_DAY"
        ] if meeting.get(day)]
        day_str = "".join(days) if days else "N/A"
        time_str = f"{meeting.get('SSRMEET_BEGIN_TIME', 'N/A')} - {meeting.get('SSRMEET_END_TIME', 'N/A')}"
        location_str = f"{meeting.get('SSRMEET_BLDG_CODE', 'N/A')} {meeting.get('SSRMEET_ROOM_CODE', 'N/A')}"
        mtyp = meeting.get("SSRMEET_MTYP_CODE", "N/A")
        meeting_parts[mtyp]=(f"{mtyp}: {day_str} {time_str} at {location_str}")
    
    return meeting_parts

def parse_prof(str: str):
    out = []
    str = recursive_parse_json(str)
    for prof in str:
        try:
            name = prof['NAME'].rstrip(' (P)')
            if prof['HAS_CV'] == 'Y':
                cv = f'https://compass-ssb.tamu.edu/pls/PROD/bwykfupd.p_showdoc?doctype_in=CV&pidm_in={prof["MORE"]}'
            else:
                cv = None
            out.append((name, cv))
        except KeyError:
            out.append(('Not assigned', None))
    return out