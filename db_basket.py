"""
================================================================================
AREA199 HUMAN PERFORMANCE LAB — LIVELLO DATI
================================================================================
Connessione, letture cachate, motore punteggi, utenti, licenze, logo.
Modulo autosufficiente: nessuna dipendenza da altri moduli AREA199.

Segreti richiesti (pannello Streamlit Cloud):

    supabase_url = "https://xxxxx.supabase.co"
    supabase_key = "eyJ...."        # legacy service_role key
    pin_admin    = "197519"         # chiave maestra dell'amministratore
    openai_key   = "sk-..."         # facoltativo

Versione 4.0 — Agosto 2026
================================================================================
"""

import base64
import hashlib
import io
import math
import secrets as pysecrets
from datetime import date, datetime

import pandas as pd
import streamlit as st
from supabase import create_client, Client

try:
    from PIL import Image
except ImportError:
    Image = None


# ==============================================================================
# 1. CONFIGURAZIONE
# ==============================================================================

CATEGORIA = "DR3"
RUOLI = ["Playmaker", "Guardia", "Ala Piccola", "Ala Grande", "Centro"]

# Sei assi valutati. MOB e' stato aggiunto perche' la dorsiflessione di
# caviglia limitata e' il fattore modificabile piu' documentato nel valgo
# dinamico di ginocchio: in uno sport fatto di atterraggi non puo' mancare.
ASSI = {
    "MOB": "mob_kneewall",
    "ELE": "ele_salto",
    "ACC": "acc_10m",
    "AGI": "agi_lane",
    "RES": "res_navetta",
    "FOR": "for_piegamenti",
}

META_TEST = {
    "mob_kneewall": {
        "sigla": "MOB", "label": "Mobilita' caviglia",
        "protocollo": "Knee to Wall (dorsiflessione in carico)",
        "unita": "cm", "decimali": 1, "prove": 2, "recupero": "—",
        "min": 0.0, "max": 20.0, "step": 0.5,
        "promemoria": "Si registra il lato piu' limitato. "
                      "Differenza tra i lati oltre 1.5 cm da segnalare.",
        "sop": [
            "Metro a nastro fissato a terra perpendicolare alla parete, "
            "lo zero contro il muro.",
            "Atleta in affondo, alluce del piede avanzato sulla linea del metro, "
            "piede perfettamente allineato alla direzione del metro.",
            "Spingere il ginocchio in avanti fino a toccare la parete "
            "MANTENENDO IL TALLONE A TERRA.",
            "Se il ginocchio tocca senza che il tallone si sollevi, arretrare "
            "il piede di un centimetro e ripetere.",
            "Il risultato e' la distanza massima alluce-parete con contatto "
            "del ginocchio e tallone a terra.",
            "Due misurazioni per lato. Il ginocchio deve puntare dritto: "
            "se cade verso l'interno la prova non e' valida.",
        ],
        "interpretazione": "Sotto i 9 cm la letteratura segnala aumento del valgo "
                           "dinamico in atterraggio e maggiore carico su ginocchio "
                           "e tendine rotuleo. E' un parametro molto allenabile: "
                           "risponde in due o tre settimane di lavoro mirato.",
    },
    "ele_salto": {
        "sigla": "ELE", "label": "Elevazione",
        "protocollo": "Salto verticale al muro (Sargent)",
        "unita": "cm", "decimali": 1, "prove": 3, "recupero": "45 secondi",
        "min": 10.0, "max": 110.0, "step": 0.5,
        # Si rileva e si trascrive l'ALTEZZA DEL TOCCO. La sottrazione dello
        # standing reach la fa il sistema: chiedere una sottrazione a mano su
        # quindici atleti a bordo campo e' il modo piu' rapido per introdurre
        # errori che poi non sono piu' distinguibili dai dati veri.
        "input_label": "Altezza tocco (cm)",
        "input_min": 150.0, "input_max": 400.0,
        "promemoria": "Stacco a piedi pari, nessuna rincorsa. Si registra "
                      "l'ALTEZZA DEL TOCCO: il reach lo sottrae il sistema.",
        "sop": [
            "Metro a nastro fissato verticalmente su parete liscia. "
            "Polvere o gesso sulle dita della mano dominante.",
            "STANDING REACH: atleta a piedi piatti, fianco al muro, braccio "
            "dominante esteso al massimo. Segnare il punto. Si rileva una volta "
            "sola e si registra nell'anagrafica.",
            "SALTO: contromovimento libero di gambe e braccia, stacco a piedi "
            "pari senza passi ne' rincorsa, tocco del muro nel punto piu' alto.",
            "Si trascrive l'ALTEZZA DEL TOCCO in centimetri, non la differenza: "
            "l'elevazione la calcola il sistema sottraendo lo standing reach.",
            "Tre prove, si registra il tocco piu'' alto. Recupero 45 secondi.",
            "Prova nulla: rincorsa, passo di stacco, doppio stacco.",
        ],
        "interpretazione": "Espressione di potenza degli arti inferiori. "
                           "Migliora di 2-4 cm in tre settimane su atleti non "
                           "allenati, quasi tutto per adattamento neurale.",
    },
    "acc_10m": {
        "sigla": "ACC", "label": "Sprint 10 metri",
        "protocollo": "Accelerazione lineare da fermo",
        "unita": "s", "decimali": 2, "prove": 2, "recupero": "2 minuti",
        "min": 1.20, "max": 3.50, "step": 0.01,
        "promemoria": "Cronometro al primo movimento. "
                      "Sempre lo stesso cronometrista tra T0 e T1.",
        "sop": [
            "Misurare 10 metri esatti con il metro e marcare con due coni. "
            "La misurazione si fa una volta sola.",
            "Partenza da fermo in piedi, piede avanzato SULLA linea, "
            "nessun contromovimento all'indietro.",
            "Cronometro avviato al primo movimento visibile, fermato al "
            "passaggio del busto sul cono dei 10 metri.",
            "Due prove, si registra la migliore. Recupero 2 minuti pieni.",
            "VINCOLO: deve cronometrare sempre la stessa persona al T0 e al T1.",
        ],
        "interpretazione": "In tre settimane si muove di 3-6 centesimi, che "
                           "rientrano nell'errore del cronometraggio manuale. "
                           "Serve al profilo, NON va usato come prova di efficacia "
                           "del programma.",
    },
    "agi_lane": {
        "sigla": "AGI", "label": "Lane Agility",
        "protocollo": "Giro completo del pitturato, andata e ritorno",
        "unita": "s", "decimali": 2, "prove": 2, "recupero": "3 minuti",
        "min": 8.00, "max": 22.00, "step": 0.01,
        "promemoria": "Sprint, slide, corsa indietro, slide. Poi senso inverso "
                      "senza fermarsi. Nullo se un angolo viene tagliato.",
        "sop": [
            "Nessuna misurazione: il percorso sono le linee dell'area.",
            "Partenza dall'angolo ALTO SINISTRO dell'area, lato lunetta.",
            "1) Sprint frontale fino all'angolo basso sinistro (fondo).",
            "2) Slide laterale difensiva fino all'angolo basso destro.",
            "3) Corsa ALL'INDIETRO fino all'angolo alto destro.",
            "4) Slide laterale fino al punto di partenza.",
            "5) Senza fermarsi, ripetere il giro in senso inverso e tornare "
            "al punto di partenza. Il tempo e' del giro completo.",
            "Due prove, si registra la migliore. Recupero 3 minuti.",
            "Prova nulla: angolo tagliato, piede che non raggiunge la linea, "
            "slide eseguita con passi incrociati.",
        ],
        "interpretazione": "Il test piu' reattivo del gruppo: -0.4/-0.8 secondi "
                           "in tre settimane. Zero errore di setup perche' il "
                           "percorso e' gia' disegnato sul campo. E' il dato da "
                           "mostrare quando serve dimostrare che il lavoro funziona.",
    },
    "asi_monopodalico": {
        "sigla": "ASI", "label": "Asimmetria monopodalica",
        "protocollo": "Salto in lungo da fermo su una gamba",
        "unita": "%", "decimali": 1, "prove": 2, "recupero": "60 secondi",
        "min": 0.0, "max": 60.0, "step": 0.1,
        "promemoria": "Atterraggio sulla stessa gamba, stabilizzazione 2 secondi. "
                      "Si misurano i centimetri di destra e di sinistra.",
        "sop": [
            "Metro a nastro steso a terra, nastro adesivo per la linea di partenza.",
            "Salto in lungo da fermo su UNA gamba sola, braccia libere.",
            "Atterraggio sulla stessa gamba con stabilizzazione di almeno "
            "2 secondi: se l'atleta appoggia l'altro piede o salta, prova nulla.",
            "Misura dalla linea al tallone dell'appoggio.",
            "Due prove per lato, si registra la migliore per ciascun lato.",
            "L'app calcola la percentuale di squilibrio.",
        ],
        "interpretazione": "Oltre il 10% di differenza tra i lati il rischio di "
                           "infortunio agli arti inferiori aumenta in modo "
                           "documentato. E' un indicatore di rischio, non di "
                           "prestazione: non entra nel punteggio complessivo.",
    },
    "for_piegamenti": {
        "sigla": "FOR", "label": "Piegamenti 60 secondi",
        "protocollo": "Massimo numero di ripetizioni valide",
        "unita": "rip", "decimali": 0, "prove": 1, "recupero": "—",
        "min": 0, "max": 120, "step": 1,
        "promemoria": "Gomito a 90 gradi, corpo in linea. Non valida se il bacino "
                      "cede. A coppie: uno esegue, uno conta.",
        "sop": [
            "Atleti a coppie: uno esegue, uno conta ad alta voce.",
            "Mani a larghezza spalle, corpo in linea retta da caviglia a testa.",
            "Discesa fino a gomito a 90 gradi, risalita a braccia "
            "completamente estese.",
            "Ritmo libero: si puo' fermare in posizione alta senza scendere "
            "a terra, il cronometro non si ferma.",
            "Una sola prova, massimo numero di ripetizioni VALIDE in 60 secondi.",
            "Non valida: bacino che cede o si solleva, escursione incompleta, "
            "ginocchia a terra.",
        ],
        "interpretazione": "Forza-resistenza del treno superiore, rilevante nei "
                           "contatti e nella tenuta del corpo in traffico. "
                           "Molto reattivo: +5/+10 ripetizioni in tre settimane.",
    },
    "res_navetta": {
        "sigla": "RES", "label": "Navetta (line drill)",
        "protocollo": "Lunetta, meta campo, lunetta opposta, fondo opposto",
        "unita": "s", "decimali": 1, "prove": 1, "recupero": "—",
        "min": 20.0, "max": 60.0, "step": 0.1,
        "promemoria": "Ogni linea va toccata con la mano. "
                      "SEMPRE l'ultimo test della sessione.",
        "sop": [
            "Partenza dalla linea di fondo. Percorso sulle linee del campo.",
            "Andata e ritorno toccando CON LA MANO ogni linea, tornando ogni "
            "volta alla linea di fondo di partenza:",
            "lunetta tiro libero vicina, meta' campo, lunetta opposta, "
            "fondo opposto.",
            "Una sola prova cronometrata, a recupero completo dai test "
            "precedenti.",
            "E' il test piu' affaticante: va SEMPRE eseguito per ultimo, "
            "altrimenti falsa tutti gli altri.",
        ],
        "interpretazione": "Capacita' di ripetere sforzi intensi, il profilo "
                           "metabolico della pallacanestro. Migliora di 1-2 "
                           "secondi in tre settimane.",
    },
}

# Ordine di esecuzione: mobilita' prima (si valuta a freddo, dopo il
# riscaldamento generale), navetta ultima perche' affatica.
ORDINE_TEST = ["mob_kneewall", "ele_salto", "acc_10m", "agi_lane",
               "asi_monopodalico", "for_piegamenti", "res_navetta"]

# SOGLIE — vedi RIFERIMENTI_SCIENTIFICI.md per la giustificazione di ciascuna.
#
# ASIMMETRIA 10%: soglia mutuata dalla letteratura sul ritorno allo sport dopo
# ricostruzione del LCA (Limb Symmetry Index >= 90%). NON e' un valore
# predittivo validato su atleti sani: fino a un quarto degli atleti sani non
# lo raggiunge. Va trattato come innesco di approfondimento, non come diagnosi.
SOGLIA_ASIMMETRIA = 10.0

# DIFFERENZA CAVIGLIE 2.0 cm: nei soggetti sani le asimmetrie al knee-to-wall
# arrivano tipicamente fino a 1.5 cm. Sopra i 2.0 cm si esce dal range di
# normalita' senza segnalare mezza squadra. Alzata da 1.5 dopo revisione
# della letteratura normativa sul weight-bearing lunge test.
SOGLIA_MOB_DIFF = 2.0

# DORSIFLESSIONE MINIMA 9.0 cm: convenzione operativa del weight-bearing lunge
# test. L'evidenza prospettica sul basket (Backman e Danielson 2011) usa i
# GRADI (soglia 36.5 gradi), non i centimetri: la corrispondenza fra le due
# scale e' forte (r = 0.95) ma non e' una conversione esatta.
SOGLIA_MOB_MINIMA = 9.0

# MDC — minima variazione rilevabile al knee-to-wall: sotto 1.5 cm una
# differenza fra due misurazioni rientra nell'errore dello strumento.
MDC_MOB = 1.5
TTL_CACHE = 300
SLOT_DEFAULT = 15
LOGO_LATO_MAX = 320           # pixel, ridimensionamento del logo caricato


# ==============================================================================
# 2. CONNESSIONE
# ==============================================================================

@st.cache_resource
def get_client() -> Client:
    try:
        return create_client(st.secrets["supabase_url"], st.secrets["supabase_key"])
    except KeyError as e:
        st.error(f"Segreto mancante: {e}. Servono 'supabase_url' e 'supabase_key'.")
        st.stop()
    except Exception as e:
        st.error(f"Connessione a Supabase fallita: {e}")
        st.stop()


def invalidate_cache():
    """Da chiamare dopo OGNI scrittura."""
    load_atleti.clear()
    load_test.clear()
    load_confronto.clear()
    load_utenti.clear()


# ==============================================================================
# 3. UTENTI, PIN E LICENZE
# ==============================================================================
#
# L'AMMINISTRATORE non e' nel database: il suo PIN sta nei secrets, cosi'
# l'accesso resta possibile anche con tabella utenti vuota o corrotta.
#
# I PIN dei coach non sono mai salvati in chiaro. Al momento della creazione
# il PIN viene mostrato UNA VOLTA; poi resta solo la sua impronta.
# ==============================================================================

RUOLO_ADMIN = "admin"
RUOLO_PARTNER = "partner"

PERMESSI = {
    RUOLO_ADMIN: {
        "etichetta": "Direttore Tecnico",
        "elimina": True, "vede_norme": True, "modifica_norme": True,
        "gestisce_utenti": True, "vede_tutte_squadre": True, "usa_ai": True,
        "vede_diagnostica": True,
    },
    RUOLO_PARTNER: {
        "etichetta": "Coach",
        "elimina": False, "vede_norme": False, "modifica_norme": False,
        "gestisce_utenti": False, "vede_tutte_squadre": False, "usa_ai": True,
        "vede_diagnostica": False,
    },
}


def _impronta(pin: str, salt: str) -> str:
    return hashlib.sha256((salt + str(pin).strip()).encode("utf-8")).hexdigest()


def genera_pin(lunghezza: int = 6) -> str:
    """PIN numerico casuale, sorgente crittografica."""
    return "".join(str(pysecrets.randbelow(10)) for _ in range(lunghezza))


def puo(azione: str) -> bool:
    return bool(PERMESSI.get(st.session_state.get("ruolo"), {}).get(azione, False))


def etichetta_ruolo() -> str:
    return PERMESSI.get(st.session_state.get("ruolo"), {}).get("etichetta", "Ospite")


def verifica_accesso(pin: str) -> dict | None:
    """Autentica un PIN. Restituisce {ruolo, utente_id, nome, ...} oppure None."""
    pin = str(pin).strip()
    if not pin:
        return None

    try:
        master = str(st.secrets.get("pin_admin", "\x00")).strip()
        if master and pin == master:
            return {"ruolo": RUOLO_ADMIN, "utente_id": None,
                    "nome": "Amministratore", "slot_max": None,
                    "stato_servizio": "attivo"}
    except Exception:
        pass

    try:
        res = get_client().table("utenti").select("*").eq("attivo", True).execute()
        for u in (res.data or []):
            if _impronta(pin, u["pin_salt"]) == u["pin_hash"]:
                scad = u.get("scadenza")
                if scad and str(scad) < date.today().isoformat():
                    return {"errore": "Licenza scaduta. Contattare AREA199."}
                _registra_accesso(u["id"])
                return {"ruolo": RUOLO_PARTNER, "utente_id": u["id"],
                        "nome": u["nome"], "slot_max": u["slot_max"],
                        "stato_servizio": u.get("stato_servizio", "preattivo")}
    except Exception:
        return None
    return None


def _registra_accesso(utente_id: int):
    try:
        get_client().table("utenti").update(
            {"ultimo_accesso": datetime.utcnow().isoformat()}
        ).eq("id", utente_id).execute()
    except Exception:
        pass


@st.cache_data(ttl=60, show_spinner=False)
def load_utenti() -> pd.DataFrame:
    """Elenco coach con conteggio slot, dalla vista v_utilizzo_slot."""
    try:
        df = pd.DataFrame(
            get_client().table("v_utilizzo_slot").select("*")
            .order("nome").execute().data or [])
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame(columns=["coach_id", "nome", "organizzazione",
                                     "slot_max", "slot_usati", "slot_liberi",
                                     "attivo", "scadenza", "ultimo_accesso",
                                     "logo_b64"])
    for c in ["slot_max", "slot_usati", "slot_liberi"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    return df


def dati_coach(coach_id) -> dict:
    """Nome, societa' e logo di un coach. Dizionario vuoto se non trovato."""
    vuoto = {"nome": "", "organizzazione": "", "logo_b64": ""}
    if coach_id is None:
        return vuoto
    u = load_utenti()
    if u.empty:
        return vuoto
    r = u[u["coach_id"] == coach_id]
    if r.empty:
        return vuoto
    r = r.iloc[0]
    return {"nome": str(r.get("nome") or ""),
            "organizzazione": str(r.get("organizzazione") or ""),
            "logo_b64": str(r.get("logo_b64") or "")}


def crea_utente(nome: str, organizzazione: str = "", slot_max: int = SLOT_DEFAULT,
                scadenza=None, note: str = "") -> tuple[bool, str, str]:
    """
    Crea un coach e genera il suo PIN.
    Il PIN in chiaro esiste solo nel valore restituito: va comunicato subito.
    """
    try:
        pin = genera_pin()
        salt = pysecrets.token_hex(16)
        dati = {
            "nome": nome.strip(), "organizzazione": organizzazione.strip() or None,
            "ruolo": "partner", "pin_hash": _impronta(pin, salt), "pin_salt": salt,
            "slot_max": int(slot_max), "attivo": True, "note": note.strip() or None,
        }
        if scadenza:
            dati["scadenza"] = (scadenza.isoformat()
                                if hasattr(scadenza, "isoformat") else str(scadenza))
        get_client().table("utenti").insert(dati).execute()
        load_utenti.clear()
        return True, "Utente creato.", pin
    except Exception as e:
        return False, str(e), ""


def rigenera_pin(utente_id: int) -> tuple[bool, str]:
    """Nuovo PIN. Il precedente smette immediatamente di funzionare."""
    try:
        pin = genera_pin()
        salt = pysecrets.token_hex(16)
        get_client().table("utenti").update(
            {"pin_hash": _impronta(pin, salt), "pin_salt": salt}
        ).eq("id", utente_id).execute()
        load_utenti.clear()
        return True, pin
    except Exception as e:
        return False, str(e)


def aggiorna_licenza(utente_id: int, slot_max: int | None = None,
                     attivo: bool | None = None, scadenza=None,
                     organizzazione: str | None = None) -> bool:
    try:
        campi = {}
        if slot_max is not None:
            campi["slot_max"] = int(slot_max)
        if attivo is not None:
            campi["attivo"] = bool(attivo)
        if scadenza is not None:
            campi["scadenza"] = (scadenza.isoformat()
                                 if hasattr(scadenza, "isoformat") else scadenza)
        if organizzazione is not None:
            campi["organizzazione"] = organizzazione.strip() or None
        if not campi:
            return True
        get_client().table("utenti").update(campi).eq("id", utente_id).execute()
        load_utenti.clear()
        return True
    except Exception:
        return False


CAMPI_ANAGRAFICI = [
    "tipo_soggetto", "ragione_sociale", "legale_rappr", "codice_fiscale",
    "partita_iva", "indirizzo", "cap", "citta", "provincia", "email",
    "pec", "telefono", "categoria_squadra", "atleti_minorenni",
    "organizzazione",
]

CAMPI_CONTRATTUALI = [
    "contratto_data_inizio", "contratto_data_fine", "importo_attivazione",
    "importo_canone", "periodicita_canone", "condizioni_note", "prezzo_pilota",
    "sedute_settimana", "minuti_seduta", "attrezzatura_dich", "spazi_dich",
]

# Campi minimi perche' il contratto sia compilabile
CAMPI_OBBLIGATORI = ["codice_fiscale", "indirizzo", "citta", "email"]


def salva_dati_cliente(coach_id: int, dati: dict) -> tuple[bool, str]:
    """Aggiorna anagrafica e/o condizioni contrattuali di un coach."""
    try:
        ammessi = set(CAMPI_ANAGRAFICI) | set(CAMPI_CONTRATTUALI)
        campi = {k: v for k, v in dati.items() if k in ammessi}
        for k, v in list(campi.items()):
            if isinstance(v, str):
                campi[k] = v.strip() or None
            elif hasattr(v, "isoformat"):
                campi[k] = v.isoformat()
        if not campi:
            return True, "nessuna modifica"
        if any(k in campi for k in CAMPI_ANAGRAFICI):
            campi["dati_completati_il"] = datetime.utcnow().isoformat()
        get_client().table("utenti").update(campi).eq("id", coach_id).execute()
        load_utenti.clear()
        return True, "Dati salvati."
    except Exception as e:
        return False, str(e)


def dati_mancanti(coach_id) -> list:
    """Campi obbligatori ancora vuoti, per segnalarlo prima di generare atti."""
    d = dati_coach_completi(coach_id)
    if not d:
        return CAMPI_OBBLIGATORI
    return [c for c in CAMPI_OBBLIGATORI if not str(d.get(c) or "").strip()]


def dati_coach_completi(coach_id) -> dict:
    """Riga completa del coach dalla vista, come dizionario."""
    if coach_id is None:
        return {}
    u = load_utenti()
    if u.empty:
        return {}
    r = u[u["coach_id"] == coach_id]
    return {} if r.empty else r.iloc[0].to_dict()


def registra_accettazione(coach_id: int, documento: str, versione: str,
                          nome: str, testo: str = "") -> tuple[bool, str]:
    """
    Registra l'accettazione di un documento in piattaforma.

    NATURA GIURIDICA: firma elettronica semplice ai sensi del Regolamento
    eIDAS. Non le si puo' negare valore probatorio, ma il suo peso e'
    liberamente valutabile dal giudice ed e' inferiore a quello di una firma
    autografa o di una firma elettronica qualificata. L'impronta del testo
    serve a dimostrare che il documento non e' stato alterato dopo.
    """
    try:
        impronta = hashlib.sha256(testo.encode("utf-8")).hexdigest() if testo else None
        get_client().table("accettazioni").insert({
            "coach_id": coach_id, "documento": documento, "versione": versione,
            "nome_dichiarante": nome.strip(), "impronta_testo": impronta,
        }).execute()
        load_accettazioni.clear()
        return True, "Accettazione registrata."
    except Exception as e:
        return False, str(e)


@st.cache_data(ttl=60, show_spinner=False)
def load_accettazioni(coach_id=None) -> pd.DataFrame:
    q = get_client().table("accettazioni").select("*")
    if coach_id is not None:
        q = q.eq("coach_id", coach_id)
    return pd.DataFrame(q.order("accettato_il", desc=True).execute().data or [])


STATI_SERVIZIO = {
    "preattivo": "In attivazione",
    "attivo": "Attivo",
    "sospeso": "Sospeso",
}


def servizio_attivo() -> bool:
    """
    True se l'utente in sessione ha accesso pieno.

    In stato 'preattivo' o 'sospeso' il coach entra ma vede solo la propria
    anagrafica e il contratto: nessun atleta, nessun test, nessuna scheda.
    L'amministratore non e' mai limitato.
    """
    if st.session_state.get("ruolo") == RUOLO_ADMIN:
        return True
    return st.session_state.get("stato_servizio") == "attivo"


def cambia_stato_servizio(coach_id: int, nuovo_stato: str,
                          motivo: str = "") -> tuple[bool, str]:
    """
    Passaggio di stato con registrazione nello storico.
    L'attivazione e' un atto deliberato del direttore tecnico.
    """
    if nuovo_stato not in STATI_SERVIZIO:
        return False, "Stato non valido."
    try:
        cl = get_client()
        prec = (cl.table("utenti").select("stato_servizio")
                .eq("id", coach_id).limit(1).execute())
        stato_da = prec.data[0]["stato_servizio"] if prec.data else None

        campi = {"stato_servizio": nuovo_stato}
        if nuovo_stato == "attivo":
            campi["attivato_il"] = datetime.utcnow().isoformat()
            campi["sospeso_il"] = None
        elif nuovo_stato == "sospeso":
            campi["sospeso_il"] = datetime.utcnow().isoformat()
        if motivo:
            campi["note_attivazione"] = motivo.strip()

        cl.table("utenti").update(campi).eq("id", coach_id).execute()
        cl.table("storico_attivazioni").insert({
            "coach_id": coach_id, "stato_da": stato_da, "stato_a": nuovo_stato,
            "motivo": motivo.strip() or None}).execute()
        load_utenti.clear()
        return True, f"Servizio ora in stato: {STATI_SERVIZIO[nuovo_stato]}."
    except Exception as e:
        return False, str(e)


def aggiorna_prerequisiti(coach_id: int, contratto: bool | None = None,
                          pagamento: bool | None = None) -> bool:
    """Spunta contratto ricevuto e pagamento ricevuto, senza attivare."""
    try:
        campi = {}
        if contratto is not None:
            campi["contratto_ricevuto"] = bool(contratto)
        if pagamento is not None:
            campi["pagamento_ricevuto"] = bool(pagamento)
        if not campi:
            return True
        get_client().table("utenti").update(campi).eq("id", coach_id).execute()
        load_utenti.clear()
        return True
    except Exception:
        return False


def prerequisiti_attivazione(coach_id) -> dict:
    """
    Stato dei tre requisiti che precedono l'attivazione.
    Non bloccano: informano. La decisione resta del direttore tecnico.
    """
    d = dati_coach_completi(coach_id)
    acc = load_accettazioni(coach_id)
    accettato = (not acc.empty
                 and (acc["documento"] == "contratto").any())
    return {
        "anagrafica": len(dati_mancanti(coach_id)) == 0,
        "accettazione": accettato,
        "contratto": bool(d.get("contratto_ricevuto")),
        "pagamento": bool(d.get("pagamento_ricevuto")),
        "stato": d.get("stato_servizio", "preattivo"),
    }


def slot_info(coach_id) -> dict:
    vuoto = {"usati": 0, "max": None, "liberi": None, "pieno": False}
    if coach_id is None:
        return vuoto
    u = load_utenti()
    if u.empty:
        return vuoto
    r = u[u["coach_id"] == coach_id]
    if r.empty:
        return vuoto
    r = r.iloc[0]
    usati, massimo = int(r["slot_usati"] or 0), int(r["slot_max"] or 0)
    return {"usati": usati, "max": massimo, "liberi": max(0, massimo - usati),
            "pieno": usati >= massimo}


# ==============================================================================
# 4. LOGO SOCIETA'
# ==============================================================================

def prepara_logo(file_caricato) -> tuple[bool, str]:
    """
    Converte l'immagine caricata in data URI base64, ridimensionandola.
    Il ridimensionamento evita di trascinare file da megabyte dentro ogni
    lettura della tabella utenti.
    """
    try:
        grezzo = file_caricato.read()
        if not grezzo:
            return False, "File vuoto."

        if Image is not None:
            img = Image.open(io.BytesIO(grezzo))
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            img.thumbnail((LOGO_LATO_MAX, LOGO_LATO_MAX), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            grezzo = buf.getvalue()
            mime = "image/png"
        else:
            if len(grezzo) > 400_000:
                return False, ("Immagine troppo grande. Caricane una sotto i 400 KB "
                               "oppure ridimensionala prima.")
            mime = getattr(file_caricato, "type", "image/png") or "image/png"

        return True, f"data:{mime};base64,{base64.b64encode(grezzo).decode()}"
    except Exception as e:
        return False, f"Immagine non leggibile: {e}"


def salva_logo(utente_id: int, data_uri: str) -> bool:
    try:
        get_client().table("utenti").update({"logo_b64": data_uri or None}) \
            .eq("id", utente_id).execute()
        load_utenti.clear()
        return True
    except Exception:
        return False


# ==============================================================================
# 5. LETTURE
# ==============================================================================

@st.cache_data(ttl=TTL_CACHE, show_spinner=False)
def load_atleti(coach_id=None, solo_attivi: bool = True,
                tutte_squadre: bool = False) -> pd.DataFrame:
    q = get_client().table("atleti").select("*")
    if solo_attivi:
        q = q.eq("attivo", True)
    if not tutte_squadre:
        q = q.eq("coach_id", coach_id) if coach_id is not None \
            else q.is_("coach_id", "null")
    df = pd.DataFrame(q.order("cognome").execute().data or [])
    if df.empty:
        return pd.DataFrame(columns=[
            "id", "nome", "cognome", "anno_nascita", "squadra", "ruolo", "mano",
            "peso", "altezza", "reach", "apertura", "foto_url", "attivo", "coach_id"])
    for c in ["anno_nascita", "altezza", "reach", "apertura"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    if "peso" in df.columns:
        df["peso"] = pd.to_numeric(df["peso"], errors="coerce")
    return df


@st.cache_data(ttl=TTL_CACHE, show_spinner=False)
def load_test(atleta_id: str | None = None) -> pd.DataFrame:
    q = get_client().table("test_sessioni").select("*")
    if atleta_id:
        q = q.eq("atleta_id", atleta_id)
    df = pd.DataFrame(q.order("data_test", desc=True).execute().data or [])
    if df.empty:
        return pd.DataFrame(columns=[
            "id", "atleta_id", "data_test", "sessione", "eta", "peso", "altezza",
            "mob_kneewall", "mob_diff", "ele_salto", "acc_10m", "agi_lane",
            "res_navetta", "for_piegamenti", "asi_monopodalico", "note",
            "ai_comment"])
    for c in list(ASSI.values()) + ["asi_monopodalico", "mob_diff", "peso"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "data_test" in df.columns:
        df["data_test"] = pd.to_datetime(df["data_test"], errors="coerce")
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def load_norme(categoria: str = CATEGORIA) -> pd.DataFrame:
    res = (get_client().table("norme_riferimento").select("*")
           .eq("categoria", categoria).execute())
    df = pd.DataFrame(res.data or [])
    if not df.empty:
        df["media"] = pd.to_numeric(df["media"], errors="coerce")
        df["dev_st"] = pd.to_numeric(df["dev_st"], errors="coerce")
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def load_targets() -> dict:
    res = get_client().table("role_targets").select("*").execute()
    return {
        r["ruolo"]: {
            "MOB": int(r.get("mob_target", 75)), "ELE": int(r.get("ele_target", 70)),
            "ACC": int(r.get("acc_target", 70)), "AGI": int(r.get("agi_target", 70)),
            "RES": int(r.get("res_target", 70)), "FOR": int(r.get("for_target", 70)),
        } for r in (res.data or [])
    }


@st.cache_data(ttl=TTL_CACHE, show_spinner=False)
def load_confronto(coach_id=None, tutte_squadre: bool = False) -> pd.DataFrame:
    q = get_client().table("v_confronto_sessioni").select("*")
    if not tutte_squadre and coach_id is not None:
        q = q.eq("coach_id", coach_id)
    df = pd.DataFrame(q.execute().data or [])
    if df.empty:
        return df
    for c in df.columns:
        if c.endswith(("_t0", "_t1", "_delta")):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ==============================================================================
# 6. MOTORE PUNTEGGI
# ==============================================================================
#
# Il confronto e' contro NORME FISSE per ruolo, non contro la coorte interna.
# Se la squadra intera migliora, i punteggi salgono: e' la condizione perche'
# il retest di fine pre-season mostri qualcosa.
# ==============================================================================

def _norma(norme: pd.DataFrame, ruolo: str, test: str):
    if norme is None or norme.empty:
        return None
    sel = norme[(norme["ruolo"] == ruolo) & (norme["test"] == test)]
    if sel.empty:
        return None
    r = sel.iloc[0]
    try:
        media, dev = float(r["media"]), float(r["dev_st"])
    except (TypeError, ValueError):
        return None
    return (media, dev, str(r["direzione"])) if dev > 0 else None


def calcola_punteggio(test: str, valore, ruolo: str, norme: pd.DataFrame) -> int | None:
    """
    Risultato grezzo -> punteggio 30-99 rispetto alla norma di ruolo.
    None se il dato manca: non viene inventato un numero di ripiego.
    """
    if valore is None:
        return None
    try:
        val = float(valore)
    except (TypeError, ValueError):
        return None
    if pd.isna(val) or val <= 0:
        return None

    n = _norma(norme, ruolo, test)
    if n is None:
        return None
    media, dev, direzione = n

    z = (val - media) / dev
    if direzione == "basso_meglio":
        z = -z
    percentile = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    return int(max(30, min(99, round(30 + percentile * 69))))


def calcola_tutti(riga_test, ruolo: str, norme: pd.DataFrame) -> dict:
    return {
        asse: calcola_punteggio(
            col, riga_test.get(col) if hasattr(riga_test, "get") else None,
            ruolo, norme)
        for asse, col in ASSI.items()
    }


def calcola_overall(punteggi: dict) -> int | None:
    validi = [v for v in punteggi.values() if v is not None]
    return int(round(sum(validi) / len(validi))) if validi else None


def flag_asimmetria(valore) -> bool:
    try:
        v = float(valore)
        return not pd.isna(v) and v > SOGLIA_ASIMMETRIA
    except (TypeError, ValueError):
        return False


def calcola_asimmetria(destra, sinistra) -> float | None:
    """Percentuale di squilibrio tra i due arti, dai centimetri rilevati."""
    try:
        d, s = float(destra), float(sinistra)
    except (TypeError, ValueError):
        return None
    if pd.isna(d) or pd.isna(s) or d <= 0 or s <= 0:
        return None
    alto, basso = max(d, s), min(d, s)
    return round((alto - basso) / alto * 100, 1)


def calcola_elevazione(altezza_tocco, reach) -> tuple[float | None, str | None]:
    """
    Elevazione = altezza del tocco meno standing reach.

    Restituisce (valore, errore). L'errore e' un messaggio leggibile, non
    un'eccezione: serve a dire al coach QUALE atleta ha il problema.
    """
    try:
        t = float(altezza_tocco)
    except (TypeError, ValueError):
        return None, None
    if pd.isna(t) or t <= 0:
        return None, None

    try:
        r = float(reach)
    except (TypeError, ValueError):
        return None, "standing reach mancante in anagrafica"
    if pd.isna(r) or r <= 0:
        return None, "standing reach mancante in anagrafica"

    salto = round(t - r, 1)
    if salto <= 0:
        return None, f"tocco ({t:.0f}) non superiore al reach ({r:.0f}): verificare"
    if salto > 120:
        return None, f"elevazione di {salto:.0f} cm implausibile: verificare i valori"
    return salto, None


def calcola_mobilita(destra, sinistra) -> tuple[float | None, float | None]:
    """
    Dal knee-to-wall dei due lati restituisce (lato piu' limitato, differenza).

    Si registra il PEGGIORE perche' e' quello che determina il rischio:
    una caviglia mobile non compensa quella rigida durante l'atterraggio.
    """
    try:
        d, s = float(destra), float(sinistra)
    except (TypeError, ValueError):
        return None, None
    if pd.isna(d) or pd.isna(s) or d < 0 or s < 0:
        return None, None
    return round(min(d, s), 1), round(abs(d - s), 1)


def flag_mobilita(valore) -> bool:
    """True se la dorsiflessione e' sotto la soglia di rischio."""
    try:
        v = float(valore)
        return not pd.isna(v) and 0 < v < SOGLIA_MOB_MINIMA
    except (TypeError, ValueError):
        return False


def flag_mob_diff(valore) -> bool:
    """True se la differenza tra i due lati e' clinicamente significativa."""
    try:
        v = float(valore)
        return not pd.isna(v) and v > SOGLIA_MOB_DIFF
    except (TypeError, ValueError):
        return False


# ==============================================================================
# 7. SCRITTURE
# ==============================================================================

def genera_id(nome: str, cognome: str, anno) -> str:
    return f"{nome[:2]}{cognome[:2]}{str(anno)[-2:]}".upper().replace(" ", "")


def salva_atleta(dati: dict, coach_id=None) -> tuple[bool, str]:
    """
    Inserisce o aggiorna un atleta rispettando il limite di licenza.
    Il controllo e' doppio: qui e nel trigger del database.
    """
    try:
        nuovo = not dati.get("id")
        if nuovo:
            dati["id"] = genera_id(dati.get("nome", "XX"), dati.get("cognome", "XX"),
                                   dati.get("anno_nascita", 2000))
        if coach_id is not None:
            dati["coach_id"] = coach_id

        if nuovo and coach_id is not None:
            info = slot_info(coach_id)
            if info["pieno"]:
                return False, (f"Licenza esaurita: {info['usati']} slot su "
                               f"{info['max']} occupati. Per aggiungere un atleta "
                               "occorre prima rimuoverne uno dalla rosa.")

        get_client().table("atleti").upsert(dati).execute()
        invalidate_cache()
        return True, dati["id"]
    except Exception as e:
        msg = str(e)
        if "Licenza esaurita" in msg or "check_violation" in msg:
            return False, "Licenza esaurita: nessuno slot disponibile."
        return False, msg


def _pulisci(v):
    if v is None or v == "":
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    return v


def salva_misure(atleta_id: str, data_test, sessione: str,
                 misure: dict, meta: dict | None = None) -> tuple[bool, str]:
    """
    Salva UNA O PIU' misure senza toccare quelle gia' presenti.

    PERCHE' NON E' UN UPSERT
    ------------------------
    I test si inseriscono una griglia alla volta: prima la mobilita' di tutti,
    poi l'elevazione di tutti. Un upsert completo riscriverebbe l'intera riga
    e azzererebbe i test salvati prima. Qui si cerca la riga della sessione e
    si aggiornano SOLO le colonne effettivamente passate.
    """
    try:
        d = (data_test.isoformat()[:10]
             if isinstance(data_test, (date, datetime)) else str(data_test)[:10])

        campi = {k: _pulisci(v) for k, v in misure.items()}
        campi = {k: v for k, v in campi.items() if v is not None}
        if not campi:
            return True, "nessun dato"

        cl = get_client()
        esistente = (cl.table("test_sessioni").select("id")
                     .eq("atleta_id", atleta_id).eq("data_test", d)
                     .eq("sessione", sessione).limit(1).execute())

        if esistente.data:
            cl.table("test_sessioni").update(campi) \
                .eq("id", esistente.data[0]["id"]).execute()
        else:
            nuovo = {"atleta_id": atleta_id, "data_test": d, "sessione": sessione}
            if meta:
                nuovo.update({k: _pulisci(v) for k, v in meta.items()})
            nuovo.update(campi)
            cl.table("test_sessioni").insert(nuovo).execute()
        return True, "ok"
    except Exception as e:
        return False, str(e)


def salva_commento_ai(sessione_id: int, testo: str) -> bool:
    try:
        get_client().table("test_sessioni").update({"ai_comment": testo}) \
            .eq("id", sessione_id).execute()
        invalidate_cache()
        return True
    except Exception:
        return False


def elimina_test(sessione_id: int) -> bool:
    try:
        get_client().table("test_sessioni").delete().eq("id", sessione_id).execute()
        invalidate_cache()
        return True
    except Exception:
        return False


def disattiva_atleta(atleta_id: str) -> bool:
    """Libera lo slot senza perdere lo storico dei test."""
    try:
        get_client().table("atleti").update({"attivo": False}) \
            .eq("id", atleta_id).execute()
        invalidate_cache()
        return True
    except Exception:
        return False


def aggiorna_norma(ruolo: str, test: str, media: float, dev_st: float,
                   categoria: str = CATEGORIA) -> bool:
    try:
        get_client().table("norme_riferimento").update(
            {"media": float(media), "dev_st": float(dev_st)}
        ).eq("categoria", categoria).eq("ruolo", ruolo).eq("test", test).execute()
        load_norme.clear()
        return True
    except Exception:
        return False


# ==============================================================================
# 8. PRESENTAZIONE
# ==============================================================================

def formatta_valore(col: str, valore) -> str:
    if valore is None or (isinstance(valore, float) and pd.isna(valore)):
        return "—"
    meta = META_TEST.get(col, {"unita": "", "decimali": 1})
    try:
        v = float(valore)
    except (TypeError, ValueError):
        return "—"
    d = meta["decimali"]
    return (f"{v:.0f} {meta['unita']}".strip() if d == 0
            else f"{v:.{d}f} {meta['unita']}".strip())


def formatta_delta(col: str, delta) -> str:
    if delta is None or (isinstance(delta, float) and pd.isna(delta)):
        return "—"
    try:
        v = float(delta)
    except (TypeError, ValueError):
        return "—"
    meta = META_TEST.get(col, {"unita": "", "decimali": 1})
    d = meta["decimali"]
    return (f"{v:+.0f} {meta['unita']}".strip() if d == 0
            else f"{v:+.{d}f} {meta['unita']}".strip())


def eta_da_anno(anno, riferimento: date | None = None) -> int | None:
    try:
        return (riferimento or date.today()).year - int(anno)
    except (TypeError, ValueError):
        return None


def check_connessione() -> tuple[bool, str]:
    try:
        n_norme = len(load_norme())
        n_utenti = len(load_utenti())
        if n_norme == 0:
            return False, "Connesso, ma la tabella norme e' vuota: rilanciare lo schema SQL."
        return True, f"Connesso. {n_norme} norme, {n_utenti} coach registrati."
    except Exception as e:
        return False, f"Errore: {e}"
