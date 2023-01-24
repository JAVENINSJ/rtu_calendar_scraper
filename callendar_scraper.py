"""
requests - Used to fetch the calendar HTML and API's
lxml - Used to fetch specific parts of the HTML
os
"""
#!/usr/bin/python
from os import system, name
from datetime import datetime

import requests
from lxml import html
from icalendar import Calendar, Event
from dateutil import tz
import pytz

class CalendarFetcher():
    """Class to handle calendar parsing from RTU website"""
    def __init__(self):
        self.clear()
        self.study_year = None
        self.timeout_seconds = 10

        self.rtu_calendar_url = "https://nodarbibas.rtu.lv"
        self.parsed_data = self.fetch_calendar_html()

        self.clear()
        semesters = self.fetch_semester_values()
        semester_id = self.enter_semester_value(semesters)

        self.clear()
        course_id = self.fetch_course(semester_id)
        self.clear()
        year = self.fetch_year(semester_id, course_id)
        self.clear()
        group_id = self.fetch_group(semester_id, course_id, year)
        self.clear()
        if not self.check_if_calendar_is_published(group_id):
            print("Calendar not yet published. Please try again later...")
            return

        print("Creating file from events...")
        dates = self.get_needed_months(semester_id)
        event_elements = self.get_event_elements(dates, group_id)

        self.generate_ics_file(event_elements)

    def clear(self):
        """Function to clear the command line"""
        # for windows
        if name == 'nt':
            _ = system('cls')

        # for mac and linux(here, os.name is 'posix')
        else:
            _ = system('clear')

    def fetch_calendar_html(self):
        """Function to fetch the html"""
        print(f"Fetching html file from {self.rtu_calendar_url}...")

        response_data = requests.get(
            self.rtu_calendar_url,
            timeout=self.timeout_seconds
        )
        return html.fromstring(response_data.content)

    def input_integer(self, message, min_val:int = None, max_val:int = None):
        """Function to validate user input"""
        while True:
            try:
                user_input = int(input(message))
            except ValueError:
                print("Input is not an integer")
                continue
            else:
                if min_val is not None and user_input < min_val:
                    print("Pick a value from the list")
                    continue
                if max_val is not None and user_input > max_val:
                    print("Pick a value from the list")
                    continue
                return user_input

    def fetch_semester_values(self):
        """Fetch available values for semesters"""
        # Example of the semester choice:
        # <select id="semester-id" class="form-select form-control" required="required">
        #     <option value="18">2022/2023 Pavasara semestris (22/23-P)</option>
        #     <option value="17" selected="selected">2022/2023 Rudens semestris (22/23-R)</option>
        # </select>

        # The xPath of the select element
        query_for_semesters = '//*[@id="semester-id"]/option'

        # The options, which is a list of semester id's
        semester_elements = self.parsed_data.xpath(query_for_semesters)

        semesters = []

        self.study_year = semester_elements[0].text_content()[:4]

        for idx, semester_id in enumerate(semester_elements):
            # Put the values in to a list of dicts, so it's easier to deal with
            semesters.append({
                "name": semester_id.text_content(),
                "id": semester_id.get("value"),
                "choice": idx
            })

        return semesters

    def enter_semester_value(self, semesters):
        """Get user input for semester values"""
        max_semester = 0
        for semester in semesters:
            print(f"{semester['choice']+1}) {semester['name']}")
            max_semester = semester['choice']+1
        choice = self.input_integer(
            "Pick a semester: ",
            min_val=1,
            max_val=max_semester
        ) - 1
        return semesters[choice]["id"]

    def fetch_course(self, semester):
        """Function to get the course from semester"""
        head = {
            "Accept":"text/html,*/*"
        }
        body = {
            "semesterId": str(semester)
        }
        print("Fetching faculties...")
        response_data = requests.post(
            f"{self.rtu_calendar_url}/findProgramsBySemesterId",
            headers=head,
            data=body,
            timeout=self.timeout_seconds
        ).json()
        self.clear()

        idx = None

        for idx, faculty in enumerate(response_data):
            if faculty["titleLV"] is not None:
                print(f"{idx + 1}) {faculty['titleLV'].capitalize()}")

        choice = self.input_integer(
            "Pick a faculty: ",
            min_val=1,
            max_val=idx
        ) - 1
        faculty = response_data[choice]["program"]

        self.clear()
        for idx, course in enumerate(faculty):
            if course["titleLV"] is not None:
                print(f"{idx + 1}) {course['titleLV'].capitalize()} ({course['code']})")


        choice = self.input_integer("Pick a course: ") - 1
        return faculty[choice]["programId"]

    def fetch_year(self, semester_id, course_id):
        """Fetch the available year"""
        head = {
            "Accept":"text/html,*/*"
        }
        body = {
            "semesterId": str(semester_id),
            "programId": str(course_id)
        }
        print("Fetching years...")
        response_data = requests.post(
            f"{self.rtu_calendar_url}/findCourseByProgramId",
            headers=head,
            data=body,
            timeout=self.timeout_seconds
        ).json()
        self.clear()
        choice = self.input_integer(
            f"Pick a year {response_data}: ",
            min(response_data),
            max(response_data)
        )
        return choice

    def fetch_group(self, semester_id, course_id, year_id):
        """Fetch group from provided data"""
        head = {
            "Accept":"text/html,*/*",
        }
        body = {
            "semesterId": str(semester_id),
            "programId": str(course_id),
            "courseId": str(year_id)
        }
        print("Fetching groups...")
        response_data = requests.post(
            f"{self.rtu_calendar_url}/findGroupByCourseId",
            headers=head,
            data=body,
            timeout=self.timeout_seconds
        ).json()
        self.clear()

        if response_data[0]["group"] == "0":
            response_data.pop(0)

        groups = []

        for idx, group in enumerate(response_data):
            print(f"{idx + 1}) {group['group']}")
            groups.append({
                "group_id": group["semesterProgramId"],
                "value": group["group"]
            })

        choice = self.input_integer("Pick a group: ") - 1

        return response_data[choice]["semesterProgramId"]

    def check_if_calendar_is_published(self, group_id):
        """Function to call API to check if calendar is published"""
        head = {
            "Accept":"text/html,*/*",
        }
        body = {
            "semesterProgramId": str(group_id)
        }
        response_data = requests.post(
            f"{self.rtu_calendar_url}/isSemesterProgramPublished",
            headers=head,
            data=body,
            timeout=self.timeout_seconds
        ).json()

        return response_data

    def get_needed_months(self, semester_id):
        """Function to get all of the required dates"""
        months = {
            0: range(1, 7),
            1: [9, 10, 11, 12, 1]
        }
        dates = []
        for month in months[int(semester_id) % 2]:
            date = {
                "m": month
            }
            if month < 9:
                date["y"] = int(self.study_year)+1
            else:
                date["y"] = int(self.study_year)
            dates.append(date)
        return dates

    def get_event_elements(self, dates, group_id):
        """Function to get all of the event elements"""
        elements = []
        for date in dates:
            head = {
                "Accept":"text/html,*/*",
            }
            body = {
                "semesterProgramId": str(group_id),
                "year": str(date["y"]),
                "month": str(date["m"])
            }
            response_data = requests.post(
                f"{self.rtu_calendar_url}/getSemesterProgEventList",
                headers=head,
                data=body,
                timeout=self.timeout_seconds
            ).json()
            elements.extend(response_data)
        return elements

    def generate_ics_file(self, events):
        """Function to generate the ics file"""
        calendar = Calendar()
        idx = None
        for idx, calendar_event in enumerate(events):
            event = Event()
            event.add(
                "summary",
                f"{calendar_event['eventTempName']} ({calendar_event['roomInfoText']})"
            )

            timestamp = int(calendar_event["eventDate"])/1000
            date_utc = datetime.utcfromtimestamp(timestamp)
            to_tz = tz.gettz("Riga")
            date_utc = date_utc.replace(tzinfo=tz.tzutc())
            date_riga = date_utc.astimezone(to_tz)
            date = date_riga.strftime("%Y-%m-%d").split("-")
            start_date = datetime(
                int(date[0]),
                int(date[1]),
                int(date[2]),
                int(calendar_event['customStart']['hour']),
                int(calendar_event['customStart']['minute']),
                tzinfo=pytz.timezone("Europe/Riga")
            )
            end_date = datetime(
                int(date[0]),
                int(date[1]),
                int(date[2]),
                int(calendar_event['customEnd']['hour']),
                int(calendar_event['customEnd']['minute']),
                tzinfo=pytz.timezone("Europe/Riga")
            )
            event.add("dtstart", start_date)
            event.add("dtend", end_date)
            calendar.add_component(event)


        with open("calendar_file.ics", "wb") as write_file:
            write_file.write(calendar.to_ical())
            print(f"In total {idx+1} events mapped. File calendar_file.ics created.")
            print("Exiting...")

if __name__ == "__main__":
    instance = CalendarFetcher()
