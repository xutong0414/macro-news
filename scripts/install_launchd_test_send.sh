#!/usr/bin/env bash
set -eu

minutes="${1:-5}"
label="com.macro-news.test-send"
plist="$HOME/Library/LaunchAgents/${label}.plist"

if ! [[ "$minutes" =~ ^[0-9]+$ ]] || [ "$minutes" -lt 1 ]; then
  echo "Usage: /bin/bash scripts/install_launchd_test_send.sh [minutes_from_now]"
  echo "Example: /bin/bash scripts/install_launchd_test_send.sh 5"
  exit 2
fi

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "${script_dir}/.." && pwd)"
python_bin="${repo_root}/.venv/bin/python"

if [ ! -x "$python_bin" ]; then
  python_bin="$(command -v python3)"
fi

if date -v+"${minutes}"M +%H >/dev/null 2>&1; then
  hour="$(date -v+"${minutes}"M +%H)"
  minute="$(date -v+"${minutes}"M +%M)"
else
  hour="$(date -d "+${minutes} minutes" +%H)"
  minute="$(date -d "+${minutes} minutes" +%M)"
fi

xml_escape() {
  printf '%s' "$1" | sed \
    -e 's/&/\&amp;/g' \
    -e 's/</\&lt;/g' \
    -e 's/>/\&gt;/g'
}

repo_root_xml="$(xml_escape "$repo_root")"
python_bin_xml="$(xml_escape "$python_bin")"

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
  <dict>
    <key>Hour</key>
    <integer>${hour}</integer>
    <key>Minute</key>
    <integer>${minute}</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>${repo_root_xml}/logs/scheduler-test.out.log</string>

  <key>StandardErrorPath</key>
  <string>${repo_root_xml}/logs/scheduler-test.err.log</string>
</dict>
</plist>
PLIST

plutil -lint "$plist"
launchctl bootout "gui/$(id -u)" "$plist" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$plist"

echo "Loaded one test schedule:"
echo "  label: ${label}"
echo "  time:  ${hour}:${minute} local Mac time"
echo "  plist: ${plist}"
echo
echo "Wait for the email, then unload the test schedule:"
echo "  launchctl bootout gui/$(id -u) ${plist}"
echo
echo "Check logs if needed:"
echo "  tail -n 40 ${repo_root}/logs/scheduler-test.err.log"
