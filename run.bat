@echo off
REM Refresh all data and rebuild dashboard.html. Each step runs even if an earlier one fails.
cd /d "%~dp0"
if not exist logs mkdir logs
echo ===== %date% %time% ===== >> logs\run.log
python fetch_nwac.py >> logs\run.log 2>&1
python fetch_snotel.py >> logs\run.log 2>&1
python fetch_nws.py >> logs\run.log 2>&1
python fetch_avy.py >> logs\run.log 2>&1
python build_dashboard.py >> logs\run.log 2>&1
