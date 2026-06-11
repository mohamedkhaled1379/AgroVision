# Run website + instructions for serial bridge
Set-Location $PSScriptRoot

Write-Host @"

========================================
  AgroVision IoT - START HERE
========================================

OPTION A - WiFi (ESP32 posts alone):
  1. Upload iot/iot.ino in Arduino IDE
  2. Serial Monitor 115200 -> copy ESP32 IP
  3. Run this script (website)
  4. http://192.168.1.2:5000/crop-recommendation
  5. Save ESP32 IP -> Load from IoT sensors

OPTION B - USB Serial (WiFi broken):
  1. Run start_serial_bridge.ps1 in another PowerShell
  2. Then open crop page -> Load from IoT sensors

Website starting now...
"@ -ForegroundColor Cyan

.\.venv\Scripts\python.exe app.py
