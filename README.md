 # VIT-AP VTOP CLI Dashboard 🎓

A fast, asynchronous command-line interface for the VIT-AP Student Portal (VTOP). Access your attendance, timetable, marks, and course materials directly from your terminal or mobile device.

## 🚀 Features

* **⚡ Fast & Async:** Built with `httpx` and `asyncio` for rapid data fetching.
* **📊 Rich UI:** Beautiful tables and colored output using the `rich` library.
* **📥 Material Downloader:** Download lecture slides and reference materials directly to your device.
* **📅 Schedules:** View today's classes and full semester timetable.
* **📝 Academic Data:** Check attendance history, internal marks, exam schedules, and grade history.

## 🛠️ Installation

### 1. Clone the Repository 
```bash
git clone [https://github.com/vrmanideep/vtop.git](https://github.com/vrmanideep/vtop.git)
cd vtop
```
Or Download and extract the zip file
```bash
(Note: Clicking this link will start downloading the .zip folder)

https://github.com/vrmanideep/vtop/archive/refs/heads/main.zip
cd vtop-main
```
### 2. Install Dependencies
```bash
pip install -r requirements.txt
```
### 3. 🔑 Configuration
To log in automatically, create a file named credentials.txt in the root directory.

Format:
Line 1: Your Registration Number (e.g., 24BCExxxx)
Line 2: Your VTOP Password

```PlainText
24BCAxxxx
password
```

### 🖥️ Usage
Simply run the main script to start the interactive dashboard:
```python
python vtop.py
```
### Menu Options:
1. **Profile:** View personal and proctor details.
2. **Transcript:** View complete grade history and CGPA.
3. **Attendance:** Detailed subject-wise attendance tracking.
4. **Timetable:** Full weekly schedule.
5. **Today's Schedule:** What classes do you have right now?
6. **Internal Marks:** View marks for CAT, FAT, and assignments.
7. **Exam Schedule:** Upcoming exam dates and seat locations.
8. **Change Semester:** Switch context to view previous semester data.
9. **Academic Credits:** View credit distribution (Earned vs Required).
10. **Course Page:** View and download lecture notes.
11. **General Outing:** Apply for General Outing and View/ download outpass.
12. **Weekend Outing:** View/ download outpass.

### ⚠️ Disclaimer
This is an unofficial client for the VIT-AP VTOP portal. It is developed for educational purposes and personal use.
The tool uses SSL verification bypassing (verify=False) to communicate with the VTOP server.
Use responsibly and ensure your credentials are kept secure locally.