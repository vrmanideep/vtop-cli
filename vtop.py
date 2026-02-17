import argparse
import asyncio
import json
import time
import sys
import subprocess
import os
import glob
import re
from rich.console import Console
from datetime import datetime as dt 
from vitap_vtop_client.client import VtopClient

console = Console()

from services import (
    vtopClientLogin,
    fetchSemesters,
    fetchAttendance,
    fetchAttendanceDetail,
    fetchMarks,
    fetchTimetable,
    fetchExamSchedule,
    fetchGradeHistory,
    fetchProfile,
    fetchCredits,
    fetchCoursePage,
    fetchCourseList, 
    fetchCourseClasses,
    download_course_material, 
    get_credentials,
    fetchGeneralOuting,
    submitGeneralOuting,
    download_g_outpass,
    fetchWeekendOuting,
    submitWeekendOuting,
    deleteWeekendOuting,
    download_w_outpass,
    fetchDACourseList,
    fetchDADetails
)

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
        print(f"\n   {status_icon} {code} : {name} ({ctype})")
        print(f"       Attendance: {perc}% ({attended}/{total})")
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
                    print(f"       📅 Attendance Last Updated on: {last_date}")
                    absents = [h for h in history if "Present" not in h['status']]
                    if absents:
                        print(f"       [!] Found {len(absents)} Absences:")
                        print(f"           {'DATE':<12} {'DAY':<5} {'SLOT':<8} {'STATUS'}") 
                        print("           " + "-" * 40)
                        absents.sort(key=parse_date, reverse=True)
                        for h in absents:
                            date_str = h.get('date', '-')
                            day_name = "-"
                            try:
                                d_obj = parse_date(h)
                                if d_obj != dt.min:
                                    day_name = d_obj.strftime("%a")
                            except: pass
                            print(f"           {date_str:<12} {day_name:<5} {h['slot']:<8} ❌ {h['status']}")
                    else:
                          print(f"       (History fetched: {len(history)} classes, All Present)")
                else:
                    print("       (No history records found)")
            except Exception as e:
                print(f"       [!] Detail fetch error: {e}")
        else:
            print("       [!] Cannot fetch details (ID missing).")
        print("   " + "-" * 40)

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
    reg_no, password = get_credentials("credentials.txt")
    print(f"[-] Connecting to V-TOP as {reg_no}...")
    
    async with VtopClient(reg_no, password) as client:
        if not await vtopClientLogin(client):
            print(f"[!] Login Failed.")
            return

        # Fetch Initial Data
        await client._client.get("https://vtop.vitap.ac.in/vtop/content")
        available_sems = await fetchSemesters(client)
        profile_data = await fetchProfile(client)
        
        student_name = profile_data.get("basic", {}).get("name", "Student")
        target_sem = available_sems[0]['id'] if available_sems else None
        current_sem_name = available_sems[0]['name'] if available_sems else "None"

        print(f"\n{'='*55}")
        print(f" SUCCESS  : Logged in as {student_name}")
        print(f" REG NO   : {reg_no}")
        print(f" CURRENT SEM : {current_sem_name}")
        print(f"{'='*55}")


        while True:
            print("\nAVAILABLE OPTIONS:")
            print("  1. View Profile & Proctor Details")
            print("  2. View Grade History (Transcript)")
            print("  3. View Attendance")
            print("  4. View Full Timetable")
            print("  5. View Today's Schedule")
            print("  6. View Internal Marks")
            print("  7. View Exam Schedule")
            print("  8. Change/Select Semester")
            print("  9. View Credits (Academics)")
            print("  10. View Course Page (Lecture Plan & Materials)")
            print("  11. General Outing")
            print("  12. Weekend Outing")
            print("  13. Digital Assignments")
            print("  0. Exit")
            
            
            choice = input(f"\n[{reg_no}] Enter choice (0-13): ").strip()

            if choice == '0':
                print("Logging out... Goodbye!")
                break
            
            if choice == '1':
                print_header("STUDENT PROFILE")
                print_profile(profile_data)

            elif choice == '2':
                print_header("ACADEMIC TRANSCRIPT")
                g_data = await fetchGradeHistory(client)
                print_grade_history(g_data)

            elif choice == '3':
                if not target_sem:
                    print("[!] No semester selected. Use option 8.")
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
            
            elif choice == '4':
                if not target_sem:
                    print("[!] No semester selected. Use option 8.")
                    continue
                print_header(f"FULL TIMETABLE - {current_sem_name}")
                data = await fetchTimetable(client, target_sem)
                print_timetable(data)

            elif choice == '5':
                if not target_sem:
                    print("[!] No semester selected. Use option 8.")
                    continue
                print_header(f"TODAY'S SCHEDULE - {current_sem_name}")
                data = await fetchTimetable(client, target_sem)
                print_today_schedule(data)

            elif choice == '6':
                if not target_sem:
                    print("[!] No semester selected. Use option 8.")
                    continue
                print_header(f"INTERNAL MARKS - {current_sem_name}")
                data = await fetchMarks(client, target_sem)
                print_marks(data)

            elif choice == '7':
                if not target_sem:
                    print("[!] No semester selected. Use option 8.")
                    continue
                print_header(f"EXAM SCHEDULE - {current_sem_name}")
                data = await fetchExamSchedule(client, target_sem)
                print_exam_schedule(data)

            elif choice == '8':
                if not available_sems:
                    print("   ...No semester data available. Re-scraping...")
                    available_sems = await fetchSemesters(client)
                if available_sems:
                    print_header("SELECT SEMESTER")
                    for i, s in enumerate(available_sems):
                        print(f"   {i+1}. {s['name']}")
                    sel = input("\nSelect a semester number (0 to cancel): ").strip()
                    if sel == '0': continue
                    try:
                        idx = int(sel) - 1
                        if 0 <= idx < len(available_sems):
                            target_sem = available_sems[idx]['id']
                            current_sem_name = available_sems[idx]['name']
                            print(f"[+] Active Semester set to: {current_sem_name}")
                        else:
                            print("[!] Invalid selection.")
                    except ValueError:
                        print("[!] Please enter a valid number.")

            elif choice == '9':
                print_header("ACADEMIC CREDITS DISTRIBUTION")
                c_data = await fetchCredits(client)
                print_credits(c_data)

            elif choice == '10': 
                if not target_sem:
                    print("[!] No semester selected. Use option 8.")
                    continue
                
                print(f"   [.] Fetching Course List...")
                
                # STEP 1: Fetch the authoritative Master List
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

                            # STEP 2: Fetch specific classes/slots for this course
                            classes = await fetchCourseClasses(client, target_sem, selected_course['generic_class_id'])
                            
                            if not classes:
                                print(f"   [!] No active classes found for {selected_code}.")
                                continue

                            selected_class = None
                            
                            if len(classes) == 1:
                                selected_class = classes[0]
                                fac_clean = re.sub(r'^\d+\s*-\s*', '', selected_class['faculty'])
                                print(f"   [+] Auto-selected: SLOT: {selected_class['slot']} | FAC: {fac_clean}")
                            else:
                                print(f"\n   SELECT COMPONENT FOR {selected_code}:")
                                print(f"   {'#':<4} {'SLOT':<17} {'FACULTY NAME'}")
                                print("   " + "-" * 60)
                                
                                current_slot = ""
                                for i, cls in enumerate(classes):
                                    # Group by Slot for visual clarity
                                    if cls['slot'] != current_slot:
                                        if current_slot != "": print("")
                                        print(f"   🔹 [{cls['slot']}]")
                                        current_slot = cls['slot']

                                    # Clean Faculty Name
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

                            # STEP 3: Fetch the final materials page
                            c_page = await fetchCoursePage(
                                client, 
                                target_sem, 
                                selected_class['class_id'], 
                                selected_class['erp_id']
                            )
                            
                            print_course_page_table(c_page)
                            
                            # --- DOWNLOAD LOOP ---
                            home = os.path.expanduser("~")
                            save_dir = os.path.join(home, "Downloads")

                            # Helper function to skip existing files
                            def check_exists(base_name):
                                safe_name = re.sub(r'[\\/*?:"<>|]', "", base_name).strip()
                                if not safe_name: safe_name = "downloaded_material"
                                return len(glob.glob(os.path.join(save_dir, f"{safe_name}.*"))) > 0

                            # Helper function to format General Material Names
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
                                print("   [1, 2..] Enter S.No to download a specific lecture")
                                print("   [G1, G2] Enter G1, G2.. to download General Material")
                                print("   [A]      Download ALL materials (Skips existing files)")
                                print("   [0]      Back to Subject List") 
                                
                                dl_choice = input("\n   Choice: ").strip().upper()
                                if dl_choice == '0': break 
                                
                                # --- 1. Download ALL ---
                                if dl_choice == 'A':
                                    count = 0
                                    skipped = 0
                                    print(f"   [.] Saving files directly to: {save_dir}")
                                    
                                    # Download Lectures
                                    for lec in c_page['lectures']:
                                        # Sanitize the topic so Windows/Mac doesn't crash on bad characters
                                        safe_topic = re.sub(r'[\\/*?:"<>|]', "", lec['topic'])[:50]
                                        
                                        # 1. Main Lecture
                                        if lec.get('download_path'):
                                            fname = f"{selected_code}_{safe_topic}"
                                            if check_exists(fname):
                                                print(f"   [-] Skipped (Already exists): {fname[:50]}...")
                                                skipped += 1
                                            else:
                                                res, _ = await download_course_material(client, lec['download_path'], save_dir, fname)
                                                if res: count += 1
                                                
                                        # 2. Reference Materials
                                        for r_idx, r_path in enumerate(lec.get('ref_paths', [])):
                                            fname = f"{selected_code}_{safe_topic}_Ref_{r_idx+1}"
                                            if check_exists(fname):
                                                print(f"   [-] Skipped (Already exists): {fname[:50]}...")
                                                skipped += 1
                                            else:
                                                res, _ = await download_course_material(client, r_path, save_dir, fname)
                                                if res: count += 1
                                                
                                        # 3. Web Links (Print to CLI)
                                        if lec.get('web_links'):
                                            print(f"\n   [🔗] Web Links for: {lec['topic'][:50]}...")
                                            for link in lec['web_links']:
                                                print(f"        -> {link}")
                                            print("") # Spacer
                                            
                                    # Download General Materials
                                    for i, gen in enumerate(c_page.get('general', [])):
                                        fname = format_general_name(selected_code, gen['title'], i+1)
                                        if check_exists(fname):
                                            print(f"   [-] Skipped (Already exists): {fname[:50]}...")
                                            skipped += 1
                                        else:
                                            res, _ = await download_course_material(client, gen['download_path'], save_dir, fname)
                                            if res: count += 1
                                        
                                    print(f"   [✓] Downloaded {count} new files. (Skipped {skipped})")
                                            
                                    # Download General Materials
                                    for i, gen in enumerate(c_page['general']):
                                        fname = format_general_name(selected_code, gen['title'], i+1)
                                        if check_exists(fname):
                                            print(f"   [-] Skipped (Already exists): {fname[:50]}...")
                                            skipped += 1
                                        else:
                                            res, _ = await download_course_material(client, gen['download_path'], save_dir, fname)
                                            if res: count += 1
                                        
                                    print(f"   [✓] Downloaded {count} new files. (Skipped {skipped})")

                                # --- 2. Download General Material (e.g., G1) ---
                                elif dl_choice.startswith('G'):
                                    try:
                                        g_idx = int(dl_choice[1:]) - 1
                                        if 0 <= g_idx < len(c_page['general']):
                                            item = c_page['general'][g_idx]
                                            fname = format_general_name(selected_code, item['title'], g_idx+1)
                                            
                                            if check_exists(fname):
                                                print(f"   [-] File already exists in Downloads: {fname}")
                                            else:
                                                print(f"   [.] Downloading {fname}...")
                                                res, filepath = await download_course_material(client, item['download_path'], save_dir, fname)
                                                if res: print(f"   [✓] Saved to: {filepath}")
                                                else: print(f"   [x] Failed: {filepath}")
                                        else:
                                            print("   [!] Invalid G number.")
                                    except ValueError: 
                                        print("   [!] Invalid input format. Use G1, G2, etc.")

                                # --- 3. Download Specific Lecture ---
                                elif dl_choice.isdigit():
                                    try:
                                        target_sno = int(dl_choice)
                                        target_lec = next((l for l in c_page['lectures'] if l['s_no'] == target_sno), None)
                                        
                                        if target_lec:
                                            # Strip bad characters for the filename, but let it be long
                                            safe_topic = re.sub(r'[\\/*?:"<>|]', "", target_lec['topic'])[:50]
                                            downloads_started = False
                                            
                                            # 1. Download Main File
                                            if target_lec.get('download_path'):
                                                downloads_started = True
                                                fname = f"{selected_code}_{safe_topic}"
                                                if check_exists(fname): 
                                                    print(f"   [-] Main file already exists: {fname}")
                                                else:
                                                    print(f"   [.] Downloading Main: {fname}...")
                                                    res, filepath = await download_course_material(client, target_lec['download_path'], save_dir, fname)
                                                    if res: print(f"   [✓] Saved: {filepath}")
                                                    
                                            # 2. Download Reference Files
                                            for r_idx, r_path in enumerate(target_lec.get('ref_paths', [])):
                                                downloads_started = True
                                                fname = f"{selected_code}_{safe_topic}_Ref_{r_idx+1}"
                                                if check_exists(fname): 
                                                    print(f"   [-] Reference file already exists: {fname}")
                                                else:
                                                    print(f"   [.] Downloading Reference {r_idx+1}...")
                                                    res, filepath = await download_course_material(client, r_path, save_dir, fname)
                                                    if res: print(f"   [✓] Saved: {filepath}")
                                            
                                            # 3. Print Web Links to CLI
                                            if target_lec.get('web_links'):
                                                downloads_started = True
                                                print(f"\n   [🔗] Web Links for this lecture:")
                                                for link in target_lec['web_links']:
                                                    print(f"        -> {link}")
                                                
                                            # If literally nothing was there
                                            if not downloads_started:
                                                print("   [!] No materials available for this lecture.")
                                                
                                            # If literally nothing was there
                                            if not downloads_started:
                                                print("   [!] No materials available for this lecture.")
                                        else:
                                            print("   [!] Invalid Lecture S.No.")
                                    except ValueError: 
                                        print("   [!] Invalid number.")
                                        
                                # --- 4. Catch-all ---
                                else:
                                    print("   [!] Invalid command. Type a number, G#, or A.")

                        else:
                            print("   [!] Invalid selection.")
                    except ValueError:
                        print("   [!] Please enter a number.")

            elif choice == '11':
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
                                        
                                        home = os.path.expanduser("~")
                                        download_folder = os.path.join(home, "Downloads")
                                        clean_date = item['out_date'].replace(" ", "-")
                                        filename = f"general_outing_{clean_date}.pdf"
                                        full_path = os.path.join(download_folder, filename)
                                        res, msg = await download_g_outpass(client, item['download_url'], full_path)
                                        
                                        if res: 
                                            print(f"   ✅ Saved to: {full_path}")
                                        else:   
                                            print(f"   ❌ {msg}")
                                    else:
                                        print("   [!] No pass available (Must be Approved).")
                                else:
                                    print("   [!] Invalid Index.")
                            except ValueError:
                                print("   [!] Please enter a number.")
                        
                        elif act == 'D':
                            try:
                                idx = int(input("   Enter IDX to delete: ")) - 1
                                if 0 <= idx < len(history):
                                    item = history[idx]
                                    if "Wait" in item['status'] or "Pending" in item['status']:
                                         if item['booking_id']:
                                            confirm = input(f"   Delete request for {item['place']}? (y/n): ")
                                            if confirm.lower() == 'y':
                                                res, msg = await deleteOuting(client, item['booking_id'])
                                                if res: print(f"   ✅ {msg}")
                                                else:   print(f"   ❌ {msg}")
                                    else:
                                        print("   [!] Cannot delete. (Only 'Waiting' requests can be deleted)")
                                else:
                                    print("   [!] Invalid Index.")
                            except ValueError:
                                print("   [!] Please enter a number.")

                elif sub == '1':
                    print("\n   --- NEW OUTING APPLICATION ---")
                    print("   ⚠️  NOTE: You must apply at least 24 HOURS in advance.")
                    print("   [Enter '0' to Cancel and Go Back]")
                    
                    try:
                        place = input("\n   Place of Visit : ").strip()
                        if place == '0':
                            print("   [x] Cancelled.")
                            continue

                        purpose = input("   Purpose        : ").strip()
                        if purpose == '0':
                            print("   [x] Cancelled.")
                            continue

                        print("   (Format: DD-MMM-YYYY, e.g., 11-Feb-2026)")
                        out_d = input("   Out Date       : ").strip()
                        if out_d == '0': continue

                        out_t = input("   Out Time (HH:MM): ").strip()
                        
                        in_d  = input("   In Date        : ").strip()
                        in_t  = input("   In Time (HH:MM): ").strip()
                        
                        confirm = input("\n   Submit this request? (y/n): ").lower()
                        if confirm == 'y':
                            print("\n   [.] Submitting...")
                            success, msg = await submitGeneralOuting(client, info, place, purpose, out_d, out_t, in_d, in_t)
                            
                            if success:
                                print(f"   ✅ SUCCESS: {msg}")
                            else:
                                print(f"   ❌ FAILED: {msg}")
                        else:
                            print("   [x] Cancelled.")

                    except Exception as e:
                        print(f"   [!] Error: {e}")

            elif choice == '12':
                
                
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
                
                if not can_apply:
                    print("   STATUS : 🔴 Applications Closed (Tue-Fri Only)")
                else:
                    print("   STATUS : 🟢 Applications Open")
                    
                print("   " + "-" * 60)
                
                while True:
                    print("\n   MENU:")
                    print("   1. Apply for Weekend Outing")
                    print("   2. View History / Delete / Download Outpass")
                    print("   0. Back")
                    
                    sub = input("\n   Select Option: ").strip()
                    if sub == '0': break
                    
                    if sub == '1':
                        if not can_apply:
                            print("\n   ⚠️  ACCESS DENIED: Time Restriction")
                            print("   [!] You can only apply from Tuesday 12:00 AM to Friday 11:59 PM.")
                            input("   Press Enter to return...")
                            continue
                        
                        print("\n   --- NEW WEEKEND OUTING ---")
                        print("   [Enter '0' to Cancel at any time]")
                        
                        try:
                            # 1. Strict Place Selection
                            places = ["Vijayawada", "Guntur", "Tenali", "Eluru", "Others"]
                            print("\n   Select Place of Visit:")
                            for i, p in enumerate(places):
                                print(f"   {i+1}. {p}")
                            p_idx = input("   Choice: ").strip()
                            if p_idx == '0': continue
                            place = places[int(p_idx) - 1]
                            
                            # 2. Purpose
                            purpose = input("\n   Purpose (Max 20 chars): ").strip()
                            if purpose == '0': continue
                            
                            # 3. Date
                            print("\n   (Format: DD-MMM-YYYY, e.g., 22-Feb-2026)")
                            print("   *Note: Must be within the next 6 days.")
                            out_d = input("   Date: ").strip()
                            if out_d == '0': continue
                            
                            # 4. Strict Time Selection
                            times = [
                                "9:30 AM- 3:30PM", 
                                "10:30 AM- 4:30PM", 
                                "11:30 AM- 5:30PM", 
                                "12:30 PM- 6:30PM"
                            ]
                            print("\n   Select Outing Time:")
                            for i, t in enumerate(times):
                                print(f"   {i+1}. {t}")
                            t_idx = input("   Choice: ").strip()
                            if t_idx == '0': continue
                            out_t = times[int(t_idx) - 1]
                            
                            # 5. Strict Contact Validation
                            import re
                            while True:
                                contact = input("\n   Contact No (10 digits, starts with 7-9): ").strip()
                                if contact == '0': break
                                if re.match(r"^[7-9]\d{9}$", contact):
                                    break
                                else:
                                    print("   [!] Invalid format. Try again.")
                            if contact == '0': continue
                            
                            confirm = input(f"\n   Submit request for {place} on {out_d}? (y/n): ").lower()
                            if confirm == 'y':
                                print("\n   [.] Submitting payload...")
                                success, msg = await submitWeekendOuting(client, info, place, purpose, out_d, out_t, contact)
                                if success: 
                                    print(f"   ✅ SUCCESS: {msg}")
                                    data = await fetchWeekendOuting(client)
                                    history = data.get('history', [])
                                else: 
                                    print(f"   ❌ FAILED: {msg}")
                            else: 
                                print("   [x] Cancelled.")
                                
                        except (ValueError, IndexError): 
                            print("   [!] Invalid selection. Please enter the correct number.")
                        except Exception as e: 
                            print(f"   [!] Error: {e}")

                    elif sub == '2':
                        printWeekendOuting(history)
                        
                        if history:
                            print("\n   [#] Type Row Number to Download Outpass")
                            print("   [D] Delete a Pending Request")
                            print("   [0] Go Back")
                            act = input("\n   Choice: ").strip().upper()
                            
                            if act == '0' or act == '':
                                continue
                                
                            # HANDLE DELETION
                            elif act == 'D':
                                try:
                                    idx = int(input("   Enter Row # to delete: ")) - 1
                                    if 0 <= idx < len(history):
                                        item = history[idx]
                                        if "Wait" in item['status'] or "Pending" in item['status']:
                                            if item['booking_id']:
                                                confirm = input(f"   Delete request for {item['place']}? (y/n): ")
                                                if confirm.lower() == 'y':
                                                    res, msg = await deleteWeekendOuting(client, item['booking_id'])
                                                    if res: 
                                                        print(f"   ✅ {msg}")
                                                        data = await fetchWeekendOuting(client)
                                                        history = data.get('history', [])
                                                    else:   
                                                        print(f"   ❌ {msg}")
                                            else:
                                                print("   [!] Could not find Booking ID to delete.")
                                        else:
                                            print("   [!] Cannot delete active/processed requests.")
                                    else:
                                        print("   [!] Invalid Row Number.")
                                except ValueError:
                                    print("   [!] Please enter a valid number.")
                                    
                            # HANDLE PDF DOWNLOAD
                            elif act.isdigit():
                                idx = int(act) - 1
                                if 0 <= idx < len(history):
                                    selected_outing = history[idx]
                                    if selected_outing['download_link']:
                                        save_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                                        fname = f"Outpass_{selected_outing['out_date']}_{selected_outing['place']}"
                                        
                                        print(f"   [.] Securing Outpass from VTOP servers...")
                                        res, path = await download_w_outpass(
                                            client, 
                                            selected_outing['download_link'], 
                                            save_dir, 
                                            fname
                                        )
                                        if res: print(f"   [✓] Saved to: {path}")
                                        else: print(f"   [x] Failed to download Outpass.")
                                    else:
                                        print("   [!] Outpass is not available for this request yet.")
                                else:
                                    print("   [!] Invalid Row Number.")

            elif choice == '13':
                from services import fetchDACourseList, fetchDADetails
                
                if not target_sem:
                    print("[!] No semester selected. Use option 8.")
                    continue
                    
                print(f"   [.] Fetching Digital Assignment Courses...")
                da_courses = await fetchDACourseList(client, target_sem)
                
                if not da_courses:
                    print("   [!] No digital assignments found for this semester.")
                    continue
                    
                # --- OUTER LOOP: Course Selection ---
                while True:
                    print_header("DIGITAL ASSIGNMENTS")
                    print(f"   {'#':<3} {'CODE':<10} {'COURSE TITLE':<45} {'FACULTY'}")
                    print("   " + "─" * 90)
                    for i, c in enumerate(da_courses):
                        print(f"   {i+1:<3} {c['code']:<10} {c['title'][:43]:<45} {c['faculty'][:25]}")
                    print("   " + "─" * 90)
                    print("   0. Back to Main Menu")
                    
                    c_sel = input("\n   Select course number: ").strip()
                    if c_sel == '0': break
                    
                    try:
                        idx = int(c_sel) - 1
                        if 0 <= idx < len(da_courses):
                            selected_course = da_courses[idx]
                            print(f"\n   [.] Fetching assignments for {selected_course['code']}...")
                            assignments = await fetchDADetails(client, selected_course['class_id'])
                            
                            if not assignments:
                                print(f"   [!] No assignments posted yet for {selected_course['code']}.")
                                input("\n   Press Enter to continue...")
                                continue
                                
                            # --- INNER LOOP: Assignment Downloads ---
                            while True:
                                print(f"\n   ASSIGNMENTS: {selected_course['code']} - {selected_course['title']}")
                                print(f"   {'#':<3} {'TITLE':<25} {'DUE DATE':<15} {'FILES'}")
                                print("   " + "─" * 65)
                                
                                for asn in assignments:
                                    files = []
                                    if asn['qp_link']: files.append("📄 QP")
                                    if asn['sub_link']: files.append("✅ SUB")
                                    f_str = ", ".join(files) if files else "None"
                                    print(f"   {asn['s_no']:<3} {asn['title']:<25} {asn['due_date']:<15} {f_str}")
                                print("   " + "─" * 65)
                                print("   [#]  Enter # to Download Files")
                                print("   [A]  Download ALL Files for this course")
                                print("   [0]  Go Back")
                                
                                a_sel = input("\n   Choice: ").strip().upper()
                                if a_sel == '0': break
                                
                                save_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                                
                                if a_sel == 'A':
                                    print(f"   [.] Downloading all available files to {save_dir}...")
                                    for asn in assignments:
                                        if asn['qp_link']:
                                            fname = f"{selected_course['code']}_{asn['title'].replace(' ', '')}_QP"
                                            await download_course_material(client, asn['qp_link'], save_dir, fname)
                                        if asn['sub_link']:
                                            fname = f"{selected_course['code']}_{asn['title'].replace(' ', '')}_MySubmission"
                                            await download_course_material(client, asn['sub_link'], save_dir, fname)
                                    print("   [✓] Bulk download complete.")
                                    
                                elif a_sel.isdigit():
                                    a_idx = int(a_sel) - 1
                                    if 0 <= a_idx < len(assignments):
                                        target_asn = assignments[a_idx]
                                        
                                        if target_asn['qp_link']:
                                            fname = f"{selected_course['code']}_{target_asn['title'].replace(' ', '')}_QP"
                                            print(f"   [.] Downloading Question Paper...")
                                            res, path = await download_course_material(client, target_asn['qp_link'], save_dir, fname)
                                            if res: print(f"   [✓] Saved: {path}")
                                            
                                        if target_asn['sub_link']:
                                            fname = f"{selected_course['code']}_{target_asn['title'].replace(' ', '')}_MySubmission"
                                            print(f"   [.] Downloading Your Submission...")
                                            res, path = await download_course_material(client, target_asn['sub_link'], save_dir, fname)
                                            if res: print(f"   [✓] Saved: {path}")
                                            
                                        if not target_asn['qp_link'] and not target_asn['sub_link']:
                                            print("   [!] No files available to download for this assignment.")
                                    else:
                                        print("   [!] Invalid number.")
                        else:
                            print("   [!] Invalid selection.")
                    except ValueError:
                        print("   [!] Please enter a valid number.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Scraper stopped by user.")
    except Exception as e:
        print(f"\n[!] Fatal Error: {e}")