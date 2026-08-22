@echo off
schtasks /create /tn "KAOMI 오늘의 단신 2" /tr "wscript.exe \"%~dp0start_silent.vbs\"" /sc daily /st 06:00 /f
echo.
echo 작업 스케줄러 등록 완료 (매일 06:00)
echo 확인: 작업 스케줄러 → "KAOMI 오늘의 단신 2"
pause
