 # VIT-AP VTOP CLI Dashboard 🎓

A fast, asynchronous command-line interface for the VIT-AP Student Portal (VTOP). Access your attendance, timetable, marks, and course materials directly from your terminal or mobile device.

## 🚀 Features

* **⚡ Fast & Async:** Built with `httpx` and `asyncio` for rapid data fetching.
* **📊 Rich UI:** Neatly designed tables using the `rich` library.
* **📥 Material Downloader:** Download lecture slides and reference materials directly to your device.
* **📅 Schedules:** View today's classes and full semester timetable.
* **📝 Academic Data:** Check attendance history, course page, internal marks, exam schedules, and grade history.

## 🛠️ Installation

### 1. Clone the Repository 
```bash
git clone https://github.com/vrmanideep/vtop-cli.git
cd vtop
```
Or [Download](https://github.com/vrmanideep/vtop-cli/archive/refs/heads/main.zip) and extract the zip file

**(Note: Clicking the **`Download`** button will start downloading the .zip folder)**

```bash
cd vtop-main
```
---
### 2. 🔑 Configuration
Run `python vtop.py`. If you are a first time user, the CLI will prompt you for your login credentials. It will save the credentials in a file `credentials.txt`, which will be used to login from the next time.

Format:
* **Line 1:** Your Registration Number (e.g., 24BCExxxx)
* **Line 2:** Your VTOP Password

```PlainText
24BCAxxxx
password
```
---
### 🖥️ Usage
Simply run the main script to start the interactive dashboard:
```python
python vtop.py
```
---
### Menu Options:
1. **Today's Schedule:** What classes do you have right now?
2. **Timetable:** Full weekly schedule.
3. **Attendance:** Detailed subject-wise attendance tracking.
4. **Course Page:** View and download lecture notes.
5. **Internal Marks:** View marks for CAT, FAT, and internal examinations.
6. **Exam Schedule:** Upcoming exam dates and seat locations.
7. **Grade History:** View complete grade history and CGPA.
8. **Digital Assignments:** View/download question paper and solutions. Cannot upload solution to V-TOP.
9. **Academic Credits:** View credit distribution (Earned vs Required).
10. **General Outing:** Apply for General Outing and View/download outpass.
11. **Weekend Outing:** Apply for Weekend Outing and View/download outpass.
12. **Attendance Calculator**: Calculates number of classes to bunk upon manual entry of number of total and attended classes.
13. **Profile:** View personal and proctor details.
14. **Change Semester:** Switch context to view previous semester data.
15. **Update Credentials**: Allows you to change your credentials to login when you changed them in V-TOP.
15. **Academic Calendar**: View Academic Calendar of the current semester. 
17. **Bunk Simulator**: Allows you to simulate attendance impact before skipping class by printing the attendnace of each class if you skipped on a particular date of your choice.
18. **Open V-TOP in browser**: Opens a logged in, ready-to-use V-TOP page.
---
### ⚠️ Disclaimer
This is an unofficial client for the [VIT-AP VTOP](https://vtop.vitap.ac.in/open/page) portal. It is developed for educational purposes and personal use.
 The authors assume no responsibility for account restrictions, policy violations, or misuse of the software.

---
### Contact & Support
Developed and maintained by **V R Manideep P** ([@vrmanideep](https://github.com/vrmanideep)).

* **Bug Reports & Feature Requests:** [Submit an Issue](https://github.com/vrmanideep/vtop-cli/issues)
* **Email:** pvrmanideep@gmail.com
* **LinkedIn:** [@vrmanideep](https://www.linkedin.com/in/vrmanideep)
---
### Credits

```PlainText
https://github.com/Udhay-Adithya/vitap-vtop-client
```