import os
import sys
import subprocess

def check_dependencies():
    try:
        # Try to load the 3rd party packages your app relies on
        import bs4
        import httpx
        import pwinput
        # (If you added any other libraries to requirements.txt, list them here)
    except ImportError as e:
        print(f"\n   [!] Missing required module: {e.name}")
        print("   [.] Running First-Time Setup: Installing dependencies...")
        print("   [.] This will only happen once. Please wait...\n")
        
        try:
            # Silently run: pip install -r requirements.txt
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"]
            )
            print("\n   [✓] Dependencies installed successfully!")
            print("   [🚀] Launching VTOP CLI...\n")
            
            # Magically restart the Python script so it can use the new modules!
            os.execv(sys.executable, ['python'] + sys.argv)
            
        except subprocess.CalledProcessError:
            print("\n   [x] Auto-install failed.")
            print("   [!] Please run 'pip install -r requirements.txt' manually.")
            sys.exit(1)

check_dependencies()

import argparse
import requests
import asyncio
import json
import time
import sys
import subprocess
import os
import getpass
import traceback
import glob
import re
import math
import urllib.request
from rich.console import Console
from datetime import datetime as dt 
from vitap_vtop_client.client import VtopClient
from services import *

console = Console()
# --- CONFIGURATION ---
CURRENT_VERSION = "4.13"
REPO_URL = "https://raw.githubusercontent.com/vrmanideep/vtop/main/vtop.py"
SERVICES_URL = "https://raw.githubusercontent.com/vrmanideep/vtop/main/services.py"

import urllib.request
import json

def check_for_updates_via_api():
    # Format: https://api.github.com/repos/{owner}/{repo}/releases/latest
    API_URL = "https://api.github.com/repos/YourUsername/YourRepo/releases/latest"
    CURRENT_VERSION = "4.1.3"

    print("   [.] Checking for updates...", end="\r") 
    
    try:
        # Create a request object with a User-Agent (GitHub requires this for API calls)
        req = urllib.request.Request(API_URL, headers={'User-Agent': 'My-Updater-Script'})
        
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        remote_version = data['tag_name'].replace('v', '') # e.g., strips 'v' from 'v1.0.1'
        changelog = data['body'] # This is the "changelog thing"
        
        if remote_version != CURRENT_VERSION:
            print(" " * 50, end="\r")
            print(f"   🚨 UPDATE AVAILABLE: v{CURRENT_VERSION} -> v{remote_version}")
            
            # Show the user the changelog!
            print("\n--- Release Notes ---")
            print(changelog)
            print("---------------------\n")
            
            choice = input("   Download now? (y/n): ").lower().strip()
            if choice == 'y':
                # Grab the zipball or specific assets attached to the release here
                print("   [⬇️] Downloading update...")
                # ... download and extraction logic ...
                
    except Exception as e:
        print(" " * 50, end="\r")
        # print(f"Update check failed: {e}") # Uncomment to debug

async def download_material(client, url_suffix, filename):
    return await download_gate_pass(client, url_suffix, filename)

def print_header(title):
    print(f"\n{title}")
    print("=" * 60)

def print_profile(data):
    if not data or not data.get("basic"):
        print("   (No profile data found)")
        return
    b = data["basic"]
    print(f"\n   {'STUDENT PROFILE':^60}")
    print("   " + "=" * 60)
    print(f"   {'Name':<15} : {b.get('name')}")
    print(f"   {'Reg No':<15} : {b.get('regno')}")
    print(f"   {'Program':<15} : {b.get('program')}")
    print(f"   {'VIT Email':<15} : {b.get('vitemail')}")
    print(f"   {'Mobile':<15} : {b.get('mobile')}")
    print("   " + "-" * 60)
    p = data.get("proctor")
    if p and p.get("Name"):
        print(f"\n   {'PROCTOR INFORMATION':^60}")
        print("   " + "=" * 60)
        fields = [("Name", "Name"), ("ID", "Faculty ID"), ("Email", "Email"), ("Mobile", "Mobile"), ("Cabin", "Cabin")]
        for label, key in fields:
            if key in p:
                print(f"   {label:<15} : {p[key]}")
    else:
        print("\n   [!] Proctor Information section was not found or is empty.")
    print("   " + "=" * 60 + "\n")

def print_grade_history(data):
    if not data or not data.get("courses"):
        print("\n   [!] No grade history found.")
        return
    print("\n   ACADEMIC TRANSCRIPT")
    print("   " + "─" * 95)
    print(f"   {'CODE':<15} {'GRADE':<12} {'CREDITS':<12} {'COURSE NAME'}")
    print("   " + "─" * 95)
    for c in data["courses"]:
        print(f"   {c['code']:<15} {c['grade']:<12} {c['credits']:<12} {c['name']}")
    print("   " + "─" * 95 + "\n")
    s = data.get("summary", {})
    print(f"   ACADEMIC STANDING (OVERALL)")
    print(f"   -------------------------------------------")
    print(f"   CURRENT CGPA          : {s.get('cgpa')}")
    print(f"   CREDITS EARNED        : {s.get('earned')}")
    print(f"   CREDITS REGISTERED    : {s.get('registered')}")
    print(f"   -------------------------------------------\n")

def print_today_schedule(data):
    if not data:
        print("   (No timetable data available)")
        return

    current_day_upper = dt.now().strftime("%A").upper() 
    current_day_title = dt.now().strftime("%A").title()
    
    print(f"\n   {'SCHEDULE FOR ' + current_day_upper:^60}")
    print("   " + "=" * 80)
    classes = data.get(current_day_title) or data.get(current_day_upper) or []
    if not classes:
        print(f"   🎉 No classes scheduled for {current_day_title}!")
        print("   " + "=" * 80)
        return
    try: 
        classes.sort(key=lambda x: x.get('time', '23:59').split('-')[0].strip())
    except: 
        pass
    print(f"   {'TIME':<15} {'VENUE':<8} {'CODE':<10} {'SLOT':<14} {'COURSE NAME'}")
    print("   " + "-" * 100)
    for c in classes:
        time_str = c.get('time', '-')        
        venue    = c.get('venue', '-')       
        code     = c.get('course_code', '-') 
        name     = c.get('course_name', '-')[:60]
        slot     = c.get('slot', '-')        
        if slot.endswith('-'): slot = slot[:-1].strip()
        print(f"   {time_str:<15} {venue:<8} {code:<10} {slot:<15} {name}")
    print("   " + "-" * 100)

async def print_attendance_with_details(client, semester_id, summary_data):
    if not summary_data:
        print("   (No data found)")
        return
    print(f"\n   {'ATTENDANCE REPORT (Detailed History)':^80}")
    print("   " + "=" * 80)
    for sub in summary_data:
        code = sub.get('course_code', '-')
        name = sub.get('course_name', '-')
        ctype = sub.get('course_type', '-')
        perc = sub.get('percentage', '0')
        attended = sub.get('attended', '0')
        total = sub.get('total', '0')
        try: is_low = float(perc) < 75
        except: is_low = False
        status_icon = "🔴" if is_low else "🟢"
        print(f"\n   {status_icon} {name}")
        print(f"        Attendance: {perc}% ({attended}/{total})")
        c_id = sub.get('course_id')
        type_id = sub.get('type_id') 
        if not type_id: type_id = sub.get('type_code')
        if c_id and type_id:
            try:
                history = await fetchAttendanceDetail(client, semester_id, c_id, type_id)
                if history:
                    def parse_date(x):
                        try: 
                            return dt.strptime(x['date'], "%d-%b-%Y")
                        except: 
                            try: return dt.strptime(x['date'], "%d-%m-%Y")
                            except: return dt.min 
                    
                    history.sort(key=parse_date)
                    last_date = history[-1].get('date', 'N/A')
                    print(f"        📅 Attendance Last Updated on: {last_date}")
                    
                    # Filter out 'Present' so we keep both Absences and OnDuty records
                    exceptions = [h for h in history if "Present" not in h['status']]
                    
                    if exceptions:
                        print(f"        [!] Found {len(exceptions)} Absences/OnDuty:")
                        print(f"            {'DATE':<12} {'DAY':<5} {'SLOT':<8} {'STATUS'}") 
                        print("            " + "-" * 40)
                        exceptions.sort(key=parse_date, reverse=True)
                        
                        for h in exceptions:
                            date_str = h.get('date', '-')
                            day_name = "-"
                            try:
                                d_obj = parse_date(h)
                                if d_obj != dt.min:
                                    day_name = d_obj.strftime("%a")
                            except: pass
                            
                            # Dynamic icon: Yellow for OnDuty, Red X for Absences
                            icon = "" if "On Duty" in h['status'] else "❌"
                            
                            print(f"            {date_str:<12} {day_name:<5} {h['slot']:<8} {icon} {h['status']}")
                    else:
                          print(f"        (History fetched: {len(history)/total} classes, All Present)")
                else:
                    print("        (No history records found)")
            except Exception as e:
                print(f"        [!] Detail fetch error: {e}")
        else:
            print("        [!] Cannot fetch details (ID missing).")
        print("   " + "-" * 50)

def print_attendance(data):
    if not data:
        print("   (No data found)")
        return
    print(f"\n   {'S.No':<5} {'CODE':<9} {'FACULTY':<30} {'TYPE':<10} {'SLOT':<15} {'%':<5} {'STATUS'}")
    print("   " + "─" * 90)
    for i, sub in enumerate(data):
        code = sub.get('course_code', '-')
        faculty = sub.get('faculty_name', 'N/A')
        if len(faculty) > 30: faculty = faculty[:28] + ".."
        ctype = sub.get('course_type', '').replace("Embedded Theory", "Emb Th").replace("Embedded Lab", "Emb Lab").replace("Theory Only", "Theory")
        raw_slot = sub.get('course_slot') or sub.get('slot') or '-'
        if ' - ' in raw_slot: slot = raw_slot.split(' - ')[1] 
        else: slot = raw_slot
        perc = sub.get('attendance_percentage', '0')
        if perc == '0': perc = sub.get('percentage', '0')
        try: status = "LOW ⚠️" if float(perc) < 75 else "OK"
        except: status = "-"
        print(f"   {i+1:<5} {code:<9} {faculty:<30} {ctype:<10} {slot:<15} {perc:<5} {status}")
    print("   " + "─" * 90)

def print_marks(data):
    if not data or "courses" not in data:
        print("   (No marks found)")
        return
    courses = data["courses"]
    courses.sort(key=lambda x: x.get('course_code', ''))
    
    print(f"\n   {'CODE':<10} {'COURSE TITLE':<60} {'MARK TITLE':<40} {'SCORE':<8} {'MAX':<6} {'WGT%':<6} {'WGT MRK'}")
    print("   " + "━" * 145)
    
    for course in courses:
        code = course.get('course_code', '-')
        title = course.get('course_title', '-')[:58]
        details = course.get('details', [])
        
        if not details:
             print(f"   {code:<10} {title:<60} {'-':<40} {'-':<8} {'-':<6} {'-':<6} {'-'}")
             print("   " + "-" * 145)
             continue
             
        first_line = True
        for mark in details:
            m_title = mark.get('mark_title', '-')[:38] 
            score   = str(mark.get('scored_mark', '-'))
            max_m   = str(mark.get('max_mark', '-'))
            w_pct   = str(mark.get('weightage_pct', '-'))
            w_mrk   = str(mark.get('weightage_mark', '-'))
            
            if first_line:
                print(f"   {code:<10} {title:<60} {m_title:<40} {score:<8} {max_m:<6} {w_pct:<6} {w_mrk}")
                first_line = False
            else:
                print(f"   {'':<10} {'':<60} {m_title:<40} {score:<8} {max_m:<6} {w_pct:<6} {w_mrk}")
                
        print("   " + "-" * 145)

def print_timetable(data):
    if not data:
        print("   (No timetable found)")
        return
    print(f"   {'TIME':<15} {'VENUE':<8} {'CODE':<10} {'SLOT':<15} {'COURSE NAME'}")
    print("   " + "=" * 100)
    day_order = {"MONDAY": 1, "TUESDAY": 2, "WEDNESDAY": 3, "THURSDAY": 4, "FRIDAY": 5, "SATURDAY": 6, "SUNDAY": 7}
    sorted_days = sorted(data.keys(), key=lambda d: day_order.get(d.upper(), 99))
    for day in sorted_days:
        classes = data[day]
        if not isinstance(classes, list) or not classes: continue
        print(f"   [{day.upper()}]")
        try: classes.sort(key=lambda x: x.get('time', '23:59').split('-')[0].strip())
        except: pass
        for c in classes:
            time_str = c.get('time', '-')        
            venue    = c.get('venue', '-')       
            code     = c.get('course_code', '-') 
            name     = c.get('course_name', '-') 
            slot     = c.get('slot', '-')        
            if slot.endswith('-'): slot = slot[:-1].strip()
            print(f"   {time_str:<15} {venue:<8} {code:<10} {slot:<15} {name}")
        print(f"   {'-' *100}")

def print_exam_schedule(data):
    if not data:
        print("   (No exams scheduled)")
        return

    # Helper to parse dates for sorting
    def parse_date(d):
        try: 
            # [FIX] Use dt.strptime
            return dt.strptime(d, "%d-%b-%Y")
        except: return dt.max

    cat_priority = {"FAT": 0, "CAT2": 1, "CAT1": 2}
    
    try:
        data.sort(key=lambda x: (
            cat_priority.get(x.get('category', 'FAT'), 3), # Primary Sort: Category
            parse_date(x.get('exam_date', ''))             # Secondary Sort: Date
        ))
    except: pass

    # --- STACKED HEADER ---
    print(f"\n   {'COURSE' :<10} {'': <60} {'COURSE':<6} {'':<16} {'':<18} {'EXAM' :<10} {'EXAM' :<8} {'' :<20} {'':<12} {'SEAT' :<7} {'SEAT'}")
    print(f"   {'CODE' :<25} {'COURSE TITLE' :<46} {'TYPE' :<8} {'CLASS ID' :<14} {'SLOT':<17} {'DATE' :<9} {'SESSION':<15} {'EXAM TIME' :<17} {'VENUE':<7} {'LOCATION':<10} {'NO.'}")
    print("   " + "─" * 182)

    current_cat = None
    for ex in data:
        cat = ex.get('category', 'FAT')
        
        if cat != current_cat:
            display_cat = cat
            if cat == "CAT1": display_cat = "CAT- 1"
            elif cat == "CAT2": display_cat = "CAT- 2"
            
            if display_cat in ["CAT- 1", "CAT- 2"]: 
                print(f"\n   {'-'*84} {display_cat} EXAMS {'-'*84}\n")
            else :
                print(f"\n   {'-'*85} {display_cat} EXAMS {'-'*86}\n")
                
            current_cat = cat
        
        code  = ex.get('course_code', '-')
        title = ex.get('course_title', '-')[:58] 
        etype = ex.get('exam_type', '-')
        cid   = ex.get('class_id', '-')
        slot  = ex.get('slot', '-')
        date  = ex.get('exam_date', '-')
        sess  = ex.get('session', '-')
        
        time_str = ex.get('exam_time', '-') 
        if time_str in [None, "", "-"]: time_str = "-"
        
        venue = ex.get('venue', '-')
        sloc  = ex.get('seat_location', '-')
        seat  = ex.get('seat_number', '-')

        if seat in ["", "-"]: seat = "-"
        if venue in ["", "-"]: venue = "-"
        if sloc in ["", "-"]: sloc = "-"

        print(f"   {code:<10} {title:<60} {etype:<6} {cid:<16} {slot:<15} {date:<14} {sess:<8} {time_str:<22} {venue:<8} {sloc:<10} {seat}")

    print("   " + "─" * 182)

def print_credits(data):
    if not data:
        print("   (No credit details found)")
        return
    print(f"\n   {'CATEGORY':<25} {'EARNED':<8} {'TOTAL':<8} {'PROGRESS'}")
    print("   " + "─" * 65)
    total_earned = 0
    total_required = 0
    for item in data:
        cat = item['category']
        earned = item['earned']
        total = item['total']
        pct = item['percent']
        if "Total" in cat: continue
        total_earned += earned
        total_required += total
        bar_len = 15
        filled = int((pct / 100) * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"   {cat:<25} {earned:<8.1f} {total:<8.0f} {bar} {int(pct)}%")
    print("   " + "─" * 65)
    tot_pct = (total_earned / total_required * 100) if total_required > 0 else 0
    bar_len = 15
    filled = int((tot_pct / 100) * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"   {'TOTAL CREDITS':<25} {total_earned:<8.1f} {total_required:<8.0f} {bar} {int(tot_pct)}%")
    print("   " + "─" * 65)

def print_course_page_table(data):
    if not data:
        print("\n   [!] No data received from Course Page.")
        return

    meta = data.get("metadata", {})
    if meta:
        print(f"\n   COURSE: {meta.get('code')} - {meta.get('title')}")
        print(f"   SLOT: {meta.get('slot')} | FACULTY: {meta.get('faculty')}")
        print("   " + "─" * 105)

    found = False
    if data.get("general"):
        found = True
        print(f"\n   GENERAL MATERIALS")
        print("   " + "-" * 60)
        for i, item in enumerate(data["general"]):
            print(f"   [G{i+1}] {item['title']:<60} 📥 AVAILABLE")

    if data.get("lectures"):
        found = True
        print(f"\n   {'S.NO':<5} {'DATE':<12} {'DAY':<5} {'TOPIC':<100} {'MATERIALS'}")
        print("   " + "─" * 145)
        
        for lec in data["lectures"]:
            s_no = lec['s_no']
            date = lec['date']
            day = lec['day']
            topic = lec['topic'][:98]
            
            assets = []
            if lec.get('download_path'): assets.append("Main")
            if lec.get('ref_paths'): assets.append(f"{len(lec['ref_paths'])} Refs")
            if lec.get('web_links'): assets.append(f"{len(lec['web_links'])} Web")
            
            mat = ", ".join(assets) if assets else "-"
            
            print(f"   {s_no:<5} {date:<12} {day:<5} {topic:<100} {mat}")
            
        print("   " + "─" * 145)
    
    if not found:
        print("\n   (No course data found. Check if the course page loaded correctly.)")

def printGeneralOuting(history):
    """
    Prints the Outing History in a compact table.
    """
    if not history:
        print("\n   (No history found)")
        return

    header = (
        f"\n   {'#':<3} "
        f"{'OUT DATE':<11} {'TIME':<9} "
        f"{'PLACE':<20} "
        f"{'PURPOSE':<25} "
        f"{'IN DATE':<11} {'TIME':<9} "
        f"{'STATUS':<18} {'PASS'}"
    )
    
    print(header)
    print("   " + "─" * 120) 

    for i, h in enumerate(history):
        status_raw = h['status'].strip()
        status_lower = status_raw.lower()
        
        if "accepted" in status_lower or "approved" in status_lower:
            stat_display = "🟢 Approved"
        elif "rejected" in status_lower:
            stat_display = "🔴 Rejected"
        elif "mentor" in status_lower and "waiting" in status_lower:
            stat_display = "🟡 Wait: Mentor"
        elif "warden" in status_lower and "waiting" in status_lower:
            stat_display = "🟡 Wait: Warden"
        else:
            stat_display = "⚪ " + status_raw[:15]

        pass_display = "📄" if h.get('download_url') else " "

        def trunc(text, length):
            text = text.replace('\n', ' ').strip()
            return (text[:length-2] + '..') if len(text) > length else text

        # Short date format
        def short_date(d): 
            return d[:-4] + d[-2:] if len(d) > 10 else d

        out_d = short_date(h['out_date'])
        in_d  = short_date(h['in_date'])
        
        place = trunc(h['place'], 20)
        purp  = trunc(h['purpose'], 25)
        stat  = trunc(stat_display, 18)

        print(
            f"   {i+1:<3} "
            f"{out_d:<11} {h['out_time']:<9} "
            f"{place:<20} "
            f"{purp:<25} "
            f"{in_d:<11} {h['in_time']:<9} "
            f"{stat:<18} {pass_display}"
        )

    print("   " + "─" * 120)

def printWeekendOuting(history):
    """Prints Weekend Outing History cleanly."""
    if not history:
        print("\n   (No history found)")
        return

    header = (
        f"\n   {'#':<3} {'BLK':<6} {'ROOM':<6} {'PURPOSE':<20} "
        f"{'TIME':<16} {'DATE':<12} {'STATUS':<20} {'OUTPASS'}"
    )
    
    print(header)
    print("   " + "─" * 95) 

    for idx, h in enumerate(history):
        status_lower = h['status'].lower()
        
        # Cleanly map to the 3 exact VTOP states
        if "accepted" in status_lower or "approved" in status_lower:
            stat_display = "🟢 Approved"
        elif "rejected" in status_lower:
            stat_display = "🔴 Rejected"
        elif "wait" in status_lower or "warden" in status_lower:
            stat_display = "🟡 Wait: Warden"
        else:
            # Fallback just in case VTOP changes their backend strings
            stat_display = "⚪ " + h['status'][:15]

        def trunc(text, length):
            text = text.replace('\n', ' ').strip()
            return (text[:length-2] + '..') if len(text) > length else text

        dl_avail = "✅" if h['download_link'] else "❌"

        print(
            f"   {idx+1:<3} {h['block']:<6} {h['room']:<6} "
            f"{trunc(h['purpose'], 20):<20} {trunc(h['out_time'], 16):<16} "
            f"{h['out_date']:<12} {stat_display:<20} {dl_avail}"
        )

    print("   " + "─" * 95)
    
async def main():
    global asyncio
    
    # --- THE MASTER REBOOT LOOP ---
    while True:
        reg_no, password = get_credentials("credentials.txt")
        print(f"\n[-] Connecting to V-TOP as {reg_no}...")
        
        login_success = False
        
        # 1. Create a BRAND NEW socket connection
        async with VtopClient(reg_no, password) as client:
            
            # 2. Login Phase (Relies on vitap_vtop_client's internal retries)
            try:
                if await vtopClientLogin(client):
                    login_success = True
                else:
                    print("   [x] Server rejected the connection.")
            except Exception as e:
                print(f"   [x] Fatal Connection Crash: {e}")

            if not login_success:
                print(f"\n[!] LOGIN FAILED. The VTOP server timed out, or your password is wrong.")
                action = input("[-] [ENTER] Retry | [0/EXIT] Close | [WIPE] Delete Saved Pass: ").strip().upper()
                
                if action in ['EXIT', '0']:
                    print("Exiting... See you later!")
                    import sys
                    sys.exit() 
                elif action == 'WIPE':
                    import os
                    if os.path.exists("credentials.txt"):
                        os.remove("credentials.txt")
                    print("[-] Trashed credentials. Let's try again...\n")
                
                continue

            # 3. Home Page Phase (The Gatekeeper)
            print("   [.] Entering Home Page...")
            home_success = False
            
            for attempt in range(1, 4):
                try:
                    import httpx
                    content_resp = await client._client.get(
                        "https://vtop.vitap.ac.in/vtop/content?", 
                        timeout=25.0,
                        follow_redirects=True
                    )
                    if content_resp.status_code == 200:
                        home_success = True
                        break
                except Exception as e:
                    print(f"   [!] Connection timeout. Retrying landing page ({attempt}/3)...")
                    await asyncio.sleep(2)
            
            # If the socket is dead, do NOT proceed to fetchSemesters. Restart entirely.
            if not home_success:
                print("   [x] The VTOP server dropped the connection. Rebuilding socket...")
                continue 

            # 4. Data Scraping Phase
            try:
                available_sems = await fetchSemesters(client)
                profile_data = await fetchProfile(client)
                
                if not available_sems:
                    print("   [x] Server returned empty semester data. Rebuilding...")
                    continue
            except Exception as e:
                print(f"   [x] Connection broke while scraping data: {e}")
                continue 
            
            student_name = profile_data.get("basic", {}).get("name", "Student")
            target_sem = available_sems[0]['id'] if available_sems else None
            current_sem_name = available_sems[0]['name'] if available_sems else "None"

            print(f"{'='*65}\n")
            print(f" NAME:       : {student_name}")
            print(f" REG NO      : {reg_no}")
            print(f" CURRENT SEM : {current_sem_name}")
            print(f"{'='*65}\n")
            
            # 5. The Menu Loop
            while True:
                print_header("MAIN MENU")
                print("   " + "─" * 40)
                
                print("   [ ACADEMICS ]")
                print("   1.  Today's Schedule")
                print("   2.  Full Timetable")
                print("   3.  Attendance Record")
                print("   4.  Course Page ")
                print("   5.  Internal Marks")
                print("   6.  Exam Schedule")
                print("   7.  Grade History (Transcript)")
                print("   8.  Digital Assignments")
                print("   9.  Credits Distribution")
                
                print("\n   [ HOSTEL ]")
                print("   10. General Outing")
                print("   11. Weekend Outing")
                
                print("\n   [ TOOLS ]")
                print("   12. Attendance Calculator")
                print("   13. Student Profile")
                print("   14. Change Semester")
                print("   15. Update Credentials")
                print("   16. Bunk Predictor (Simulate Absences)")

                print("\n   0.  Exit")
                print("   " + "─" * 40)
                
                print("", end="\n", flush=True)
                choice = input(f"[{reg_no}] Enter choice (0-16): ").strip()
                
                if choice == '0':
                    print("Logging out... Goodbye!")
                    return 
                
                elif choice == '1': # Today's Schedule
                    if not target_sem:
                        print("[!] No semester selected. Use option 14.")
                        continue
                    print_header(f"TODAY'S SCHEDULE - {current_sem_name}")
                    data = await fetchTimetable(client, target_sem)
                    print_today_schedule(data)

                elif choice == '2': # Full Timetable
                    if not target_sem:
                        print("[!] No semester selected. Use option 14.")
                        continue
                    print_header(f"FULL TIMETABLE - {current_sem_name}")
                    data = await fetchTimetable(client, target_sem)
                    print_timetable(data)

                elif choice == '3': # Attendance
                    if not target_sem:
                        print("[!] No semester selected. Use option 14.")
                        continue
                    while True:
                        print("\n--- ATTENDANCE MENU ---")
                        print("1. View Summary (All Subjects)")
                        print("2. View Detailed Attendance (Subject-wise)")
                        print("0. Back to Main Menu")
                        sub = input("Select option: ")
                        if sub == "1":
                            data = await fetchAttendance(client, target_sem)
                            print_attendance(data)
                        elif sub == "2":
                            data = await fetchAttendance(client, target_sem)
                            await print_attendance_with_details(client, target_sem, data)
                        elif sub == "0":
                            break
                        else:
                            print("[!] Invalid option")

                elif choice == '5': # Internal Marks
                    if not target_sem:
                        print("[!] No semester selected. Use option 14.")
                        continue
                    print_header(f"INTERNAL MARKS - {current_sem_name}")
                    data = await fetchMarks(client, target_sem)
                    print_marks(data)

                elif choice == '7': # Grade History (Transcript)
                    print_header("ACADEMIC TRANSCRIPT")
                    g_data = await fetchGradeHistory(client)
                    print_grade_history(g_data)

                elif choice == '9': # Credits Distribution
                    print_header("ACADEMIC CREDITS DISTRIBUTION")
                    c_data = await fetchCredits(client)
                    print_credits(c_data)

                elif choice == '4': # Course Page (Lecture Plan & Materials)
                    if not target_sem:
                        print("[!] No semester selected. Use option 14.")
                        continue
                    
                    print(f"   [.] Fetching Course List...")
                    master_courses = await fetchCourseList(client, target_sem)

                    if not master_courses:
                        print("   [!] No registered courses found for this semester.")
                        continue

                    while True:
                        print_header(f"SELECT COURSE ({len(master_courses)} Found)")
                        for idx, c in enumerate(master_courses):
                            print(f"   {idx+1}. {c['code']} : {c['title'][:40]} - {c['type']}")
                        print("   0. Back to Main Menu")
                        
                        c_sel = input("\n   Select course number: ").strip()
                        if c_sel == '0': break 

                        try:
                            sel_idx = int(c_sel) - 1
                            if 0 <= sel_idx < len(master_courses):
                                selected_course = master_courses[sel_idx]
                                selected_code = selected_course['code']
                                
                                print(f"   [.] Fetching classes/slots for {selected_code}...")
                                classes = await fetchCourseClasses(client, target_sem, selected_course['generic_class_id'])
                                
                                if not classes:
                                    print(f"   [!] No active classes found for {selected_code}.")
                                    continue

                                selected_class = None
                                
                                if len(classes) == 1:
                                    selected_class = classes[0]
                                    import re
                                    fac_clean = re.sub(r'^\d+\s*-\s*', '', selected_class['faculty'])
                                    print(f"   [+] Auto-selected: SLOT: {selected_class['slot']} | FAC: {fac_clean}")
                                else:
                                    print(f"\n   SELECT COMPONENT FOR {selected_code}:")
                                    print(f"   {'#':<4} {'SLOT':<17} {'FACULTY NAME'}")
                                    print("   " + "-" * 60)
                                    
                                    current_slot = ""
                                    import re
                                    for i, cls in enumerate(classes):
                                        if cls['slot'] != current_slot:
                                            if current_slot != "": print("")
                                            print(f"   🔹 [{cls['slot']}]")
                                            current_slot = cls['slot']

                                        fac_clean = re.sub(r'^\d+\s*-\s*', '', cls['faculty'])
                                        fac_clean = re.sub(r'\s*-[A-Z\s]+$', '', fac_clean).strip()
                                        print(f"       {i+1:<2}. {fac_clean}")
                                        
                                    print("   " + "-" * 60)
                                    print("       0 . Cancel")
                                    
                                    cls_sel = input("\n   Select component: ").strip()
                                    if cls_sel == '0': continue
                                    try:
                                        cls_idx = int(cls_sel) - 1
                                        if 0 <= cls_idx < len(classes):
                                            selected_class = classes[cls_idx]
                                        else:
                                            print("   [!] Invalid component selection.")
                                            continue
                                    except ValueError:
                                        print("   [!] Please enter a number.")
                                        continue

                                if not selected_class['erp_id']:
                                    print(f"\n   [!] Faculty ID could not be scraped for {selected_code}.")
                                    manual_id = input(f"   Enter Faculty ID (erpId) manually: ").strip()
                                    if manual_id: 
                                        selected_class['erp_id'] = manual_id
                                    else:
                                        print("   [x] Cannot proceed without Faculty ID.")
                                        continue

                                print(f"   [.] Fetching materials page...")
                                c_page = await fetchCoursePage(
                                    client, 
                                    target_sem, 
                                    selected_class['class_id'], 
                                    selected_class['erp_id']
                                )
                                
                                print_course_page_table(c_page)
                                
                                import os
                                import glob
                                home = os.path.expanduser("~")
                                save_dir = os.path.join(home, "Downloads")

                                def check_exists(base_name):
                                    safe_name = re.sub(r'[\\/*?:"<>|]', "", base_name).strip()
                                    if not safe_name: safe_name = "downloaded_material"
                                    return len(glob.glob(os.path.join(save_dir, f"{safe_name}.*"))) > 0

                                def format_general_name(code, title, index):
                                    t_lower = title.lower()
                                    if "syllabus" in t_lower:
                                        return f"{code}-syllabus"
                                    elif "reference-material" in t_lower or "reference material" in t_lower:
                                        match = re.search(r'reference[- ]material[- _]*([ivxIVX\d]+)', t_lower)
                                        if match:
                                            numeral = match.group(1).upper()
                                            return f"{code}- Reference material - {numeral}"
                                        return f"{code}- Reference material - {index}"
                                    else:
                                        return f"{code}-{title[:30]}"

                                while True:
                                    print("\n   ACTIONS:")
                                    print("   [1, 2..] Enter S.No(s) to download")
                                    print("   [G1, G2] Enter G1, G2.. to download General Material")
                                    print("   [A]      Download ALL materials")
                                    print("   [0]      Back to Subject List") 
                                    
                                    dl_choice = input("\n   Choice: ").strip().upper()
                                    if dl_choice == '0': break 
                                    
                                    def get_short_date(date_str):
                                        if not date_str: return "UnknownDate"
                                        parts = date_str.split('-')
                                        return f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else date_str

                                    if dl_choice == 'A':
                                        count = 0
                                        skipped = 0
                                        print(f"   [.] Saving files directly to: {save_dir}")
                                        
                                        for lec in c_page['lectures']:
                                            short_date = get_short_date(lec.get('date', ''))
                                            safe_topic = re.sub(r'[\\/*?:"<>|]', "", lec['topic']).strip()
                                            
                                            if lec.get('download_path'):
                                                fname = f"{short_date}_{selected_code}_{safe_topic}"
                                                if check_exists(fname):
                                                    print(f"   [-] Skipped (Exists): {fname[:60]}...")
                                                    skipped += 1
                                                else:
                                                    res, _ = await download_course_material(client, lec['download_path'], save_dir, fname)
                                                    if res: count += 1
                                            
                                            for r_idx, r_path in enumerate(lec.get('ref_paths', [])):
                                                fname = f"{short_date}_{selected_code}_{safe_topic}_Ref_{r_idx+1}"
                                                if check_exists(fname):
                                                    print(f"   [-] Skipped (Exists): {fname[:60]}...")
                                                    skipped += 1
                                                else:
                                                    res, _ = await download_course_material(client, r_path, save_dir, fname)
                                                    if res: count += 1
                                            
                                            if lec.get('web_links'):
                                                print(f"\n   [🔗] Web Links for: {lec['topic'][:50]}...")
                                                for link in lec['web_links']:
                                                    print(f"        -> {link}")
                                                print("") 
                                                
                                        for i, gen in enumerate(c_page.get('general', [])):
                                            fname = format_general_name(selected_code, gen['title'], i+1)
                                            if check_exists(fname):
                                                print(f"   [-] Skipped (Exists): {fname[:60]}...")
                                                skipped += 1
                                            else:
                                                res, _ = await download_course_material(client, gen['download_path'], save_dir, fname)
                                                if res: count += 1
                                        
                                        print(f"   [✓] Downloaded {count} new files. (Skipped {skipped})")
                                                
                                    elif dl_choice.startswith('G'):
                                        try:
                                            g_idx = int(dl_choice[1:]) - 1
                                            if 0 <= g_idx < len(c_page['general']):
                                                item = c_page['general'][g_idx]
                                                fname = format_general_name(selected_code, item['title'], g_idx+1)
                                                
                                                if check_exists(fname):
                                                    print(f"   [-] File already exists: {fname}")
                                                else:
                                                    print(f"   [.] Downloading {fname[:60]}...")
                                                    res, filepath = await download_course_material(client, item['download_path'], save_dir, fname)
                                                    if res: print(f"   [✓] Saved to: {filepath}")
                                                    else: print(f"   [x] Failed: {filepath}")
                                            else:
                                                print("   [!] Invalid G number.")
                                        except ValueError: 
                                            print("   [!] Invalid input format.")

                                    elif all(part.strip().isdigit() for part in dl_choice.split(',')):
                                        choices = [x.strip() for x in dl_choice.split(',')]
                                        
                                        for choice in choices:
                                            target_sno = int(choice)
                                            target_lec = next((l for l in c_page['lectures'] if l['s_no'] == target_sno), None)
                                            
                                            if target_lec:
                                                short_date = get_short_date(target_lec.get('date', ''))
                                                safe_topic = re.sub(r'[\\/*?:"<>|]', "", target_lec['topic']).strip()
                                                downloads_started = False
                                                
                                                if target_lec.get('download_path'):
                                                    downloads_started = True
                                                    fname = f"{short_date}_{selected_code}_{safe_topic}"
                                                    if check_exists(fname): 
                                                        print(f"   [-] Main file exists: {fname[:60]}...")
                                                    else:
                                                        print(f"   [.] Downloading: {fname[:60]}...")
                                                        res, filepath = await download_course_material(client, target_lec['download_path'], save_dir, fname)
                                                        if res: print(f"   [✓] Saved: {filepath}")
                                                
                                                for r_idx, r_path in enumerate(target_lec.get('ref_paths', [])):
                                                    downloads_started = True
                                                    fname = f"{short_date}_{selected_code}_{safe_topic}_Ref_{r_idx+1}"
                                                    if check_exists(fname): 
                                                        print(f"   [-] Reference exists: {fname[:60]}...")
                                                    else:
                                                        print(f"   [.] Downloading Reference {r_idx+1}...")
                                                        res, filepath = await download_course_material(client, r_path, save_dir, fname)
                                                        if res: print(f"   [✓] Saved: {filepath}")
                                                
                                                if target_lec.get('web_links'):
                                                    downloads_started = True
                                                    print(f"\n   [🔗] Web Links for Lecture {target_sno}:")
                                                    for link in target_lec['web_links']:
                                                        print(f"        -> {link}")
                                                
                                                if not downloads_started:
                                                    print(f"   [!] No materials available for Lecture {target_sno}.")
                                            else:
                                                print(f"   [!] Lecture S.No {target_sno} not found.")
                                    else:
                                        print("   [!] Invalid command.")
                        except ValueError:
                            print("   [!] Please enter a valid number.")

                elif choice == '8': # Digital Assignments
                    if not target_sem:
                        print("   [!] No semester selected. Use option 14.")
                        input("\n   Press Enter to return...")
                        continue
                        
                    print(f"   [.] Fetching Digital Assignment Courses...")
                    da_courses = await fetchDACourseList(client, target_sem)
                    
                    if not da_courses:
                        print("   [!] No digital assignments found for this semester.")
                        input("\n   Press Enter to return...")
                        continue
                        
                    while True:
                        import os
                        os.system('cls' if os.name == 'nt' else 'clear')
                        print_header("DIGITAL ASSIGNMENTS")
                        print(f"   {'#':<3} {'CODE':<10} {'COURSE TITLE':<40} {'FACULTY'}")
                        print("   " + "─" * 95)
                        
                        for i, c in enumerate(da_courses):
                            title = (c['title'][:37] + '..') if len(c['title']) > 37 else c['title']
                            fac = (c['faculty'][:25])
                            print(f"   {i+1:<3} {c['code']:<10} {title:<40} {fac}")
                        
                        print("   " + "─" * 95)
                        print("   0. Back to Main Menu")
                        
                        c_sel = input("\n   Select course number: ").strip()
                        if c_sel == '0': break
                        
                        try:
                            idx = int(c_sel) - 1
                            if 0 <= idx < len(da_courses):
                                selected_course = da_courses[idx]
                                print(f"\n   [.] Fetching records for {selected_course['code']}...")
                                
                                assignments = await fetchDADetails(client, selected_course['class_id'])
                                
                                if not assignments:
                                    print(f"   [!] No assignments posted yet for {selected_course['code']}.")
                                    input("\n   Press Enter to continue...")
                                    continue
                                    
                                while True:
                                    print(f"\n   ASSIGNMENTS: {selected_course['code']} - {selected_course['title']}")
                                    print(f"   {'#':<3} {'TITLE':<25} {'DUE DATE':<15} {'STATUS':<20} {'FILES'}")
                                    print("   " + "─" * 85)
                                    
                                    for asn in assignments:
                                        raw = asn['submission_status']
                                        if not raw: ui_status = "⏳ Pending"
                                        elif raw == 'File Not Uploaded': ui_status = "❌ Missed"
                                        else: ui_status = "✅ Submitted"

                                        files = []
                                        if asn['can_qp_download']: files.append("📄 QP")
                                        if asn['can_da_download']: files.append("📤 MY-DA")
                                        f_str = ", ".join(files) if files else "None"
                                        
                                        print(f"   {asn['serial_number']:<3} {asn['assignment_title'][:23]:<25} {asn['due_date']:<15} {ui_status:<20} {f_str}")
                                    
                                    print("   " + "─" * 85)
                                    print("   [#] Enter # to Download | [A] Download ALL | [0] Go Back")
                                    
                                    a_sel = input("\n   Choice: ").strip().upper()
                                    if a_sel == '0': break
                                    
                                    save_dir = os.path.join(os.path.expanduser("~"), "Downloads", "VTOP_Assignments", selected_course['code'])
                                    if not os.path.exists(save_dir): os.makedirs(save_dir)
                                    
                                    to_download = []
                                    if a_sel == 'A':
                                        to_download = assignments
                                    elif a_sel.isdigit():
                                        a_idx = int(a_sel) - 1
                                        if 0 <= a_idx < len(assignments):
                                            to_download = [assignments[a_idx]]
                                    
                                    if not to_download:
                                        print("   [!] Invalid selection.")
                                        continue

                                    for target_asn in to_download:
                                        if target_asn['can_qp_download']:
                                            fname = f"{target_asn['assignment_title'].replace(' ', '_')}_QP"
                                            print(f"   [.] Downloading QP: {target_asn['assignment_title']}...")
                                            await download_course_material(client, target_asn['qp_id'], save_dir, fname)
                                        
                                        if target_asn['can_da_download']:
                                            fname = f"{target_asn['assignment_title'].replace(' ', '_')}_Submission"
                                            print(f"   [.] Downloading Your Submission...")
                                            await download_course_material(client, target_asn['da_id'], save_dir, fname)
                                    
                                    print(f"   [✓] Done. Files saved to: {save_dir}")
                                    input("\n   Press Enter to continue...")
                            else:
                                print("   [!] Invalid selection.")
                        except ValueError:
                            print("   [!] Please enter a valid number.")

                elif choice == '6': # Exam Schedule
                    if not target_sem:
                        print("[!] No semester selected. Use option 14.")
                        continue
                    print_header(f"EXAM SCHEDULE - {current_sem_name}")
                    data = await fetchExamSchedule(client, target_sem)
                    print_exam_schedule(data)

                elif choice == '10': # General Outing
                    print_header("GENERAL OUTING SYSTEM")
                    print("   [.] Fetching student details...")
                    data = await fetchGeneralOuting(client)
                    
                    if not data or not data.get('info'):
                        print("   [!] Could not fetch data. Try logging in again.")
                        continue

                    info = data['info']
                    history = data.get('history', [])

                    print(f"\n   STUDENT: {info.get('name')}")
                    print(f"   BLOCK  : {info.get('hostelBlock')} | ROOM: {info.get('roomNo')}")
                    print("   " + "-" * 60)
                    
                    print("\n   MENU:")
                    print("   1. Apply for New Outing")
                    print("   2. View History / Actions")
                    print("   0. Back")
                    
                    sub = input("\n   Select Option: ").strip()
                    
                    if sub == '2':
                        printGeneralOuting(history)
                        if history:
                            print("\n   [P] Download Gate Pass (PDF)")
                            print("   [D] Delete a Request")
                            print("   [Enter] Go Back")
                            act = input("   Choice: ").strip().upper()
                            
                            if act == 'P':
                                try:
                                    idx = int(input("   Enter IDX to download: ")) - 1
                                    if 0 <= idx < len(history):
                                        item = history[idx]
                                        if item['download_url']:
                                            print("   [.] Downloading...")
                                            import os
                                            home = os.path.expanduser("~")
                                            download_folder = os.path.join(home, "Downloads")
                                            clean_date = item['out_date'].replace(" ", "-")
                                            filename = f"general_outing_{clean_date}.pdf"
                                            full_path = os.path.join(download_folder, filename)
                                            res, msg = await download_g_outpass(client, item['download_url'], full_path)
                                            if res: print(f"   ✅ Saved to: {full_path}")
                                            else:   print(f"   ❌ {msg}")
                                        else:
                                            print("   [!] No pass available (Must be Approved).")
                                    else: print("   [!] Invalid Index.")
                                except ValueError: print("   [!] Please enter a number.")
                            
                            elif act == 'D':
                                try:
                                    idx = int(input("   Enter IDX to delete: ")) - 1
                                    if 0 <= idx < len(history):
                                        item = history[idx]
                                        if "Wait" in item['status'] or "Pending" in item['status']:
                                                if item['booking_id']:
                                                    confirm = input(f"   Delete request for {item['place']}? (y/n): ")
                                                    if confirm.lower() == 'y':
                                                        res, msg = await deleteGeneralOuting(client, item['booking_id'])
                                                        if res: print(f"   ✅ {msg}")
                                                        else:   print(f"   ❌ {msg}")
                                        else: print("   [!] Cannot delete. (Only 'Waiting' requests can be deleted)")
                                    else: print("   [!] Invalid Index.")
                                except ValueError: print("   [!] Please enter a number.")

                    elif sub == '1':
                        print("\n   --- NEW OUTING APPLICATION ---")
                        print("   ⚠️  NOTE: You must apply at least 24 HOURS in advance.")
                        try:
                            place = input("\n   Place of Visit : ").strip()
                            if place == '0': continue
                            purpose = input("   Purpose        : ").strip()
                            if purpose == '0': continue
                            out_d = input("   Out Date (DD-MMM-YYYY): ").strip()
                            if out_d == '0': continue
                            out_t = input("   Out Time (HH:MM): ").strip()
                            in_d  = input("   In Date         : ").strip()
                            in_t  = input("   In Time (HH:MM): ").strip()
                            
                            confirm = input("\n   Submit this request? (y/n): ").lower()
                            if confirm == 'y':
                                print("\n   [.] Submitting...")
                                success, msg = await submitGeneralOuting(client, info, place, purpose, out_d, out_t, in_d, in_t)
                                if success: print(f"   ✅ SUCCESS: {msg}")
                                else: print(f"   ❌ FAILED: {msg}")
                        except Exception as e: print(f"   [!] Error: {e}")

                elif choice == '11': # Weekend Outing
                    print_header("WEEKEND OUTING SYSTEM")
                    print("   [.] Fetching details...")
                    data = await fetchWeekendOuting(client)
                    if not data:
                        print("   [!] Could not fetch data. (Check internet or re-login)")
                        continue

                    info = data.get('info', {})
                    history = data.get('history', [])
                    can_apply = data.get('can_apply', True)

                    print(f"\n   STUDENT: {info.get('name')}")
                    print(f"   BLOCK  : {info.get('hostelBlock')} | ROOM: {info.get('roomNo')}")
                    
                    if not can_apply: print("   STATUS : 🔴 Applications Closed (Tue-Fri Only)")
                    else: print("   STATUS : 🟢 Applications Open")
                        
                    print("   " + "-" * 60)
                    while True:
                        print("\n   MENU:")
                        print("   1. Apply for Weekend Outing")
                        print("   2. View History / Actions")
                        print("   0. Back")
                        
                        sub = input("\n   Select Option: ").strip()
                        if sub == '0': break
                        
                        if sub == '1':
                            if not can_apply:
                                print("\n   ⚠️  ACCESS DENIED: Time Restriction")
                                input("   Press Enter to return...")
                                continue
                            
                            try:
                                places = ["Vijayawada", "Guntur", "Tenali", "Eluru", "Others"]
                                print("\n   Select Place of Visit:")
                                for i, p in enumerate(places): print(f"   {i+1}. {p}")
                                p_idx = input("   Choice: ").strip()
                                if p_idx == '0': continue
                                place = places[int(p_idx) - 1]
                                
                                purpose = input("\n   Purpose (Max 20 chars): ").strip()
                                if purpose == '0': continue
                                out_d = input("   Date (DD-MMM-YYYY): ").strip()
                                if out_d == '0': continue
                                
                                times = ["9:30 AM- 3:30PM", "10:30 AM- 4:30PM", "11:30 AM- 5:30PM", "12:30 PM- 6:30PM"]
                                print("\n   Select Outing Time:")
                                for i, t in enumerate(times): print(f"   {i+1}. {t}")
                                t_idx = input("   Choice: ").strip()
                                if t_idx == '0': continue
                                out_t = times[int(t_idx) - 1]
                                
                                import re
                                while True:
                                    contact = input("\n   Contact No (10 digits): ").strip()
                                    if contact == '0': break
                                    if re.match(r"^[7-9]\d{9}$", contact): break
                                    else: print("   [!] Invalid format.")
                                if contact == '0': continue
                                
                                confirm = input(f"\n   Submit request for {place}? (y/n): ").lower()
                                if confirm == 'y':
                                    print("\n   [.] Submitting payload...")
                                    success, msg = await submitWeekendOuting(client, info, place, purpose, out_d, out_t, contact)
                                    if success: print(f"   ✅ SUCCESS: {msg}")
                                    else: print(f"   ❌ FAILED: {msg}")
                            except Exception as e: print(f"   [!] Error: {e}")

                        elif sub == '2':
                            printWeekendOuting(history)
                            if history:
                                print("\n   [#] Type Row Number to Download Outpass")
                                print("   [D] Delete a Pending Request")
                                print("   [0] Go Back")
                                act = input("\n   Choice: ").strip().upper()
                                
                                if act == '0' or act == '': continue
                                elif act.upper() == 'D':
                                    try:
                                        idx = int(input("   Enter Row # to delete: ")) - 1
                                        if 0 <= idx < len(history):
                                            item = history[idx]
                                            if "Wait" in item['status'] or "Pending" in item['status']:
                                                if item.get('booking_id'):
                                                    res, msg = await deleteWeekendOuting(client, item['booking_id'])
                                                    if res: print(f"   ✅ {msg}")
                                                    else:   print(f"   ❌ {msg}")
                                            else: print("   [!] Cannot delete active requests.")
                                    except ValueError: print("   [!] Please enter a valid number.")
                                        
                                elif act.isdigit():
                                    idx = int(act) - 1
                                    if 0 <= idx < len(history):
                                        selected_outing = history[idx]
                                        if selected_outing['download_link']:
                                            import os
                                            save_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                                            fname = f"Outpass_{selected_outing['out_date']}_{selected_outing['place']}"
                                            print(f"   [.] Securing Outpass from VTOP servers...")
                                            res, path = await download_w_outpass(client, selected_outing['download_link'], save_dir, fname)
                                            if res: print(f"   [✓] Saved to: {path}")
                                            else: print(f"   [x] Failed to download Outpass.")
                                        else: print("   [!] Outpass is not available yet.")

                elif choice == '12': # 75% Calculator
                    print_header("75% ATTENDANCE CALCULATOR")
                    try:
                        import math
                        target = 75.0
                        present = int(input("   Classes Attended (Present): ").strip())
                        total = int(input("   Total Classes Conducted:    ").strip())
                        
                        if total == 0: continue
                        current_pct = (present / total) * 100
                        print("   " + "─" * 60)
                        print(f"   Current Attendance: {current_pct:.2f}%")
                        
                        if current_pct >= target:
                            bunkable = math.floor((100 * present - target * total) / target)
                            if bunkable > 0:
                                print(f"   ✅ You are SAFE! You can bunk {int(bunkable)} next classes.")
                            else:
                                print(f"   ⚠️  You are on the edge! You cannot miss any more classes.")
                        else:
                            needed = math.ceil((target * total - 100 * present) / (100 - target))
                            print(f"   ❌ You are in the DANGER ZONE! Attend {int(needed)} next classes continuously.")
                    except ValueError: print("   [!] Invalid input.")
                    input("\n   Press Enter to return...")

                elif choice == '13': # Student Profile
                    print_header("STUDENT PROFILE")
                    print_profile(profile_data)

                elif choice == '14': # Change Semester
                    if not available_sems:
                        print("   ...No semester data available. Re-scraping...")
                        available_sems = await fetchSemesters(client)
                    if available_sems:
                        print_header("SELECT SEMESTER")
                        for i, s in enumerate(available_sems): print(f"   {i+1}. {s['name']}")
                        sel = input("\nSelect a semester number (0 to cancel): ").strip()
                        if sel == '0': continue
                        try:
                            idx = int(sel) - 1
                            if 0 <= idx < len(available_sems):
                                target_sem = available_sems[idx]['id']
                                current_sem_name = available_sems[idx]['name']
                                print(f"[+] Active Semester set to: {current_sem_name}")
                        except ValueError: pass

                elif choice == '15': # Update Credentials
                    print("\n   =======================================")
                    print("   🔄 UPDATE SAVED CREDENTIALS")
                    print("   =======================================")
                    new_user = input("   👉 Enter Registration Number: ").strip().upper()
                    import pwinput
                    new_pass = pwinput.pwinput(prompt="   👉 Enter New VTOP Password: ", mask="*").strip()
                    
                    if new_user and new_pass:
                        confirm = input("\n   Save new credentials and restart? (y/n): ").strip().lower()
                        if confirm == 'y':
                            with open("credentials.txt", "w") as f:
                                f.write(f"{new_user}\n{new_pass}\n")
                            import os
                            import sys
                            print("   [✓] Credentials updated successfully! Restarting...")
                            os.execv(sys.executable, ['python'] + sys.argv)
                
                elif choice == '16': # Bunk Predictor
                    try:
                        import json
                        import os
                        from datetime import datetime as dt_obj, timedelta
                        import services
                        import asyncio

                        print("\n   [ BUNK SIMULATOR ]")
                        current_year = dt_obj.now().year
                        if os.path.exists("bunk_cache.json"):
                            try:
                                with open("bunk_cache.json", "r") as f:
                                    cache_data = json.load(f)
                                    if isinstance(cache_data, dict) and "blocked_dates" in cache_data:
                                        b_dates = cache_data["blocked_dates"]
                                        if b_dates:
                                            today_dt = dt_obj.now().replace(hour=0, minute=0, second=0, microsecond=0)
                                            print("   [i] Upcoming Non-Instructional, Exam Days and Holidays:")
                                            
                                            printed_any = False
                                            for d_str, purpose in b_dates.items():
                                                try:
                                                    event_date = dt_obj.strptime(f"{d_str}-{current_year}", "%d-%m-%Y")
                                                    # Only print if the event is today or in the future
                                                    if event_date >= today_dt:
                                                        day_name = event_date.strftime("%A")
                                                        print(f"       {d_str} -- {day_name:<9} -- {purpose}")
                                                        printed_any = True
                                                except Exception:
                                                    pass # Silently skip malformed dates
                                                    
                                            if not printed_any:
                                                print("       (No upcoming holidays/exams found)")
                                            print("   " + "-"*45)
                            except Exception: pass

                        bunk_input = input("   Enter dates/range to bunk (ex: 24-2, 5-3 or 3-3 to 6-3): ").strip()
                        if not bunk_input: continue

                        valid_dates = []
                        try:
                            if 'to' in bunk_input.lower():
                                start_str, end_str = [x.strip() for x in bunk_input.lower().split('to')]
                                start_dt = dt_obj.strptime(f"{start_str}-{current_year}", "%d-%m-%Y")
                                end_dt = dt_obj.strptime(f"{end_str}-{current_year}", "%d-%m-%Y")
                                delta = end_dt - start_dt
                                for i in range(delta.days + 1): valid_dates.append(start_dt + timedelta(days=i))
                            else:
                                date_strs = [x.strip() for x in bunk_input.split(',')]
                                for ds in date_strs: valid_dates.append(dt_obj.strptime(f"{ds}-{current_year}", "%d-%m-%Y"))
                        except Exception as e:
                            print(f"   [!] Invalid date format.")
                            continue

                        # --- SEMESTER BOUNDARY CHECK ---
                        sem_end_dt = dt_obj(current_year, 5, 19) # May 19th
                        if max(valid_dates) > sem_end_dt:
                            print(f"\n   [!] Halt: The semester officially ends on 19-05.")
                            print("   [!] You cannot simulate attendance beyond this date.")
                            continue

                        print(f"\n   [.] Fetching timetable...")
                        timetable_data = await fetchTimetable(client, target_sem)
                        print(f"   [.] Fetching attendance...")
                        attendance_data = await fetchAttendance(client, target_sem)

                        if not timetable_data or not attendance_data:
                            print("   [x] Data fetch failed. Cannot run simulation.")
                            continue

                        print(f"   [.] Syncing exact timelines for subjects... (Takes a few seconds)")
                        for sub in attendance_data:
                            c_id = sub.get('course_id')
                            type_id = sub.get('type_id') or sub.get('type_code')
                            sub['exact_last_date'] = None 
                            if c_id and type_id:
                                try:
                                    history = await fetchAttendanceDetail(client, target_sem, c_id, type_id)
                                    if history:
                                        def p_date(x):
                                            try: return dt_obj.strptime(x['date'], "%d-%b-%Y")
                                            except:
                                                try: return dt_obj.strptime(x['date'], "%d-%m-%Y")
                                                except: return dt_obj.min
                                        
                                        history.sort(key=p_date)
                                        sub['exact_last_date'] = history[-1].get('date') 
                                        
                                    # Crucial anti-spam delay so VTOP doesn't block your connection
                                    await asyncio.sleep(0.4)
                                except Exception: pass

                        academic_calendar_blocks = {}
                        if os.path.exists("bunk_cache.json"):
                            try:
                                with open("bunk_cache.json", "r") as f:
                                    cache_data = json.load(f)
                                    if isinstance(cache_data, dict) and "blocked_dates" in cache_data:
                                        for date_str, reason in cache_data["blocked_dates"].items():
                                            academic_calendar_blocks[date_str] = str(reason)
                            except Exception: pass

                        report = services.simulate_multi_day_bunk(valid_dates, timetable_data, attendance_data, academic_calendar_blocks)
                        print(report)
                        input("\n   Press Enter to return to menu...")
                    except Exception as e: 
                        print(f"   [!] Simulation error: {e}")

if __name__ == "__main__":
    #check_for_updates()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Exiting...")