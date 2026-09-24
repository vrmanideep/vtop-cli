import time
import os
import re
import sys
import getpass
import asyncio
import httpx
import pwinput
import json
from datetime import datetime as dt
from typing import List, Dict, Any, Tuple
from bs4 import BeautifulSoup
from colorama import Fore
from vitap_vtop_client.client import VtopClient

PEACH = '\033[38;2;245;231;158m'

# ==========================================
# HARDWARE-LOCKED ENCRYPTION ENGINE
# ==========================================

def get_hardware_id() -> str:
    import platform
    import subprocess
    sys_name = platform.system()
    try:
        if sys_name == 'Windows':
            # Try PowerShell first (default in Win 11), swallow all errors silently
            try:
                res = subprocess.run('powershell.exe -Command "(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID"', shell=True, capture_output=True, text=True)
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip()
            except Exception: pass
            
            # Fallback to WMIC (older Windows), completely hiding the stderr message
            try:
                res = subprocess.run('wmic csproduct get uuid', shell=True, capture_output=True, text=True)
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.split('\n')[1].strip()
            except Exception: pass
        elif sys_name == 'Darwin':
            res = subprocess.run("/usr/sbin/ioreg -rd1 -c IOPlatformExpertDevice | grep IOPlatformUUID", shell=True, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.split('"')[3]
        elif sys_name == 'Linux':
            with open('/etc/machine-id', 'r') as f:
                return f.read().strip()
    except Exception:
        pass
    
    import socket
    return socket.gethostname()

def get_encryption_key() -> bytes:
    import hashlib
    import base64
    hw_id = get_hardware_id()
    # Hash the hardware UUID to guarantee a consistent 32-byte key
    key = hashlib.sha256(hw_id.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(key)

def get_credentials(file_path="credentials.dat"):
    from cryptography.fernet import Fernet
    
    key = get_encryption_key()
    cipher = Fernet(key)

    if os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                encrypted_data = f.read()
            decrypted_data = cipher.decrypt(encrypted_data).decode('utf-8')
            creds = json.loads(decrypted_data)
            return creds["username"], creds["password"]
        except Exception:
            print(f"\n   {Fore.RED}[!] HARDWARE LOCK MISMATCH. This PC cannot decrypt the vault.")
            print(f"   {Fore.RED}[!] Trashing corrupted or stolen credentials file...")
            os.remove(file_path)

    print(f"\n   {PEACH}=======================================")
    print(f"   {PEACH}[ FIRST TIME SETUP: SECURE VTOP CLI ]")
    print(f"   {Fore.CYAN}🔒 Vault will be hardware-locked to this PC.")
    print(f"   {PEACH}=======================================\n")
    
    while True:
        username = input(f"   {PEACH}[>] Enter Login ID (Reg No, App No, or Email): {Fore.WHITE}").strip()
        if '@' not in username:
            username = username.upper()
            
        password = pwinput.pwinput(prompt=f"   {PEACH}[>] Enter VTOP Password: {Fore.WHITE}", mask="*").strip()
        
        if not username or not password:
            print(f"   {Fore.RED}[!] Fields cannot be empty. Try again.\n")
            continue

        print(f"\n   {Fore.CYAN}--- Verify Your Details ---")
        print(f"   {Fore.WHITE}Login ID: {username}")
        print(f"   {Fore.WHITE}Password: {'*' * len(password)}")
        
        confirm = input(f"\n   {PEACH}Encrypt and lock to this PC? (y/n): {Fore.WHITE}").strip().lower()
        
        if confirm == 'y':
            data = json.dumps({"username": username, "password": password}).encode('utf-8')
            encrypted_data = cipher.encrypt(data)
            with open(file_path, "wb") as f:
                f.write(encrypted_data)
            print(f"   {Fore.GREEN}[✓] Vault encrypted successfully!\n")
            return username, password
        else:
            print(f"   {Fore.RED}[!] Setup cancelled. Let's try typing that again.\n")

# ==========================================
# UTILITIES & GLOBALS
# ==========================================

def get_auth_id(client: VtopClient) -> str:
    try:
        if hasattr(client, "_logged_in_student") and client._logged_in_student:
            if hasattr(client._logged_in_student, "registration_number") and client._logged_in_student.registration_number:
                return client._logged_in_student.registration_number
    except Exception:
        pass
    return getattr(client, "username", getattr(client, "reg_no", ""))

def parse_date(raw: str, default_year: int = None):
    from datetime import datetime as dt_obj
    import re

    if default_year is None:
        default_year = dt_obj.now().year

    raw = raw.strip().lower()
    raw = re.sub(r'[-/.\s]+', ' ', raw)
    parts = raw.split()

    if len(parts) == 2:
        parts.append(str(default_year))

    if len(parts) != 3:
        raise ValueError(f"Cannot parse: '{raw}'. Use dd-mm, dd-mm-yy, or dd-mm-yyyy")

    day_str, month_str, year_str = parts

    try:
        day = int(day_str)
    except ValueError:
        raise ValueError(f"Invalid day: '{day_str}'")

    month_map = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, 
        "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
    }

    if month_str.isdigit():
        month = int(month_str)
    elif month_str in month_map:
        month = month_map[month_str]
    else:
        raise ValueError(f"Invalid month: '{month_str}'")

    year = int(year_str)
    if year < 100:
        year += 2000

    return dt_obj(year, month, day)

def to_vtop_date(raw: str) -> str:
    return parse_date(raw).strftime("%d-%b-%Y")

def to_display_date(raw: str) -> str:
    return parse_date(raw).strftime("%d-%b-%Y")

def to_bunk_date(raw: str) -> str:
    d = parse_date(raw)
    return f"{d.day}-{d.month}"

# SSL BYPASS
_original_init = httpx.AsyncClient.__init__
def _patched_init(self, *args, **kwargs):
    kwargs['verify'] = False
    _original_init(self, *args, **kwargs)
httpx.AsyncClient.__init__ = _patched_init

def save_calendar_cache(data: list, filename: str = "calendar_cache.json") -> bool:
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        print(f"   [!] Failed to save calendar cache: {e}")
        return False

def load_calendar_cache(filename: str = "calendar_cache.json") -> list:
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"   [!] Failed to load calendar cache: {e}")
        return []

async def vtopClientLogin(client: VtopClient) -> bool:
    try:
        await client._perform_login_sequence()
        return True
    except Exception as e:
        print(f"Login Failed: {e}")
        return False

# ==========================================
# SCRAPING LOGIC
# ==========================================

async def fetchTimetable(client, semester_id: str) -> dict:
    from bs4 import BeautifulSoup
    from collections import defaultdict
    
    print(f"   [.] Fetching and parsing Timetable Grid...")
    if not getattr(client, "_logged_in_student", None):
        print(f"   {Fore.RED}[!] No active session found. Please login again.")
        return {}
        
    token = client._logged_in_student.post_login_csrf_token
    reg_no = get_auth_id(client)
    headers = {
        "X-Requested-With": "XMLHttpRequest", 
        "Referer": "https://vtop.vitap.ac.in/vtop/content",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    try:
        menu_url = "https://vtop.vitap.ac.in/vtop/academics/common/StudentTimeTable"
        menu_payload = {"authorizedID": reg_no, "_csrf": token}
        await client._client.post(menu_url, data=menu_payload, headers=headers)
        await asyncio.sleep(0.2)

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
            print(f"   {Fore.RED}[!] Timetable grid is missing from the page.")
            return {}

        classname_code, faculty_code, course_to_class_nbr, course_to_slot_venue = {}, {}, {}, {}

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
                    if code not in classname_code: classname_code[code] = name

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
                    if faculty_name: faculty_code[class_nbr] = faculty_name

        raw_slots, timings_temp, count_for_offset, day = [], [], 0, ""

        for row in tables[1].find_all('tr'):
            cells = row.find_all('td')
            if len(cells) > 6:
                if count_for_offset % 2 == 0:
                    day = cells[0].get_text(strip=True)
                    cells = cells[1:]

                for index, val_td in enumerate(cells):
                    val = val_td.get_text(strip=True)
                    if count_for_offset == 0:
                        timings_temp.append({"serial": index, "course_type": "ETH", "start_time": val, "end_time": ""})
                    elif count_for_offset == 1:
                        if index < len(timings_temp): timings_temp[index]["end_time"] = val
                    elif count_for_offset == 2:
                        timings_temp.append({"serial": index, "course_type": "ELA", "start_time": val, "end_time": ""})
                    elif count_for_offset == 3:
                        if (22 + index) < len(timings_temp): timings_temp[22 + index]["end_time"] = val
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

                                course_key = f"{course_code}_{course_type}"
                                found_name = classname_code.get(course_code, "")
                                
                                raw_slots.append({
                                    "serial": index, "day": day, "slot": slot_name, "course_code": course_code,
                                    "course_type": course_type, "room_no": room_no, "block": block,
                                    "start_time": "", "end_time": "", "name": found_name,
                                    "class_nbr": course_to_class_nbr.get(course_key, "")
                                })
            count_for_offset += 1

        for slot in raw_slots:
            for t in timings_temp:
                if t["serial"] == slot["serial"] and (t["course_type"] == slot["course_type"] or slot["course_type"] in t["course_type"]):
                    slot["start_time"] = t["start_time"]
                    slot["end_time"] = t["end_time"]
                    break

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
                
                slots.sort(key=lambda x: x['start_time'])
                consecutive_groups, current_group = [], []

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
                
                if current_group: consecutive_groups.append(current_group)

                full_day_name = day_map.get(d, d)
                
                for group in consecutive_groups:
                    first = group[0]
                    last = group[-1]
                    slots_combined = "+".join([s['slot'] for s in group])

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
                        "start_time": first['start_time'], "venue": final_venue, "course_code": first['course_code'],
                        "course_type": first['course_type'], "slot": final_slot, "course_name": first['name'],
                        "faculty": faculty_name
                    })

        for day in weekly_timetable: weekly_timetable[day].sort(key=lambda x: x['start_time'])

        return dict(weekly_timetable)
    except Exception as e:
        print(f"   [!] fetchTimetable Error: {e}")
        return {}

async def get_todays_schedule(client):
    print("\n   [+] Fetching Timetable...")
    try:
        timetable = await client.get_timetable()
        today_name = dt.now().strftime("%A")
        
        print(f"\n   --- SCHEDULE FOR {today_name.upper()} ---")
        
        if today_name in timetable:
            todays_classes = timetable[today_name]
            if not todays_classes:
                print("   No classes scheduled for today!")
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
        reg_no = get_auth_id(client)
        payload = {"verifyMenu": "true", "authorizedID": reg_no, "_csrf": token, "nocache": "@(new Date().getTime())"}

        response = await client._client.post(url, data=payload, headers={
            "X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content"
        })
        soup = BeautifulSoup(response.text, 'html.parser')
        
        data = {"basic": {"name": "-", "regno": "-", "vitemail": "-", "mobile": "-", "program": "-", "school": "-"}, "proctor": {}}
        
        labels = soup.find_all('label')
        for i, label in enumerate(labels):
            key = label.get_text(strip=True).upper()
            if i + 1 < len(labels):
                val = labels[i+1].get_text(strip=True)
                if "REGISTER NUMBER" in key: data["basic"]["regno"] = val
                elif "VIT EMAIL" in key and "@vitapstudent.ac.in" in val: data["basic"]["vitemail"] = val
                elif "PROGRAM" in key: data["basic"]["program"] = val
                elif "SCHOOL NAME" in key: data["basic"]["school"] = val

        name_p = soup.find('p', style=lambda s: s and "font-weight: bold" in s and "text-align: center" in s)
        if name_p: data["basic"]["name"] = name_p.get_text(strip=True)

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
        dash_res = await client._client.get("vtop/content")
        csrf_match = re.search(r'name="_csrf"\s+value="([a-f0-9-]+)"', dash_res.text)
        token = csrf_match.group(1) if csrf_match else getattr(client, "csrf_token", "")
        client.csrf_token = token 

        url = "https://vtop.vitap.ac.in/vtop/academics/common/StudentTimeTable"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content"
        }
        reg_no = get_auth_id(client)
        payload = {"verifyMenu": "true", "authorizedID": reg_no, "_csrf": token, "nocache": "@(new Date().getTime())"}

        response = await client._client.post(url, data=payload, headers=headers)
        pattern = r'<option\s+value="([A-Z0-9]+)"[^>]*>([^<]+)</option>'
        matches = re.findall(pattern, response.text)
        
        semesters, seen = [], set()
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
        reg_no = get_auth_id(client)
        headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content"}
        multipart_data = {"authorizedID": (None, reg_no), "semesterSubId": (None, semesterId), "_csrf": (None, token)}

        response = await client._client.post(url, files=multipart_data, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        courses_data, current_course = [], None
        
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if not cols: continue
            col2_text = cols[2].get_text(strip=True) if len(cols) > 2 else ""
            
            if re.match(r'^[A-Z]{3,}\d{3,}', col2_text): 
                if current_course: courses_data.append(current_course)
                current_course = {
                    "course_code": col2_text,
                    "course_title": cols[3].get_text(strip=True) if len(cols) > 3 else "Unknown",
                    "course_type": cols[4].get_text(strip=True) if len(cols) > 4 else "",
                    "details": []
                }
                continue 
            
            if current_course and len(cols) >= 6: 
                sl_no = cols[0].get_text(strip=True)
                if sl_no.isdigit():
                    status, scored = cols[4].get_text(strip=True), cols[5].get_text(strip=True)
                    weightage_mark = cols[6].get_text(strip=True) if len(cols) > 6 else "-"
                    
                    if not scored or scored == "-":
                        if "Absent" in status:
                            scored, weightage_mark = "ABSENT", "0.0"
                        else:
                            scored, weightage_mark = "N/A", "-"

                    current_course["details"].append({
                        "mark_title": cols[1].get_text(strip=True),
                        "max_mark": cols[2].get_text(strip=True),
                        "weightage_pct": cols[3].get_text(strip=True) if len(cols) > 3 else "-",
                        "scored_mark": scored,
                        "weightage_mark": weightage_mark
                    })

        if current_course: courses_data.append(current_course)
        if courses_data:
            print(f"   [+] Parsed marks for {len(courses_data)} courses.")
            return {"courses": courses_data}
        return {}
    except Exception as e:
        print(f"   [!] Marks fetch error: {e}")
        return {}

async def fetchGrades(client, semester_id: str) -> list:
    print(f"   [.] Fetching Grades for {semester_id}...")
    url = "https://vtop.vitap.ac.in/vtop/examinations/examGradeView/doStudentGradeView"
    try:
        reg_no = get_auth_id(client)
        headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content"}
        multipart_data = {"authorizedID": (None, reg_no), "semesterSubId": (None, semester_id), "_csrf": (None, getattr(client, "csrf_token", ""))}

        response = await client._client.post(url, files=multipart_data, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        grades_data = []
        
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 8 and cols[0].get_text(strip=True).isdigit():
                course_id = ""
                btn = cols[7].find('button')
                if btn and btn.has_attr('onclick'):
                    match = re.search(r"getGradeViewDetails\((?:'|&#39;)(.*?)(?:'|&#39;)\)", btn['onclick'])
                    if match: course_id = match.group(1)
                        
                grades_data.append({
                    "course_code": cols[1].get_text(strip=True), "course_title": cols[2].get_text(strip=True),
                    "course_type": cols[3].get_text(strip=True), "grading_type": cols[4].get_text(strip=True),
                    "grand_total": cols[5].get_text(strip=True), "grade": cols[6].get_text(strip=True),
                    "course_id": course_id
                })
        return grades_data
    except Exception as e:
        print(f"   [!] Grades fetch error: {e}")
        return []

async def fetchGradeDetails(client, semester_id: str, course_id: str) -> list:
    url = "https://vtop.vitap.ac.in/vtop/examinations/examGradeView/getGradeViewDetails"
    try:
        payload = {
            "authorizedID": get_auth_id(client), "semesterSubId": semester_id, "courseId": course_id,
            "_csrf": getattr(client, "csrf_token", ""), "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        }
        headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Referer": "https://vtop.vitap.ac.in/vtop/content"}

        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        expanded_courses, current_course = [], None

        for tr in soup.find_all('tr'):
            cols = [td for td in tr.find_all(['td', 'th']) if td.parent == tr]
            if not cols: continue
            
            if len(cols) >= 8:
                sl_no, code = cols[0].get_text(strip=True), cols[1].get_text(strip=True)
                if sl_no.isdigit() and re.match(r'^[A-Z]{3,}\d{3,}', code):
                    current_course = {"code": code, "title": cols[2].get_text(strip=True), "stats": None, "components": []}
                    expanded_courses.append(current_course)
                    continue
            
            if current_course and len(cols) == 1 and cols[0].has_attr('colspan'):
                for tbl in cols[0].find_all('table'):
                    text = tbl.get_text(" ", strip=True).lower()
                    if "mean" in text and "sd" in text and "range of grades" in text:
                        rows = tbl.find_all('tr')
                        if len(rows) >= 3:
                            val_cols = rows[-1].find_all(['td', 'th'])
                            if len(val_cols) >= 11:
                                current_course["stats"] = {
                                    "class_strength": val_cols[0].get_text(strip=True), "grading_strength": val_cols[1].get_text(strip=True),
                                    "mean": val_cols[2].get_text(strip=True), "sd": val_cols[3].get_text(strip=True),
                                    "S": val_cols[4].get_text(strip=True), "A": val_cols[5].get_text(strip=True),
                                    "B": val_cols[6].get_text(strip=True), "C": val_cols[7].get_text(strip=True),
                                    "D": val_cols[8].get_text(strip=True), "E": val_cols[9].get_text(strip=True),
                                    "F": val_cols[10].get_text(strip=True)
                                }
                    elif "mark title" in text and "scored mark" in text:
                        comp = {"class_number": "N/A", "course_type": "N/A", "marks": [], "total": "0.0"}
                        parent_text = tbl.parent.get_text(" ", strip=True)
                        m1 = re.search(r"Class Number\s*:\s*([A-Z0-9]+)", parent_text, re.IGNORECASE)
                        if m1: comp["class_number"] = m1.group(1).strip()
                        m2 = re.search(r"Course Type\s*:\s*(.*?)(?=Sl\.?No|Max\.? Mark|$)", parent_text, re.IGNORECASE)
                        if m2: comp["course_type"] = m2.group(1).replace("Sl", "").replace("No", "").replace(".", "").strip()

                        total_wgt, explicit_total = 0.0, None
                        for c_tr in tbl.find_all('tr'):
                            c_cols = c_tr.find_all(['td', 'th'])
                            if not c_cols: continue
                            row_txt, c_sl_no = c_tr.get_text(" ", strip=True).lower(), c_cols[0].get_text(strip=True)
                            
                            if c_sl_no.isdigit() and len(c_cols) >= 6:
                                if not c_cols[1].get_text(strip=True).replace('.', '', 1).isdigit():
                                    wgt_mark = c_cols[6].get_text(strip=True) if len(c_cols) > 6 else "-"
                                    try: total_wgt += float(wgt_mark)
                                    except: pass
                                    comp["marks"].append({
                                        "mark_title": c_cols[1].get_text(strip=True), "max_mark": c_cols[2].get_text(strip=True),
                                        "weightage_pct": c_cols[3].get_text(strip=True) if len(c_cols) > 3 else "-",
                                        "status": c_cols[4].get_text(strip=True) if len(c_cols) > 4 else "-",
                                        "scored_mark": c_cols[5].get_text(strip=True) if len(c_cols) > 5 else "-",
                                        "weightage_mark": wgt_mark
                                    })
                            elif "total" in row_txt and "grand" not in row_txt and not c_sl_no.isdigit():
                                tot = c_cols[-1].get_text(strip=True)
                                if tot.replace('.', '', 1).isdigit(): explicit_total = tot

                        comp["total"] = explicit_total if explicit_total else f"{total_wgt:.2f}"
                        if comp["marks"]: current_course["components"].append(comp)

        return [c for c in expanded_courses if c["stats"] or c["components"]]
    except Exception as e:
        print(f"   [!] Grade details fetch error: {e}")
        return []

async def fetchExamSchedule(client, semester_id):
    url = "https://vtop.vitap.ac.in/vtop/examinations/doSearchExamScheduleForStudent"
    try:
        payload = {"semesterSubId": semester_id, "authorizedID": get_auth_id(client), "_csrf": getattr(client, "csrf_token", ""), "nocache": "@(new Date().getTime())"}
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

        exam_data, current_category = [], "FAT" 
        for row in table.find_all('tr'):
            cols = row.find_all('td')
            text = row.get_text(strip=True)
            if len(cols) == 1:
                if cols[0].get_text(strip=True) in ["FAT", "CAT1", "CAT2"]:
                    current_category = cols[0].get_text(strip=True)
                    continue
            if "Course Code" in text or "S.No." in text or not cols or not cols[0].get_text(strip=True).isdigit(): continue
            def get_col(idx): return cols[idx].get_text(strip=True) if len(cols) > idx else "-"
            exam_data.append({
                "category": current_category, "course_code": get_col(1), "course_title": get_col(2), "exam_type": get_col(3),
                "class_id": get_col(4), "slot": get_col(5), "exam_date": get_col(6), "session": get_col(7),
                "exam_time": get_col(9), "venue": get_col(10), "seat_location": get_col(11), "seat_number": get_col(12)
            })
        return exam_data
    except Exception as e:
        print(f"   [!] fetchExamSchedule Error: {e}")
        return []

async def fetchAttendance(client: VtopClient, semesterId: str) -> List[Dict[str, Any]]:
    url = "https://vtop.vitap.ac.in/vtop/processViewStudentAttendance"
    try:
        payload = {"semesterSubId": semesterId, "authorizedID": get_auth_id(client), "_csrf": getattr(client, "csrf_token", ""), "nocache": "@(new Date().getTime())"}
        headers = { "X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content" }
        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'id': 'AttendanceDetailDataTable'})
        if not table: return []

        attendance_data = []
        for row in table.find_all('tr')[1:]:
            cols = row.find_all('td')
            if len(cols) < 8: continue
            raw_course, slot, faculty_name = cols[2].get_text(strip=True), cols[3].get_text(strip=True), cols[4].get_text(strip=True)
            view_btn, course_id, type_code = row.find('a', onclick=True), None, None
            if view_btn:
                match = re.search(r"Display\('[^']+',\s*'[^']+',\s*'([^']+)',\s*'([^']+)'\)", view_btn['onclick'])
                if match: course_id, type_code = match.group(1), match.group(2)

            attendance_data.append({
                'course_code': raw_course.split(' - ')[0], 'course_name': raw_course, 'course_type': raw_course.split(' - ')[-1],
                'percentage': cols[7].get_text(strip=True).replace("%", ""), 'attended': cols[5].get_text(strip=True),
                'total': cols[6].get_text(strip=True), 'slot': slot, 'faculty_name': faculty_name,
                'course_id': course_id, 'type_code': type_code
            })
        return attendance_data
    except Exception as e:
        print(f"   [!] fetchAttendance Error: {e}")
        return []

async def fetchAttendanceDetail(client: VtopClient, semesterId: str, courseId: str, courseType: str):
    url = "https://vtop.vitap.ac.in/vtop/processViewAttendanceDetail"
    try:
        reg_no = get_auth_id(client)
        headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content"}
        payload = {
            "_csrf": getattr(client, "csrf_token", ""), "semesterSubId": semesterId, "registerNumber": reg_no,
            "courseId": courseId, "courseType": courseType, "authorizedID": reg_no,
            "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        }

        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'id': 'StudentAttendanceDetailDataTable'})
        if not table: return []

        history = []
        for row in table.find('tbody').find_all('tr'):
            cols = row.find_all('td')
            if len(cols) < 5: continue
            raw_date = cols[1].get_text(strip=True)
            try: date_val = dt.strptime(raw_date, "%d-%b-%Y").strftime("%d-%b")
            except: date_val = raw_date
            history.append({'date': date_val, 'slot': cols[2].get_text(strip=True), 'status': cols[4].get_text(strip=True)})
        return history
    except Exception as e:
        print(f"   [!] Detail fetch error: {e}")
        return []

async def fetchGradeHistory(client: VtopClient) -> Dict[str, Any]:
    url = "https://vtop.vitap.ac.in/vtop/examinations/examGradeView/StudentGradeHistory"
    try:
        payload = {"verifyMenu": "true", "authorizedID": get_auth_id(client), "_csrf": getattr(client, "csrf_token", ""), "nocache": f"@{int(time.time() * 1000)}"}
        headers = {"X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content?"}

        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        history = {"courses": [], "summary": {"cgpa": "0.0", "earned": "0.0", "registered": "0.0"}}
        seen_codes = set()

        for table in soup.find_all('table'):
            if "course code" in table.get_text().lower():
                for row in table.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) >= 6:
                        code = cols[1].get_text(strip=True)
                        if re.match(r'^[A-Z]{3,}\d{3,}', code) and code not in seen_codes:
                            history["courses"].append({
                                "code": code, "name": cols[2].get_text(strip=True), "credits": cols[4].get_text(strip=True), "grade": cols[5].get_text(strip=True)
                            })
                            seen_codes.add(code)
                break
        
        for table in soup.find_all('table'):
            if "credits registered" in table.get_text().lower():
                tr = table.find('tbody').find('tr') if table.find('tbody') else None
                if tr:
                    tds = tr.find_all('td')
                    if len(tds) >= 3:
                        history["summary"]["registered"], history["summary"]["earned"], history["summary"]["cgpa"] = tds[0].get_text(strip=True), tds[1].get_text(strip=True), tds[2].get_text(strip=True)
                break
        return history
    except Exception:
        return history

async def fetchCredits(client):
    url = "https://vtop.vitap.ac.in/vtop/academics/common/CreditsDistributionDetails"
    try:
        reg_no = get_auth_id(client)
        payload = {"registerNumber": reg_no, "authorizedID": reg_no, "_csrf": getattr(client, "csrf_token", ""), "x": "@(new Date().toUTCString())"}
        headers = { "X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content" }

        print("   [+] Fetching Credit Summary...")
        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        main_table = soup.find('table', class_='table table-hover table-bordered')
        if not main_table: return []

        credits_data = []
        for row in main_table.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 4 and cols[0].get_text(strip=True).replace('.', '').isdigit():
                cat_name, total_str, earned_str = cols[1].get_text(strip=True), cols[2].get_text(strip=True), cols[3].get_text(strip=True)
                if earned_str == "-": earned_str = "0"
                try: total, earned, percent = float(total_str), float(earned_str), (float(earned_str) / float(total_str) * 100) if float(total_str) > 0 else 0
                except: total, earned, percent = 0, 0, 0
                credits_data.append({"category": cat_name, "total": total, "earned": earned, "percent": percent})
        return credits_data
    except Exception as e:
        print(f"   [!] fetchCredits Error: {e}")
        return []

async def fetchCourseList(client, semester_id):
    url = "https://vtop.vitap.ac.in/vtop/getCourseForCoursePage"
    try:
        payload = {"_csrf": getattr(client, "csrf_token", ""), "authorizedID": get_auth_id(client), "semSubId": semester_id, "paramReturnId": "getCourseForCoursePage", "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())}
        headers = { "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8" }
        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        courses = []
        for opt in soup.find_all('option'):
            class_id, text = opt.get('value'), opt.get_text(strip=True)
            if not class_id or "Select" in text: continue
            parts = text.split(' - ')
            courses.append({"code": parts[0].strip(), "title": parts[1].strip() if len(parts) > 1 else text, "type": parts[-1].strip() if len(parts) > 2 else "TH", "generic_class_id": class_id, "full_text": text})
        return courses
    except Exception as e:
        print(f"   [!] fetchCourseList Error: {e}")
        return []

async def fetchCourseClasses(client, semester_id, generic_class_id):
    url = "https://vtop.vitap.ac.in/vtop/getSlotIdForCoursePage"
    try:
        payload = {"_csrf": getattr(client, "csrf_token", ""), "classId": generic_class_id, "praType": "source", "paramReturnId": "getSlotIdForCoursePage", "semSubId": semester_id, "authorizedID": get_auth_id(client), "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())}
        headers = { "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8" }
        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        classes, table = [], soup.find('table')
        if not table: return []

        for row in table.find_all('tr')[1:]:
            cols = row.find_all('td')
            if len(cols) >= 9:
                faculty = cols[7].get_text(strip=True)
                match = re.search(r"'(\d{4,6})'", str(row))
                erp_id = match.group(1) if match else (re.search(r"(\d{4,6})", faculty).group(1) if re.search(r"(\d{4,6})", faculty) else "")
                classes.append({"course_type": cols[4].get_text(strip=True), "class_id": cols[5].get_text(strip=True), "slot": cols[6].get_text(strip=True), "faculty": faculty, "erp_id": erp_id})
        return classes
    except Exception as e:
        print(f"   [!] fetchCourseClasses Error: {e}")
        return []

async def fetchCoursePage(client, semester_id, class_id, erp_id):
    url = "https://vtop.vitap.ac.in/vtop/processViewStudentCourseDetail"
    try:
        payload = {"_csrf": getattr(client, "csrf_token", ""), "semSubId": semester_id, "erpId": erp_id, "classId": class_id, "authorizedID": get_auth_id(client), "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())}
        headers = { "X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8" }
        response = await client._client.post(url, data=payload, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        data = { "metadata": {}, "general": [], "lectures": [] }
        meta_table = next((t for t in soup.find_all('table') if "Class Group" in t.get_text()), None)
        if meta_table:
            rows = meta_table.find_all('tr')
            if len(rows) > 1 and len(rows[1].find_all('td')) >= 7:
                cols = rows[1].find_all('td')
                data["metadata"] = {"code": cols[1].get_text(strip=True), "title": cols[2].get_text(strip=True), "type": cols[3].get_text(strip=True), "slot": cols[5].get_text(strip=True), "faculty": cols[6].get_text(strip=True)}

        for tr in soup.find_all('tr'):
            cols = tr.find_all('td')
            if not cols: continue
            first_col_text = cols[0].get_text(strip=True)

            if "Syllabus" in first_col_text or "Reference Material" in first_col_text:
                if len(cols) >= 2:
                    anchor = cols[1].find('a', href=True)
                    if anchor:
                        match = re.search(r"vtopDownload\((?:'|&#39;)(.*?)(?:'|&#39;)\)", anchor['href'])
                        if match: data["general"].append({"title": cols[1].get_text(strip=True).replace("Download", "").strip() or first_col_text, "download_path": match.group(1)})

            elif first_col_text.isdigit() and len(cols) >= 5:
                raw_date = cols[1].get_text(strip=True)
                date_match = re.search(r"\[(.*?)\]", raw_date)
                main_path, ref_paths, web_links = None, [], []

                for a in cols[4].find_all('a'):
                    href, link_text = a.get('href', ''), a.get_text(strip=True).upper()
                    if 'javascript:vtopDownload' in href:
                        match = re.search(r"vtopDownload\((?:'|&#39;)(.*?)(?:'|&#39;)\)", href)
                        if match:
                            path = match.group(1)
                            if "REFERENCE" in link_text or "REF" in link_text: ref_paths.append(path)
                            elif not main_path: main_path = path 
                            else: ref_paths.append(path) 
                    elif href.startswith('http'): web_links.append(href)

                data["lectures"].append({
                    "s_no": int(first_col_text), "date": date_match.group(1) if date_match else raw_date.split('[')[0],
                    "day": cols[2].get_text(strip=True), "topic": cols[3].get_text(strip=True),
                    "download_path": main_path, "ref_paths": ref_paths, "web_links": web_links
                })

        return data
    except Exception as e:
        print(f"   [!] fetchCoursePage Error: {e}")
        return {"metadata": {}, "general": [], "lectures": []}

async def download_course_material(client, url_suffix, folder_path, base_filename):
    from rich.progress import Progress, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
    clean_path = url_suffix.lstrip('/')
    test_urls = [f"https://vtop.vitap.ac.in/vtop/{clean_path}", f"https://vtop.vitap.ac.in/vtop/academics/common/{clean_path}"]
    payload = {"authorizedID": get_auth_id(client), "_csrf": getattr(client, "csrf_token", "")}
    headers = { "Content-Type": "application/x-www-form-urlencoded", "Referer": "https://vtop.vitap.ac.in/vtop/content", "User-Agent": "Mozilla/5.0" }

    for method, target_url in [("POST", test_urls[0]), ("GET", test_urls[0]), ("POST", test_urls[1]), ("GET", test_urls[1])]:
        try:
            kwargs = {"headers": headers, "follow_redirects": True, **({"data": payload} if method == "POST" else {"params": payload})}
            async with client._client.stream(method, target_url, **kwargs) as response:
                if response.status_code != 200: continue
                iterator = response.aiter_bytes(8192)
                try: first_chunk = await iterator.__anext__()
                except StopAsyncIteration: continue
                if len(first_chunk) < 100 or b"<html" in first_chunk[:100].lower() or b"page-holder" in first_chunk[:500].lower(): continue 
                    
                ext = ".pdf"
                cd = response.headers.get("Content-Disposition", "")
                if "filename=" in cd:
                    match = re.search(r'filename="?([^";]+)"?', cd)
                    if match: ext = os.path.splitext(match.group(1))[1].lower() or ext
                        
                magic = first_chunk[:4]
                if magic.startswith(b'%PDF'): ext = ".pdf"
                elif magic.startswith(b'PK\x03\x04'): ext = ".zip" if ext not in [".docx", ".pptx", ".xlsx", ".zip"] else ext
                elif magic.startswith(b'\xd0\xcf\x11\xe0'): ext = ".doc" if ext not in [".doc", ".ppt", ".xls"] else ext
                elif magic.startswith(b'\x89PNG'): ext = ".png"
                elif first_chunk[:3] == b'\xff\xd8\xff': ext = ".jpg"
                
                os.makedirs(folder_path, exist_ok=True)
                safe_filename = re.sub(r'[\\/*?:"<>|]', "", base_filename).strip() or "downloaded_material"
                final_path = os.path.join(folder_path, f"{safe_filename}{ext}")
                total_size = int(response.headers.get("Content-Length", 0))
                
                with Progress(TextColumn("   [cyan]{task.description}"), BarColumn(complete_style="green"), DownloadColumn(), TransferSpeedColumn(), TimeRemainingColumn(), transient=True) as progress:
                    task_id = progress.add_task(safe_filename[:25] + ".." if len(safe_filename) > 25 else safe_filename, total=total_size or None)
                    with open(final_path, 'wb') as f:
                        f.write(first_chunk)
                        if total_size: progress.update(task_id, advance=len(first_chunk))
                        async for chunk in iterator:
                            f.write(chunk)
                            if total_size: progress.update(task_id, advance=len(chunk))
                return True, final_path
        except Exception: pass
    return False, "Failed: VTOP blocked the request or the file no longer exists."

async def fetchGeneralOuting(client):
    url = "https://vtop.vitap.ac.in/vtop/hostel/StudentGeneralOuting"
    try:
        payload = {"verifyMenu": "true", "authorizedID": get_auth_id(client), "_csrf": getattr(client, "csrf_token", ""), "nocache": int(round(time.time() * 1000))}
        response = await client._client.post(url, data=payload, headers={"X-Requested-With": "XMLHttpRequest"})
        soup = BeautifulSoup(response.text, 'html.parser')
        if "Login" in response.text: return None

        def get_val(name):
            inp = soup.find('input', {'name': name})
            return inp.get('value', '').strip() if inp else ''

        info = {'name': get_val('name'), 'hostelBlock': get_val('hostelBlock'), 'roomNo': get_val('roomNo'), 'mobileNo': get_val('mobileNo')}
        history, table = [], soup.find('table', {'id': 'BookingRequests'})
        
        if table:
            for tr in table.find_all('tr')[1:]:
                cols = tr.find_all('td')
                if len(cols) >= 10:
                    try: sort_obj = dt.strptime(cols[4].get_text(strip=True).split('.')[0], "%Y-%m-%d %H:%M:%S")
                    except: sort_obj = dt.min
                    btn = cols[8].find('button')
                    anchor = cols[10].find('a') if len(cols) > 10 else None

                    history.append({
                        "place": cols[2].get_text(strip=True), "purpose": cols[3].get_text(strip=True),
                        "out_date": sort_obj.strftime("%d-%b-%Y") if sort_obj != dt.min else cols[4].get_text(strip=True)[:10],
                        "out_time": cols[5].get_text(strip=True),
                        "in_date": dt.strptime(cols[6].get_text(strip=True).split('.')[0], "%Y-%m-%d %H:%M:%S").strftime("%d-%b-%Y") if "." in cols[6].get_text(strip=True) else cols[6].get_text(strip=True)[:10],
                        "in_time": cols[7].get_text(strip=True),
                        "status": cols[9].get_text(strip=True),
                        "booking_id": btn.get('data-bookingid') if btn else None,
                        "download_url": anchor['data-url'] if anchor and anchor.has_attr('data-url') else None,
                        "sort_date": sort_obj 
                    })
        history.sort(key=lambda x: x['sort_date'], reverse=True)
        return {"info": info, "history": history}
    except Exception as e:
        print(f"   [!] fetchOutingMetadata Error: {e}")
        return None
        
async def download_g_outpass(client, url_suffix, filename):
    url = f"https://vtop.vitap.ac.in/{url_suffix.lstrip('/')}"
    try:
        payload = {"authorizedID": get_auth_id(client), "_csrf": getattr(client, "csrf_token", ""), "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())}
        response = await client._client.post(url, data=payload, headers={ "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8" })
        if response.status_code == 200 and ("application/pdf" in response.headers.get("Content-Type", "") or b"%PDF" in response.content[:10]):
            with open(filename, 'wb') as f: f.write(response.content)
            return True, f"Saved as {filename}"
        return False, "Failed to fetch PDF."
    except Exception as e:
        return False, str(e)

async def submitGeneralOuting(client, meta_info, place, purpose, out_date, out_time, in_date, in_time):
    url = "https://vtop.vitap.ac.in/vtop/hostel/saveGeneralOutingForm"
    try:
        oh, om = [x.zfill(2) for x in out_time.split(':')]
        ih, im = [x.zfill(2) for x in in_time.split(':')]
    except: return False, "Invalid Time Format. Use HH:MM"

    try:
        payload = {
            "authorizedID": get_auth_id(client), "LeaveId": "", "regNo": get_auth_id(client), "name": meta_info.get('name', ''),
            "applicationNo": meta_info.get('applicationNo', ''), "gender": meta_info.get('gender', ''), "hostelBlock": meta_info.get('hostelBlock', ''),
            "roomNo": meta_info.get('roomNo', ''), "placeOfVisit": place, "purposeOfVisit": purpose,
            "outDate": out_date, "outTimeHr": oh, "outTimeMin": om, "inDate": in_date, "inTimeHr": ih, "inTimeMin": im,
            "_csrf": getattr(client, "csrf_token", ""), "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        }
        response = await client._client.post(url, data=payload, files={'upload_file': (None, '')}, headers={"X-Requested-With": "XMLHttpRequest"})
        soup = BeautifulSoup(response.text, 'html.parser')
        success_inp, error_inp = soup.find('input', {'id': 'success'}), soup.find('input', {'id': 'jsonBom'})
        if success_inp and success_inp.get('value'): return True, success_inp.get('value').strip()
        if error_inp and error_inp.get('value'): return False, error_inp.get('value').strip()
        return True, "Leave Applied Successfully" if "leave applied successfully" in soup.get_text().lower() else (False, "Unknown Error")
    except Exception as e: return False, str(e)

async def deleteGeneralOuting(client, booking_id):
    url = "https://vtop.vitap.ac.in/vtop/hostel/deleteGeneralOutingInfo"
    try:
        payload = {"_csrf": getattr(client, "csrf_token", ""), "LeaveId": booking_id, "authorizedID": get_auth_id(client), "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())}
        response = await client._client.post(url, data=payload, headers={"X-Requested-With": "XMLHttpRequest"})
        return (True, "Deleted Successfully") if response.status_code == 200 else (False, "Delete Failed")
    except Exception as e: return False, str(e)

async def fetchWeekendOuting(client):
    url = "https://vtop.vitap.ac.in/vtop/hostel/StudentWeekendOuting"
    try:
        reg_no = get_auth_id(client)
        response = await client._client.post(url, data={"authorizedID": reg_no, "_csrf": getattr(client, "csrf_token", "")}, headers={"X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content"})
        if response.status_code != 200: return None
        soup = BeautifulSoup(response.text, 'html.parser')
        
        can_apply = False if soup.find('input', {'id': 'jsonBom'}) and soup.find('input', {'id': 'jsonBom'}).get('value') else True
        history, info = [], {'name': reg_no, 'hostelBlock': 'N/A', 'roomNo': 'N/A'}
        table = soup.find('table', {'id': 'BookingRequests'})
        if table and table.find('tbody'):
            for row in table.find('tbody').find_all('tr'):
                cols = row.find_all('td')
                if len(cols) >= 11:
                    if info['hostelBlock'] == 'N/A': info['hostelBlock'], info['roomNo'] = cols[2].get_text(strip=True), cols[3].get_text(strip=True)
                    delete_btn = cols[8].find('button') or cols[8].find('a')
                    booking_id = (delete_btn.get('data-bookingid') or delete_btn.get('data-booking-id')) if delete_btn else (re.search(r"(W\d{8,})", str(cols[8])).group(1) if re.search(r"(W\d{8,})", str(cols[8])) else None)
                    btn = cols[10].find('a', {'data-leave-url': True})
                    
                    history.append({
                        "block": cols[2].get_text(strip=True), "room": cols[3].get_text(strip=True), "place": cols[4].get_text(strip=True),
                        "purpose": cols[5].get_text(strip=True), "out_time": cols[6].get_text(strip=True), "out_date": cols[7].get_text(strip=True),
                        "booking_id": booking_id, "status": cols[9].get_text(strip=True).replace("Outing Request", "").strip(),
                        "download_link": btn['data-leave-url'] if btn else None
                    })
        return {"info": info, "can_apply": can_apply, "history": history}
    except Exception as e:
        print(f"   [!] Outing fetch error: {e}")
        return None

async def deleteWeekendOuting(client, booking_id):
    url = "https://vtop.vitap.ac.in/vtop/hostel/deleteBookingInfo"
    try:
        payload = {"BookingId": booking_id, "authorizedID": get_auth_id(client), "_csrf": getattr(client, "csrf_token", ""), "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())}
        res = await client._client.post(url, data=payload, headers={"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded"})
        return (True, "Deleted Successfully.") if res.status_code == 200 else (False, "Server rejected deletion.")
    except Exception as e: return False, str(e)

async def submitWeekendOuting(client, info, place, purpose, out_d, out_t, contact):
    try:
        current_user, csrf = get_auth_id(client), getattr(client, "csrf_token", "")
        form_res = await client._client.post("https://vtop.vitap.ac.in/vtop/hostel/StudentWeekendOuting", data={"authorizedID": current_user, "_csrf": csrf}, headers={"X-Requested-With": "XMLHttpRequest", "Referer": "https://vtop.vitap.ac.in/vtop/content"})
        soup = BeautifulSoup(form_res.text, 'html.parser')

        def get_val(field_name):
            elem = soup.find('input', {'id': field_name}) or soup.find('input', {'name': field_name})
            return elem.get('value', '') if elem else ''

        profile_data = { "name": get_val("name"), "applicationNo": get_val("applicationNo"), "gender": get_val("gender"), "hostelBlock": get_val("hostelBlock"), "roomNo": get_val("roomNo"), "parentContactNumber": get_val("parentContactNumber") }
        if not profile_data.get("applicationNo"): return False, "Failed to scrape hidden profile data from VTOP."
            
        multipart_payload = {
            "authorizedID": (None, current_user), "BookingId": (None, ""), "regNo": (None, current_user), "name": (None, profile_data.get('name', '')),
            "applicationNo": (None, profile_data.get('applicationNo', '')), "gender": (None, profile_data.get('gender', '')),
            "hostelBlock": (None, profile_data.get('hostelBlock', '')), "roomNo": (None, profile_data.get('roomNo', '')),
            "outPlace": (None, place), "purposeOfVisit": (None, purpose), "outingDate": (None, out_d), "outTime": (None, out_t),
            "contactNumber": (None, contact), "parentContactNumber": (None, profile_data.get('parentContactNumber', '')),
            "_csrf": (None, csrf), "x": (None, time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime()))
        }
            
        print("   [.] Sending Dynamic Payload...")
        res_submit = await client._client.post("https://vtop.vitap.ac.in/vtop/hostel/saveOutingForm", files=multipart_payload, headers={"X-Requested-With": "XMLHttpRequest", "Origin": "https://vtop.vitap.ac.in", "Referer": "https://vtop.vitap.ac.in/vtop/content?", "User-Agent": "Mozilla/5.0"})
        submit_soup = BeautifulSoup(res_submit.text, 'html.parser')
        error_msg, success_msg = submit_soup.find('input', {'id': 'jsonBom'}), submit_soup.find('input', {'id': 'success'})
        
        if error_msg and error_msg.get('value'): return False, error_msg['value']
        if success_msg and success_msg.get('value'): return True, success_msg['value']
        if "Outing Request Accepted" in res_submit.text or "Successfully" in res_submit.text: return True, "Weekend Outing Applied Successfully."
        return False, "Failed. Server did not return a success message."
    except Exception as e: return False, f"Submission Error: {str(e)}"

async def download_w_outpass(client, url_suffix, folder_path, base_filename):
    url = f"https://vtop.vitap.ac.in/{url_suffix.lstrip('/') if not url_suffix.lstrip('/').startswith('vtop/') else url_suffix.lstrip('/')}"
    try:
        payload = {"authorizedID": get_auth_id(client), "_csrf": getattr(client, "csrf_token", "")}
        response = await client._client.post(url, data=payload, headers={ "Content-Type": "application/x-www-form-urlencoded", "Referer": "https://vtop.vitap.ac.in/vtop/hostel/StudentWeekendOuting", "Origin": "https://vtop.vitap.ac.in", "User-Agent": "Mozilla/5.0" })
        if response.status_code == 200:
            if b"%PDF" in response.content[:100]:
                os.makedirs(folder_path, exist_ok=True)
                final_path = os.path.join(folder_path, f"{base_filename}.pdf")
                with open(final_path, 'wb') as f: f.write(response.content)
                return True, final_path
            return False, "VTOP returned an invalid file format."
        return False, f"HTTP {response.status_code}"
    except Exception as e: return False, str(e)

async def fetchDACourseList(client, sem_id):
    try:
        payload = {"semesterSubId": sem_id, "authorizedID": get_auth_id(client), "_csrf": getattr(client, "csrf_token", ""), "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())}
        res = await client._client.post("https://vtop.vitap.ac.in/vtop/examinations/doDigitalAssignment", data=payload, headers={"X-Requested-With": "XMLHttpRequest"})
        soup = BeautifulSoup(res.text, 'html.parser')
        courses, table = [], soup.find('table', class_='customTable')
        if table:
            for row in table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) >= 6: courses.append({"class_id": cols[1].get_text(strip=True), "code": cols[2].get_text(strip=True), "title": cols[3].get_text(strip=True), "type": cols[4].get_text(strip=True), "faculty": cols[5].get_text(strip=True)})
        return courses
    except Exception as e:
        print(f"   [!] Error fetching DA courses: {e}")
        return []

async def fetchDADetails(client, class_id):
    try:
        payload = {"classId": class_id, "authorizedID": get_auth_id(client), "_csrf": getattr(client, "csrf_token", ""), "x": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())}
        res = await client._client.post("https://vtop.vitap.ac.in/vtop/examinations/processDigitalAssignment", data=payload, headers={"X-Requested-With": "XMLHttpRequest"})
        soup = BeautifulSoup(res.text, 'html.parser')
        assignments, tables = [], soup.find_all('table', class_='customTable')
        if len(tables) > 1:
            for row in tables[1].find_all('tr'):
                cols = row.find_all('td')
                if len(cols) >= 9 and cols[0].get_text(strip=True).isdigit():
                    qp_a, sub_a, qp_id, da_id = cols[5].find('a'), cols[8].find('a'), None, None
                    if qp_a and 'href' in qp_a.attrs:
                        match = re.search(r"vtopDownload\((?:'|&#39;)(.*?)(?:'|&#39;)\)", qp_a['href'])
                        if match: qp_id = match.group(1)
                    if sub_a and 'href' in sub_a.attrs:
                        match = re.search(r"vtopDownload\((?:'|&#39;)(.*?)(?:'|&#39;)\)", sub_a['href'])
                        if match: da_id = match.group(1)

                    assignments.append({
                        "serial_number": cols[0].get_text(strip=True), "assignment_title": cols[1].get_text(strip=True), "max_mark": cols[2].get_text(strip=True),
                        "weightage": cols[3].get_text(strip=True), "due_date": cols[4].get_text(strip=True), "can_qp_download": bool(qp_id),
                        "qp_id": qp_id or "", "submission_status": cols[6].get_text(strip=True), "can_da_download": bool(da_id), "da_id": da_id or ""
                    })
        return assignments
    except Exception as e:
        print(f"   [!] Error fetching DA details: {e}")
        return []

async def fetch_calendar_months(client, semester_id: str) -> list:
    import re, time
    from bs4 import BeautifulSoup
    base_url = "https://vtop.vitap.ac.in/vtop"
    reg_no = get_auth_id(client)
    token = getattr(client, "csrf_token", "")
    headers = {'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://vtop.vitap.ac.in', 'Referer': 'https://vtop.vitap.ac.in/vtop/content?'}
    
    await client._client.post(f"{base_url}/academics/common/CalendarPreview", data={'verifyMenu': 'true', 'authorizedID': reg_no, '_csrf': token, 'nocache': '@(new Date().getTime())'}, headers=headers)
    res_months = await client._client.post(f"{base_url}/getDateForSemesterPreview", data={'_csrf': token, 'paramReturnId': 'getDateForSemesterPreview', 'semSubId': semester_id, 'authorizedID': reg_no, 'x': time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())}, headers=headers)
    
    soup = BeautifulSoup(res_months.text, 'html.parser')
    months, seen = [], set()
    for a in soup.find_all('a'):
        onclick = a.get('onclick', '')
        # Uses the precise quote-escaped regex to find the months[cite: 6]
        match = re.search(r"processViewCalendar\(\s*(?:'|&#39;)(.*?)(?:'|&#39;)\s*\)", onclick)
        if match:
            cal_date = match.group(1)
            if cal_date not in seen:
                label = a.get_text(strip=True) or cal_date
                months.append({'label': label, 'cal_date': cal_date})
                seen.add(cal_date)
    return months

async def fetch_calendar_view(client, semester_id: str, cal_date: str) -> list:
    import time
    from bs4 import BeautifulSoup
    base_url = "https://vtop.vitap.ac.in/vtop"
    reg_no = get_auth_id(client)
    token = getattr(client, "csrf_token", "")
    headers = {'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://vtop.vitap.ac.in', 'Referer': 'https://vtop.vitap.ac.in/vtop/content?'}
    
    # Passing classGroupId COMB for the standard academic calendar[cite: 6]
    payload = {'_csrf': token, 'calDate': cal_date, 'semSubId': semester_id, 'classGroupId': 'COMB', 'authorizedID': reg_no, 'x': time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())}
    res_cal = await client._client.post(f"{base_url}/processViewCalendar", data=payload, headers=headers)
    soup = BeautifulSoup(res_cal.text, 'html.parser')
    
    table = soup.select_one("table.calendar-table, table")
    days = []
    if not table: return days
    
    rows = table.find_all('tr')
    if len(rows) < 2: return days
    weekdays = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
    
    for row in rows[1:]:
        for i, cell in enumerate(row.find_all('td')):
            spans = cell.find_all('span')
            if not spans: continue
            day_num = spans[0].get_text(strip=True)
            if not day_num.isdigit(): continue
            
            events = [span.get_text(strip=True) for span in spans[1:] if span.get_text(strip=True)]
            days.append({'day': int(day_num), 'weekday': weekdays[i] if i < len(weekdays) else "", 'events': events})
            
    days.sort(key=lambda x: x['day'])
    return days

def generate_da_report(da_data):
    from colorama import Fore, Style
    if not da_data: return f"   {Fore.RED}[!] No Digital Assignment data available."

    result_msg = f"\n   {Fore.CYAN}" + "="*65 + "\n"
    result_msg += f"   {PEACH}{Style.BRIGHT}DIGITAL ASSIGNMENTS DASHBOARD\n"
    result_msg += f"   {Fore.CYAN}" + "="*65 + "\n\n"

    for course in da_data:
        assignments = course.get('assignments', [])
        pending, missed, submitted = 0, 0, 0
        for a in assignments:
            status = a['submission_status']
            if not status: pending += 1
            elif status == 'File Not Uploaded': missed += 1
            else: submitted += 1
            
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
            if not raw: ui_status = f"{PEACH}Pending (Still Open){Fore.WHITE}"
            elif raw == 'File Not Uploaded': ui_status = f"{Fore.RED}Missed (Deadline Passed){Fore.WHITE}"
            else: ui_status = f"{Fore.GREEN}Submitted on {raw}{Fore.WHITE}"

            qp_info = f"{Fore.GREEN}Available{Fore.WHITE}" if assign['can_qp_download'] else f"{Fore.RED}Not Posted{Fore.WHITE}"
            result_msg += f"{Fore.WHITE}{prefix} {assign['serial_number']}. {assign['assignment_title']} (Due: {assign['due_date']})\n"
            result_msg += f"{Fore.WHITE}{inner}├ Marks  : {assign['weightage']} / {assign['max_mark']} weightage\n"
            result_msg += f"{Fore.WHITE}{inner}├ QP     : {qp_info}\n"
            result_msg += f"{Fore.WHITE}{inner}└ Status : {ui_status}\n"
        result_msg += "\n"
    return result_msg

async def fetch_academic_calendar_holidays(client, semester_id: str) -> dict:
    import re
    import time
    from bs4 import BeautifulSoup

    base_url = "https://vtop.vitap.ac.in/vtop"
    reg_no = get_auth_id(client)
    token = getattr(client, "csrf_token", "")
    headers = {
        'X-Requested-With': 'XMLHttpRequest', 
        'Origin': 'https://vtop.vitap.ac.in', 
        'Referer': 'https://vtop.vitap.ac.in/vtop/content?'
    }

    await client._client.post(
        f"{base_url}/academics/common/CalendarPreview",
        data={'verifyMenu': 'true', 'authorizedID': reg_no, '_csrf': token, 'nocache': '@(new Date().getTime())'},
        headers=headers
    )

    res_months = await client._client.post(
        f"{base_url}/getDateForSemesterPreview",
        data={
            '_csrf': token, 
            'paramReturnId': 'getDateForSemesterPreview', 
            'semSubId': semester_id, 
            'authorizedID': reg_no,
            'x': time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        },
        headers=headers
    )

    month_dates = re.findall(r"processViewCalendar\(\s*(?:'|&#39;)(.*?)(?:'|&#39;)\s*\)", res_months.text)
    
    blocked_dates = {}
    month_map = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}

    for cal_date in set(month_dates):
        parts = cal_date.split('-')
        if len(parts) != 3: continue
        month_num = month_map.get(parts[1].upper())
        if not month_num: continue
        
        payload = {
            '_csrf': token, 'calDate': cal_date, 'semSubId': semester_id,
            'classGroupId': 'COMB', 'authorizedID': reg_no,
            'x': time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        }
        res_cal = await client._client.post(f"{base_url}/processViewCalendar", data=payload, headers=headers)
        soup = BeautifulSoup(res_cal.text, 'html.parser')
        
        table = soup.select_one("table.calendar-table, table")
        if not table: continue

        rows = table.find_all('tr')
        if len(rows) < 2: continue

        for row in rows[1:]:
            for cell in row.find_all('td'):
                spans = cell.find_all('span')
                if not spans: continue
                
                day_str = spans[0].get_text(strip=True)
                if not day_str.isdigit(): continue
                
                is_holiday = False
                combined_text = " ".join(span.get_text(strip=True).lower() for span in spans[1:])
                
                blocked_keywords = [
                    "holiday", "no instructional", "non instructional", 
                    "exam days", "cat -", "cat-", "final assessment test"
                ]
                
                if "lab fat" in combined_text and "exam days" not in combined_text:
                    is_holiday = False
                elif any(kw in combined_text for kw in blocked_keywords):
                    is_holiday = True
                        
                if is_holiday:
                    # Save the clean name of the holiday/exam so the predictor can tell you why it skipped it
                    clean_name = spans[1].get_text(strip=True) if len(spans) > 1 else "Holiday / Exam"
                    blocked_dates[f"{int(day_str):02d}-{month_num:02d}"] = clean_name

    return blocked_dates

def simulate_absences(absence_dates, timetable_data, attendance_data, blocked_dates):
    import math
    from datetime import datetime as dt_obj, timedelta
    from colorama import Fore, Style

    if not absence_dates: return f"   {Fore.RED}[!] No valid dates provided."

    max_absence_date = max(absence_dates)
    if (max_absence_date - dt_obj.now()).days > 180:
        return f"\n   {Fore.RED}[!] HALT: Cannot simulate more than 6 months into the future.\n"

    absence_set = {dt_obj.strftime(dt, "%d-%m") for dt in absence_dates}
    sim_att, original_data, classes_missed = {}, {}, 0
    
    # Track which requested bunks are impossible because they fall on holidays/weekends
    ignored_bunks = {}
    for d in absence_set:
        if d in blocked_dates:
            ignored_bunks[d] = blocked_dates[d]

    for att in attendance_data:
        key = att['course_code'] + att['type_code']
        exact_date = att.get('exact_last_date')
        
        if exact_date:
            try: last_upd_dt = dt_obj.strptime(exact_date, "%d-%b-%Y").replace(hour=0, minute=0, second=0, microsecond=0)
            except ValueError:
                try: last_upd_dt = dt_obj.strptime(exact_date, "%d-%m-%Y").replace(hour=0, minute=0, second=0, microsecond=0)
                except ValueError: last_upd_dt = dt_obj.now().replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            last_upd_dt = dt_obj.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
        if last_upd_dt > dt_obj.now().replace(hour=0, minute=0, second=0, microsecond=0):
            last_upd_dt = dt_obj.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        val = {
            "code": att['course_code'], "type": att['type_code'], "attended": int(att['attended']), "total": int(att['total']),
            "current_pct": float(att['percentage']), "last_updated": last_upd_dt, "gap_classes": 0, "gap_breakdown": [], "missed_breakdown": []    
        }
        sim_att[key], original_data[key] = val.copy(), val.copy()
        
        curr_dt = last_upd_dt + timedelta(days=1)
        while curr_dt <= max_absence_date:
            day_name, date_str_full = curr_dt.strftime("%A"), curr_dt.strftime("%d-%m")
            
            # Skip if it's a scraped holiday or a weekend
            if date_str_full in blocked_dates or day_name in ["Saturday", "Sunday"]:
                if date_str_full in absence_set and date_str_full not in ignored_bunks and day_name in ["Saturday", "Sunday"]:
                    ignored_bunks[date_str_full] = "Weekend"
                curr_dt += timedelta(days=1)
                continue
            
            day_classes, course_happens_today, daily_penalty = timetable_data.get(day_name, []), False, 0
            for cls in day_classes:
                if cls['course_code'] == val['code'] and cls['course_type'] == val['type']:
                    course_happens_today = True
                    c_type = cls.get('course_type', '').upper()
                    daily_penalty += 2 if c_type in ['ELA', 'LO', 'PRACTICAL', 'LAB'] else 1
            
            if course_happens_today and daily_penalty > 0:
                if date_str_full in absence_set:
                    sim_att[key]['total'] += daily_penalty
                    classes_missed += daily_penalty
                    sim_att[key]['missed_breakdown'].append(f"{date_str_full} ({day_name[:3]}) : +{daily_penalty} missed")
                else:
                    sim_att[key]['total'] += daily_penalty
                    sim_att[key]['attended'] += daily_penalty
                    sim_att[key]['gap_classes'] += daily_penalty
                    sim_att[key]['gap_breakdown'].append(f"{date_str_full} ({day_name[:3]}) : +{daily_penalty}")
            curr_dt += timedelta(days=1)

    result_msg = f"\n   {Fore.CYAN}" + "="*60 + "\n"
    result_msg += f"   {PEACH}{Style.BRIGHT}SUBJECT-WISE ABSENCE PREDICTION\n"
    result_msg += f"   {Fore.CYAN}" + "="*60 + f"\n\n{Fore.WHITE}"
    
    # Print the explanation if the user tried to bunk an exam/holiday
    if ignored_bunks:
        result_msg += f"   {Fore.YELLOW}[i] Some dates were ignored because no classes are scheduled:\n"
        for date_val, reason in ignored_bunks.items():
            result_msg += f"       - {date_val} ({reason})\n"
        result_msg += "\n"
    
    impact_found = False
    for key in sim_att:
        curr, new = original_data[key], sim_att[key]
        if new['total'] > curr['total']:
            impact_found = True
            new_pct = (new['attended'] / new['total']) * 100
            alert = f" {Fore.RED}[DANGER]{Fore.WHITE}" if new_pct < 75 else ""
            upd_str = curr['last_updated'].strftime('%d-%m')
            
            result_msg += f"   {Fore.BLUE}[COURSE] {new['code']} ({new['type']})\n{Fore.WHITE}"
            result_msg += f"   ├ Current : {curr['current_pct']:.0f}% ({curr['attended']}/{curr['total']}) [Upd: {upd_str}]\n"
            
            if new['gap_classes'] > 0:
                result_msg += f"   ├ In-Between : {Fore.GREEN}+{new['gap_classes']} classes{Fore.WHITE} (Assuming 100% attendance)\n"
                for g_log in new['gap_breakdown']: result_msg += f"   │  ├ {g_log}\n"
            
            if new['missed_breakdown']:
                result_msg += f"   ├ Skipping :\n"
                for m_log in new['missed_breakdown']: result_msg += f"   │  ├ {Fore.RED}{m_log}{Fore.WHITE}\n"
                
            result_msg += f"   └ Projected: {PEACH if new_pct < 75 else Fore.GREEN}{new_pct:.0f}% ({new['attended']}/{new['total']}){alert}\n"
            
            if new_pct >= 75:
                safe_margin = math.floor(new['attended'] - 0.75 * new['total'])
                safe_str = "class" if safe_margin == 1 else "classes"
                result_msg += f"     └ You can safely miss {Fore.GREEN}{safe_margin}{Fore.WHITE} more {safe_str}.\n\n"
            else:
                needed = math.ceil((0.75 * new['total'] - new['attended']) / 0.25)
                attend_str = "class" if needed == 1 else "classes"
                result_msg += f"     └ Must attend next {Fore.RED}{needed}{Fore.WHITE} {attend_str}.\n\n"

    if not impact_found: result_msg += f"   {Fore.GREEN}[OK] No attendance changes detected for this timeframe.\n"
    else: result_msg += f"   {PEACH}Total attendance periods skipped: {classes_missed}"

    return result_msg

async def open_vtop_browser(client):
    import subprocess
    import sys
    import os
    import json
    from colorama import Fore

    vtop_cookies = []
    try:
        for cookie in client._client.cookies.jar:
            vtop_cookies.append({
                "name": cookie.name, "value": cookie.value, "domain": cookie.domain or "vtop.vitap.ac.in",
                "path": cookie.path or "/", "secure": cookie.secure, "httpOnly": False, "sameSite": "Lax"
            })
    except Exception as e:
        print(f"   {Fore.RED}[x] Could not extract session cookies: {e}")
        return

    if not vtop_cookies:
        print(f"   {Fore.RED}[x] No cookies found in session. Are you logged in?")
        return

    temp_dir = os.path.join(os.getcwd(), "cache")
    os.makedirs(temp_dir, exist_ok=True)
    
    cookies_file = os.path.join(temp_dir, "vtop_session_cookies.json")
    runner_file  = os.path.join(temp_dir, "vtop_browser_login.py")
    log_file     = os.path.join(temp_dir, "vtop_browser_log.txt")

    with open(cookies_file, "w", encoding="utf-8") as f:
        json.dump(vtop_cookies, f)

    print(f"   {Fore.CYAN}[.] Session cookies extracted ({len(vtop_cookies)} cookies). Launching browser...")

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
        user_data_dir = os.path.join({repr(temp_dir)}, "vtop_browser_session")
        os.makedirs(user_data_dir, exist_ok=True)

        try:
            context = await p.chromium.launch_persistent_context(user_data_dir, channel="chrome", headless=False, args=["--start-maximized"], no_viewport=True, ignore_https_errors=True)
        except Exception:
            browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
            context = await browser.new_context(no_viewport=True, ignore_https_errors=True)

        try:
            await context.add_cookies(cookies)
            print(f"[+] Injected {{len(cookies)}} session cookies.", flush=True)
        except Exception as e:
            print(f"[!] Cookie injection warning: {{e}}", flush=True)

        page = context.pages[0] if len(context.pages) > 0 else await context.new_page()

        async def handle_download(download):
            try:
                downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads", "VTOP_Browser_Downloads")
                os.makedirs(downloads_dir, exist_ok=True)
                final_path = os.path.join(downloads_dir, download.suggested_filename)
                print(f"\\n[.] Downloading: {{download.suggested_filename}}...", flush=True)
                await download.save_as(final_path)
                print(f"[+] Saved to: {{final_path}}", flush=True)
            except Exception as e:
                print(f"\\n[x] Download error: {{e}}", flush=True)

        page.on("download", handle_download)
        context.on("page", lambda new_page: new_page.on("download", handle_download))
        
        print("[.] Opening VTOP dashboard...", flush=True)
        try:
            await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"[x] Navigation failed: {{e}}", flush=True)

        try:
            await page.wait_for_selector("#vtopLink, .navbar, #quickLinkModalCenter", timeout=8000)
            print("[+] Dashboard loaded. Session is live.", flush=True)
        except Exception:
            current = page.url
            if "vtopLoginForm" in current or "login" in current.lower():
                print("[!] Session expired or cookies rejected. Falling back to manual login...", flush=True)
                try:
                    await page.goto("https://vtop.vitap.ac.in/vtop/", wait_until="domcontentloaded")
                    await page.wait_for_selector("#username", timeout=10000)
                    if {repr(getattr(client, "username", ""))}: await page.fill("#username", {repr(getattr(client, "username", ""))})
                    if {repr(getattr(client, "password", getattr(client, "_password", "")))}: await page.fill("#password", {repr(getattr(client, "password", getattr(client, "_password", "")))})
                    print("[!] Credentials pre-filled. Solve CAPTCHA manually, then click Sign In.", flush=True)
                except Exception as fe:
                    print(f"[x] Fallback also failed: {{fe}}", flush=True)
            else:
                print(f"[.] Loaded: {{current}}", flush=True)

        print("[.] Browser is open. Close it to exit.", flush=True)
        try:
            while True:
                if not context.pages: break
                await asyncio.sleep(2)
        except Exception: pass
        print("[.] Browser closed.", flush=True)

asyncio.run(run())
'''
    with open(runner_file, "w", encoding="utf-8") as f:
        f.write(runner_code)

    try:
        subprocess.Popen([sys.executable, "-u", runner_file], stdout=open(log_file, "w", encoding="utf-8"), stderr=subprocess.STDOUT, cwd=temp_dir)
        print(f"   {Fore.GREEN}[+] VTOP session launched — no login needed.")
        print(f"   {Fore.CYAN}[i] Log: {log_file}")
    except Exception as e:
        print(f"   {Fore.RED}[x] Failed to launch browser: {e}")


def get_cache_dir():
    import os
    # Get the exact folder where services.py (and vtop.py) is located
    base_dir = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(base_dir, "cache")
    os.makedirs(d, exist_ok=True)
    return d

def save_cache(name, data):
    try:
        with open(os.path.join(get_cache_dir(), f"{name}.json"), "w") as f:
            # Added indent=4 to pretty-print the JSON file
            json.dump({"ts": time.time(), "data": data}, f, indent=4)
    except: pass

def load_cache(name, max_hours=6):
    try:
        with open(os.path.join(get_cache_dir(), f"{name}.json"), "r") as f:
            c = json.load(f)
            if time.time() - c["ts"] <= max_hours * 3600:
                return c["data"]
    except: pass
    return None