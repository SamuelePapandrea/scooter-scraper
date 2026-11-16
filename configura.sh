#!/bin/zsh
# Collega il bot Telegram e programma lo scraper una volta all'ora (launchd).
# Si puo' rilanciare quando si vuole: rifa' solo i passi che servono.
set -e
cd "${0:A:h}"
PY="$PWD/.venv/bin/python"
ETICHETTA="it.scooterscraper.orario"
PLIST="$HOME/Library/LaunchAgents/$ETICHETTA.plist"

if [[ ! -x "$PY" ]]; then
  echo "Creo l'ambiente Python..."
  uv venv -q .venv && uv pip install -q --python "$PY" -r requirements.txt
fi

if ! grep -q '^TELEGRAM_BOT_TOKEN=.' .env 2>/dev/null; then
  echo "Incolla il token che ti ha dato @BotFather e premi Invio (non viene mostrato):"
  read -rs TOKEN
  if [[ ! "$TOKEN" =~ '^[0-9]+:[A-Za-z0-9_-]{30,}$' ]]; then
    echo "Non sembra un token valido: deve essere tutto su una riga, tipo 123456789:AAH...(numeri, due punti, lettere)."
    echo "Copialo per intero dal messaggio di BotFather e rilancia ./configura.sh"
    exit 1
  fi
  print -r -- "TELEGRAM_BOT_TOKEN=$TOKEN" >> .env
  chmod 600 .env
fi

if ! grep -q '^TELEGRAM_CHAT_ID=.' .env; then
  echo "Ora apri il tuo bot su Telegram e premi Avvia (/start), poi premi Invio qui."
  read -r
  "$PY" scraper.py --chat-id
fi

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$ETICHETTA</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>$PWD/scraper.py</string></array>
  <key>WorkingDirectory</key><string>$PWD</string>
  <key>StartInterval</key><integer>3600</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$PWD/scraper.log</string>
  <key>StandardErrorPath</key><string>$PWD/scraper.log</string>
</dict>
</plist>
EOF
launchctl bootout "gui/$UID/$ETICHETTA" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"

echo "Fatto: il primo giro parte adesso, poi uno ogni ora. Log in scraper.log"
echo "Per fermarlo: launchctl bootout gui/$UID/$ETICHETTA"
