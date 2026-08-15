"""
================================================================================
AREA199 HUMAN PERFORMANCE LAB — MOTORE DI PROGRAMMAZIONE
================================================================================
Analisi delle lacune, divisione in gruppi di lavoro, generazione del programma,
pianificazione dei retest, produzione delle schede stampabili.

PRINCIPIO DI FONDO
------------------
Nessun esercizio viene inventato. Il motore SELEZIONA e ASSEMBLA esclusivamente
dalla tabella `esercizi`, filtrando per attrezzatura realmente disponibile.
Se un attrezzo non e' in libreria non puo' comparire in una scheda: le
allucinazioni sono impossibili per costruzione, non per istruzione.

PERIODIZZAZIONE
---------------
Mesociclo di 4 settimane: tre di carico crescente piu' una di scarico.
Su atleti amatoriali con tre sedute settimanali serve quel tempo perche'
l'adattamento si consolidi, e la settimana di scarico e' dove il guadagno
si esprime invece di restare mascherato dalla fatica.

RETEST
------
Distinzione tra TEST COMPLETO (raro, produce il referto) e VERIFICA (frequente,
leggera, dentro il riscaldamento). Ritestare tutto ogni tre settimane misura
l'errore dello strumento, non il progresso: su sprint ed elevazione il
guadagno reale a tre settimane e' dello stesso ordine dell'errore di misura.

Versione 1.0 — Agosto 2026
================================================================================
"""

import random
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import db_basket as db


# ==============================================================================
# 1. CONFIGURAZIONE DELLA PERIODIZZAZIONE
# ==============================================================================

SETTIMANE_MESOCICLO = 4
MAX_GRUPPI = 3

# Moltiplicatore del volume settimana per settimana dentro il mesociclo.
# Le prime tre salgono, la quarta scarica mantenendo l'intensita'.
CARICO_SETTIMANA = {1: 1.00, 2: 1.15, 3: 1.30, 4: 0.60}

ETICHETTA_SETTIMANA = {
    1: "Introduzione", 2: "Carico", 3: "Picco", 4: "Scarico",
}

# Struttura della singola seduta, in minuti sul blocco disponibile
STRUTTURA_BLOCCO = [
    ("attivazione", 0.25, 2, ["mobilita", "attivazione", "correttivo"]),
    ("centrale",    0.55, 3, ["forza", "pliometria", "agilita"]),
    ("chiusura",    0.20, 1, ["condizionamento", "core"]),
]

# Marcatori usati nelle verifiche leggere: rapidi da rilevare su quindici
# persone e sensibili all'adattamento neuromuscolare.
TEST_VERIFICA_LEGGERA = ["mob_kneewall", "ele_salto"]

# Verifica parziale per blocchi corti: i tre test piu' reattivi, quelli in cui
# a tre settimane il guadagno supera con chiarezza l'errore di misura.
TEST_VERIFICA_PARZIALE = ["mob_kneewall", "agi_lane", "for_piegamenti"]

TEST_COMPLETI = ["mob_kneewall", "ele_salto", "acc_10m", "agi_lane",
                 "asi_monopodalico", "for_piegamenti", "res_navetta"]

ATTREZZATURA_BASE = ["corpo_libero", "muro", "campo", "cronometro", "cinesini"]

NOMI_GRUPPO = {
    "MOB": "Mobilità e controllo",
    "ELE": "Potenza e salto",
    "ACC": "Accelerazione",
    "AGI": "Agilità e cambi di direzione",
    "RES": "Condizionamento",
    "FOR": "Forza e stabilità",
}


# ==============================================================================
# 2. LETTURA LIBRERIA
# ==============================================================================

@st.cache_data(ttl=3600, show_spinner=False)
def load_esercizi() -> pd.DataFrame:
    df = pd.DataFrame(
        db.get_client().table("esercizi").select("*")
        .eq("attivo", True).order("codice").execute().data or [])
    if df.empty:
        return pd.DataFrame(columns=[
            "id", "codice", "nome", "asse_primario", "assi_secondari",
            "categoria", "attrezzatura", "livello", "serie_default",
            "rip_default", "recupero_sec", "durata_stimata_sec",
            "setup", "esecuzione", "focus", "errori_comuni"])
    for c in ["livello", "serie_default", "recupero_sec", "durata_stimata_sec"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df


def filtra_disponibili(esercizi: pd.DataFrame, attrezzatura: list) -> pd.DataFrame:
    """
    Tiene solo gli esercizi eseguibili con l'attrezzatura dichiarata.
    E' il filtro che rende impossibile prescrivere attrezzi inesistenti.
    """
    ammessa = set(attrezzatura) | set(ATTREZZATURA_BASE)
    if esercizi.empty:
        return esercizi
    return esercizi[esercizi["attrezzatura"].apply(
        lambda a: set(a or []).issubset(ammessa))].copy()


# ==============================================================================
# 3. ANALISI DELLE LACUNE
# ==============================================================================

def analizza_squadra(atleti: pd.DataFrame, norme: pd.DataFrame,
                     targets: dict, sessione: str = "T0") -> pd.DataFrame:
    """
    Per ogni atleta calcola il divario rispetto al target di ruolo su ogni asse.

    Il divario, non il punteggio assoluto, e' il criterio giusto: un centro
    con 70 di agilita' puo' essere in linea con il suo ruolo, mentre un
    playmaker con lo stesso 70 e' sotto di dodici punti.
    """
    test = db.load_test()
    righe = []

    for _, a in atleti.iterrows():
        suoi = test[test["atleta_id"] == a["id"]] if not test.empty else pd.DataFrame()
        if not suoi.empty and sessione:
            filtrati = suoi[suoi["sessione"] == sessione]
            if not filtrati.empty:
                suoi = filtrati

        voce = {"atleta_id": a["id"],
                "nome": f"{a['cognome']} {a['nome']}",
                "ruolo": a["ruolo"], "testato": not suoi.empty,
                "flag_mob": False, "flag_mob_diff": False, "flag_asi": False}

        if suoi.empty:
            for asse in db.ASSI:
                voce[f"gap_{asse}"] = None
            voce["deficit_primario"] = None
            righe.append(voce)
            continue

        u = suoi.iloc[0]
        punteggi = db.calcola_tutti(u, a["ruolo"], norme)
        tgt = targets.get(a["ruolo"], {k: 70 for k in db.ASSI})

        gaps = {}
        for asse in db.ASSI:
            p = punteggi.get(asse)
            gaps[asse] = None if p is None else (tgt.get(asse, 70) - p)
            voce[f"gap_{asse}"] = gaps[asse]

        validi = {k: v for k, v in gaps.items() if v is not None}
        voce["deficit_primario"] = max(validi, key=validi.get) if validi else None
        voce["gap_massimo"] = max(validi.values()) if validi else None

        voce["flag_mob"] = db.flag_mobilita(u.get("mob_kneewall"))
        voce["flag_mob_diff"] = db.flag_mob_diff(u.get("mob_diff"))
        voce["flag_asi"] = db.flag_asimmetria(u.get("asi_monopodalico"))
        righe.append(voce)

    return pd.DataFrame(righe)


def costruisci_gruppi(analisi: pd.DataFrame, max_gruppi: int = MAX_GRUPPI) -> list:
    """
    Divide la rosa in gruppi di lavoro per lacuna prevalente.

    Massimo tre: oltre, un allenatore da solo in palestra non riesce a
    gestirli e la qualita' dell'esecuzione crolla.
    """
    if analisi.empty:
        return []

    testati = analisi[analisi["testato"] & analisi["deficit_primario"].notna()]

    if testati.empty:
        return [{
            "nome": "Gruppo unico — base generale",
            "focus_assi": ["FOR", "MOB"],
            "descrizione": "Nessun test disponibile: lavoro generale di base "
                           "su forza, controllo e mobilità in attesa della "
                           "prima batteria di test.",
            "atleti_ids": analisi["atleta_id"].tolist(),
        }]

    conteggio = testati["deficit_primario"].value_counts()
    assi_gruppo = list(conteggio.index[:max_gruppi])

    gruppi = {a: [] for a in assi_gruppo}
    for _, r in analisi.iterrows():
        dp = r["deficit_primario"]
        if dp in gruppi:
            gruppi[dp].append(r["atleta_id"])
            continue
        # Chi ha un deficit fuori dai gruppi creati, oppure non e' stato
        # testato, finisce dove il suo divario e' comunque maggiore.
        migliore, valore = assi_gruppo[0], -999
        for a in assi_gruppo:
            g = r.get(f"gap_{a}")
            if g is not None and g > valore:
                migliore, valore = a, g
        gruppi[migliore].append(r["atleta_id"])

    out = []
    for i, asse in enumerate(assi_gruppo, start=1):
        if not gruppi[asse]:
            continue
        secondario = _asse_secondario(analisi, gruppi[asse], asse)
        out.append({
            "nome": f"Gruppo {i} — {NOMI_GRUPPO.get(asse, asse)}",
            "focus_assi": [asse] + ([secondario] if secondario else []),
            "descrizione": _descrizione_gruppo(asse, secondario, len(gruppi[asse])),
            "atleti_ids": gruppi[asse],
        })
    return out


def _asse_secondario(analisi: pd.DataFrame, ids: list, principale: str):
    """Seconda lacuna piu' diffusa nel gruppo, per dare varieta' al lavoro."""
    sub = analisi[analisi["atleta_id"].isin(ids)]
    medie = {}
    for asse in db.ASSI:
        if asse == principale:
            continue
        v = sub[f"gap_{asse}"].dropna()
        if len(v):
            medie[asse] = v.mean()
    if not medie:
        return None
    migliore = max(medie, key=medie.get)
    return migliore if medie[migliore] > 0 else None


def _descrizione_gruppo(asse: str, secondario, n: int) -> str:
    base = {
        "MOB": "Escursione articolare limitata: priorità a caviglia e anca. "
               "È il prerequisito degli altri lavori, non un complemento.",
        "ELE": "Deficit di espressione della potenza: lavoro pliometrico "
               "progressivo con attenzione alla qualità dell'atterraggio.",
        "ACC": "Deficit di accelerazione: tecnica di partenza, angoli di "
               "spinta e forza orizzontale.",
        "AGI": "Deficit nei cambi di direzione: decelerazione, controllo del "
               "ginocchio e riaccelerazione.",
        "RES": "Deficit di condizionamento: capacità di ripetere sforzi "
               "intensi con recuperi incompleti.",
        "FOR": "Deficit di forza e stabilità: base strutturale e controllo "
               "del corpo nei contatti.",
    }.get(asse, "Lavoro generale.")
    coda = (f" Secondo obiettivo: {NOMI_GRUPPO.get(secondario, secondario)}."
            if secondario else "")
    return f"{n} atleti. {base}{coda}"


# ==============================================================================
# 4. PIANIFICAZIONE DEI RETEST
# ==============================================================================

def pianifica_test(data_inizio: date, settimane: int,
                   sedute_settimana: int = 3) -> list:
    """
    Calendario dei controlli.

    REGOLA
    ------
    Sotto le 4 settimane si fa una VERIFICA PARZIALE sui tre test piu'
    reattivi. Sprint ed elevazione restano fuori: a tre settimane il loro
    guadagno reale e' dello stesso ordine dell'errore del cronometraggio
    manuale, e un confronto del genere non dimostra nulla, o peggio mostra
    un peggioramento che non esiste.

    Sopra le 4 settimane: verifica leggera a fine di ogni mesociclo,
    test completo alla fine del percorso.
    """
    piano = []

    if settimane < SETTIMANE_MESOCICLO:
        piano.append({
            "settimana": settimane,
            "data_prevista": data_inizio + timedelta(weeks=settimane) - timedelta(days=1),
            "etichetta": "T1",
            "test_da_fare": TEST_VERIFICA_PARZIALE,
            "motivo": (f"Verifica parziale a {settimane} settimane. Si ripetono "
                       "solo i test in cui il guadagno atteso supera con "
                       "chiarezza l'errore di misura: agilità, piegamenti e "
                       "mobilità di caviglia. Sprint ed elevazione sono esclusi "
                       "di proposito, perché su questa finestra il loro "
                       "miglioramento non sarebbe distinguibile dal rumore "
                       "del cronometraggio manuale."),
        })
        return piano

    blocchi = (settimane + SETTIMANE_MESOCICLO - 1) // SETTIMANE_MESOCICLO
    n = 1
    for b in range(1, blocchi + 1):
        sett = min(b * SETTIMANE_MESOCICLO, settimane)
        ultimo = (b == blocchi)
        piano.append({
            "settimana": sett,
            "data_prevista": data_inizio + timedelta(weeks=sett) - timedelta(days=1),
            "etichetta": f"T{n}",
            "test_da_fare": TEST_COMPLETI if ultimo else TEST_VERIFICA_LEGGERA,
            "motivo": (
                "Test completo di fine percorso: produce il referto e i dati "
                "di confronto con la baseline."
                if ultimo else
                f"Verifica leggera a fine mesociclo {b}, da svolgere dentro il "
                "riscaldamento in circa 10 minuti. Salto verticale e mobilità "
                "di caviglia sono i due marcatori più sensibili "
                "all'adattamento e i più rapidi da rilevare su tutta la rosa."),
        })
        n += 1
    return piano


# ==============================================================================
# 5. GENERAZIONE DEL PROGRAMMA
# ==============================================================================

def _scegli(pool: pd.DataFrame, n: int, rnd: random.Random,
            esclusi: set, livello_max: int) -> list:
    """Seleziona n esercizi evitando ripetizioni nella stessa seduta."""
    if pool.empty:
        return []
    cand = pool[(pool["livello"] <= livello_max)
                & (~pool["codice"].isin(esclusi))]
    if cand.empty:
        cand = pool[pool["livello"] <= livello_max]
    if cand.empty:
        cand = pool
    righe = cand.to_dict("records")
    rnd.shuffle(righe)
    return righe[:n]


def genera_programma(coach_id, nome: str, data_inizio: date, settimane: int,
                     sedute_settimana: int, minuti_blocco: int,
                     attrezzatura: list, gruppi: list, analisi: pd.DataFrame,
                     sessione_base: str = "T0", obiettivo: str = "",
                     seme: int = 42) -> tuple[bool, str]:
    """
    Crea il programma in stato BOZZA con gruppi, sedute, correttivi e calendario.

    Nasce sempre come bozza: la pubblicazione e' un atto separato del
    direttore tecnico, perche' quel materiale esce con la sua firma.
    """
    try:
        cl = db.get_client()
        esercizi = filtra_disponibili(load_esercizi(), attrezzatura)
        if esercizi.empty:
            return False, ("Nessun esercizio compatibile con l'attrezzatura "
                           "selezionata. Aggiungere almeno elastici o palle mediche.")

        prog = cl.table("programmi").insert({
            "coach_id": coach_id, "nome": nome.strip(),
            "data_inizio": data_inizio.isoformat(), "settimane": int(settimane),
            "sedute_settimana": int(sedute_settimana),
            "minuti_blocco": int(minuti_blocco),
            "attrezzatura": attrezzatura, "sessione_base": sessione_base,
            "obiettivo": obiettivo.strip() or None, "stato": "bozza",
        }).execute()
        pid = prog.data[0]["id"]

        # --- Gruppi e sedute ---
        for i, g in enumerate(gruppi, start=1):
            gr = cl.table("programma_gruppi").insert({
                "programma_id": pid, "nome": g["nome"],
                "focus_assi": g["focus_assi"], "descrizione": g["descrizione"],
                "atleti_ids": g["atleti_ids"], "ordine": i,
            }).execute()
            gid = gr.data[0]["id"]

            righe = _sedute_gruppo(esercizi, g, settimane, sedute_settimana,
                                   minuti_blocco, pid, gid, seme + i)
            for blocco in [righe[k:k + 100] for k in range(0, len(righe), 100)]:
                if blocco:
                    cl.table("programma_sedute").insert(blocco).execute()

        # --- Correttivi individuali ---
        correttivi = _correttivi(esercizi, analisi, pid)
        if correttivi:
            cl.table("programma_correttivi").insert(correttivi).execute()

        # --- Calendario dei controlli ---
        piano = pianifica_test(data_inizio, settimane, sedute_settimana)
        cl.table("test_pianificati").insert([{
            "programma_id": pid, "data_prevista": p["data_prevista"].isoformat(),
            "settimana": p["settimana"], "etichetta": p["etichetta"],
            "test_da_fare": p["test_da_fare"], "motivo": p["motivo"],
        } for p in piano]).execute()

        invalidate_programmi()
        return True, str(pid)
    except Exception as e:
        return False, str(e)


def _sedute_gruppo(esercizi, gruppo, settimane, sedute_settimana,
                   minuti_blocco, pid, gid, seme) -> list:
    """Costruisce tutte le sedute di un gruppo per l'intero programma."""
    rnd = random.Random(seme)
    focus = gruppo["focus_assi"]
    righe = []

    for sett in range(1, settimane + 1):
        pos = ((sett - 1) % SETTIMANE_MESOCICLO) + 1
        carico = CARICO_SETTIMANA.get(pos, 1.0)
        livello_max = 1 if sett <= 2 else (2 if sett <= 6 else 3)

        for sed in range(1, sedute_settimana + 1):
            usati = set()
            con_palla = (sed == 1)  # la prima seduta integra il lavoro con palla

            for blocco, quota, n_es, categorie in STRUTTURA_BLOCCO:
                minuti = minuti_blocco * quota

                if blocco == "centrale":
                    pool = esercizi[
                        (esercizi["asse_primario"].isin(focus))
                        & (esercizi["categoria"].isin(categorie))]
                    if con_palla:
                        conp = pool[pool["con_palla"] == True]  # noqa: E712
                        if not conp.empty:
                            usati.add(conp.iloc[0]["codice"])
                            righe.append(_riga(pid, gid, sett, sed, blocco, 1,
                                               conp.iloc[0], carico))
                            n_es -= 1
                else:
                    pool = esercizi[esercizi["categoria"].isin(categorie)]

                if pool.empty:
                    pool = esercizi

                scelti = _scegli(pool, max(0, n_es), rnd, usati, livello_max)
                for k, e in enumerate(scelti, start=len(righe) % 100 + 1):
                    usati.add(e["codice"])
                    righe.append(_riga(pid, gid, sett, sed, blocco,
                                       len([r for r in righe
                                            if r["settimana"] == sett
                                            and r["seduta"] == sed
                                            and r["blocco"] == blocco]) + 1,
                                       e, carico))
    return righe


def _riga(pid, gid, sett, sed, blocco, ordine, es, carico) -> dict:
    serie = max(2, int(round(int(es.get("serie_default") or 3) * carico)))
    return {
        "programma_id": pid, "gruppo_id": gid, "settimana": sett, "seduta": sed,
        "blocco": blocco, "ordine": ordine, "esercizio_id": int(es["id"]),
        "serie": serie, "ripetizioni": str(es.get("rip_default") or "8"),
        "recupero_sec": int(es.get("recupero_sec") or 60),
        "nota": None,
    }


def _correttivi(esercizi, analisi, pid) -> list:
    """
    Assegna il lavoro individuale a chi ha marcatori di rischio.

    Va a casa, non in seduta: in palestra con quindici persone non c'e' tempo,
    a casa costa cinque minuti al giorno ed e' li' che la caviglia si guadagna.
    """
    if analisi.empty:
        return []
    out = []
    mob = esercizi[esercizi["codice"].isin(["MOB01", "MOB02", "MOB03", "COR03"])]
    equil = esercizi[esercizi["codice"].isin(["COR01", "COR02"])]

    for _, r in analisi.iterrows():
        if r.get("flag_mob"):
            for _, e in mob.head(2).iterrows():
                out.append({
                    "programma_id": pid, "atleta_id": r["atleta_id"],
                    "esercizio_id": int(e["id"]),
                    "motivo": "Dorsiflessione di caviglia sotto i 9 cm: fattore "
                              "di rischio per il ginocchio in atterraggio.",
                    "frequenza": "quotidiana", "serie": 3, "ripetizioni": "10",
                })
        if r.get("flag_mob_diff"):
            for _, e in mob.tail(1).iterrows():
                out.append({
                    "programma_id": pid, "atleta_id": r["atleta_id"],
                    "esercizio_id": int(e["id"]),
                    "motivo": "Differenza fra le caviglie oltre 1.5 cm: lavoro "
                              "mirato sul lato più limitato.",
                    "frequenza": "quotidiana", "serie": 3, "ripetizioni": "12",
                })
        if r.get("flag_asi"):
            for _, e in equil.iterrows():
                out.append({
                    "programma_id": pid, "atleta_id": r["atleta_id"],
                    "esercizio_id": int(e["id"]),
                    "motivo": "Asimmetria fra gli arti inferiori oltre il 10%: "
                              "lavoro unilaterale di riequilibrio.",
                    "frequenza": "tre volte a settimana", "serie": 3,
                    "ripetizioni": "10 per lato",
                })
    return out


# ==============================================================================
# 6. LETTURE E STATO
# ==============================================================================

def invalidate_programmi():
    load_programmi.clear()


@st.cache_data(ttl=120, show_spinner=False)
def load_programmi(coach_id=None, solo_pubblicati: bool = False) -> pd.DataFrame:
    tabella = "v_programmi_pubblicati" if solo_pubblicati else "programmi"
    q = db.get_client().table(tabella).select("*")
    if coach_id is not None:
        q = q.eq("coach_id", coach_id)
    df = pd.DataFrame(q.order("data_inizio", desc=True).execute().data or [])
    if not df.empty and "data_inizio" in df.columns:
        df["data_inizio"] = pd.to_datetime(df["data_inizio"], errors="coerce")
    return df


def load_dettaglio(programma_id: int) -> dict:
    """Gruppi, sedute, correttivi e calendario di un programma."""
    cl = db.get_client()
    gruppi = pd.DataFrame(
        cl.table("programma_gruppi").select("*")
        .eq("programma_id", programma_id).order("ordine").execute().data or [])
    sedute = pd.DataFrame(
        cl.table("programma_sedute").select("*")
        .eq("programma_id", programma_id).execute().data or [])
    correttivi = pd.DataFrame(
        cl.table("programma_correttivi").select("*")
        .eq("programma_id", programma_id).execute().data or [])
    piano = pd.DataFrame(
        cl.table("test_pianificati").select("*")
        .eq("programma_id", programma_id).order("settimana").execute().data or [])

    es = load_esercizi()
    if not sedute.empty and not es.empty:
        sedute = sedute.merge(
            es[["id", "codice", "nome", "categoria", "setup", "esecuzione",
                "focus", "errori_comuni", "asse_primario", "unilaterale"]],
            left_on="esercizio_id", right_on="id", how="left",
            suffixes=("", "_es"))
        sedute = sedute.sort_values(["settimana", "seduta", "blocco", "ordine"])
    if not correttivi.empty and not es.empty:
        correttivi = correttivi.merge(
            es[["id", "codice", "nome", "setup", "esecuzione", "focus"]],
            left_on="esercizio_id", right_on="id", how="left",
            suffixes=("", "_es"))

    return {"gruppi": gruppi, "sedute": sedute,
            "correttivi": correttivi, "piano": piano}


def pubblica(programma_id: int, pubblica_si: bool = True) -> bool:
    try:
        campi = {"stato": "pubblicato" if pubblica_si else "bozza"}
        if pubblica_si:
            campi["pubblicato_il"] = pd.Timestamp.utcnow().isoformat()
        db.get_client().table("programmi").update(campi) \
            .eq("id", programma_id).execute()
        invalidate_programmi()
        return True
    except Exception:
        return False


def archivia(programma_id: int) -> bool:
    try:
        db.get_client().table("programmi").update({"stato": "archiviato"}) \
            .eq("id", programma_id).execute()
        invalidate_programmi()
        return True
    except Exception:
        return False


def elimina(programma_id: int) -> bool:
    try:
        db.get_client().table("programmi").delete().eq("id", programma_id).execute()
        invalidate_programmi()
        return True
    except Exception:
        return False


# ==============================================================================
# 7. SCHEDA STAMPABILE
# ==============================================================================

BLOCCO_LABEL = {"attivazione": "Attivazione", "centrale": "Blocco centrale",
                "chiusura": "Chiusura", "correttivo": "Correttivo"}


def genera_scheda_html(programma: dict, dettaglio: dict, settimana: int,
                       atleti: pd.DataFrame, logo_b64: str = "") -> str:
    """Scheda di una settimana, un blocco per gruppo, pronta da stampare."""
    gruppi, sedute = dettaglio["gruppi"], dettaglio["sedute"]
    nomi = {r["id"]: f"{r['cognome']} {r['nome']}" for _, r in atleti.iterrows()} \
        if not atleti.empty else {}

    pos = ((settimana - 1) % SETTIMANE_MESOCICLO) + 1
    fase = ETICHETTA_SETTIMANA.get(pos, "")
    logo = f'<img src="{logo_b64}" class="logo-soc">' if logo_b64 else ""

    corpo = ""
    for _, g in gruppi.iterrows():
        elenco = ", ".join(nomi.get(a, a) for a in (g["atleti_ids"] or []))
        sg = sedute[(sedute["gruppo_id"] == g["id"])
                    & (sedute["settimana"] == settimana)] \
            if not sedute.empty else pd.DataFrame()

        sedute_html = ""
        for sed in sorted(sg["seduta"].unique()) if not sg.empty else []:
            ss = sg[sg["seduta"] == sed]
            righe = ""
            for blocco in ["attivazione", "centrale", "chiusura"]:
                bb = ss[ss["blocco"] == blocco]
                if bb.empty:
                    continue
                righe += (f'<tr class="sep"><td colspan="5">'
                          f'{BLOCCO_LABEL[blocco]}</td></tr>')
                for _, e in bb.iterrows():
                    righe += (
                        f'<tr><td class="cod">{e.get("codice","")}</td>'
                        f'<td class="es"><b>{e.get("nome","")}</b><br>'
                        f'<span class="det">{e.get("focus","")}</span></td>'
                        f'<td class="c">{e.get("serie","")}</td>'
                        f'<td class="c">{e.get("ripetizioni","")}</td>'
                        f'<td class="c">{e.get("recupero_sec","")}"</td></tr>')
            sedute_html += (
                f'<div class="seduta"><div class="seduta-tit">Seduta {sed}</div>'
                f'<table><thead><tr><th class="cod">Cod</th><th class="es">Esercizio</th>'
                f'<th class="c">Serie</th><th class="c">Rip</th>'
                f'<th class="c">Rec</th></tr></thead><tbody>{righe}</tbody>'
                f'</table></div>')

        corpo += (f'<section class="gruppo"><div class="gruppo-tit">{g["nome"]}</div>'
                  f'<div class="gruppo-desc">{g.get("descrizione","")}</div>'
                  f'<div class="gruppo-atl"><b>Atleti:</b> {elenco or "—"}</div>'
                  f'{sedute_html}</section>')

    return f"""<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">
<title>AREA199 — Scheda settimana {settimana}</title><style>
@page {{ size: A4; margin: 12mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: Arial, Helvetica, sans-serif; color:#111; font-size:11px;
        margin:0; background:#fff; }}
.testata {{ display:flex; justify-content:space-between; align-items:center;
   border-bottom:3px solid #C9A227; padding-bottom:9px; margin-bottom:14px; gap:16px; }}
.marchio {{ font-size:21px; font-weight:bold; letter-spacing:2px; white-space:nowrap; }}
.marchio small {{ display:block; font-size:8.5px; font-weight:normal;
   letter-spacing:2.4px; color:#666; margin-top:3px; }}
.logo-soc {{ max-height:58px; max-width:150px; object-fit:contain; }}
.dati {{ text-align:right; font-size:11px; line-height:1.7; }}
.dati b {{ font-size:13px; }}
.fase {{ background:#FAF6E8; border-left:3px solid #C9A227; padding:8px 11px;
   margin-bottom:14px; font-size:10.5px; line-height:1.5; }}
.gruppo {{ margin-bottom:22px; page-break-inside:avoid; }}
.gruppo-tit {{ background:#111; color:#fff; padding:5px 10px; font-size:13px;
   font-weight:bold; text-transform:uppercase; letter-spacing:0.6px; }}
.gruppo-desc {{ font-size:10px; color:#333; padding:6px 2px 3px; line-height:1.45; }}
.gruppo-atl {{ font-size:10px; color:#333; padding-bottom:7px; }}
.seduta {{ margin-bottom:11px; page-break-inside:avoid; }}
.seduta-tit {{ font-size:11px; font-weight:bold; text-transform:uppercase;
   border-bottom:1px solid #999; padding-bottom:2px; margin-bottom:4px; }}
table {{ width:100%; border-collapse:collapse; }}
th {{ background:#F2F2F2; border:1px solid #999; padding:4px 3px; font-size:9px;
   text-transform:uppercase; }}
td {{ border:1px solid #BBB; padding:4px 6px; vertical-align:top; }}
td.cod, th.cod {{ width:42px; text-align:center; font-size:9px; color:#555; }}
td.c, th.c {{ width:48px; text-align:center; }}
td.es {{ font-size:11px; }}
.det {{ font-size:9px; color:#555; line-height:1.35; }}
tr.sep td {{ background:#EDEDED; font-size:9px; font-weight:bold;
   text-transform:uppercase; letter-spacing:0.8px; padding:3px 6px; }}
.pie {{ margin-top:18px; text-align:center; font-size:8px; color:#777;
   letter-spacing:1px; text-transform:uppercase; border-top:1px solid #DDD;
   padding-top:7px; }}
.stampa {{ position:fixed; top:14px; right:14px; background:#C9A227; color:#111;
   border:none; padding:11px 22px; font-weight:bold; font-size:13px;
   border-radius:4px; cursor:pointer; z-index:99; }}
@media print {{ .stampa {{ display:none; }} }}
</style></head><body>
<button class="stampa" onclick="window.print()">STAMPA</button>
<div class="testata">
  <div class="marchio">AREA199<small>HUMAN PERFORMANCE LAB</small></div>
  {logo}
  <div class="dati"><b>{programma.get('nome','Programma')}</b><br>
  Settimana {settimana} di {programma.get('settimane','')} · {fase}<br>
  {programma.get('sedute_settimana','')} sedute · {programma.get('minuti_blocco','')} minuti</div>
</div>
<div class="fase">
  <b>Settimana di {fase.lower()}.</b>
  {'Volume ridotto: e'' la settimana in cui l''adattamento si esprime. Non aggiungere lavoro.' if pos == 4 else 'Rispettare i recuperi indicati: sono parte dell''esercizio, non una pausa.'}
  La qualita'' di esecuzione viene prima del numero di ripetizioni: se la tecnica
  degrada, si interrompe la serie.
</div>
{corpo}
<div class="pie">AREA199 — Human Performance Lab · Dott. Antonio Petruzzi ·
Programmazione riservata alla squadra indicata</div>
</body></html>"""
