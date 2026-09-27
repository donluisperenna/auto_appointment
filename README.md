# Introduction
This is an automatic appointment making executable robot.
# Release
## Latest version
[下載 v1.0.4 版本 (exe)](https://github.com/donluisperenna/auto_appointment/releases/download/v1.0.4/auto_appointment_v1.0.4.exe)

[下載 v1.0.4 版本 (rar)](https://github.com/donluisperenna/auto_appointment/releases/download/v1.0.4/auto_appointment_v1.0.4.rar)

## Previous version

| Version| Download link | Discription|
| v1.0.3 | [下載 v1.0.3 版本 (rar)](https://github.com/donluisperenna/auto_appointment/releases/download/v1.0.3/auto_appointment_v1.0.3.rar) | |
| v1.0.2 | [下載 v1.0.2 版本 (rar)](https://github.com/donluisperenna/auto_appointment/releases/download/v1.0.2/auto_appointment_v1.0.2.rar) | |
| v1.0.1 | [下載 v1.0.1 版本 (exe)](https://github.com/donluisperenna/auto_appointment/releases/download/v1.0.1/auto_appointment_v1.0.1.exe) [下載 v1.0.1 版本 (rar)](https://github.com/donluisperenna/auto_appointment/releases/download/v1.0.1/auto_appointment_v1.0.1.rar) |  |
| v1.0.0 | [下載 v1.0.0 版本](https://github.com/donluisperenna/auto_appointment/releases/download/v1.0.0/auto_appointment_v1.0.0.exe) | Original version |

# Usage
## Installation
1. `pip install -r requirements.txt`
2. `playwright install`
3. Copy `config.example.json` to `config.json`, fill in personal information.
    "target_dept": department of your interest;
    "target_doctor": doctor of your interest;
    "target_date": the date of the outpatient clinic;
    "my_id": your identification number;
    "my_year": birth year;
    "my_month": birth month;
    "my_day": birth date;
    "target_time": time for appointment making in the form of hh:mm:ss;
    "automatic_confirm":if set to 'True', the program would autamtically confirm your appointment; otherwise, you need to press 'Enter' to proceed;
    "discord_webhook_url": your discord webhook url; if nothing typed in, this function would not work
## Run
`python gui_main.py`
## Alternatives
Alternatively, you can use the GUI itself to fill in personal information and run the programs.
# Disclaimer
This project is intended solely for programming language learning, academic research, and personal automation technology exchange.
Do not use this tool for commercial profit, malicious consumption of medical resources, or any behavior that undermines the fairness of hospital appointment systems.
Users shall assume full responsibility for any legal disputes arising from the use of this program; the developers accept no liability whatsoever.