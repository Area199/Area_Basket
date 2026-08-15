"""
================================================================================
AREA199 BASKET LAB — LIVELLO DATI
================================================================================
Connessione, letture cachate, motore punteggi, gestione utenti e licenze.
Modulo autosufficiente: nessuna dipendenza da altri moduli AREA199.

Segreti richiesti (pannello Streamlit Cloud):

    supabase_url = "https://xxxxx.supabase.co"
    supabase_key = "eyJ...."        # service_role key, NON la anon key
    pin_admin    = "197519"         # chiave maestra dell'amministratore
    openai_key   = "sk-..."         # facoltativo

I PIN dei coach NON stanno nei secrets: si generano dal pannello di
amministrazione e vivono nel database sotto forma di impronta.

Versione 3.0 — Agosto 2026
================================================================================
"""

import hashlib
import math
import secrets as pysecrets
from datetime import date, datetime

import pandas as pd
import streamlit as st
from supabase import create_client, Client


# ==============================================================================
# 1. CONFIGURAZIONE
# ==============================================================================

CATEGORIA = "DR3"
RUOLI = ["Playmaker", "Guardia", "Ala Piccola", "Ala Grande", "Centro"]

ASSI = {
    "ELE": "ele_salto",
    "ACC": "acc_10m",
    "AGI": "agi_lane",
    "RES": "res_navetta",
    "FOR": "for_piegamenti",
}

META_TEST = {
    "ele_salto": {
        "sigla": "ELE", "label": "Elevazione",
        "protocollo": "Salto verticale al muro (Sargent)",
        "unita": "cm", "decimali": 1, "prove": 3, "recupero": "45 secondi",
        "min": 10.0, "max": 110.0, "step": 0.5,
        "promemoria": "Stacco a piedi pari, nessuna rincorsa. "
                      "Risultato = altezza tocco meno standing reach.",
    },
    "acc_10m": {
        "sigla": "ACC", "label": "Sprint 10 metri",
        "protocollo": "Accelerazione lineare da fermo",
        "unita": "s", "decimali": 2, "prove": 2, "recupero": "2 minuti",
        "min": 1.20, "max": 3.50, "step": 0.01,
        "promemoria": "Cronometro al primo movimento. "
                      "Sempre lo stesso cronometrista tra T0 e T1.",
    },
    "agi_lane": {
        "sigla": "AGI", "label": "Lane Agility",
        "protocollo": "Giro completo del pitturato, andata e ritorno",
        "unita": "s", "decimali": 2, "prove": 2, "recupero": "3 minuti",
        "min": 8.00, "max": 22.00, "step": 0.01,
        "promemoria": "Sprint, slide, corsa indietro, slide. Poi senso inverso "
                      "senza fermarsi. Nullo se un angolo viene tagliato.",
    },
    "asi_monopodalico": {
        "sigla": "ASI", "label": "Asimmetria monopodalica",
        "protocollo": "Salto in lungo da fermo su una gamba",
        "unita": "%", "decimali": 1, "prove": 2, "recupero": "60 secondi",
        "min": 0.0, "max": 60.0, "step": 0.1,
        "promemoria": "Atterraggio sulla stessa gamba, stabilizzazione 2 secondi. "
                      "Si misurano i centimetri di destra e di sinistra.",
    },
    "for_piegamenti": {
        "sigla": "FOR", "label": "Piegamenti 60 secondi",
        "protocollo": "Massimo numero di ripetizioni valide",
        "unita": "rip", "decimali": 0, "prove": 1, "recupero": "—",
        "min": 0, "max": 120, "step": 1,
        "promemoria": "Gomito a 90 gradi, corpo in linea. Non valida se il bacino "
                      "cede. A coppie: uno esegue, uno conta.",
    },
    "res_navetta": {
        "sigla": "RES", "label": "Navetta (line drill)",
        "protocollo": "Lunetta, meta campo, lunetta opposta, fondo opposto",
        "unita": "s", "decimali": 1, "prove": 1, "recupero": "—",
        "min": 20.0, "max": 60.0, "step": 0.1,
        "promemoria": "Ogni linea va toccata con la mano. "
                      "SEMPRE l'ultimo test della sessione.",
    },
}

# Dal meno al piu' affaticante. Invertirlo falsa i risultati.
ORDINE_TEST = ["ele_salto", "acc_10m", "agi_lane", "asi_monopodalico",
               "for_piegamenti", "res_navetta"]

SOGLIA_ASIMMETRIA = 10.0
TTL_CACHE = 300
SLOT_DEFAULT = 15


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
# L'AMMINISTRATORE non e' nel database: il suo PIN sta nei secrets. Cosi'
# l'accesso resta possibile anche con tabella utenti vuota o corrotta.
#
# I PIN dei coach non sono mai salvati in chiaro. Al momento della creazione
# il PIN viene mostrato UNA VOLTA; poi resta solo la sua impronta. Se si
# perde non si recupera: si rigenera.
# ==============================================================================

RUOLO_ADMIN = "admin"
RUOLO_PARTNER = "partner"

PERMESSI = {
    RUOLO_ADMIN: {
        "etichetta": "Direttore Tecnico",
        "elimina": True, "vede_norme": True, "modifica_norme": True,
        "gestisce_utenti": True, "vede_tutte_squadre": True, "usa_ai": True,
    },
    RUOLO_PARTNER: {
        "etichetta": "Coach",
        "elimina": False, "vede_norme": False, "modifica_norme": False,
        "gestisce_utenti": False, "vede_tutte_squadre": False, "usa_ai": True,
    },
}


def _impronta(pin: str, salt: str) -> str:
    return hashlib.sha256((salt + str(pin).strip()).encode("utf-8")).hexdigest()


def genera_pin(lunghezza: int = 6) -> str:
    """PIN numerico casuale, generato con sorgente crittografica."""
    return "".join(str(pysecrets.randbelow(10)) for _ in range(lunghezza))


def puo(azione: str) -> bool:
    return bool(PERMESSI.get(st.session_state.get("ruolo"), {}).get(azione, False))


def etichetta_ruolo() -> str:
    return PERMESSI.get(st.session_state.get("ruolo"), {}).get("etichetta", "Ospite")


def verifica_accesso(pin: str) -> dict | None:
    """
    Autentica un PIN.
    Restituisce {ruolo, utente_id, nome, slot_max} oppure None.
    """
    pin = str(pin).strip()
    if not pin:
        return None

    # 1) Chiave maestra dai secrets
    try:
        master = str(st.secrets.get("pin_admin", "\x00")).strip()
        if master and pin == master:
            return {"ruolo": RUOLO_ADMIN, "utente_id": None,
                    "nome": "Amministratore", "slot_max": None}
    except Exception:
        pass

    # 2) Coach dal database
    try:
        res = (get_client().table("utenti").select("*")
               .eq("attivo", True).execute())
        for u in (res.data or []):
            if _impronta(pin, u["pin_salt"]) == u["pin_hash"]:
                scad = u.get("scadenza")
                if scad and str(scad) < date.today().isoformat():
                    return {"errore": "Licenza scaduta. Contattare AREA199."}
                _registra_accesso(u["id"])
                return {"ruolo": RUOLO_PARTNER, "utente_id": u["id"],
                        "nome": u["nome"], "slot_max": u["slot_max"]}
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
                                     "attivo", "scadenza", "ultimo_accesso"])
    for c in ["slot_max", "slot_usati", "slot_liberi"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    return df


def crea_utente(nome: str, organizzazione: str = "", slot_max: int = SLOT_DEFAULT,
                scadenza=None, note: str = "") -> tuple[bool, str, str]:
    """
    Crea un coach e genera il suo PIN.
    Restituisce (esito, messaggio, pin_in_chiaro).
    Il PIN in chiaro esiste solo qui: va comunicato subito, poi non e' piu'
    recuperabile.
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
            dati["scadenza"] = scadenza.isoformat() if hasattr(scadenza, "isoformat") \
                else str(scadenza)
        get_client().table("utenti").insert(dati).execute()
        load_utenti.clear()
        return True, "Utente creato.", pin
    except Exception as e:
        return False, str(e), ""


def rigenera_pin(utente_id: int) -> tuple[bool, str]:
    """Nuovo PIN per un coach. Il precedente smette immediatamente di funzionare."""
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
                     attivo: bool | None = None, scadenza=None) -> bool:
    try:
        campi = {}
        if slot_max is not None:
            campi["slot_max"] = int(slot_max)
        if attivo is not None:
            campi["attivo"] = bool(attivo)
        if scadenza is not None:
            campi["scadenza"] = (scadenza.isoformat()
                                 if hasattr(scadenza, "isoformat") else scadenza)
        if not campi:
            return True
        get_client().table("utenti").update(campi).eq("id", utente_id).execute()
        load_utenti.clear()
        return True
    except Exception:
        return False


def slot_info(coach_id) -> dict:
    """Stato della licenza: usati, massimo, liberi."""
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
# 4. LETTURE
# ==============================================================================

@st.cache_data(ttl=TTL_CACHE, show_spinner=False)
def load_atleti(coach_id=None, solo_attivi: bool = True,
                tutte_squadre: bool = False) -> pd.DataFrame:
    """
    Rosa di un coach. Con tutte_squadre=True restituisce tutto
    (riservato all'amministratore).
    """
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
            "ele_salto", "acc_10m", "agi_lane", "res_navetta", "for_piegamenti",
            "asi_monopodalico", "note", "ai_comment"])
    for c in list(ASSI.values()) + ["asi_monopodalico", "peso"]:
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
            "ELE": int(r.get("ele_target", 70)), "ACC": int(r.get("acc_target", 70)),
            "AGI": int(r.get("agi_target", 70)), "RES": int(r.get("res_target", 70)),
            "FOR": int(r.get("for_target", 70)),
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
# 5. MOTORE PUNTEGGI
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


# ==============================================================================
# 6. SCRITTURE
# ==============================================================================

def genera_id(nome: str, cognome: str, anno) -> str:
    return f"{nome[:2]}{cognome[:2]}{str(anno)[-2:]}".upper().replace(" ", "")


def salva_atleta(dati: dict, coach_id=None) -> tuple[bool, str]:
    """
    Inserisce o aggiorna un atleta rispettando il limite di licenza.

    Il controllo e' doppio: qui e nel trigger del database. Se il limite viene
    superato per qualunque via, l'inserimento viene rifiutato a livello di
    database e l'eccezione risale fin qui.
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
    I test si inseriscono una griglia alla volta: prima l'elevazione di tutti,
    poi lo sprint di tutti. Un upsert completo riscriverebbe l'intera riga e
    azzererebbe i test salvati prima. Qui si cerca la riga della sessione e si
    aggiornano SOLO le colonne effettivamente passate.
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
# 7. PRESENTAZIONE
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
