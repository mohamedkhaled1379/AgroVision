# Start AgroVision — run from project folder
Set-Location $PSScriptRoot
Write-Host "PC website: http://192.168.1.2:5000/crop-recommendation"
Write-Host "If ipconfig shows a different IPv4, update IOT_HOST in iot/iot.ino"
& ".\.venv\Scripts\python.exe" app.py
