#!/usr/bin/env bash
set -eu

hkt_time="${1:-08:15}"
label="com.macro-news.weekday-send"
plist="$HOME/Library/LaunchAgents/${label}.plist"

if ! [[ "$hkt_time" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
  echo "Usage: /bin/bash scripts/install_launchd_weekday_hk.sh [HH:MM_HKT]"
  echo "Example: /bin/bash scripts/install_launchd_weekday_hk.sh 08:15"
  exit 2
fi

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "${script_dir}/.." && pwd)"
python_bin="${repo_root}/.venv/bin/python"

if [ ! -x "$python_bin" ]; then
  python_bin="$(command -v python3)"
fi

xml_escape() {
  printf '%s' "$1" | sed \
    -e 's/&/\&amp;/g' \
    -e 's/</\&lt;/g' \
    -e 's/>/\&gt;/g'
}

repo_root_xml="$(xml_escape "$repo_root")"
python_bin_xml="$(xml_escape "$python_bin")"

schedule_xml="$("$python_bin" - "$hkt_time" <<'PY'
import datetime as dt
import sys
from zoneinfo import ZoneInfo

hour, minute = map(int, sys.argv[1].split(":"))
hkt = ZoneInfo("Asia/Hong_Kong")
today_hkt = dt.datetime.now(hkt).date()
next_monday_hkt = today_hkt + dt.timedelta(days=(0 - today_hkt.weekday()) % 7)

for offset in range(5):
    hkt_date = next_monday_hkt + dt.timedelta(days=offset)
    hkt_dt = dt.datetime(
        hkt_date.year,
        hkt_date.month,
        hkt_date.day,
        hour,
        minute,
        tzinfo=hkt,
    )
    local_dt = hkt_dt.astimezone()
    launchd_weekday = local_dt.isoweekday()
    print("    <dict>")
    print("      <key>Weekday</key>")
    print(f"      <integer>{launchd_weekday}</integer>")
    print("      <key>Hour</key>")
    print(f"      <integer>{local_dt.hour}</integer>")
    print("      <key>Minute</key>")
    print(f"      <integer>{local_dt.minute}</integer>")
    print("    </dict>")
PY
)"

mkdir -p "$HOME/Library/LaunchAgents" "$repo_root/logs"

cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${repo_root_xml}/scripts/run_daily_brief.sh</string>
  </array>

  <key>WorkingDirectory</key>
  <string>${repo_root_xml}</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHON_BIN</key>
    <string>${python_bin_xml}</string>
    <key>PATH</key>
    <string>/opt/anaconda3/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>

  <key>StartCalendarInterval</key>
  <array>
${schedule_xml}
  </array>

  <key>StandardOutPath</key>
  <string>${repo_root_xml}/logs/scheduler.out.log</string>

  <key>StandardErrorPath</key>
  <string>${repo_root_xml}/logs/scheduler.err.log</string>
</dict>
</plist>
PLIST

plutil -lint "$plist"
launchctl bootout "gui/$(id -u)" "$plist" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$plist"

echo "Loaded weekday schedule:"
echo "  label: ${label}"
echo "  target: Monday-Friday at ${hkt_time} Hong Kong time"
echo "  plist: ${plist}"
echo
echo "Check the loaded job:"
echo "  launchctl print gui/$(id -u)/${label}"
echo
echo "Unload this schedule:"
echo "  launchctl bootout gui/$(id -u) ${plist}"
