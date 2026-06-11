# Remove old test sensor rows — keeps only the latest reading
Set-Location $PSScriptRoot
$env:PYTHONPATH = $PSScriptRoot
.\.venv\Scripts\python.exe -c @"
from database import get_db_connection

conn = get_db_connection()
latest = conn.execute('SELECT MAX(id) AS max_id FROM iot_readings').fetchone()
latest_id = latest['max_id'] if latest else None
if latest_id:
    conn.execute('DELETE FROM iot_readings WHERE id < ?', (latest_id,))
    conn.commit()
    print('Deleted old readings. Latest id kept:', latest_id)
else:
    print('No readings in database.')
conn.close()
"@
