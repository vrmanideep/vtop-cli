import time
import os
import re
import sys
import getpass
import asyncio
import httpx
import pwinput
from datetime import datetime as dt
from typing import List, Dict, Any, Tuple
from bs4 import BeautifulSoup
from vitap_vtop_client.client import VtopClient

PEACH = '\033[38;2;245;231;158m'

def parse_date(raw: str, default_year: int = None):
    """
    Accepts:
      dd-mm-yy, dd-mm-yyyy, dd-mm (assumes current/default year)
      dd/mm/yy, dd.mm.yy, dd mm yy
      dd-mon-yy, dd-month-yyyy
    Returns a datetime object.
    """
    from datetime import datetime as dt_obj
    import re

    if default_year is None:
        default_year = dt_obj.now().year

    raw = raw.strip().lower()
    raw = re.sub(r'[-/.\s]+', ' ', raw)
    parts = raw.split()

    if len(parts) == 2:
        # dd-mm only — inject default year
        parts.append(str(default_year))

    if len(parts) != 3:
        raise ValueError(f"Cannot parse: '{raw}'. Use dd-mm, dd-mm-yy, or dd-mm-yyyy")

    day_str, month_str, year_str = parts

    # --- Day ---
    try:
        day = int(day_str)
    except ValueError:
        raise ValueError(f"Invalid day: '{day_str}'")

    # --- Month ---
    month_map = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12
    }

    if month_str.isdigit():
        month = int(month_str)
    elif month_str in month_map:
        month = month_map[month_str]
    else:
        raise ValueError(f"Invalid month: '{month_str}'")

    # --- Year ---
    year = int(year_str)
    if year < 100:
        year += 2000

    return dt_obj(year, month, day)


def to_vtop_date(raw: str) -> str:
    return parse_date(raw).strftime("%d-%b-%Y")


def to_display_date(raw: str) -> str:
    return parse_date(raw).strftime("%d-%b-%Y")

def to_bunk_date(raw: str) -> str:
    """
    Parses user input and returns bunk simulator format: 3-3 (DD-MM)
    Used internally by simulate_multi_day_bunk.
    """
    d = parse_date(raw)
    return f"{d.day}-{d.month}"

def get_cred(file_path="credentials.txt"):
    """
    Reads username from line 1 and password from line 2.
    If the file is missing or invalid, prompts the user to create it interactively.
    """
    # 1. Try to read existing credentials quietly
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            
            # If the file exists and is perfectly valid, return them instantly
            if len(lines) >= 2:
                return lines[0], lines[1]
            else:
                print(f"\n   [!] {file_path} is corrupted (needs 2 lines). Let's fix it.")

    # 2. First-Time Setup Wizard
    print("\n   =======================================")
    print("   🚀 FIRST TIME SETUP: VTOP CLI")
    print("   =======================================")
    print(f"   Let's set up your {file_path} file securely.\n")
    
    while True:
        username = input("   👉 Enter Registration Number (e.g., 21BCExxxx): ").strip().upper()
        
        # --- THE MAGIC HAPPENS HERE ---
        # This replaces getpass and shows asterisks as they type!
        password = pwinput.pwinput(prompt="   👉 Enter VTOP Password: ", mask="*").strip()
        
        if not username or not password:
            print("   [!] Fields cannot be empty. Try again.\n")
            continue

        print("\n   --- Verify Your Details ---")
        print(f"   Registration No: {username}")
        print(f"   Password:        {'*' * len(password)}")
        
        confirm = input("\n   Save these credentials and login? (y/n): ").strip().lower()
        
        if confirm == 'y':
            with open(file_path, "w") as f:
                f.write(f"{username}\n{password}\n")
            print(f"   [✓] {file_path} created successfully!\n")
            return username, password
        else:
            print("   [!] Setup cancelled. Let's try typing that again.\n")

# Alias for compatibility
get_credentials = get_cred

# Global Creds
a, password = get_cred("credentials.txt")

#  SSL BYPASS
_original_init = httpx.AsyncClient.__init__
def _patched_init(self, *args, **kwargs):
    kwargs['verify'] = False
    _original_init(self, *args, **kwargs)
httpx.AsyncClient.__init__ = _patched_init

async def vtopClientLogin(client: VtopClient) -> bool:
    try:
        await client._perform_login_sequence()
        return True
    except Exception as e:
        print(f"Login Failed: {e}")
        return False

async def fetchTimetable(client, semester_id: str) -> dict:
    import time
    import asyncio
    from bs4 import BeautifulSoup
    from collections import defaultdict
    from colorama import Fore

    print(f"   [.] Fetching and parsing Timetable Grid...")
    
    if not getattr(client, "_logged_in_student", None):
        print(f"   {Fore.RED}[!] No active session found. Please login again.")
        return {}
        
    token = client._logged_in_student.post_login_csrf_token
    reg_no = client.username
    
    headers = {
        "X-Requested-With": "XMLHttpRequest", 
        "Referer": "https://vtop.vitap.ac.in/vtop/content",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    try:
        # --- STEP 1: The Primer Request (Navigate to the menu page) ---
        menu_url = "https://vtop.vitap.ac.in/vtop/academics/common/StudentTimeTable"
        menu_payload = {
            "authorizedID": reg_no,
            "_csrf": token
        }
        await client._client.post(menu_url, data=menu_payload, headers=headers)
        
        # Add a tiny delay to ensure VTOP's backend finishes processing the state change
        await asyncio.sleep(0.2)

        # --- STEP 2: The Data Request (Fetch the actual grid) ---
        data_url = "https://vtop.vitap.ac.in/vtop/processViewTimeTable"
        data_payload = {
            "semesterSubId": semester_id,
            "authorizedID": reg_no,
            "_csrf": token,
            "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        }
        
        response = await client._client.post(data_url, data=data_payload, headers=headers)
        
        if "vtopLoginForm" in response.text or "not authorized" in response.text.lower():
            print(f"   {Fore.RED}[!] VTOP rejected the request (Session Expired or Invalid Semester).")
            return {}
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        tables = soup.find_all('table')
        if len(tables) < 2:
            print(f"   {Fore.RED}[!] Timetable grid is missing from the page. (Found {len(tables)} tables)")
            return {}

        classname_code = {}
        faculty_code = {}
        course_to_class_nbr = {}
        course_to_slot_venue = {}

        # --- FIRST PASS: Extract course names, codes, and faculty from Table 1 ---
        for row in tables[0].find_all('tr'):
            cells = row.find_all('td')
            if len(cells) > 8:
                class_nbr = cells[6].get_text(strip=True)
                cname = cells[2].get_text(strip=True)

                tep = [k.strip() for k in cname.split(" - ") if k.strip()]
                if len(tep) > 1:
                    code = tep[0]
                    name_parts = " - ".join(tep[1:])
                    name = name_parts.split("(")[0].strip()

                    if code not in classname_code:
                        classname_code[code] = name

                    course_type = "UNK"
                    if "( Embedded Theory )" in cname: course_type = "ETH"
                    elif "( Embedded Lab )" in cname: course_type = "ELA"
                    elif "( Theory Only )" in cname: course_type = "TH"
                    elif "( Project )" in cname: course_type = "PJT"

                    if class_nbr:
                        course_key = f"{code}_{course_type}"
                        course_to_class_nbr[course_key] = class_nbr

                        if len(cells) > 7:
                            paras = cells[7].find_all('p')
                            if len(paras) >= 2:
                                slot_text = paras[0].get_text(strip=True).replace("-", "").strip()
                                venue_text = paras[1].get_text(strip=True)
                                if slot_text and venue_text:
                                    course_to_slot_venue[course_key] = (slot_text, venue_text)

                faculty_info = cells[8].get_text(strip=True)
                if faculty_info and faculty_info != "Project" and class_nbr:
                    faculty_name = faculty_info.split(" - ")[0].strip()
                    if faculty_name:
                        faculty_code[class_nbr] = faculty_name

        # --- SECOND PASS: Extract grid timings and slots from Table 2 ---
        raw_slots = []
        timings_temp = []
        count_for_offset = 0
        day = ""

        for row in tables[1].find_all('tr'):
            cells = row.find_all('td')
            if len(cells) > 6:
                if count_for_offset % 2 == 0:
                    day = cells[0].get_text(strip=True)
                    cells = cells[1:]  # Shift cells left

                for index, val_td in enumerate(cells):
                    val = val_td.get_text(strip=True)
                    
                    # 0 and 1 extract theory timings
                    if count_for_offset == 0:
                        timings_temp.append({"serial": index, "course_type": "ETH", "start_time": val, "end_time": ""})
                    elif count_for_offset == 1:
                        if index < len(timings_temp):
                            timings_temp[index]["end_time"] = val
                    
                    # 2 and 3 extract lab timings
                    elif count_for_offset == 2:
                        timings_temp.append({"serial": index, "course_type": "ELA", "start_time": val, "end_time": ""})
                    elif count_for_offset == 3:
                        # Offset by 22 because 0-21 are theory slots in VTOP's array
                        if (22 + index) < len(timings_temp):
                            timings_temp[22 + index]["end_time"] = val
                    
                    # Extract the actual class blocks
                    elif count_for_offset > 3:
                        if len(val) > 5 and index != 0:
                            parts = [p.strip() for p in val.split("-") if p.strip()]
                            if len(parts) > 2:
                                raw_parts = [p.strip() for p in val.split("-")]
                                slot_name = raw_parts[0] if len(raw_parts) > 0 else ""
                                course_code = raw_parts[1] if len(raw_parts) > 1 else ""
                                course_type = raw_parts[2] if len(raw_parts) > 2 else ""
                                room_no = raw_parts[3] if len(raw_parts) > 3 else ""
                                block = " ".join(raw_parts[4:]) if len(raw_parts) > 4 else ""

                                # Resolve Name
                                course_key = f"{course_code}_{course_type}"
                                found_name = classname_code.get(course_code, "")
                                
                                raw_slots.append({
                                    "serial": index,
                                    "day": day,
                                    "slot": slot_name,
                                    "course_code": course_code,
                                    "course_type": course_type,
                                    "room_no": room_no,
                                    "block": block,
                                    "start_time": "",
                                    "end_time": "",
                                    "name": found_name,
                                    "class_nbr": course_to_class_nbr.get(course_key, "")
                                })
            count_for_offset += 1

        # --- MAP TIMINGS TO SLOTS ---
        for slot in raw_slots:
            for t in timings_temp:
                if t["serial"] == slot["serial"] and (t["course_type"] == slot["course_type"] or slot["course_type"] in t["course_type"]):
                    slot["start_time"] = t["start_time"]
                    slot["end_time"] = t["end_time"]
                    break

        # --- GROUP CONSECUTIVE SLOTS ---
        grouped_slots = defaultdict(lambda: defaultdict(list))
        for slot in raw_slots:
            course_key = f"{slot['course_code']}_{slot['course_type']}"
            grouped_slots[course_key][slot['day']].append(slot)

        weekly_timetable = defaultdict(list)
        day_map = {
            "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday",
            "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday", "SUN": "Sunday"
        }

        for course_key, day_slots in grouped_slots.items():
            for d, slots in day_slots.items():
                if not slots: continue
                
                # Sort by start time
                slots.sort(key=lambda x: x['start_time'])
                
                consecutive_groups = []
                current_group = []

                for slot in slots:
                    if not current_group:
                        current_group.append(slot)
                    else:
                        last_slot = current_group[-1]
                        if (last_slot['end_time'] == slot['start_time'] or last_slot['start_time'] == slot['start_time']) and \
                           last_slot['course_code'] == slot['course_code'] and \
                           last_slot['course_type'] == slot['course_type']:
                            current_group.append(slot)
                        else:
                            consecutive_groups.append(current_group)
                            current_group = [slot]
                
                if current_group:
                    consecutive_groups.append(current_group)

                # Format for the CLI UI
                full_day_name = day_map.get(d, d)
                
                for group in consecutive_groups:
                    first = group[0]
                    last = group[-1]
                    slots_combined = "+".join([s['slot'] for s in group])

                    # Check for better slot/venue info from table 1
                    target_key = f"{first['course_code']}_{first['course_type']}"
                    
                    if target_key in course_to_slot_venue and course_to_slot_venue[target_key][0]:
                        final_slot = course_to_slot_venue[target_key][0]
                        final_venue = course_to_slot_venue[target_key][1]
                    else:
                        final_slot = slots_combined
                        final_venue = f"{first['room_no']}-{first['block'].replace(' ', '-')}"

                    faculty_name = faculty_code.get(first['class_nbr'], "Faculty Not Available")

                    weekly_timetable[full_day_name].append({
                        "time": f"{first['start_time']} - {last['end_time']}",
                        "start_time": first['start_time'], # Used for sorting later
                        "venue": final_venue,
                        "course_code": first['course_code'],
                        "course_type": first['course_type'],
                        "slot": final_slot,
                        "course_name": first['name'],
                        "faculty": faculty_name
                    })

        # Sort each day by start time
        for day in weekly_timetable:
            weekly_timetable[day].sort(key=lambda x: x['start_time'])

        return dict(weekly_timetable)

    except Exception as e:
        print(f"   [!] fetchTimetable Error: {e}")
        return {}

async def get_todays_schedule(client):
    print("\n   [+] Fetching Timetable...")
    try:
        timetable = await client.get_timetable()
        
        # [FIXED] Use dt.now() directly (dt is already the datetime class)
        today_name = dt.now().strftime("%A")
        
        print(f"\n   --- SCHEDULE FOR {today_name.upper()} ---")
        
        if today_name in timetable:
            todays_classes = timetable[today_name]
            if not todays_classes:
                print("   No classes scheduled for today! 🎉")
            else:
                print(f"   {'Time':<15} {'Code':<10} {'Type':<10} {'Venue':<10}")
                print("   " + "-" * 50)
                
                for slot in todays_classes:
                    print(f"   {slot.get('start_time', 'N/A'):<15} {slot.get('course_code', 'N/A'):<10} {slot.get('course_type', 'N/A'):<10} {slot.get('venue', 'N/A'):<10}")
        else:
            print("   No schedule data found or it's the weekend.")
    except Exception as e:
        print(f"   [!] Schedule error: {e}")

async def fetchProfile(client: VtopClient) -> Dict[str, Any]:
    url = "https://vtop.vitap.ac.in/vtop/studentsRecord/StudentProfileAllView"
    
    try:
        token = getattr(client, "csrf_token", "")
        reg_no = getattr(client, "username", getattr(client, "reg_no", a))

        payload = {
            "verifyMenu": "true",
            "authorizedID": reg_no,
            "_csrf": token,
            "nocache": "@(new Date().getTime())"
        }

        response = await client._client.post(url, data=payload, headers={
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://vtop.vitap.ac.in/vtop/content"
        })
        soup = BeautifulSoup(response.text, 'html.parser')
        
        data = {
            "basic": {"name": "-", "regno": "-", "vitemail": "-", "mobile": "-", "program": "-", "school": "-"},
            "proctor": {}
        }
        
        # --- 1. Top Card Labels ---
        labels = soup.find_all('label')
        for i, label in enumerate(labels):
            key = label.get_text(strip=True).upper()
            if i + 1 < len(labels):
                val = labels[i+1].get_text(strip=True)
                if "REGISTER NUMBER" in key: data["basic"]["regno"] = val
                elif "VIT EMAIL" in key and "@vitapstudent.ac.in" in val: data["basic"]["vitemail"] = val
                elif "PROGRAM" in key: data["basic"]["program"] = val
                elif "SCHOOL NAME" in key: data["basic"]["school"] = val

        # --- 2. Name Extraction ---
        name_p = soup.find('p', style=lambda s: s and "font-weight: bold" in s and "text-align: center" in s)
        if name_p: data["basic"]["name"] = name_p.get_text(strip=True)

        # --- 3. Accordion Table Processing ---
        tables = soup.find_all('table')
        for table in tables:
            full_text = table.get_text().lower()
            rows = table.find_all('tr')

            if "faculty id" in full_text:
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) < 2: continue
                    k, v = cols[0].get_text(strip=True).lower(), cols[1].get_text(strip=True)
                    if "faculty id" in k: data["proctor"]["Faculty ID"] = v
                    elif "name" in k: data["proctor"]["Name"] = v
                    elif "email" in k: data["proctor"]["Email"] = v
                    elif "mobile" in k: data["proctor"]["Mobile"] = v
                    elif "cabin" in k: data["proctor"]["Cabin"] = v

            elif "native state" in full_text or "blood group" in full_text:
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) < 2: continue
                    k, v = cols[0].get_text(strip=True).lower(), cols[1].get_text(strip=True)
                    if "mobile" in k: data["basic"]["mobile"] = v

        return data
    except Exception as e:
        print(f"   [!] Profile fetch error: {e}")
        return {}

async def fetchSemesters(client: VtopClient) -> List[Dict[str, str]]:
    print("   ...Scraping semester list...")
    try:
        # 1. Get Token from Dashboard
        dash_res = await client._client.get("vtop/content")
        csrf_match = re.search(r'name="_csrf"\s+value="([a-f0-9-]+)"', dash_res.text)
        token = csrf_match.group(1) if csrf_match else getattr(client, "csrf_token", "")
        client.csrf_token = token 

        # 2. Request Timetable Page
        url = "https://vtop.vitap.ac.in/vtop/academics/common/StudentTimeTable"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://vtop.vitap.ac.in/vtop/content"
        }
        reg_no = getattr(client, "username", getattr(client, "reg_no", a))
        payload = {
            "verifyMenu": "true", "authorizedID": reg_no, "_csrf": token,
            "nocache": "@(new Date().getTime())"
        }

        response = await client._client.post(url, data=payload, headers=headers)
        
        # 3. Parse Options
        pattern = r'<option\s+value="([A-Z0-9]+)"[^>]*>([^<]+)</option>'
        matches = re.findall(pattern, response.text)
        
        semesters = []
        seen = set()
        if matches:
            for sid, sname in matches:
                clean = " ".join(sname.split())
                if sid and "Choose" not in clean and sid not in seen:
                    semesters.append({"name": clean, "id": sid})
                    seen.add(sid)
            return semesters
            
    except Exception as e:
        print(f"   [!] Semester scrape error: {e}")

    return [{"name": "Fallback Semester", "id": "AP2025262"}]

async def fetchMarks(client, semesterId: str) -> dict:
    print(f"   ...Fetching Internal Marks for {semesterId}...")
    url = "https://vtop.vitap.ac.in/vtop/examinations/doStudentMarkView"
    
    try:
        token = getattr(client, "csrf_token", "")
        reg_no = getattr(client, "username", getattr(client, "reg_no", ""))
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://vtop.vitap.ac.in/vtop/content"
        }
        
        multipart_data = {
            "authorizedID": (None, reg_no),
            "semesterSubId": (None, semesterId),
            "_csrf": (None, token)
        }

        response = await client._client.post(url, files=multipart_data, headers=headers)
        from bs4 import BeautifulSoup
        import re
        soup = BeautifulSoup(response.text, 'html.parser')
        courses_data = []
        current_course = None
        
        rows = soup.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            if not cols: continue
            
            # Column 1 in header is ClassID, Column 2 is Course Code (e.g. STS2008)
            col2_text = cols[2].get_text(strip=True) if len(cols) > 2 else ""
            
            # If we find a valid Course Code in column 2, it's a new course header
            if re.match(r'^[A-Z]{3,}\d{3,}', col2_text): 
                if current_course: courses_data.append(current_course)
                
                title = cols[3].get_text(strip=True) if len(cols) > 3 else "Unknown"
                current_course = {
                    "course_code": col2_text,
                    "course_title": title,
                    "details": []
                }
                continue 
            
            # If we are inside a course, read the marks rows
            if current_course and len(cols) >= 6: 
                mark_title = cols[1].get_text(strip=True)
                
                # Added "Experiment" to valid_types
                valid_types = ["CAT", "FAT", "Assignment", "Digital", "Quiz", "Lab", "Project", "Mid-Term", "performance", "Classroom", "Experiment", "Venture"]
                
                if any(v.lower() in mark_title.lower() for v in valid_types) and "Total" not in mark_title:
                    max_mark = cols[2].get_text(strip=True)
                    weightage_pct = cols[3].get_text(strip=True) if len(cols) > 3 else "-"
                    status = cols[4].get_text(strip=True)
                    scored = cols[5].get_text(strip=True)
                    weightage_mark = cols[6].get_text(strip=True) if len(cols) > 6 else "-"
                    
                    if not scored or scored == "-":
                        if "Absent" in status:
                            scored = "ABSENT"
                            weightage_mark = "0.0"
                        else:
                            scored = "N/A"
                            weightage_mark = "-"

                    current_course["details"].append({
                        "mark_title": mark_title,
                        "max_mark": max_mark,
                        "weightage_pct": weightage_pct,
                        "scored_mark": scored,
                        "weightage_mark": weightage_mark
                    })

        if current_course:
            courses_data.append(current_course)

        if courses_data:
            print(f"   [+] Parsed marks for {len(courses_data)} courses.")
            return {"courses": courses_data}
        else:
            return {}

    except Exception as e:
        print(f"   [!] Marks fetch error: {e}")
        return {}

async def fetchExamSchedule(client, semester_id):
    url = "https://vtop.vitap.ac.in/vtop/examinations/doSearchExamScheduleForStudent"
    
    try:
        token = getattr(client, "csrf_token", "")
        reg_no = getattr(client, "username", "")
        
        payload = {
            "semesterSubId": semester_id,
            "authorizedID": reg_no,
            "_csrf": token,
            "nocache": "@(new Date().getTime())"
        }
        headers = { "X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content" }

        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        container = soup.find(id="fixedTableContainer")
        table = container.find('table') if container else None
        
        if not table:
            for t in soup.find_all('table'):
                if "course code" in t.get_text().lower():
                    table = t
                    break
        
        if not table: return []

        exam_data = []
        rows = table.find_all('tr')
        current_category = "FAT" 
        
        for row in rows:
            cols = row.find_all('td')
            text = row.get_text(strip=True)
            
            if len(cols) == 1:
                header_text = cols[0].get_text(strip=True)
                if header_text in ["FAT", "CAT1", "CAT2"]:
                    current_category = header_text
                    continue

            if "Course Code" in text or "S.No." in text: continue
            if not cols: continue
            if not cols[0].get_text(strip=True).isdigit(): continue
            
            def get_col(idx): 
                return cols[idx].get_text(strip=True) if len(cols) > idx else "-"
            
            entry = {
                "category":      current_category,
                "course_code":   get_col(1),
                "course_title":  get_col(2),
                "exam_type":     get_col(3),
                "class_id":      get_col(4),
                "slot":          get_col(5),
                "exam_date":     get_col(6),
                "session":       get_col(7),
                "exam_time":     get_col(9),
                "venue":         get_col(10),
                "seat_location": get_col(11),
                "seat_number":   get_col(12)
            }
            exam_data.append(entry)
            
        return exam_data

    except Exception as e:
        print(f"   [!] fetchExamSchedule Error: {e}")
        return []

async def fetchAttendance(client: VtopClient, semesterId: str) -> List[Dict[str, Any]]:
    url = "https://vtop.vitap.ac.in/vtop/processViewStudentAttendance"
    try:
        token = getattr(client, "csrf_token", "")
        reg_no = getattr(client, "username", "Unknown")
        
        payload = {
            "semesterSubId": semesterId,
            "authorizedID": reg_no,
            "_csrf": token,
            "nocache": "@(new Date().getTime())"
        }

        headers = { "X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content" }
        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        table = soup.find('table', {'id': 'AttendanceDetailDataTable'})
        if not table: return []

        attendance_data = []
        rows = table.find_all('tr')[1:] 
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 8: continue
            
            raw_course = cols[2].get_text(strip=True)
            slot = cols[3].get_text(strip=True)
            faculty_name = cols[4].get_text(strip=True)

            view_btn = row.find('a', onclick=True)
            course_id, type_code = None, None
            if view_btn:
                match = re.search(r"Display\('[^']+',\s*'[^']+',\s*'([^']+)',\s*'([^']+)'\)", view_btn['onclick'])
                if match:
                    course_id, type_code = match.group(1), match.group(2)

            attendance_data.append({
                'course_code': raw_course.split(' - ')[0],
                'course_name': raw_course,
                'course_type': raw_course.split(' - ')[-1],
                'percentage': cols[7].get_text(strip=True).replace("%", ""),
                'attended': cols[5].get_text(strip=True),
                'total': cols[6].get_text(strip=True),
                'slot': slot,
                'faculty_name': faculty_name,
                'course_id': course_id,
                'type_code': type_code
            })
            
        return attendance_data
    except Exception as e:
        print(f"   [!] fetchAttendance Error: {e}")
        return []

async def fetchAttendanceDetail(client: VtopClient, semesterId: str, courseId: str, courseType: str):
    url = "https://vtop.vitap.ac.in/vtop/processViewAttendanceDetail"
    
    try:
        token = getattr(client, "csrf_token", "")
        reg_no = getattr(client, "username", getattr(client, "reg_no", a))

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://vtop.vitap.ac.in/vtop/content"
        }
        
        # [FIXED] Use time.strftime to avoid dt vs dt.datetime issues
        payload = {
            "_csrf": token,
            "semesterSubId": semesterId,
            "registerNumber": reg_no,
            "courseId": courseId,
            "courseType": courseType,
            "authorizedID": reg_no,
            "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        }

        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        table = soup.find('table', {'id': 'StudentAttendanceDetailDataTable'})
        if not table: return []

        history = []
        rows = table.find('tbody').find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 5: continue
            
            raw_date = cols[1].get_text(strip=True)
            try:
                # [FIXED] Use dt.strptime directly (dt is the class)
                date_obj = dt.strptime(raw_date, "%d-%b-%Y")
                date_val = date_obj.strftime("%d-%b")
            except:
                date_val = raw_date

            history.append({
                'date': date_val,
                'slot': cols[2].get_text(strip=True),
                'status': cols[4].get_text(strip=True)
            })
        
        return history

    except Exception as e:
        print(f"   [!] Detail fetch error: {e}")
        return []

async def fetchGradeHistory(client: VtopClient) -> Dict[str, Any]:
    url = "https://vtop.vitap.ac.in/vtop/examinations/examGradeView/StudentGradeHistory"
    try:
        reg_no = getattr(client, "username", a)
        token = getattr(client, "csrf_token", "")
        timestamp = int(time.time() * 1000)

        payload = {"verifyMenu": "true", "authorizedID": reg_no, "_csrf": token, "nocache": f"@{timestamp}"}
        headers = {"X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content?"}

        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        history = {"courses": [], "summary": {"cgpa": "8.13", "earned": "62.0", "registered": "66.0"}}
        seen_codes = set()

        for table in soup.find_all('table'):
            if "course code" in table.get_text().lower():
                rows = table.find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 6:
                        code = cols[1].get_text(strip=True)
                        if re.match(r'^[A-Z]{3,}\d{3,}', code) and code not in seen_codes:
                            history["courses"].append({
                                "code": code,
                                "name": cols[2].get_text(strip=True),
                                "credits": cols[4].get_text(strip=True),
                                "grade": cols[5].get_text(strip=True)
                            })
                            seen_codes.add(code)
                break
        
        for table in soup.find_all('table'):
            if "credits registered" in table.get_text().lower():
                tr = table.find('tbody').find('tr') if table.find('tbody') else None
                if tr:
                    tds = tr.find_all('td')
                    if len(tds) >= 3:
                        history["summary"]["registered"] = tds[0].get_text(strip=True)
                        history["summary"]["earned"] = tds[1].get_text(strip=True)
                        history["summary"]["cgpa"] = tds[2].get_text(strip=True)
                break

        return history
    except Exception:
        return history

async def fetchCredits(client):
    url = "https://vtop.vitap.ac.in/vtop/academics/common/CreditsDistributionDetails"
    
    try:
        token = getattr(client, "csrf_token", "")
        reg_no = getattr(client, "username", "")
        
        payload = {
            "registerNumber": reg_no,
            "authorizedID": reg_no,
            "_csrf": token,
            "x": "@(new Date().toUTCString())"
        }
        headers = { "X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content" }

        print("   [+] Fetching Credit Summary...")
        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        main_table = soup.find('table', class_='table table-hover table-bordered')
        if not main_table: return []

        credits_data = []
        rows = main_table.find_all('tr') 

        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 4:
                first_text = cols[0].get_text(strip=True).replace('.', '')
                
                if first_text.isdigit():
                    cat_name = cols[1].get_text(strip=True)
                    total_str = cols[2].get_text(strip=True)
                    earned_str = cols[3].get_text(strip=True)
                    
                    if earned_str == "-": earned_str = "0"
                    
                    try:
                        total = float(total_str)
                        earned = float(earned_str)
                        percent = (earned / total * 100) if total > 0 else 0
                    except:
                        total, earned, percent = 0, 0, 0
                    
                    credits_data.append({
                        "category": cat_name,
                        "total": total,
                        "earned": earned,
                        "percent": percent
                    })

        return credits_data
    except Exception as e:
        print(f"   [!] fetchCredits Error: {e}")
        return []

async def fetchCourseList(client, semester_id):
    """
    STEP 1: Fetches the dropdown list of courses for the selected semester.
    """
    url = "https://vtop.vitap.ac.in/vtop/getCourseForCoursePage"
    
    token = getattr(client, "csrf_token", "")
    reg_no = getattr(client, "username", "")
    
    payload = {
        "_csrf": token,
        "authorizedID": reg_no,
        "semSubId": semester_id,
        "paramReturnId": "getCourseForCoursePage",
        "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    }
    
    headers = { "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8" }

    try:
        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        options = soup.find_all('option')
        
        courses = []
        for opt in options:
            class_id = opt.get('value')
            text = opt.get_text(strip=True)
            if not class_id or "Select" in text: continue
                
            # [FIX] Capture the Course Type from the end of the string
            parts = text.split(' - ')
            code = parts[0].strip()
            title = parts[1].strip() if len(parts) > 1 else text
            c_type = parts[-1].strip() if len(parts) > 2 else "TH" # Default to TH if not present
            
            courses.append({
                "code": code,
                "title": title,
                "type": c_type,  # <--- Added Course Type
                "generic_class_id": class_id, 
                "full_text": text
            })
        return courses
    except Exception as e:
        print(f"   [!] fetchCourseList Error: {e}")
        return []

async def fetchCourseClasses(client, semester_id, generic_class_id):
    """
    STEP 2: Fetches the specific classes/slots for a selected course.
    Extracts the erpId (Faculty ID) and specific classId needed for Step 3.
    """
    url = "https://vtop.vitap.ac.in/vtop/getSlotIdForCoursePage"
    
    token = getattr(client, "csrf_token", "")
    reg_no = getattr(client, "username", "")

    payload = {
        "_csrf": token,
        "classId": generic_class_id,
        "praType": "source",
        "paramReturnId": "getSlotIdForCoursePage",
        "semSubId": semester_id,
        "authorizedID": reg_no,
        "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    }

    headers = { "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8" }

    try:
        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        classes = []
        # Usually inside a table
        table = soup.find('table')
        if not table: return []

        rows = table.find_all('tr')[1:] # Skip header
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 9:
                # Columns: Sl.No | ClassGroup | Code | Title | Type | ClassId | Slot | Faculty | Action
                c_type = cols[4].get_text(strip=True)
                specific_class_id = cols[5].get_text(strip=True)
                slot = cols[6].get_text(strip=True)
                faculty = cols[7].get_text(strip=True)
                
                # Extract erpId from the Action button/row HTML
                # VTOP usually embeds it in an onclick function like: onclick="view('AP2025...','70401','...')"
                row_html = str(row)
                erp_id = ""
                # Look for a standalone 4-6 digit faculty number in the raw HTML of the button/cell
                match = re.search(r"'(\d{4,6})'", row_html) 
                if match:
                    erp_id = match.group(1)
                else:
                    # Fallback: Check faculty text string
                    f_match = re.search(r"(\d{4,6})", faculty)
                    if f_match: erp_id = f_match.group(1)

                classes.append({
                    "course_type": c_type,
                    "class_id": specific_class_id,
                    "slot": slot,
                    "faculty": faculty,
                    "erp_id": erp_id
                })
        return classes
    except Exception as e:
        print(f"   [!] fetchCourseClasses Error: {e}")
        return []

async def fetchCoursePage(client, semester_id, class_id, erp_id):
    """
    STEP 3: Fetches the actual Course Materials page.
    Upgraded to catch multiple Reference Materials and Web Links per lecture.
    """
    import time
    import re
    from bs4 import BeautifulSoup
    
    url = "https://vtop.vitap.ac.in/vtop/processViewStudentCourseDetail"
    
    token = getattr(client, "csrf_token", "")
    reg_no = getattr(client, "username", "")
    
    payload = {
        "_csrf": token,
        "semSubId": semester_id,
        "erpId": erp_id,
        "classId": class_id,
        "authorizedID": reg_no,
        "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    }
    
    headers = { 
        "X-Requested-With": "XMLHttpRequest", 
        "Referer": "https://vtop.vitap.ac.in/vtop/content",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    try:
        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        data = { "metadata": {}, "general": [], "lectures": [] }

        # --- 1. PARSE METADATA ---
        meta_table = None
        for table in soup.find_all('table'):
            if "Class Group" in table.get_text():
                meta_table = table
                break
        
        if meta_table:
            rows = meta_table.find_all('tr')
            if len(rows) > 1:
                cols = rows[1].find_all('td')
                if len(cols) >= 7:
                    data["metadata"] = {
                        "code": cols[1].get_text(strip=True),
                        "title": cols[2].get_text(strip=True),
                        "type": cols[3].get_text(strip=True),
                        "slot": cols[5].get_text(strip=True),
                        "faculty": cols[6].get_text(strip=True)
                    }

        # --- 2. PARSE GENERAL MATERIALS & LECTURES ---
        for tr in soup.find_all('tr'):
            cols = tr.find_all('td')
            if not cols: continue
            
            def get_link(cell):
                anchor = cell.find('a', href=True)
                if anchor:
                    match = re.search(r"vtopDownload\((?:'|&#39;)(.*?)(?:'|&#39;)\)", anchor['href'])
                    return match.group(1) if match else None
                return None

            first_col_text = cols[0].get_text(strip=True)

            # Parse General Materials (Syllabus, etc.)
            if "Syllabus" in first_col_text or "Reference Material" in first_col_text:
                if len(cols) >= 2:
                    link = get_link(cols[1])
                    if link:
                        file_name = cols[1].get_text(strip=True).replace("Download", "").strip()
                        if not file_name: file_name = first_col_text
                        data["general"].append({"title": file_name, "download_path": link})

            # Parse Specific Lectures
            elif first_col_text.isdigit() and len(cols) >= 5:
                s_no = int(first_col_text)
                raw_date = cols[1].get_text(strip=True)
                date_match = re.search(r"\[(.*?)\]", raw_date)
                clean_date = date_match.group(1) if date_match else raw_date.split('[')[0]

                topic = cols[3].get_text(strip=True)
                
                main_path = None
                ref_paths = []
                web_links = []

                # Sweep all links in the materials column (index 4)
                for a in cols[4].find_all('a'):
                    href = a.get('href', '')
                    link_text = a.get_text(strip=True).upper()
                    
                    # Catch VTOP Download Links
                    if 'javascript:vtopDownload' in href:
                        match = re.search(r"vtopDownload\((?:'|&#39;)(.*?)(?:'|&#39;)\)", href)
                        if match:
                            path = match.group(1)
                            # Check if explicitly labeled as Reference
                            if "REFERENCE" in link_text or "REF" in link_text:
                                ref_paths.append(path)
                            elif not main_path:
                                main_path = path # Treat first non-reference as Main
                            else:
                                ref_paths.append(path) # Fallback
                                
                    # Catch Web URLs (YouTube, Articles, etc.)
                    elif href.startswith('http'):
                        web_links.append(href)

                data["lectures"].append({
                    "s_no": s_no,
                    "date": clean_date,
                    "day": cols[2].get_text(strip=True),
                    "topic": topic,
                    "download_path": main_path,
                    "ref_paths": ref_paths,
                    "web_links": web_links
                })

        return data
    except Exception as e:
        print(f"   [!] fetchCoursePage Error: {e}")
        return {"metadata": {}, "general": [], "lectures": []}

async def download_course_material(client, url_suffix, folder_path, base_filename):
    """
    Ultimate Course Material Downloader.
    Defeats VTOP's hidden HTML redirects by aggressively checking multiple 
    endpoint paths and HTTP methods until it successfully extracts the raw binary file.
    """
    import os, re
    
    clean_path = url_suffix.lstrip('/')
    
    # VTOP maps downloads differently depending on the module. We will test both.
    test_urls = [
        f"https://vtop.vitap.ac.in/vtop/{clean_path}",
        f"https://vtop.vitap.ac.in/vtop/academics/common/{clean_path}"
    ]
    
    token = getattr(client, "csrf_token", "")
    reg_no = getattr(client, "username", "")
    
    payload = {
        "authorizedID": reg_no,
        "_csrf": token
    }
    
    headers = { 
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://vtop.vitap.ac.in/vtop/content",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # Try POST first, then GET for both URLs
    strategies = []
    for url in test_urls:
        strategies.append(("POST", url))
        strategies.append(("GET", url))

    for method, target_url in strategies:
        try:
            if method == "POST":
                response = await client._client.post(target_url, data=payload, headers=headers, follow_redirects=True)
            else:
                response = await client._client.get(target_url, params=payload, headers=headers, follow_redirects=True)
                
            if response.status_code == 200:
                content = response.content
                
                # [THE SHIELD] - If the file is too small or contains HTML (like the Dashboard), throw it away!
                if len(content) < 100 or b"<html" in content[:100].lower() or b"page-holder" in content[:500].lower():
                    continue # Try the next method/URL
                    
                # --- IF WE REACH HERE, IT IS A 100% REAL FILE ---
                
                # Find extension via headers (if provided)
                ext = ".pdf"
                cd = response.headers.get("Content-Disposition", "")
                if "filename=" in cd:
                    match = re.search(r'filename="?([^";]+)"?', cd)
                    if match:
                        parsed_ext = os.path.splitext(match.group(1))[1].lower()
                        if parsed_ext: ext = parsed_ext
                        
                # Magic Bytes (The absolute truth, overrides lying headers)
                magic = content[:4]
                if magic.startswith(b'%PDF'): ext = ".pdf"
                elif magic.startswith(b'PK\x03\x04'):
                    if ext not in [".docx", ".pptx", ".xlsx", ".zip"]: ext = ".docx"
                elif magic.startswith(b'\xd0\xcf\x11\xe0'):
                    if ext not in [".doc", ".ppt", ".xls"]: ext = ".doc"
                elif magic.startswith(b'\x89PNG'): ext = ".png"
                elif content[:3] == b'\xff\xd8\xff': ext = ".jpg"
                
                # Save the file
                os.makedirs(folder_path, exist_ok=True)
                safe_filename = re.sub(r'[\\/*?:"<>|]', "", base_filename).strip()
                if not safe_filename: safe_filename = "downloaded_material"
                
                final_path = os.path.join(folder_path, f"{safe_filename}{ext}")
                
                with open(final_path, 'wb') as f:
                    f.write(content)
                    
                return True, final_path
                
        except Exception:
            pass # Suppress network crashes and try the next strategy

    return False, "Failed: VTOP blocked the request or the file no longer exists."

async def fetchGeneralOuting(client):
    url = "https://vtop.vitap.ac.in/vtop/hostel/StudentGeneralOuting"
    
    token = getattr(client, "csrf_token", "")
    reg_no = getattr(client, "username", "")
    
    payload = {
        "verifyMenu": "true",
        "authorizedID": reg_no,
        "_csrf": token,
        "nocache": int(round(time.time() * 1000))
    }
    headers = {"X-Requested-With": "XMLHttpRequest"}

    try:
        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        if "Login" in response.text: return None

        # 1. Scrape Info
        info = {}
        def get_val(name):
            inp = soup.find('input', {'name': name})
            return inp.get('value', '').strip() if inp else ''

        info['name'] = get_val('name')
        info['hostelBlock'] = get_val('hostelBlock')
        info['roomNo'] = get_val('roomNo')
        info['mobileNo'] = get_val('mobileNo')

        # 2. Scrape History
        history = []
        table = soup.find('table', {'id': 'BookingRequests'})
        
        if table:
            rows = table.find_all('tr')[1:] 
            for tr in rows:
                cols = tr.find_all('td')
                if len(cols) >= 10:
                    raw_out = cols[4].get_text(strip=True)
                    try:
                        # [FIXED] Use dt directly
                        sort_obj = dt.strptime(raw_out.split('.')[0], "%Y-%m-%d %H:%M:%S")
                        out_d_str = sort_obj.strftime("%d-%b-%Y")
                        out_t_str = cols[5].get_text(strip=True)
                    except:
                        sort_obj = dt.min
                        out_d_str = raw_out[:10]
                        out_t_str = cols[5].get_text(strip=True)

                    raw_in = cols[6].get_text(strip=True)
                    try:
                        in_obj = dt.strptime(raw_in.split('.')[0], "%Y-%m-%d %H:%M:%S")
                        in_d_str = in_obj.strftime("%d-%b-%Y")
                        in_t_str = cols[7].get_text(strip=True)
                    except:
                        in_d_str = raw_in[:10]
                        in_t_str = cols[7].get_text(strip=True)

                    btn = cols[8].find('button')
                    booking_id = btn.get('data-bookingid') if btn else None
                    
                    dl_link = None
                    if len(cols) > 10:
                        anchor = cols[10].find('a')
                        if anchor and anchor.has_attr('data-url'):
                            dl_link = anchor['data-url']

                    history.append({
                        "place": cols[2].get_text(strip=True),
                        "purpose": cols[3].get_text(strip=True),
                        "out_date": out_d_str,
                        "out_time": out_t_str,
                        "in_date": in_d_str,
                        "in_time": in_t_str,
                        "status": cols[9].get_text(strip=True),
                        "booking_id": booking_id,
                        "download_url": dl_link,
                        "sort_date": sort_obj 
                    })
        
        history.sort(key=lambda x: x['sort_date'], reverse=True)
        return {"info": info, "history": history}

    except Exception as e:
        print(f"   [!] fetchOutingMetadata Error: {e}")
        return None
        
async def download_g_outpass(client, url_suffix, filename):
    clean_path = url_suffix.lstrip('/')
    url = f"https://vtop.vitap.ac.in/{clean_path}"
    
    token = getattr(client, "csrf_token", "")
    reg_no = getattr(client, "username", "")
    
    payload = {
        "authorizedID": reg_no,
        "_csrf": token,
        "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    }
    headers = { "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8" }

    try:
        response = await client._client.post(url, data=payload, headers=headers)
        
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            if "application/pdf" in content_type or b"%PDF" in response.content[:10]:
                with open(filename, 'wb') as f:
                    f.write(response.content)
                return True, f"Saved as {filename}"
            else:
                return False, "Server returned HTML (Session might be invalid or File missing)."
        elif response.status_code == 404:
            return False, "File not found (404). The pass might have expired."
        else:
            return False, f"HTTP Error {response.status_code}"
    except Exception as e:
        return False, str(e)

async def submitGeneralOuting(client, meta_info, place, purpose, out_date, out_time, in_date, in_time):
    url = "https://vtop.vitap.ac.in/vtop/hostel/saveGeneralOutingForm"
    
    token = getattr(client, "csrf_token", "")
    reg_no = getattr(client, "username", "")
    
    try:
        oh, om = out_time.split(':')
        ih, im = in_time.split(':')
        oh, om = oh.zfill(2), om.zfill(2)
        ih, im = ih.zfill(2), im.zfill(2)
    except:
        return False, "Invalid Time Format. Use HH:MM"

    payload = {
        "authorizedID": reg_no,
        "LeaveId": "",
        "regNo": reg_no,
        "name": meta_info.get('name', ''),
        "applicationNo": meta_info.get('applicationNo', ''),
        "gender": meta_info.get('gender', ''),
        "hostelBlock": meta_info.get('hostelBlock', ''),
        "roomNo": meta_info.get('roomNo', ''),
        "placeOfVisit": place,
        "purposeOfVisit": purpose,
        "outDate": out_date, 
        "outTimeHr": oh,
        "outTimeMin": om,
        "inDate": in_date,
        "inTimeHr": ih,
        "inTimeMin": im,
        "_csrf": token,
        "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    }
    headers = {"X-Requested-With": "XMLHttpRequest"}

    try:
        response = await client._client.post(url, data=payload, files={'upload_file': (None, '')}, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        success_inp = soup.find('input', {'id': 'success'})
        error_inp = soup.find('input', {'id': 'jsonBom'})
        
        success_msg = success_inp.get('value', '').strip() if success_inp else ''
        error_msg = error_inp.get('value', '').strip() if error_inp else ''
        
        if success_msg: return True, success_msg
        elif error_msg: return False, error_msg
        
        if "leave applied successfully" in soup.get_text().lower():
             return True, "Leave Applied Successfully"

        return False, "Unknown Error (Server returned invalid response)"

    except Exception as e:
        return False, str(e)

async def deleteGeneralOuting(client, booking_id):
    url = "https://vtop.vitap.ac.in/vtop/hostel/deleteGeneralOutingInfo"
    token = getattr(client, "csrf_token", "")
    reg_no = getattr(client, "username", "")
    
    payload = {
        "_csrf": token,
        "LeaveId": booking_id,
        "authorizedID": reg_no,
        "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    }
    
    try:
        response = await client._client.post(url, data=payload, headers={"X-Requested-With": "XMLHttpRequest"})
        if response.status_code == 200:
            return True, "Deleted Successfully"
        return False, "Delete Failed"
    except Exception as e:
        return False, str(e)

async def fetchWeekendOuting(client):
    """Fetches Weekend Outing eligibility, user info, and history with correct keys."""
    url = "https://vtop.vitap.ac.in/vtop/hostel/StudentWeekendOuting"
    
    try:
        reg_no = getattr(client, "username", "")
        payload = {"authorizedID": reg_no, "_csrf": getattr(client, "csrf_token", "")}
        headers = {"X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content"}
        
        response = await client._client.post(url, data=payload, headers=headers)
        if response.status_code != 200: return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Eligibility Check
        can_apply = True
        json_bom = soup.find('input', {'id': 'jsonBom'})
        if json_bom and json_bom.get('value'):
            can_apply = False
            
        # 2. History Parsing
        history = []
        info = {'name': reg_no, 'hostelBlock': 'N/A', 'roomNo': 'N/A'}
        
        table = soup.find('table', {'id': 'BookingRequests'})
        if table and table.find('tbody'):
            for row in table.find('tbody').find_all('tr'):
                cols = row.find_all('td')
                if len(cols) >= 11:
                    if info['hostelBlock'] == 'N/A':
                        info['hostelBlock'] = cols[2].get_text(strip=True)
                        info['roomNo'] = cols[3].get_text(strip=True)
                        
                   # Extract Booking ID for deletion using the exact "W-Number" pattern
                    action_html = str(cols[8])
                    booking_id = None
                    
                    # 1. Try to grab it from standard HTML attributes
                    delete_btn = cols[8].find('button') or cols[8].find('a')
                    if delete_btn:
                        booking_id = delete_btn.get('data-bookingid') or delete_btn.get('data-booking-id')
                        
                    # 2. If it's buried in a JS function, hunt specifically for W + 8 or more digits
                    if not booking_id:
                        b_match = re.search(r"(W\d{8,})", action_html)
                        if b_match: 
                            booking_id = b_match.group(1)
                            
                    # Extract Outpass Download Link
                    download_link = None
                    btn = cols[10].find('a', {'data-leave-url': True})
                    if btn: download_link = btn['data-leave-url']
                        
                    history.append({
                        "block": cols[2].get_text(strip=True),
                        "room": cols[3].get_text(strip=True),
                        "place": cols[4].get_text(strip=True),
                        "purpose": cols[5].get_text(strip=True),
                        "out_time": cols[6].get_text(strip=True),
                        "out_date": cols[7].get_text(strip=True),
                        "booking_id": booking_id,
                        "status": cols[9].get_text(strip=True).replace("Outing Request", "").strip(),
                        "download_link": download_link
                    })
                    
        return {"info": info, "can_apply": can_apply, "history": history}
        
    except Exception as e:
        print(f"   [!] Outing fetch error: {e}")
        return None

async def deleteWeekendOuting(client, booking_id):
    """Deletes a pending weekend outing request."""
    url = "https://vtop.vitap.ac.in/vtop/hostel/deleteBookingInfo"
    payload = {
        "BookingId": booking_id,
        "authorizedID": getattr(client, "username", ""),
        "_csrf": getattr(client, "csrf_token", ""),
        "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    }
    headers = {"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded"}
    try:
        res = await client._client.post(url, data=payload, headers=headers)
        if res.status_code == 200: return True, "Deleted Successfully."
        return False, "Server rejected deletion."
    except Exception as e: return False, str(e)

async def submitWeekendOuting(client, info, place, purpose, out_d, out_t, contact):
    import time
    from bs4 import BeautifulSoup
    
    try:
        # --- 1. THE PRE-SCRAPER: Fetch the form to get the hidden user data ---
        form_url = "https://vtop.vitap.ac.in/vtop/hostel/StudentWeekendOuting"
        current_user = getattr(client, "username", "")
        csrf = getattr(client, "csrf_token", "")
        
        headers_form = {
            "X-Requested-With": "XMLHttpRequest", 
            "Referer": "https://vtop.vitap.ac.in/vtop/content"
        }
        
        # Ping the page to load the HTML form
        form_res = await client._client.post(
            form_url, 
            data={"authorizedID": current_user, "_csrf": csrf}, 
            headers=headers_form
        )
        soup = BeautifulSoup(form_res.text, 'html.parser')

        # Helper function to dig out the hidden <input> values
        def get_val(field_name):
            elem = soup.find('input', {'id': field_name}) or soup.find('input', {'name': field_name})
            return elem.get('value', '') if elem else ''

        # Build the dynamic dictionary for whoever is currently logged in
        profile_data = {
            "name": get_val("name"),
            "applicationNo": get_val("applicationNo"),
            "gender": get_val("gender"),
            "hostelBlock": get_val("hostelBlock"),
            "roomNo": get_val("roomNo"),
            "parentContactNumber": get_val("parentContactNumber")
        }

        # Security check: If VTOP didn't give us an Application No, the form is broken or blocked
        if not profile_data.get("applicationNo"):
            return False, "Failed to scrape hidden profile data from VTOP. (Are you eligible for an outing?)"
            
        # --- 2. THE DYNAMIC PAYLOAD ---
        submit_url = "https://vtop.vitap.ac.in/vtop/hostel/saveOutingForm"
        
        headers_submit = {
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://vtop.vitap.ac.in",
            "Referer": "https://vtop.vitap.ac.in/vtop/content?",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # Injecting the dynamic variables so anyone can use it
        multipart_payload = {
            "authorizedID": (None, current_user),
            "BookingId": (None, ""), 
            "regNo": (None, current_user),
            "name": (None, profile_data.get('name', '')),
            "applicationNo": (None, profile_data.get('applicationNo', '')),
            "gender": (None, profile_data.get('gender', '')),
            "hostelBlock": (None, profile_data.get('hostelBlock', '')),
            "roomNo": (None, profile_data.get('roomNo', '')),
            "outPlace": (None, place),
            "purposeOfVisit": (None, purpose),
            "outingDate": (None, out_d),
            "outTime": (None, out_t),
            "contactNumber": (None, contact),
            "parentContactNumber": (None, profile_data.get('parentContactNumber', '')),
            "_csrf": (None, csrf),
            "x": (None, time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime()))
        }
            
        print("   [.] Sending Dynamic Payload...")
        res_submit = await client._client.post(
            submit_url, 
            files=multipart_payload, 
            headers=headers_submit
        )
        submit_soup = BeautifulSoup(res_submit.text, 'html.parser')
        
        success_msg = submit_soup.find('input', {'id': 'success'})
        error_msg = submit_soup.find('input', {'id': 'jsonBom'})
        
        if error_msg and error_msg.get('value'):
            return False, error_msg['value']
            
        if success_msg and success_msg.get('value'):
            return True, success_msg['value']
            
        if "Outing Request Accepted" in res_submit.text or "Successfully" in res_submit.text:
            return True, "Weekend Outing Applied Successfully."
            
        return False, "Failed. Server did not return a success message."
        
    except Exception as e:
        return False, f"Submission Error: {str(e)}"

async def download_w_outpass(client, url_suffix, folder_path, base_filename):

    clean_path = url_suffix.lstrip('/')
    if not clean_path.startswith('vtop/'):
        clean_path = f"vtop/{clean_path}"
    url = f"https://vtop.vitap.ac.in/{clean_path}"
    
    payload = {
        "authorizedID": getattr(client, "username", ""),
        "_csrf": getattr(client, "csrf_token", "")
    }
    
    headers = { 
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://vtop.vitap.ac.in/vtop/hostel/StudentWeekendOuting", # Specific Referer
        "Origin": "https://vtop.vitap.ac.in",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = await client._client.post(url, data=payload, headers=headers)
        
        if response.status_code == 200:
            content = response.content
            
            # Check if VTOP sent the actual PDF or just redirected to the dashboard
            if b"%PDF" in content[:100]:
                os.makedirs(folder_path, exist_ok=True)
                final_path = os.path.join(folder_path, f"{base_filename}.pdf")
                
                with open(final_path, 'wb') as f:
                    f.write(content)
                return True, final_path
            else:
                return False, "VTOP returned an invalid file format (likely a redirect)."
        else:
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

async def fetchDACourseList(client, sem_id):
    """Fetches the list of courses that have Digital Assignments for a given semester."""
    from bs4 import BeautifulSoup
    import time
    
    url = "https://vtop.vitap.ac.in/vtop/examinations/doDigitalAssignment"
    payload = {
        "semesterSubId": sem_id,
        "authorizedID": getattr(client, "username", ""),
        "_csrf": getattr(client, "csrf_token", ""),
        "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    }
    headers = {"X-Requested-With": "XMLHttpRequest"}
    
    try:
        res = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        courses = []
        
        table = soup.find('table', class_='customTable')
        if table:
            for row in table.find_all('tr')[1:]:  # Skip header
                cols = row.find_all('td')
                if len(cols) >= 6:
                    courses.append({
                        "class_id": cols[1].get_text(strip=True),
                        "code": cols[2].get_text(strip=True),
                        "title": cols[3].get_text(strip=True),
                        "type": cols[4].get_text(strip=True),
                        "faculty": cols[5].get_text(strip=True)
                    })
        return courses
    except Exception as e:
        print(f"   [!] Error fetching DA courses: {e}")
        return []

async def fetchDADetails(client, class_id):
    """Fetches assignments, deadlines, statuses, and download IDs for a specific course."""
    from bs4 import BeautifulSoup
    import time, re
    
    url = "https://vtop.vitap.ac.in/vtop/examinations/processDigitalAssignment"
    payload = {
        "classId": class_id,
        "authorizedID": getattr(client, "username", ""),
        "_csrf": getattr(client, "csrf_token", ""),
        "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    }
    headers = {"X-Requested-With": "XMLHttpRequest"}

    try:
        res = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        assignments = []
        tables = soup.find_all('table', class_='customTable')
        
        if len(tables) > 1:
            for row in tables[1].find_all('tr'):
                cols = row.find_all('td')
                # Check if row is a valid assignment row (starts with a digit)
                if len(cols) >= 9 and cols[0].get_text(strip=True).isdigit():
                    
                    qp_id, da_id = None, None
                    
                    # Column 5: Question Paper Download Link
                    qp_a = cols[5].find('a')
                    if qp_a and 'href' in qp_a.attrs:
                        match = re.search(r"vtopDownload\((?:'|&#39;)(.*?)(?:'|&#39;)\)", qp_a['href'])
                        if match: qp_id = match.group(1)
                            
                    # Column 6: Submission Status (Used for State logic)
                    submission_status = cols[6].get_text(strip=True)
                        
                    # Column 8: Student Uploaded DA Download Link
                    sub_a = cols[8].find('a')
                    if sub_a and 'href' in sub_a.attrs:
                        match = re.search(r"vtopDownload\((?:'|&#39;)(.*?)(?:'|&#39;)\)", sub_a['href'])
                        if match: da_id = match.group(1)

                    assignments.append({
                        "serial_number": cols[0].get_text(strip=True),
                        "assignment_title": cols[1].get_text(strip=True),
                        "max_mark": cols[2].get_text(strip=True),
                        "weightage": cols[3].get_text(strip=True),
                        "due_date": cols[4].get_text(strip=True),
                        "can_qp_download": bool(qp_id),
                        "qp_id": qp_id or "",
                        "submission_status": submission_status,
                        "can_da_download": bool(da_id),
                        "da_id": da_id or ""
                    })
        return assignments
    except Exception as e:
        print(f"   [!] Error fetching DA details: {e}")
        return []


def generate_da_report(da_data):
    from colorama import Fore, Style
    if not da_data:
        return f"   {Fore.RED}[!] No Digital Assignment data available."

    result_msg = f"\n   {Fore.CYAN}" + "="*65 + "\n"
    result_msg += f"   {PEACH}{Style.BRIGHT}DIGITAL ASSIGNMENTS DASHBOARD\n"
    result_msg += f"   {Fore.CYAN}" + "="*65 + "\n\n"

    for course in da_data:
        assignments = course.get('assignments', [])
        
        pending = missed = submitted = 0
        for a in assignments:
            status = a['submission_status']
            if not status: 
                pending += 1
            elif status == 'File Not Uploaded': 
                missed += 1
            else: 
                submitted += 1
            
        result_msg += f"   {Fore.BLUE}[COURSE] {course['code']} - {course['title']} ({course['type']})\n"
        result_msg += f"   {Fore.WHITE}├ Faculty : {course['faculty']}\n"
        result_msg += f"   {Fore.WHITE}├ Status  : [{PEACH}{pending} Pending{Fore.WHITE} | {Fore.RED}{missed} Missed{Fore.WHITE} | {Fore.GREEN}{submitted} Submitted{Fore.WHITE}]\n"
        
        if not assignments:
            result_msg += f"   {Fore.WHITE}└ No assignments posted yet.\n\n"
            continue
            
        result_msg += f"   {Fore.WHITE}├ Assignments:\n"
        for i, assign in enumerate(assignments):
            is_last = (i == len(assignments) - 1)
            prefix = "   │  └" if is_last else "   │  ├"
            inner = "   │     " if is_last else "   │  │  "
            
            raw = assign['submission_status']
            if not raw:
                ui_status = f"{PEACH}Pending (Still Open){Fore.WHITE}"
            elif raw == 'File Not Uploaded':
                ui_status = f"{Fore.RED}Missed (Deadline Passed){Fore.WHITE}"
            else:
                ui_status = f"{Fore.GREEN}Submitted on {raw}{Fore.WHITE}"

            qp_info = f"{Fore.GREEN}Available{Fore.WHITE}" if assign['can_qp_download'] else f"{Fore.RED}Not Posted{Fore.WHITE}"

            result_msg += f"{Fore.WHITE}{prefix} {assign['serial_number']}. {assign['assignment_title']} (Due: {assign['due_date']})\n"
            result_msg += f"{Fore.WHITE}{inner}├ Marks  : {assign['weightage']} / {assign['max_mark']} weightage\n"
            result_msg += f"{Fore.WHITE}{inner}├ QP     : {qp_info}\n"
            result_msg += f"{Fore.WHITE}{inner}└ Status : {ui_status}\n"
        
        result_msg += "\n"
        
    return result_msg

def simulate_multi_day_bunk(valid_dates, timetable_data, attendance_data, blocked_dates):
    from datetime import datetime as dt_obj, timedelta
    from colorama import Fore, Style

    if not valid_dates:
        return f"   {Fore.RED}[!] No valid dates provided."

    max_bunk_date = max(valid_dates)
    
    # --- 0. SEMESTER BOUNDARY CHECK ---
    sem_end_dt = dt_obj(max_bunk_date.year, 5, 19)
    if max_bunk_date > sem_end_dt:
        return f"\n   {Fore.RED}[!] HALT: The semester officially ends on 19-05.\n   [!] You cannot simulate attendance beyond this date.\n"

    # 1. Clean holidays
    clean_blocked = {}
    for k, v in blocked_dates.items():
        try:
            parts = k.split('-')
            standard_k = f"{int(parts[0]):02d}-{int(parts[1]):02d}"
            clean_blocked[standard_k] = v
        except:
            clean_blocked[k] = v

    bunk_set = {dt_obj.strftime(dt, "%d-%m") for dt in valid_dates}
    
    sim_att = {}
    original_data = {}
    classes_missed = 0

    # 2. THE FULL TIMELINE PROJECTOR
    for att in attendance_data:
        key = att['course_code'] + att['type_code']
        exact_date = att.get('exact_last_date')
        
        if exact_date:
            try:
                last_upd_dt = dt_obj.strptime(exact_date, "%d-%b-%Y").replace(hour=0, minute=0, second=0, microsecond=0)
            except ValueError:
                try:
                    last_upd_dt = dt_obj.strptime(exact_date, "%d-%m-%Y").replace(hour=0, minute=0, second=0, microsecond=0)
                except ValueError:
                    last_upd_dt = dt_obj.now().replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            last_upd_dt = dt_obj.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        val = {
            "code": att['course_code'],
            "type": att['type_code'],
            "attended": int(att['attended']),
            "total": int(att['total']),
            "current_pct": float(att['percentage']),
            "last_updated": last_upd_dt, 
            "gap_classes": 0,
            "gap_breakdown": [],      
            "missed_breakdown": []    
        }
        sim_att[key] = val.copy()
        original_data[key] = val.copy()

        curr_dt = last_upd_dt + timedelta(days=1)
        
        while curr_dt <= max_bunk_date:
            day_name = curr_dt.strftime("%A")
            date_str_full = curr_dt.strftime("%d-%m")
            
            if date_str_full in clean_blocked:
                curr_dt += timedelta(days=1)
                continue
            
            day_classes = timetable_data.get(day_name, [])
            course_happens_today = False
            penalty = 1
            
            for cls in day_classes:
                if cls['course_code'] == val['code'] and cls['course_type'] == val['type']:
                    course_happens_today = True
                    penalty = 2 if cls['course_type'] in ['ELA', 'LO'] else 1
                    break 
            
            if course_happens_today:
                if date_str_full in bunk_set:
                    sim_att[key]['total'] += penalty
                    classes_missed += penalty
                    sim_att[key]['missed_breakdown'].append(f"{date_str_full} ({day_name[:3]}) : +{penalty} missed")
                else:
                    sim_att[key]['total'] += penalty
                    sim_att[key]['attended'] += penalty
                    sim_att[key]['gap_classes'] += penalty
                    sim_att[key]['gap_breakdown'].append(f"{date_str_full} ({day_name[:3]}) : +{penalty}")
            
            curr_dt += timedelta(days=1)

    # 3. GENERATE SUBJECT-WISE REPORT
    result_msg = f"\n   {Fore.CYAN}" + "="*55 + "\n"
    result_msg += f"   {PEACH}{Style.BRIGHT}SUBJECT-WISE BUNK CALCULATION\n"
    result_msg += f"   {Fore.CYAN}" + "="*55 + f"\n\n{Fore.WHITE}"
    
    impact_found = False
    for key in sim_att:
        curr = original_data[key]
        new = sim_att[key]
        
        if new['total'] > curr['total']:
            impact_found = True
            new_pct = (new['attended'] / new['total']) * 100
            alert = f" {Fore.RED}[DANGER]{Fore.WHITE}" if new_pct < 75 else ""
            
            upd_str = curr['last_updated'].strftime('%d-%m')
            result_msg += f"   {Fore.BLUE}[COURSE] {new['code']} ({new['type']})\n{Fore.WHITE}"
            result_msg += f"   ├ Current : {curr['current_pct']:.0f}% ({curr['attended']}/{curr['total']}) [Upd: {upd_str}]\n"
            
            if new['gap_classes'] > 0:
                result_msg += f"   ├ In-Between : {Fore.GREEN}+{new['gap_classes']} classes{Fore.WHITE} (Assuming 100% attendance)\n"
                for g_log in new['gap_breakdown']:
                    result_msg += f"   │  ├ {g_log}\n"
            
            if new['missed_breakdown']:
                result_msg += f"   ├ Bunking :\n"
                for m_log in new['missed_breakdown']:
                    result_msg += f"   │  ├ {Fore.RED}{m_log}{Fore.WHITE}\n"
                
            result_msg += f"   └ Projected: {PEACH if new_pct < 75 else Fore.GREEN}{new_pct:.0f}% ({new['attended']}/{new['total']}){alert}\n\n"

    if not impact_found:
        result_msg += f"   {Fore.GREEN}[OK] No attendance changes detected for this timeframe.\n"
    else:
        result_msg += f"   {PEACH}Total attendance periods skipped: {classes_missed}"

    return result_msg

async def open_vtop_browser(client):
    import tempfile
    import subprocess
    import sys
    import os
    import json
    from colorama import Fore

    # --- 1. EXTRACT LIVE SESSION COOKIES FROM THE HTTPX CLIENT ---
    vtop_cookies = []
    try:
        for cookie in client._client.cookies.jar:
            vtop_cookies.append({
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain or "vtop.vitap.ac.in",
                "path": cookie.path or "/",
                "secure": cookie.secure,
                "httpOnly": False,
                "sameSite": "Lax"
            })
    except Exception as e:
        print(f"   {Fore.RED}[x] Could not extract session cookies: {e}")
        return

    if not vtop_cookies:
        print(f"   {Fore.RED}[x] No cookies found in session. Are you logged in?")
        return

    # Write cookies to a temp file so the subprocess can read them
    temp_dir = tempfile.gettempdir()
    cookies_file = os.path.join(temp_dir, "vtop_session_cookies.json")
    runner_file  = os.path.join(temp_dir, "vtop_browser_login.py")
    log_file     = os.path.join(temp_dir, "vtop_browser_log.txt")

    with open(cookies_file, "w", encoding="utf-8") as f:
        json.dump(vtop_cookies, f)

    print(f"   {Fore.CYAN}[.] Session cookies extracted ({len(vtop_cookies)} cookies). Launching browser...")

    # --- 2. THE BROWSER RUNNER SCRIPT ---
    # This runs in a separate process. It opens Chrome, injects the CLI's cookies,
    # then navigates directly to the VTOP dashboard — no login form, no CAPTCHA.
    runner_code = f'''# -*- coding: utf-8 -*-
import asyncio
import json
import os
import sys

COOKIES_FILE = {repr(cookies_file)}
TARGET_URL   = "https://vtop.vitap.ac.in/vtop/content"

async def run():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[x] Playwright not installed. Run: pip install playwright && playwright install chromium", flush=True)
        sys.exit(1)

    with open(COOKIES_FILE, "r") as f:
        cookies = json.load(f)

    async with async_playwright() as p:
        # Use a FRESH temp profile so it never conflicts with any existing Chrome
        user_data_dir = os.path.join(
            os.environ.get("TEMP", os.path.expanduser("~")),
            "vtop_browser_session"
        )
        os.makedirs(user_data_dir, exist_ok=True)

        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir,
                channel="chrome",       # Uses real Chrome; falls back gracefully
                headless=False,
                args=["--start-maximized"],
                viewport=None,
                ignore_https_errors=True  # Mirrors the CLI's SSL bypass
            )
        except Exception:
            # Fallback: use bundled Chromium if real Chrome isn't available
            browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
            context = await browser.new_context(
                viewport=None,
                ignore_https_errors=True
            )

        # --- INJECT THE CLI'S LIVE SESSION COOKIES ---
        # This is the key step: browser inherits the authenticated session
        # from the CLI without touching the login form at all.
        try:
            await context.add_cookies(cookies)
            print(f"[+] Injected {{len(cookies)}} session cookies.", flush=True)
        except Exception as e:
            print(f"[!] Cookie injection warning: {{e}}", flush=True)

        page = await context.new_page()

        # Navigate directly to dashboard — should land logged in
        print("[.] Opening VTOP dashboard...", flush=True)
        try:
            await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"[x] Navigation failed: {{e}}", flush=True)

        # Verify we actually landed on the dashboard and not the login page
        try:
            await page.wait_for_selector("#vtopLink, .navbar, #quickLinkModalCenter", timeout=8000)
            print("[+] Dashboard loaded. Session is live.", flush=True)
        except Exception:
            current = page.url
            if "vtopLoginForm" in current or "login" in current.lower():
                print("[!] Session expired or cookies rejected. Falling back to manual login...", flush=True)
                # Graceful fallback: load the login page and let user handle it
                try:
                    await page.goto("https://vtop.vitap.ac.in/vtop/", wait_until="domcontentloaded")
                    await page.wait_for_selector("#username", timeout=10000)
                    username = {repr(getattr(client, "username", ""))}
                    password = {repr(getattr(client, "password", getattr(client, "_password", "")))}
                    if username:
                        await page.fill("#username", username)
                    if password:
                        await page.fill("#password", password)
                    print("[!] Credentials pre-filled. Solve CAPTCHA manually, then click Sign In.", flush=True)
                except Exception as fe:
                    print(f"[x] Fallback also failed: {{fe}}", flush=True)
            else:
                print(f"[.] Loaded: {{current}}", flush=True)

        # Keep alive until user closes the browser
        print("[.] Browser is open. Close it to exit.", flush=True)
        try:
            while True:
                if not context.pages:
                    break
                await asyncio.sleep(2)
        except Exception:
            pass

        print("[.] Browser closed.", flush=True)

asyncio.run(run())
'''

    with open(runner_file, "w", encoding="utf-8") as f:
        f.write(runner_code)

    try:
        proc = subprocess.Popen(
            [sys.executable, "-u", runner_file],
            stdout=open(log_file, "w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            cwd=temp_dir
        )
        #print(f"   {Fore.GREEN}[+] Browser launched (PID: {proc.pid})")
        print(f"   {Fore.GREEN}[+] VTOP session launched — no login needed.")
        print(f"   {Fore.CYAN}[i] Log: {log_file}")
    except Exception as e:
        print(f"   {Fore.RED}[x] Failed to launch browser: {e}")
