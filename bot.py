#!/usr/bin/env python3
"""Bot Telegram: aggiungi, togli e cambia la fascia di prezzo dei pezzi, e lancia una ricerca al volo.

Comandi (dal menu "/" di Telegram):
    /pezzi                      elenco dei pezzi con la fascia di prezzo
    /aggiungi nome del pezzo    aggiunge un pezzo e chiede la fascia di prezzo
    /prezzo [pezzo] [fascia]    cambia la fascia di un pezzo (es. /prezzo 9 30-80)
    /rimuovi [pezzo]            toglie un pezzo
    /cerca [pezzo]              cerca subito un pezzo, senza aspettare il giro orario

Il pezzo si indica col numero di /pezzi o con parte del nome; senza, il bot mostra i pulsanti.
Le modifiche finiscono in ricerche.md e, se siamo in un repository git, vengono pubblicate subito.

Uso:
    bot.py               ascolta finche' non lo fermi
    bot.py --minuti 5    ascolta per 5 minuti e poi esce (per GitHub Actions)
    bot.py --senza-git   non fa pull/commit/push
"""
import argparse
import hashlib
import html
import json
import re
import subprocess
import time

import scraper as s

COMANDI = [("pezzi", "Elenco dei pezzi e delle fasce di prezzo"),
           ("aggiungi", "Aggiungi un pezzo da cercare"),
           ("prezzo", "Cambia la fascia di prezzo di un pezzo"),
           ("rimuovi", "Togli un pezzo"),
           ("cerca", "Cerca subito un pezzo"),
           ("aiuto", "Come si usa il bot")]

# pulsanti proposti per la fascia: (etichetta, valore scritto in ricerche.md)
FASCE = [("fino a 30 €", "30"), ("fino a 50 €", "50"), ("fino a 100 €", "100"),
         ("fino a 200 €", "200"), ("10-50 €", "10-50"), ("20-80 €", "20-80"),
         ("30-150 €", "30-150"), ("da 30 €", "30-"), ("da 50 €", "50-"),
         ("nessun limite", "")]
MAX_CERCA = 5          # annunci nuovi per sito inviati da /cerca
USA_GIT = True


# ------------------------------------------------------------ ricerche.md

def id_pezzo(nome):
    return hashlib.sha1(s.normalizza(nome).encode()).hexdigest()[:8]


def _e_regole(nome):
    return s.normalizza(nome).startswith("regole per tutte")


def sezioni(righe):
    """[(nome, prima riga, riga dopo l'ultima)] delle ricerche, esclusa "Regole per tutte"."""
    inizi = [(i, r[3:].strip()) for i, r in enumerate(righe) if r.startswith("## ")]
    fuori = []
    for k, (i, nome) in enumerate(inizi):
        fine = inizi[k + 1][0] if k + 1 < len(inizi) else len(righe)
        if not _e_regole(nome):
            fuori.append((nome, i, fine))
    return fuori


def leggi_righe():
    return s.RICERCHE.read_text(encoding="utf-8").splitlines()


def scrivi_righe(righe):
    while righe and not righe[-1].strip():
        righe.pop()
    s.RICERCHE.write_text("\n".join(righe) + "\n", encoding="utf-8")


def pezzi():
    """Le ricerche come le legge lo scraper, nell'ordine del file."""
    return s.leggi_ricerche()


def trova(testo):
    """Pezzo indicato da numero (di /pezzi) o da parte del nome. Ritorna (ricerca, errore)."""
    elenco = pezzi()
    testo = testo.strip()
    if testo.isdigit():
        n = int(testo)
        return (elenco[n - 1], None) if 1 <= n <= len(elenco) else (None, f"Non c'è il pezzo n. {n}.")
    cercato = s.normalizza(testo)
    esatti = [r for r in elenco if s.normalizza(r.nome) == cercato]
    simili = esatti or [r for r in elenco if cercato in s.normalizza(r.nome)]
    if len(simili) == 1:
        return simili[0], None
    if not simili:
        return None, f"Nessun pezzo contiene «{html.escape(testo)}». Guarda /pezzi."
    return None, (f"«{html.escape(testo)}» corrisponde a {len(simili)} pezzi: usa il numero di /pezzi.")


def per_id(ident):
    return next((r for r in pezzi() if id_pezzo(r.nome) == ident), None)


def pulisci_nome(testo):
    testo = re.sub(r"\s+", " ", testo.replace("#", " ")).strip(" -*:")
    return testo[:60].strip()


def aggiungi_pezzo(nome, fascia=""):
    righe = leggi_righe()
    righe += ["", f"## {nome}", "", f"- cerca: {nome}", f"- prezzo: {fascia}"]
    scrivi_righe(righe)


def imposta_prezzo(nome, fascia):
    righe = leggi_righe()
    for n, inizio, fine in sezioni(righe):
        if n != nome:
            continue
        for i in range(inizio + 1, fine):
            if re.match(r"[-*]\s*prezzo\s*:", righe[i].strip(), re.I):
                righe[i] = f"- prezzo: {fascia}"
                break
        else:  # niente riga prezzo: la mettiamo dopo l'ultima voce della sezione
            ultima = max((i for i in range(inizio + 1, fine) if righe[i].strip().startswith(("-", "*"))),
                         default=inizio)
            righe.insert(ultima + 1, f"- prezzo: {fascia}")
        scrivi_righe(righe)
        return True
    return False


def rimuovi_pezzo(nome):
    righe = leggi_righe()
    for n, inizio, fine in sezioni(righe):
        if n == nome:
            del righe[inizio:fine]
            scrivi_righe(righe)
            return True
    return False


# --------------------------------------------------------------- fasce

def leggi_fascia(testo):
    """Testo scritto dall'utente -> valore per ricerche.md, oppure None se non si capisce.

    "20-80", "20 80", "da 30", "30-", "fino a 80", "80", "-80", "nessun limite"."""
    t = s.normalizza(testo).strip().replace("€", "").replace("euro", "")
    if t in ("", "nessun limite", "nessuno", "tutti", "tutto", "libero", "0", "-"):
        return ""
    numeri = [int(float(n.replace(",", "."))) for n in re.findall(r"\d+(?:[.,]\d+)?", t)]
    if not numeri or len(numeri) > 2 or not re.fullmatch(r"[\d\s.,\-–a-z<>]*", t):
        return None
    if len(numeri) == 2:
        lo, hi = sorted(numeri)
        return f"{lo}-{hi}"
    if re.search(r"\d\s*[-–]\s*$|^\s*(da|>|min)", t):
        return f"{numeri[0]}-"
    return str(numeri[0])


def descrivi(r):
    infinito = r.pmax == float("inf")
    if not r.pmin and infinito:
        return "nessun limite"
    if not r.pmin:
        return f"fino a {r.pmax:g} €"
    if infinito:
        return f"da {r.pmin:g} €"
    return f"{r.pmin:g}-{r.pmax:g} €"


# --------------------------------------------------------------- git

def git(*argomenti):
    return subprocess.run(["git", "-C", str(s.DIR), *argomenti], capture_output=True, text=True)


def aggiorna_da_github():
    if USA_GIT:
        esito = git("pull", "--rebase", "--autostash", "-q")
        if esito.returncode:
            s.log("git pull non riuscito")


def pubblica(messaggio, *file):
    """Commit e push dei file indicati; ritorna un avviso se non e' andato."""
    if not USA_GIT:
        return ""
    nomi = [f for f in file if (s.DIR / f).exists()]
    git("add", *nomi)
    if git("diff", "--cached", "--quiet", "--", *nomi).returncode == 0:
        return ""
    if git("commit", "-q", "-m", messaggio, "--", *nomi).returncode:
        return "\n⚠️ Modifica salvata ma non registrata in git."
    for _ in range(3):
        if git("pull", "--rebase", "--autostash", "-q").returncode == 0 and git("push", "-q").returncode == 0:
            return ""
        time.sleep(3)
    return "\n⚠️ Modifica salvata ma non pubblicata su GitHub: riprovo alla prossima modifica."


# ------------------------------------------------------------ telegram

class Bot:
    def __init__(self, tg):
        self.tg = tg

    def invia(self, testo, tastiera=None, rispondi=False):
        dati = {"chat_id": self.tg.chat_id, "text": testo, "parse_mode": "HTML",
                "disable_web_page_preview": "true"}
        if tastiera:
            dati["reply_markup"] = json.dumps({"inline_keyboard": tastiera})
        elif rispondi:
            dati["reply_markup"] = json.dumps({"force_reply": True, "input_field_placeholder": "es. 20-80"})
        return self.tg.chiama("sendMessage", dati)

    def modifica(self, messaggio, testo, tastiera=None):
        dati = {"chat_id": self.tg.chat_id, "message_id": messaggio["message_id"], "text": testo,
                "parse_mode": "HTML", "disable_web_page_preview": "true"}
        if tastiera:
            dati["reply_markup"] = json.dumps({"inline_keyboard": tastiera})
        try:
            self.tg.chiama("editMessageText", dati)
        except RuntimeError:  # es. "message is not modified"
            pass

    # ------------------------------------------------------------ tastiere

    @staticmethod
    def tastiera_pezzi(azione):
        bottoni = [{"text": f"{i}. {r.nome}"[:40], "callback_data": f"{azione}:{id_pezzo(r.nome)}"}
                   for i, r in enumerate(pezzi(), 1)]
        return [bottoni[i:i + 2] for i in range(0, len(bottoni), 2)]

    @staticmethod
    def tastiera_fasce(r):
        ident = id_pezzo(r.nome)
        bottoni = [{"text": etichetta, "callback_data": f"p:{ident}:{valore}"} for etichetta, valore in FASCE]
        righe = [bottoni[i:i + 3] for i in range(0, len(bottoni), 3)]
        righe.append([{"text": "✏️ Scrivo io", "callback_data": f"s:{ident}"}])
        return righe

    def chiedi_fascia(self, r, messaggio=None):
        testo = (f"Fascia di prezzo per <b>{html.escape(r.nome)}</b>?\n"
                 f"Adesso: {descrivi(r)}")
        if messaggio:
            self.modifica(messaggio, testo, self.tastiera_fasce(r))
        else:
            self.invia(testo, self.tastiera_fasce(r))

    # ------------------------------------------------------------ comandi

    def gestisci(self, update):
        if "callback_query" in update:
            q = update["callback_query"]
            if str(q.get("message", {}).get("chat", {}).get("id")) != str(self.tg.chat_id):
                return
            try:  # subito, se no il pulsante gira finche' la ricerca non finisce
                self.tg.chiama("answerCallbackQuery", {"callback_query_id": q["id"]})
            except RuntimeError:
                pass
            return self.pulsante(q["data"], q["message"])
        m = update.get("message")
        if not m or str(m["chat"]["id"]) != str(self.tg.chat_id) or "text" not in m:
            return  # solo la tua chat puo' comandare il bot
        testo = m["text"].strip()
        risposta_a = (m.get("reply_to_message") or {}).get("text", "")
        rif = re.search(r"rif\. ([0-9a-f]{8})", risposta_a)
        if rif and not testo.startswith("/"):
            return self.fascia_scritta(rif.group(1), testo)
        cmd = re.match(r"/(\w+)(?:@\w+)?\s*(.*)", testo, re.S)
        if not cmd:
            return self.invia("Usa i comandi del menu /, oppure /aiuto.")
        nome, argomenti = cmd.group(1).lower(), cmd.group(2).strip()
        metodo = {"start": self.aiuto, "aiuto": self.aiuto, "help": self.aiuto, "pezzi": self.elenco,
                  "aggiungi": self.aggiungi, "prezzo": self.prezzo, "rimuovi": self.rimuovi,
                  "cerca": self.cerca}.get(nome)
        if not metodo:
            return self.invia("Comando sconosciuto. Guarda /aiuto.")
        metodo(argomenti)

    def aiuto(self, _=""):
        self.invia(
            "<b>Comandi</b>\n"
            "/pezzi — elenco dei pezzi con la fascia di prezzo\n"
            "/aggiungi <i>nome</i> — aggiunge un pezzo (es. /aggiungi carburatore pwk 21)\n"
            "/prezzo — cambia la fascia di un pezzo; veloce: /prezzo 9 30-80\n"
            "/rimuovi — toglie un pezzo\n"
            "/cerca — cerca subito un pezzo; veloce: /cerca 9 oppure /cerca vhst\n\n"
            "Fasce: <code>20-80</code>, <code>80</code> (fino a 80), <code>30-</code> (da 30), "
            "<code>nessun limite</code>.\n"
            "Il pezzo si indica col numero di /pezzi o con parte del nome.")

    def elenco(self, _=""):
        righe = [f"{i}. {html.escape(r.nome)} — <i>{descrivi(r)}</i>" for i, r in enumerate(pezzi(), 1)]
        self.invia("<b>Pezzi cercati</b>\n" + "\n".join(righe) if righe else "Nessun pezzo. Usa /aggiungi.")

    def aggiungi(self, argomenti):
        nome = pulisci_nome(argomenti)
        if len(nome) < 2:
            return self.invia("Scrivi il nome dopo il comando, es. <code>/aggiungi carburatore pwk 21</code>.\n"
                              "Le parole del nome sono quelle cercate sui siti: ogni parola in più restringe.")
        aggiorna_da_github()
        if any(s.normalizza(r.nome) == s.normalizza(nome) for r in pezzi()):
            return self.invia(f"<b>{html.escape(nome)}</b> c'è già. Per la fascia usa /prezzo.")
        aggiungi_pezzo(nome)
        avviso = pubblica(f"Bot: aggiunge {nome}", "ricerche.md")
        r = per_id(id_pezzo(nome))
        self.invia(f"➕ Aggiunto <b>{html.escape(nome)}</b>.{avviso}")
        self.chiedi_fascia(r)

    def prezzo(self, argomenti):
        if not argomenti:
            return self.invia("Di quale pezzo vuoi cambiare la fascia?", self.tastiera_pezzi("f"))
        r, _ = trova(argomenti)  # prima il nome intero: "/prezzo campana polini 107" e' un pezzo, non 107 €
        if r:
            return self.chiedi_fascia(r)
        # "/prezzo 9 30-80", "/prezzo carburatore 21 30-80": la fascia e' in fondo
        m = re.match(r"(.+?)\s+((?:da\s+|fino a\s+)?\d+\s*(?:[-–]\s*\d*)?|nessun limite)\s*€?$", argomenti, re.I)
        if m:
            r, _ = trova(m.group(1))
            fascia = leggi_fascia(m.group(2)) if r else None
            if r and fascia is not None:
                return self.salva_fascia(r, fascia)
        r, errore = trova(argomenti)
        if errore:
            return self.invia(errore)
        self.chiedi_fascia(r)

    def rimuovi(self, argomenti):
        if not argomenti:
            return self.invia("Quale pezzo vuoi togliere?", self.tastiera_pezzi("r"))
        r, errore = trova(argomenti)
        if errore:
            return self.invia(errore)
        self.conferma_rimozione(r)

    def conferma_rimozione(self, r, messaggio=None):
        ident = id_pezzo(r.nome)
        testo = f"Tolgo <b>{html.escape(r.nome)}</b> dalle ricerche?"
        tastiera = [[{"text": "🗑 Sì, togli", "callback_data": f"R:{ident}"},
                     {"text": "Annulla", "callback_data": "x"}]]
        self.modifica(messaggio, testo, tastiera) if messaggio else self.invia(testo, tastiera)

    def cerca(self, argomenti):
        if not argomenti:
            return self.invia("Quale pezzo cerco adesso?", self.tastiera_pezzi("c"))
        r, errore = trova(argomenti)
        if errore:
            return self.invia(errore)
        self.esegui_ricerca(r)

    # ------------------------------------------------------------ pulsanti

    def pulsante(self, dati, messaggio):
        azione, _, resto = dati.partition(":")
        if azione == "x":
            return self.modifica(messaggio, "Annullato.")
        ident, _, valore = resto.partition(":")
        aggiorna_da_github()
        r = per_id(ident)
        if not r:
            return self.modifica(messaggio, "Questo pezzo non c'è più. Guarda /pezzi.")
        if azione == "f":
            self.chiedi_fascia(r, messaggio)
        elif azione == "p":
            self.modifica(messaggio, f"Fascia di <b>{html.escape(r.nome)}</b>: aggiorno…")
            self.salva_fascia(r, valore, messaggio)
        elif azione == "s":
            self.modifica(messaggio, f"Fascia di prezzo per <b>{html.escape(r.nome)}</b>: scrivila qui sotto.")
            self.invia(f"Rispondi a questo messaggio con la fascia per <b>{html.escape(r.nome)}</b>: "
                       f"<code>20-80</code>, <code>80</code> (fino a), <code>30-</code> (da), "
                       f"<code>nessun limite</code>. (rif. {ident})", rispondi=True)
        elif azione == "r":
            self.conferma_rimozione(r, messaggio)
        elif azione == "R":
            rimuovi_pezzo(r.nome)
            avviso = pubblica(f"Bot: toglie {r.nome}", "ricerche.md")
            self.modifica(messaggio, f"🗑 Tolto <b>{html.escape(r.nome)}</b>.{avviso}")
        elif azione == "c":
            self.modifica(messaggio, f"🔎 {html.escape(r.nome)}")
            self.esegui_ricerca(r)

    def fascia_scritta(self, ident, testo):
        aggiorna_da_github()
        r = per_id(ident)
        if not r:
            return self.invia("Questo pezzo non c'è più. Guarda /pezzi.")
        fascia = leggi_fascia(testo)
        if fascia is None:
            return self.invia(f"Non ho capito la fascia. Esempi: <code>20-80</code>, <code>80</code>, "
                              f"<code>30-</code>, <code>nessun limite</code>. (rif. {ident})", rispondi=True)
        self.salva_fascia(r, fascia)

    def salva_fascia(self, r, fascia, messaggio=None):
        imposta_prezzo(r.nome, fascia)
        avviso = pubblica(f"Bot: fascia di {r.nome} = {fascia or 'nessun limite'}", "ricerche.md")
        nuovo = per_id(id_pezzo(r.nome)) or r
        testo = f"💶 <b>{html.escape(r.nome)}</b>: {descrivi(nuovo)}.{avviso}"
        tastiera = [[{"text": "🔎 Cerca adesso", "callback_data": f"c:{id_pezzo(r.nome)}"}]]
        self.modifica(messaggio, testo, tastiera) if messaggio else self.invia(testo, tastiera)

    # ------------------------------------------------------------ ricerca al volo

    def esegui_ricerca(self, r):
        self.invia(f"🔎 Cerco <b>{html.escape(r.nome)}</b> ({descrivi(r)}) su {', '.join(r.siti)}…")
        s._EBAY_BLOCCATO[0] = False  # un blocco di eBay di prima non deve valere per sempre
        aggiorna_da_github()  # stato.json aggiornato dal giro orario: niente doppioni
        stato = json.loads(s.STATO.read_text()) if s.STATO.exists() else {}
        visti, avviate = stato.get("visti", {}), stato.get("avviate", [])
        dal_bot = s.visti_dal_bot()
        inviati, rimasti, pertinenti, errori, primo_giro = {}, 0, 0, [], False
        for sito in r.siti:
            try:
                _, buoni = s.cerca_su(r, sito)
            except Exception as e:
                s.log(f"ERRORE /cerca {sito}: {type(e).__name__}")
                errori.append(sito)
                continue
            pertinenti += len(buoni)
            nuovi = [a for a in buoni if f"{a.sito}:{a.id}" not in visti and f"{a.sito}:{a.id}" not in dal_bot]
            da_inviare, rimasti = nuovi[:MAX_CERCA], rimasti + len(nuovi[MAX_CERCA:])
            if nuovi[MAX_CERCA:] and s.chiave_avvio(r, sito) not in avviate:
                primo_giro = True  # il giro orario ne mandera' solo uno e segnera' gli altri come visti
            for a in reversed(da_inviare):
                try:
                    s.invia_annuncio(self.tg, r, a)
                    dal_bot[f"{a.sito}:{a.id}"] = time.time()
                    inviati[sito] = inviati.get(sito, 0) + 1
                except Exception as e:
                    s.log(f"ERRORE invio /cerca: {type(e).__name__}")
        limite = time.time() - s.GIORNI_MEMORIA * 86400
        s.STATO_BOT.write_text(json.dumps({"visti": {k: v for k, v in dal_bot.items() if v > limite}}, indent=1))
        pubblica(f"Bot: ricerca {r.nome}", "stato_bot.json")

        totale = sum(inviati.values())
        if totale:
            riga = f"✅ <b>{html.escape(r.nome)}</b>: {totale} nuovi (" + \
                   ", ".join(f"{k} {v}" for k, v in inviati.items()) + ")."
        else:
            riga = f"✅ <b>{html.escape(r.nome)}</b>: niente di nuovo ({pertinenti} annunci pertinenti, già visti)."
        if rimasti and primo_giro:
            riga += (f"\nCe ne sono altri {rimasti} nuovi: ripeti /cerca per vederne altri. "
                     "Il prossimo giro orario, essendo il primo con queste impostazioni, ne manda solo uno per sito.")
        elif rimasti:
            riga += f"\nAltri {rimasti} nuovi arriveranno col prossimo giro orario (o ripeti /cerca)."
        if errori:
            riga += f"\n⚠️ Non hanno risposto: {', '.join(errori)}."
        self.invia(riga)


def ascolta(minuti=None):
    env = s.leggi_env()
    if not (env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID")):
        raise SystemExit("Telegram non configurato: esegui ./configura.sh")
    tg = s.Telegram(env["TELEGRAM_BOT_TOKEN"], env["TELEGRAM_CHAT_ID"])
    bot = Bot(tg)
    tg.chiama("setMyCommands", {"commands": json.dumps([{"command": c, "description": d} for c, d in COMANDI])})
    fine = time.time() + minuti * 60 if minuti else None
    offset = None
    s.log("bot in ascolto" + (f" per {minuti} minuti" if minuti else ""))
    while fine is None or time.time() < fine:
        attesa = 25 if fine is None else max(1, min(25, int(fine - time.time())))
        try:
            dati = {"timeout": attesa, "allowed_updates": json.dumps(["message", "callback_query"])}
            if offset:
                dati["offset"] = offset
            aggiornamenti = tg.chiama("getUpdates", dati)
        except Exception as e:  # rete, oppure un altro bot.py sta gia' ascoltando (409)
            s.log(f"getUpdates: {type(e).__name__}")
            time.sleep(20)
            continue
        for u in aggiornamenti:
            offset = u["update_id"] + 1
            try:
                bot.gestisci(u)
            except Exception as e:
                s.log(f"ERRORE comando: {type(e).__name__}")  # i log di GitHub sono pubblici: niente testi
                try:
                    bot.invia(f"⚠️ Qualcosa è andato storto: {html.escape(type(e).__name__)}")
                except Exception:
                    pass
    if offset:  # conferma a Telegram gli ultimi messaggi, cosi' il prossimo avvio non li rifa'
        tg.chiama("getUpdates", {"offset": offset, "timeout": 0})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--minuti", type=float, help="ascolta per N minuti e poi esce")
    parser.add_argument("--senza-git", action="store_true", help="non fa pull/commit/push")
    opzioni = parser.parse_args()
    USA_GIT = not opzioni.senza_git
    ascolta(opzioni.minuti)
