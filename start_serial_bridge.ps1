# USB Serial -> website (use when WiFi POST fails)
# 1. Close Arduino Serial Monitor first (only one program can use COM port)
# 2. Run this script

Set-Location $PSScriptRoot

Write-Host ""
Write-Host "=== ESP32 Serial ports ===" -ForegroundColor Cyan
Get-CimInstance Win32_SerialPort | Select-Object DeviceID, Name | Format-Table -AutoSize

$port = Read-Host "Enter COM port (e.g. COM3)"
if (-not $port) { Write-Host "No port entered."; exit 1 }

Write-Host "Installing pyserial if needed..."
.\.venv\Scripts\pip.exe install pyserial -q

Write-Host ""
Write-Host "Starting bridge: $port -> http://192.168.1.2:5000" -ForegroundColor Green
Write-Host "Keep this window open. If needed, press ESP32 EN/RESET once so 'ESP32 IP: ...' is auto-saved."
Write-Host "Then open crop page and click Load from IoT sensors."
Write-Host ""

.\.venv\Scripts\python.exe iot\serial_bridge.py $port --server http://192.168.1.2:5000 --user-id 4 --save-esp-ip
