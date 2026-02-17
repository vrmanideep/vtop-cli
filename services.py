import time
import os
import re
import sys
import asyncio
import httpx
from datetime import datetime as dt
from typing import List, Dict, Any, Tuple
from bs4 import BeautifulSoup
from vitap_vtop_client.client import VtopClient

def get_cred(file_path="credentials.txt"):
    """
    Reads username from line 1 and password from line 2.
    """
    try:
        with open(file_path, "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            
            if len(lines) < 2:
                print("[!] Error: credentials.txt must have at least 2 lines (User and Pass).")
                sys.exit(1)

            username = lines[0]
            password = lines[1]
            return username, password
            
    except FileNotFoundError:
        print(f"[!] Error: {file_path} not found.")
        sys.exit(1)

# Alias for compatibility
get_credentials = get_cred

# Global Creds (Used as fallback)
a, password = get_cred("credentials.txt")

# 🛠️ SSL BYPASS
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

async def fetchTimetable(client: VtopClient, semesterId: str) -> Dict[str, Any]:
    try:
        data = await client.get_timetable(sem_sub_id=semesterId)
        if hasattr(data, "model_dump"): return data.model_dump()
        return dict(data) if data else {}
    except Exception as e:
        print(f"   [!] Timetable fetch error: {e}")
        return {}

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
                valid_types = ["CAT", "FAT", "Assignment", "Digital", "Quiz", "Lab", "Project", "Mid-Term", "performance", "Classroom", "Experiment"]
                
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
    import re
    from bs4 import BeautifulSoup
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
                        
                    # Extract Booking ID for deletion
                    action_html = str(cols[8])
                    booking_id = None
                    b_match = re.search(r"deleteStudentBookingInfo\('([^']+)'\)", action_html)
                    if b_match: booking_id = b_match.group(1)
                        
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
                        "out_date": cols[7].get_text(strip=True), # Mapped to out_date to match UI
                        "booking_id": booking_id,
                        "status": cols[9].get_text(strip=True).replace("Outing Request", "").strip(),
                        "download_link": download_link
                    })
                    
        return {"info": info, "can_apply": can_apply, "history": history}
    except Exception as e:
        print(f"   [!] Outing fetch error: {e}")
        return None
                    
        return {"info": info, "can_apply": can_apply, "history": history}
    except Exception as e:
        print(f"   [!] Outing fetch error: {e}")
        return None

async def deleteWeekendOuting(client, booking_id):
    """Deletes a pending weekend outing request."""
    import time
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
    from bs4 import BeautifulSoup
    import time
    
    submit_url = "https://vtop.vitap.ac.in/vtop/hostel/saveOutingForm"
    
    try:
        # 1. The exact headers from your browser
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://vtop.vitap.ac.in",
            "Referer": "https://vtop.vitap.ac.in/vtop/content?",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # 2. BYPASSING THE FORM: Injecting the exact data from your curl command
        multipart_payload = {
            "authorizedID": (None, "24BCE7058"),
            "BookingId": (None, ""), 
            "regNo": (None, "24BCE7058"),
            "name": (None, "PHANIHARAM VENKATA RAMANUJA MANIDEEP"),
            "applicationNo": (None, "2024028731"),
            "gender": (None, "MALE"),
            "hostelBlock": (None, "MH-2"),
            "roomNo": (None, "204"),
            "outPlace": (None, place),
            "purposeOfVisit": (None, purpose),
            "outingDate": (None, out_d),
            "outTime": (None, out_t),
            "contactNumber": (None, contact),
            "parentContactNumber": (None, "8096999391"),
            "_csrf": (None, getattr(client, "csrf_token", "")),
            "x=": (None, time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime()))
        }
            
        print("   [.] Sending Direct Payload...")
        res_submit = await client._client.post(submit_url, files=multipart_payload, headers=headers)
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
    """Fetches assignments, deadlines, and download links for a specific course."""
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
                if len(cols) >= 9 and cols[0].get_text(strip=True).isdigit():
                    
                    qp_link, sub_link = None, None
                    
                    # Column 5: Question Paper Link
                    qp_a = cols[5].find('a')
                    if qp_a:
                        match = re.search(r"vtopDownload\((?:'|&#39;)(.*?)(?:'|&#39;)\)", qp_a['href'])
                        if match: qp_link = match.group(1)
                            
                    # Column 8: Student Submission Link
                    sub_a = cols[8].find('a')
                    if sub_a:
                        match = re.search(r"vtopDownload\((?:'|&#39;)(.*?)(?:'|&#39;)\)", sub_a['href'])
                        if match: sub_link = match.group(1)

                    assignments.append({
                        "s_no": cols[0].get_text(strip=True),
                        "title": cols[1].get_text(strip=True),
                        "due_date": cols[4].get_text(strip=True),
                        "qp_link": qp_link,
                        "sub_link": sub_link
                    })
        return assignments
    except Exception as e:
        print(f"   [!] Error fetching DA details: {e}")
        return []