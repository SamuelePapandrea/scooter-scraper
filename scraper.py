#!/usr/bin/env python3
"""Cerca pezzi di scooter su Vinted, Wallapop, Subito ed eBay e manda i nuovi annunci su Telegram.

Le ricerche stanno in ricerche.md. Uso:
    scraper.py            esegue le ricerche e invia i nuovi annunci
    scraper.py --prova    mostra cosa troverebbe ogni ricerca, senza inviare ne' salvare
    scraper.py --chat-id  trova il chat id (dopo aver scritto /start al bot) e lo salva in .env
"""
import argparse
import html
import io
import json
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import requests as plain_requests
from bs4 import BeautifulSoup
from curl_cffi import requests as browser_requests

DIR = Path(__file__).resolve().parent
RICERCHE = DIR / "ricerche.md"
ENV = DIR / ".env"
STATO = DIR / "stato.json"

SITI = ("vinted", "wallapop", "subito", "ebay")
SITI_SPAGNOLO = ("vinted", "wallapop")  # siti con molti venditori spagnoli
MAX_PRIMO_AVVIO = 1      # annunci per sito inviati la prima volta che gira una ricerca
MAX_FOTO = 3             # foto per annuncio
GIORNI_MEMORIA = 90      # dopo quanti giorni un annuncio gia' visto viene dimenticato
ERRORI_PRIMA_DI_AVVISO = 6
ROMA = (41.9028, 12.4964)  # Wallapop vuole una posizione; serve solo per l'ordinamento


@dataclass
class Ricerca:
    nome: str
    cerca: str = ""
    pmin: float = 0
    pmax: float = float("inf")
    siti: tuple = SITI
    escludi: list = field(default_factory=list)
    obbligatorie: list = field(default_factory=list)
    titolo_libero: bool = False
    varianti: list = field(default_factory=list)  # coppie (testo, sito oppure None = tutti)


@dataclass
class Annuncio:
    sito: str
    id: str
    titolo: str
    prezzo: float
    url: str
    foto: list
    luogo: str = ""
    nota: str = ""


def log(*parti):
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), *parti, flush=True)


def normalizza(testo):
    testo = unicodedata.normalize("NFKD", testo.lower())
    return "".join(c for c in testo if not unicodedata.combining(c))


# ---------------------------------------------------------------- ricerche.md

def _numero(s):
    return float(s.replace(",", "."))


def leggi_ricerche(percorso=RICERCHE):
    ricerche, corrente = [], None
    for riga in percorso.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if riga.startswith("## "):
            corrente = Ricerca(nome=riga[3:].strip())
            ricerche.append(corrente)
            continue
        m = re.match(r"[-*]\s*([^:]+):\s*(.*)", riga)
        if not (corrente and m):
            continue
        chiave, valore = normalizza(m.group(1)).strip(), m.group(2).strip()
        lista = [normalizza(v).strip() for v in valore.split(",") if v.strip()]
        if chiave in ("cerca", "spagnolo") or chiave in SITI:
            solo = {"cerca": None, "spagnolo": SITI_SPAGNOLO}.get(chiave, (chiave,))
            corrente.varianti += [(v.strip(), solo) for v in valore.split(";") if v.strip()]
        elif chiave == "prezzo":
            numeri = [_numero(n) for n in re.findall(r"\d+(?:[.,]\d+)?", valore)]
            if len(numeri) >= 2:
                corrente.pmin, corrente.pmax = numeri[0], numeri[1]
            elif numeri:
                corrente.pmax = numeri[0]
        elif chiave == "siti":
            corrente.siti = tuple(s for s in lista if s in SITI)
        elif chiave == "escludi":
            corrente.escludi = lista
        elif chiave == "obbligatorie":
            corrente.obbligatorie = lista
        elif chiave == "titolo":
            corrente.titolo_libero = "libero" in normalizza(valore)
    comuni = [r for r in ricerche if normalizza(r.nome).startswith("regole per tutte")]
    ricerche = [r for r in ricerche if r not in comuni]
    valide = []
    for r in ricerche:
        r.escludi = r.escludi + [p for c in comuni for p in c.escludi]
        if not any(sito is None for _, sito in r.varianti):
            r.varianti.insert(0, (r.nome, None))
        r.cerca = r.varianti[0][0]
        if r.pmin > r.pmax:
            r.pmin, r.pmax = r.pmax, r.pmin
        valide.append(r)
    return valide


GRAFIE = [(r"stage[\s-]*6", "stage6"), (r"leo[\s-]*vince", "leovince"), (r"ital[\s-]*kit", "italkit"),
          (r"2[\s-]*fast", "2fast"), (r"dell[\s'’]*orto", "dellorto"), (r"t[\s-]*max", "tmax"),
          (r"(pwk|vhst|vhsh|phbg|phbh)[\s-]*(\d)", r"\1 \2"),  # pwk28 -> pwk 28
          (r"(?<![a-z0-9])([67])[\s-]*(?:travasi|transfers?|transferencias|t)(?![a-z0-9])", r"\1t"),  # 6 travasi -> 6t
          (r"evolution", "evo"), (r"evo(\d)", r"evo \1"),
          (r"(?<![a-z0-9])(?:due|2)[\s-]*plus", "dueplus"), (r"street[\s-]*race", "streetrace")]


def uniforma(testo):
    testo = normalizza(testo)
    for modello, forma in GRAFIE:
        testo = re.sub(modello, forma, testo)
    return testo


PAROLE_VUOTE = {"per", "con", "di", "da", "del", "della", "the", "e", "o", "in", "a",
                "de", "la", "el", "para", "y"}


def contiene(titolo, parola):
    """True se `parola` compare nel titolo come parola a se' (non dentro un'altra).

    Tollera singolare/plurale (variatore/variatori) e per i numeri accetta 50 e 50cc ma non 150 o 500.
    `a/b` significa "una delle due".
    """
    for alternativa in parola.split("/"):
        alternativa = alternativa.strip()
        if not alternativa:
            continue
        if alternativa.isdigit():
            modello = rf"(?<![0-9.,]){alternativa}(?![0-9]|[.,][0-9])"
        else:
            modello = rf"(?<![a-z0-9]){re.escape(alternativa)}"
            if len(alternativa) > 4 and alternativa[-1] in "aeio":
                # singolare/plurale: cilindro = cilindri, ma non "cilindrata"
                modello = rf"(?<![a-z0-9]){re.escape(alternativa[:-1])}[aeio]?s?(?![a-z])"
            if len(alternativa) <= 3:  # sigle corte (zx, tt, pvl, sp): solo come parola intera
                modello += r"(?![a-z0-9])"
        if re.search(modello, titolo):
            return True
    return False


def accettabile(r, a):
    if not (r.pmin <= a.prezzo <= r.pmax):
        return False
    titolo = uniforma(a.titolo)
    if any(contiene(titolo, p) for p in r.escludi):
        return False
    richieste = list(r.obbligatorie)
    if not r.titolo_libero:
        richieste += [p for p in re.findall(r"[a-z0-9/]+", uniforma(r.cerca)) if p not in PAROLE_VUOTE]
    return all(contiene(titolo, p) for p in richieste)


# ---------------------------------------------------------------------- siti

_SESSIONI = {}


def _sessione(browser):
    if browser not in _SESSIONI:
        _SESSIONI[browser] = browser_requests.Session(impersonate=browser, timeout=30)
    return _SESSIONI[browser]


def _pmax(r):
    return None if r.pmax == float("inf") else int(r.pmax)


def cerca_subito(r):
    parametri = {"q": r.cerca, "t": "s", "qso": "true", "sort": "datedesc", "lim": 60, "start": 0}
    if r.pmin:
        parametri["ps"] = int(r.pmin)
    if _pmax(r):
        parametri["pe"] = _pmax(r)
    risposta = _sessione("chrome").get(
        "https://hades.subito.it/v1/search/items", params=parametri,
        headers={"X-Subito-Channel": "web", "Accept": "application/json"})
    risposta.raise_for_status()
    annunci = []
    for ad in risposta.json().get("ads", []):
        prezzo = None
        for f in ad.get("features", []):
            if f.get("uri") == "/price" and f.get("values"):
                prezzo = _numero(f["values"][0]["key"])
        if prezzo is None or ad.get("category", {}).get("friendly_name") == "moto-e-scooter":
            continue  # senza prezzo, oppure scooter interi invece di ricambi
        geo = ad.get("geo", {})
        luogo = ", ".join(v for v in (geo.get("town", {}).get("value"),
                                      geo.get("city", {}).get("short_name")) if v)
        annunci.append(Annuncio(
            "subito", ad["urn"].split(":")[-1], ad["subject"], prezzo, ad["urls"]["default"],
            [i["cdn_base_url"] + "?rule=fullscreen-1x-auto" for i in ad.get("images", [])
             if i.get("cdn_base_url")], luogo))
    return annunci


def cerca_wallapop(r):
    parametri = {"keywords": r.cerca, "source": "search_box", "order_by": "newest",
                 "latitude": ROMA[0], "longitude": ROMA[1]}
    if r.pmin:
        parametri["min_sale_price"] = int(r.pmin)
    if _pmax(r):
        parametri["max_sale_price"] = _pmax(r)
    risposta = _sessione("chrome").get(
        "https://api.wallapop.com/api/v3/search", params=parametri,
        headers={"X-DeviceOS": "0", "Accept": "application/json"})
    risposta.raise_for_status()
    annunci = []
    for it in risposta.json()["data"]["section"]["payload"].get("items", []):
        if it.get("reserved", {}).get("flag"):
            continue
        loc = it.get("location", {})
        annunci.append(Annuncio(
            "wallapop", it["id"], it["title"], float(it["price"]["amount"]),
            "https://it.wallapop.com/item/" + it["web_slug"],
            [i["urls"]["big"] for i in it.get("images", [])],
            ", ".join(v for v in (loc.get("city"), loc.get("country_code")) if v),
            "" if it.get("shipping", {}).get("item_is_shippable") else "solo ritiro a mano"))
    return annunci


def cerca_vinted(r):
    parametri = {"search_text": r.cerca, "order": "newest_first"}
    if r.pmin:
        parametri["price_from"] = int(r.pmin)
    if _pmax(r):
        parametri["price_to"] = _pmax(r)
    if r.pmin or _pmax(r):
        parametri["currency"] = "EUR"
    risposta = _sessione("chrome").get("https://www.vinted.it/catalog", params=parametri)
    risposta.raise_for_status()
    soup = BeautifulSoup(risposta.text, "html.parser")
    annunci = []
    for link in soup.select('a[data-testid$="--overlay-link"]'):
        m = re.search(r"/items/(\d+)", link.get("href", ""))
        descrizione = link.get("title", "")
        prezzi = re.findall(r"(\d+(?:[.,]\d+)?)\s*€", descrizione)
        if not (m and prezzi):
            continue
        titolo = re.split(r", (?:Brand|Condizioni|Taglia):", descrizione)[0]
        img = soup.select_one(f'img[data-testid="product-item-id-{m.group(1)}--image--img"]')
        nota = f"{prezzi[-1]} € con protezione acquisti" if len(prezzi) > 1 else ""
        annunci.append(Annuncio(
            "vinted", m.group(1), titolo, _numero(prezzi[0]),
            "https://www.vinted.it" + link["href"].split("?")[0],
            [img["src"]] if img and img.get("src") else [], "", nota))
    return annunci


PAUSA_EBAY = 15
_ULTIMA_EBAY = [0.0]
_EBAY_BLOCCATO = [False]


def cerca_ebay(r):
    # LH_ItemCondition=3000: solo oggetti usati (eBay filtra lato server)
    parametri = {"_nkw": r.cerca, "_sop": 10, "_ipg": 60, "LH_ItemCondition": 3000}
    if r.pmin:
        parametri["_udlo"] = int(r.pmin)
    if _pmax(r):
        parametri["_udhi"] = _pmax(r)
    if _EBAY_BLOCCATO[0]:  # dopo un blocco insistere lo allunga soltanto: riprende al prossimo giro
        raise RuntimeError("eBay saltato: ha bloccato le richieste in questo giro")
    for tentativo in range(2):
        time.sleep(max(0, PAUSA_EBAY - (time.time() - _ULTIMA_EBAY[0])))
        sessione = _sessione("safari")  # con l'impronta di Chrome eBay risponde 403
        if not sessione.cookies:
            sessione.get("https://www.ebay.it/")
        risposta = sessione.get("https://www.ebay.it/sch/i.html", params=parametri,
                                headers={"Referer": "https://www.ebay.it/"})
        _ULTIMA_EBAY[0] = time.time()
        if risposta.status_code != 403 or tentativo:
            break
        _SESSIONI.pop("safari", None)  # sessione nuova e pausa lunga prima di riprovare
        time.sleep(45)
    _EBAY_BLOCCATO[0] = risposta.status_code == 403
    risposta.raise_for_status()
    soup = BeautifulSoup(risposta.text, "html.parser")
    annunci = []
    for card in soup.select("li.s-card[data-listingid]"):
        link = card.select_one("a.s-card__link[href*='/itm/']")
        titolo = card.select_one(".s-card__title")
        prezzo = card.select_one(".s-card__price")
        if not (link and titolo and prezzo):
            continue
        m = re.search(r"EUR\s*([\d.]+,\d{2})", prezzo.get_text(" ", strip=True))
        if not m:
            continue
        condizione = card.select_one(".s-card__subtitle")
        condizione = normalizza(condizione.get_text(" ", strip=True)) if condizione else ""
        if re.search(r"(?<![a-z])(nuov[oa]|new|ricondizionat)", condizione):
            continue  # doppio controllo: a volte eBay mescola annunci nuovi o sponsorizzati
        testo = titolo.get_text(" ", strip=True)
        testo = re.sub(r"\s*viene aperta una nuova finestra o scheda$", "", testo)
        testo = re.sub(r"^Nuova inserzione\s*", "", testo)
        img = card.select_one("img.s-card__image")
        foto = (img.get("data-defer-load") or img.get("src")) if img else None
        foto = re.sub(r"s-l\d+\.", "s-l800.", foto) if foto else None
        dettagli = card.get_text(" ", strip=True)
        spedizione = re.search(r"(\+\s*EUR\s*[\d.,]+ per la consegna|Consegna gratuita)", dettagli)
        annunci.append(Annuncio(
            "ebay", card["data-listingid"], testo,
            _numero(m.group(1).replace(".", "")),
            "https://www.ebay.it/itm/" + card["data-listingid"],
            [foto] if foto else [], "", spedizione.group(1) if spedizione else ""))
    return annunci


def foto_grandi_vinted(a):
    """La lista risultati ha solo miniature: le foto grandi stanno nella pagina dell'annuncio."""
    try:
        pagina = _sessione("chrome").get(a.url)
        pagina.raise_for_status()
        grandi = re.findall(r'https://images\d*\.vinted\.net/t[^"\\ ]+?/f800/[^"\\ ]+', pagina.text)
        if grandi:
            a.foto = list(dict.fromkeys(grandi))
    except Exception as e:
        log("foto grandi Vinted non disponibili:", a.url, e)


CERCATORI = {"vinted": cerca_vinted, "wallapop": cerca_wallapop,
             "subito": cerca_subito, "ebay": cerca_ebay}


# ------------------------------------------------------------------ telegram

def leggi_env():
    import os
    # su GitHub Actions i valori arrivano dai Secrets come variabili d'ambiente
    valori = {k: v for k, v in os.environ.items() if k.startswith("TELEGRAM_") and v}
    if ENV.exists():
        for riga in ENV.read_text().splitlines():
            if "=" in riga and not riga.strip().startswith("#"):
                k, v = riga.split("=", 1)
                valori[k.strip()] = v.strip().strip("\"'")
    return valori


def scrivi_env(chiave, valore):
    valori = leggi_env()
    valori[chiave] = valore
    ENV.write_text("".join(f"{k}={v}\n" for k, v in valori.items()))
    ENV.chmod(0o600)


class Telegram:
    def __init__(self, token, chat_id=None):
        self.base = f"https://api.telegram.org/bot{token}/"
        self.chat_id = chat_id

    def chiama(self, metodo, dati=None, file=None):
        for _ in range(4):
            try:
                risposta = plain_requests.post(self.base + metodo, data=dati, files=file, timeout=60)
            except plain_requests.ConnectionError:
                time.sleep(5)
                continue
            corpo = risposta.json()
            if corpo.get("ok"):
                return corpo["result"]
            attesa = corpo.get("parameters", {}).get("retry_after")
            if not attesa:
                raise RuntimeError(f"Telegram {metodo}: {corpo.get('description')}")
            time.sleep(attesa + 1)
        raise RuntimeError(f"Telegram {metodo}: troppi tentativi")

    def testo(self, messaggio):
        return self.chiama("sendMessage", {"chat_id": self.chat_id, "text": messaggio,
                                           "parse_mode": "HTML",
                                           "disable_web_page_preview": "true"})

    def annuncio(self, ricerca, a):
        didascalia = didascalia_html(ricerca, a)
        immagini = [b for b in (scarica_jpeg(u) for u in a.foto[:MAX_FOTO]) if b]
        if not immagini:
            return self.testo(didascalia)
        if len(immagini) == 1:
            return self.chiama("sendPhoto",
                               {"chat_id": self.chat_id, "caption": didascalia, "parse_mode": "HTML"},
                               {"photo": ("foto.jpg", immagini[0], "image/jpeg")})
        media = [{"type": "photo", "media": f"attach://f{i}"} for i in range(len(immagini))]
        media[0].update(caption=didascalia, parse_mode="HTML")
        return self.chiama("sendMediaGroup",
                           {"chat_id": self.chat_id, "media": json.dumps(media)},
                           {f"f{i}": (f"f{i}.jpg", b, "image/jpeg") for i, b in enumerate(immagini)})


def didascalia_html(ricerca, a):
    righe = [f"<b>{html.escape(a.titolo[:200])}</b>",
             f"💶 <b>{a.prezzo:.2f} €</b>" + (f" ({html.escape(a.nota)})" if a.nota else ""),
             f"🛒 {a.sito.capitalize()}" + (f" · 📍 {html.escape(a.luogo)}" if a.luogo else ""),
             f"🔎 {html.escape(ricerca.nome)}",
             f'<a href="{html.escape(a.url)}">Apri annuncio</a>']
    return "\n".join(righe)


def scarica_jpeg(url):
    """Scarica la foto e la converte in JPEG (Vinted usa webp, che Telegram tratta male)."""
    try:
        from PIL import Image
        dati = browser_requests.get(url, impersonate="chrome", timeout=30)
        dati.raise_for_status()
        immagine = Image.open(io.BytesIO(dati.content)).convert("RGB")
        immagine.thumbnail((1600, 1600))
        uscita = io.BytesIO()
        immagine.save(uscita, "JPEG", quality=88)
        return uscita.getvalue()
    except Exception as e:  # una foto rotta non deve bloccare l'annuncio
        log("foto non scaricata:", url, e)
        return None


def trova_chat_id():
    token = leggi_env().get("TELEGRAM_BOT_TOKEN")
    if not token:
        sys.exit("Manca TELEGRAM_BOT_TOKEN in .env")
    tg = Telegram(token)
    io_bot = tg.chiama("getMe")
    aggiornamenti = tg.chiama("getUpdates")
    chat = [u["message"]["chat"] for u in aggiornamenti if "message" in u]
    if not chat:
        sys.exit(f"Nessun messaggio trovato: apri t.me/{io_bot['username']}, premi Avvia e riprova.")
    tg.chat_id = chat[-1]["id"]
    scrivi_env("TELEGRAM_CHAT_ID", str(tg.chat_id))
    tg.testo("✅ Bot collegato. Qui arriveranno i nuovi annunci.")
    print(f"Chat id salvato. Messaggio di prova inviato da @{io_bot['username']}.")


# ---------------------------------------------------------------------- main

def cerca_su(r, sito):
    """Esegue tutte le varianti della ricerca su un sito e tiene solo gli annunci pertinenti."""
    import dataclasses
    trovati, buoni = 0, {}
    for testo, solo in r.varianti:
        if solo is not None and sito not in solo:
            continue
        variante = dataclasses.replace(r, cerca=testo)
        risultati = CERCATORI[sito](variante)
        trovati += len(risultati)
        for a in risultati:
            if a.id not in buoni and accettabile(variante, a):
                buoni[a.id] = a
        time.sleep(1)
    return trovati, list(buoni.values())


def anteprima(solo=None):
    """Mostra cosa troverebbe ogni ricerca, senza inviare e senza toccare lo stato."""
    import statistics
    for r in leggi_ricerche()[:solo]:
        print(f"\n## {r.nome}", flush=True)
        for sito in r.siti:
            try:
                trovati, buoni = cerca_su(r, sito)
            except Exception as e:
                print(f"  {sito:9} ERRORE {type(e).__name__}: {e}")
                continue
            prezzi = sorted(a.prezzo for a in buoni)
            fascia = (f"{prezzi[0]:.0f}-{prezzi[-1]:.0f} €, mediana {statistics.median(prezzi):.0f} €"
                      if prezzi else "")
            print(f"  {sito:9} {len(buoni):3} pertinenti su {trovati:3}  {fascia}")
            for a in buoni[:4]:
                print(f"            {a.prezzo:7.0f} €  {a.titolo[:75]}")


def esegui():
    ricerche = leggi_ricerche()
    if not ricerche:
        sys.exit(f"Nessuna ricerca in {RICERCHE.name}")
    env = leggi_env()
    if not (env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID")):
        sys.exit("Telegram non configurato: esegui ./configura.sh")
    tg = Telegram(env["TELEGRAM_BOT_TOKEN"], env["TELEGRAM_CHAT_ID"])

    stato = json.loads(STATO.read_text()) if STATO.exists() else {}
    visti = stato.setdefault("visti", {})
    avviate = stato.setdefault("avviate", [])
    errori = stato.setdefault("errori", {})
    adesso = time.time()
    falliti, riusciti = set(), set()
    # ogni giro parte da una ricerca diversa: se eBay blocca a meta', a turno le copre tutte
    stato["giro"] = stato.get("giro", 0) + 1
    inizio = (stato["giro"] * 10) % len(ricerche)
    ricerche = ricerche[inizio:] + ricerche[:inizio]

    for r in ricerche:
        for sito in r.siti:
            # la "prima volta" e' per ricerca+sito+testo: se cambi le parole non arriva una valanga
            chiave = normalizza(f"{sito}|" + "|".join(t for t, s_ in r.varianti if s_ is None or sito in s_))
            prima_volta = chiave not in avviate
            try:
                trovati, buoni = cerca_su(r, sito)
            except Exception as e:
                log(f"ERRORE {sito} / {r.nome}: {type(e).__name__}: {e}")
                falliti.add(sito)
                continue
            riusciti.add(sito)
            nuovi = [a for a in buoni if f"{a.sito}:{a.id}" not in visti]
            da_inviare = nuovi[:MAX_PRIMO_AVVIO] if prima_volta else nuovi
            log(f"{r.nome} / {sito}: {trovati} trovati, {len(buoni)} pertinenti, "
                f"{len(nuovi)} nuovi, {len(da_inviare)} da inviare")
            for a in reversed(da_inviare):  # dal piu' vecchio al piu' recente
                try:
                    if a.sito == "vinted":
                        foto_grandi_vinted(a)
                    tg.annuncio(r, a)
                    time.sleep(3)
                except Exception as e:
                    log(f"ERRORE invio {a.url}: {e}")
                    nuovi.remove(a)  # riprova al prossimo giro
            for a in nuovi:
                visti[f"{a.sito}:{a.id}"] = adesso
            avviate.append(chiave) if prima_volta else None
            STATO.write_text(json.dumps(stato, indent=1))  # salva subito: un giro interrotto non rimanda doppioni

    for sito in SITI:
        if sito in falliti and sito not in riusciti:
            errori[sito] = errori.get(sito, 0) + 1
            if errori[sito] == ERRORI_PRIMA_DI_AVVISO:
                tg.testo(f"⚠️ {sito.capitalize()} non risponde da {errori[sito]} giri di fila: "
                         "forse il sito e' cambiato e lo scraper va aggiornato.")
        elif sito in riusciti:
            errori[sito] = 0
    limite = adesso - GIORNI_MEMORIA * 86400
    stato["visti"] = {k: v for k, v in visti.items() if v > limite}
    STATO.write_text(json.dumps(stato, indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prova", action="store_true", help="stampa senza inviare ne' salvare")
    parser.add_argument("--solo", type=int, help="con --prova: solo le prime N ricerche")
    parser.add_argument("--chat-id", action="store_true", help="trova e salva il chat id")
    opzioni = parser.parse_args()
    if opzioni.chat_id:
        trova_chat_id()
    else:
        anteprima(opzioni.solo) if opzioni.prova else esegui()
