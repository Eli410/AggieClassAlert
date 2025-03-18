from .my_alerts import my_alerts
from .status import status
from .sync import sync
from .search_by_crn import search_by_crn
from .search_by_instructor import search_by_instructor
from .search import search

COMMANDS = [my_alerts, status, search_by_crn, sync, search_by_instructor, search]
