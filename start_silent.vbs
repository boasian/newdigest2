Dim WShell
Set WShell = CreateObject("WScript.Shell")
WShell.Run "cmd /c cd /d """ & Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\")) & """ && ""C:\Users\user\AppData\Local\Python\pythoncore-3.14-64\python.exe"" main.py", 0, False
