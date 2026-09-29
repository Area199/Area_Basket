"""
================================================================================
AREA199 HUMAN PERFORMANCE LAB — PRESENZE E NOTE SUI GIOCATORI
================================================================================
Il coach segna a ogni allenamento chi c'e' e scrive appunti sui giocatori;
il direttore tecnico legge tutto dalla propria vista, squadra per squadra.

FOGLIO PRESENZE
---------------
Un foglio per squadra e per giorno. Riaprire lo stesso giorno significa
correggerlo, non crearne un secondo: il vincolo sta nel database
(migrazione 016, unique coach_id + data).

Tre scelte per atleta: Presente, In ritardo, Assente.
Il ritardo NON e' un terzo stato nel database: chi arriva tardi e' presente,
con l'ora d'ingresso registrata, e conta come presenza nei conteggi. E' il
caso dell'assenza commutata in presenza: si passa da Assente a In ritardo e
si scrive l'ora. Per l'assenza si puo' annotare il motivo.

Un foglio nuovo parte con tutti presenti: si tocca solo chi manca.

NOTE SUI GIOCATORI
------------------
Merito, demerito o nota neutra, con data. Se quel giorno esiste un foglio
presenze la nota vi viene collegata da sola. Il coach puo' eliminare solo
le note che ha scritto lui; il direttore tecnico tutte.

RIEPILOGO
---------
Per periodo: presenze, ritardi, assenze, percentuale e conteggio delle note
per atleta, piu' la griglia atleta per giorno.

Richiede la migrazione 016. Senza, la pagina lo dice e non si rompe.

Versione 1.0 — Settembre 2026
================================================================================
"""

import html as _html
import re
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

import db_basket as db

ORO = "#C9A227"
VERDE = "#2FBF71"
ROSSO = "#E03131"
TESTO = "#E8E8EE"
TESTO_2 = "#B4B4C0"

PRESENTE = "Presente"
RITARDO = "In ritardo"
ASSENTE = "Assente"
SCELTE = [PRESENTE, RITARDO, ASSENTE]

TIPI_NOTA = {"merito": "Merito", "demerito": "Demerito", "nota": "Nota"}
COLORE_NOTA = {"merito": VERDE, "demerito": ROSSO, "nota": ORO}
AUTORI = {"coach": "Coach", "direttore": "AREA199"}

MSG_MIGRAZIONE = ("Le tabelle delle presenze non esistono ancora nel database: "
                  "va eseguita la migrazione 016 nell'SQL Editor di Supabase.")


# ==============================================================================
# 1. UTILITA'
# ==============================================================================

def oggi() -> date:
    """Data italiana. Il server di Streamlit gira in UTC: dopo mezzanotte UTC
    ma prima di quella italiana date.today() darebbe il giorno sbagliato."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Rome")).date()
    except Exception:
        return date.today()


def leggi_ora(testo: str) -> str | None:
    """Accetta 19:25, 19.25, 19,25, 1925, 19 — restituisce 'HH:MM' o None."""
    s = (testo or "").strip().replace(".", ":").replace(",", ":").replace(" ", "")
    if not s:
        return None
    m = re.fullmatch(r"(\d{1,2})(?::?(\d{2}))?", s)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if h > 23 or mi > 59:
        return None
    return f"{h:02d}:{mi:02d}"


def _ora_breve(v) -> str:
    """'19:25:00' -> '19:25'. Vuoto per None e NaN."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v)[:5]


def _testo(v) -> str:
    """Stringa pulita: i campi vuoti arrivano come None o NaN, e NaN e' truthy."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _nome(a) -> str:
    return f"{a['cognome']} {a['nome']}"


def _tabelle_mancanti(e: Exception) -> bool:
    t = str(e).lower()
    return any(k in t for k in ("allenamenti", "presenze", "note_atleti")) and \
        any(k in t for k in ("does not exist", "not found", "42p01", "pgrst205",
                             "could not find"))


# ==============================================================================
# 2. DATI
# ==============================================================================

@st.cache_data(ttl=60, show_spinner=False)
def load_allenamenti(coach_id) -> pd.DataFrame:
    r = (db.get_client().table("allenamenti")
         .select("id,coach_id,data,note,aggiornato_il")
         .eq("coach_id", coach_id).order("data", desc=True).execute())
    return pd.DataFrame(r.data or [])


@st.cache_data(ttl=60, show_spinner=False)
def load_presenze(allenamento_ids: tuple) -> pd.DataFrame:
    if not allenamento_ids:
        return pd.DataFrame(columns=["allenamento_id", "atleta_id", "stato",
                                     "ora_ingresso", "motivo_assenza"])
    r = (db.get_client().table("presenze")
         .select("allenamento_id,atleta_id,stato,ora_ingresso,motivo_assenza")
         .in_("allenamento_id", list(allenamento_ids)).execute())
    df = pd.DataFrame(r.data or [])
    if df.empty:
        return pd.DataFrame(columns=["allenamento_id", "atleta_id", "stato",
                                     "ora_ingresso", "motivo_assenza"])
    return df


@st.cache_data(ttl=60, show_spinner=False)
def load_note(coach_id) -> pd.DataFrame:
    r = (db.get_client().table("note_atleti")
         .select("id,coach_id,atleta_id,allenamento_id,data,tipo,testo,autore,creato_il")
         .eq("coach_id", coach_id).order("data", desc=True)
         .order("creato_il", desc=True).execute())
    return pd.DataFrame(r.data or [])


def _pulisci_cache():
    load_allenamenti.clear()
    load_presenze.clear()
    load_note.clear()


def salva_foglio(coach_id, giorno: date, righe: list, note_seduta: str):
    """
    righe: [{"atleta_id", "stato", "ora_ingresso", "motivo_assenza"}]
    Prima la seduta (upsert su squadra + giorno), poi le presenze
    (upsert su seduta + atleta): salvare due volte lo stesso giorno aggiorna.
    """
    try:
        ora = datetime.utcnow().isoformat()
        cl = db.get_client()
        seduta = (cl.table("allenamenti")
                  .upsert({"coach_id": int(coach_id), "data": giorno.isoformat(),
                           "note": note_seduta.strip() or None,
                           "aggiornato_il": ora},
                          on_conflict="coach_id,data")
                  .execute().data or [])
        if not seduta:
            return False, "La seduta non e' stata registrata."
        sid = int(seduta[0]["id"])
        dati = [{"allenamento_id": sid, "atleta_id": r["atleta_id"],
                 "stato": r["stato"], "ora_ingresso": r["ora_ingresso"],
                 "motivo_assenza": r["motivo_assenza"], "aggiornato_il": ora}
                for r in righe]
        if dati:
            cl.table("presenze").upsert(
                dati, on_conflict="allenamento_id,atleta_id").execute()
        _pulisci_cache()
        return True, sid
    except Exception as e:
        if _tabelle_mancanti(e):
            return False, MSG_MIGRAZIONE
        return False, str(e)


def elimina_foglio(allenamento_id) -> bool:
    """Le presenze se ne vanno con la seduta; le note restano, scollegate."""
    try:
        db.get_client().table("allenamenti").delete() \
            .eq("id", int(allenamento_id)).execute()
        _pulisci_cache()
        return True
    except Exception:
        return False


def salva_nota(coach_id, atleta_id, giorno: date, tipo, testo, autore,
               allenamento_id=None):
    try:
        campi = {"coach_id": int(coach_id), "atleta_id": atleta_id,
                 "data": giorno.isoformat(), "tipo": tipo,
                 "testo": testo.strip(), "autore": autore}
        if allenamento_id is not None:
            campi["allenamento_id"] = int(allenamento_id)
        db.get_client().table("note_atleti").insert(campi).execute()
        load_note.clear()
        return True, "Nota salvata."
    except Exception as e:
        if _tabelle_mancanti(e):
            return False, MSG_MIGRAZIONE
        return False, str(e)


def elimina_nota(nota_id) -> bool:
    try:
        db.get_client().table("note_atleti").delete().eq("id", int(nota_id)).execute()
        load_note.clear()
        return True
    except Exception:
        return False


# ==============================================================================
# 3. FOGLIO PRESENZE
# ==============================================================================

def _scheda_foglio(coach_id, atleti: pd.DataFrame, sedute: pd.DataFrame, admin):
    st.session_state.setdefault("pres_giro", 0)
    giorno = st.date_input("Giorno dell'allenamento", value=oggi(),
                           format="DD/MM/YYYY", key="pres_giorno")

    esistente = None
    if not sedute.empty:
        m = sedute[pd.to_datetime(sedute["data"]).dt.date == giorno]
        if not m.empty:
            esistente = m.iloc[0]

    precedenti = {}
    if esistente is not None:
        pr = load_presenze((int(esistente["id"]),))
        precedenti = {r["atleta_id"]: r for _, r in pr.iterrows()}
        st.info("Il foglio di questo giorno è già stato salvato: stai "
                "correggendo quello, non ne crei un secondo.")
    else:
        st.caption("Foglio nuovo: tutti partono presenti, tocca solo chi manca. "
                   "Se un assente arriva dopo, passalo a «In ritardo» e scrivi "
                   "l'ora d'ingresso.")

    if atleti.empty:
        st.warning("Nessun atleta in rosa.")
        return

    # Il giro entra nelle chiavi: dopo un salvataggio o un'eliminazione i campi
    # ripartono da quanto sta nel database e non da quanto era a schermo.
    g = st.session_state["pres_giro"]
    base = f"pr_{g}_{giorno.isoformat()}"

    righe, errori = [], []
    conta = {PRESENTE: 0, RITARDO: 0, ASSENTE: 0}

    for _, a in atleti.iterrows():
        aid = a["id"]
        prec = precedenti.get(aid)
        if prec is None:
            iniziale, ora_i, motivo_i = PRESENTE, "", ""
        elif prec["stato"] == "assente":
            iniziale, ora_i, motivo_i = ASSENTE, "", _testo(prec.get("motivo_assenza"))
        elif _ora_breve(prec.get("ora_ingresso")):
            iniziale, ora_i, motivo_i = RITARDO, _ora_breve(prec["ora_ingresso"]), ""
        else:
            iniziale, ora_i, motivo_i = PRESENTE, "", ""

        etichetta = _nome(a) + (f" · {a['ruolo']}" if _testo(a.get("ruolo")) else "")
        scelta = st.segmented_control(etichetta, SCELTE, default=iniziale,
                                      key=f"{base}_{aid}_s")
        if scelta is None:
            # toccare due volte la stessa voce la deseleziona
            scelta = iniziale
            st.caption("Nessuna scelta: resta com'era.")

        ora_ing, motivo = None, None
        if scelta == RITARDO:
            testo_ora = st.text_input("Ora d'ingresso", value=ora_i,
                                      placeholder="es. 19:25",
                                      key=f"{base}_{aid}_o")
            ora_ing = leggi_ora(testo_ora)
            if ora_ing is None:
                errori.append(f"{_nome(a)}: ora d'ingresso mancante o non valida "
                              f"(scrivila come 19:25).")
        elif scelta == ASSENTE:
            motivo = st.text_input("Motivo (facoltativo)", value=motivo_i,
                                   placeholder="es. lavoro, fisioterapia, malato",
                                   key=f"{base}_{aid}_m").strip() or None

        conta[scelta] += 1
        righe.append({"atleta_id": aid,
                      "stato": "assente" if scelta == ASSENTE else "presente",
                      "ora_ingresso": ora_ing, "motivo_assenza": motivo})

    st.divider()
    note_seduta = st.text_area(
        "Note sulla seduta (facoltative)",
        value=_testo(esistente.get("note")) if esistente is not None else "",
        placeholder="es. palestra, orario, cosa è cambiato rispetto alla scheda",
        key=f"{base}_note", height=90)

    st.markdown(
        f'<div style="font-size:14px;color:{TESTO};margin:6px 0 10px">'
        f'<b style="color:{VERDE}">{conta[PRESENTE] + conta[RITARDO]} presenti</b>'
        f' (di cui {conta[RITARDO]} in ritardo) · '
        f'<b style="color:{ROSSO}">{conta[ASSENTE]} assenti</b></div>',
        unsafe_allow_html=True)

    if st.button("Salva il foglio presenze", type="primary",
                 use_container_width=True, key=f"{base}_salva"):
        if errori:
            for e in errori:
                st.error(e)
        else:
            ok, esito = salva_foglio(coach_id, giorno, righe, note_seduta)
            if ok:
                st.session_state["pres_flash"] = (
                    f"Foglio del {giorno.strftime('%d/%m/%Y')} salvato.")
                st.session_state["pres_giro"] += 1
                st.rerun()
            else:
                st.error(esito)

    if esistente is not None:
        with st.expander("Elimina il foglio di questo giorno"):
            st.caption("Cancella le presenze del giorno. Le note sui giocatori "
                       "restano, perdono solo il collegamento alla seduta.")
            conferma = st.checkbox("Confermo l'eliminazione", key=f"{base}_conf")
            if st.button("Elimina", disabled=not conferma, key=f"{base}_del"):
                if elimina_foglio(esistente["id"]):
                    st.session_state["pres_flash"] = "Foglio eliminato."
                    st.session_state["pres_giro"] += 1
                    st.rerun()
                else:
                    st.error("Eliminazione non riuscita.")


# ==============================================================================
# 4. NOTE SUI GIOCATORI
# ==============================================================================

def _scheda_note(coach_id, atleti: pd.DataFrame, sedute: pd.DataFrame, admin):
    if atleti.empty:
        st.warning("Nessun atleta in rosa.")
        return

    nomi = {r["id"]: _nome(r) for _, r in atleti.iterrows()}

    st.session_state.setdefault("nota_giro", 0)
    g = st.session_state["nota_giro"]

    st.subheader("Nuova nota")
    aid = st.selectbox("Giocatore", list(nomi.keys()),
                       format_func=lambda k: nomi[k], key=f"nota_atl_{g}")
    tipo = st.segmented_control("Tipo", list(TIPI_NOTA.keys()), default="merito",
                                format_func=lambda k: TIPI_NOTA[k],
                                key=f"nota_tipo_{g}") or "nota"
    giorno = st.date_input("Giorno", value=oggi(), format="DD/MM/YYYY",
                           key=f"nota_giorno_{g}")
    testo = st.text_area("Nota", key=f"nota_testo_{g}", height=110,
                         placeholder="Cosa è successo, in poche righe.")

    if st.button("Salva la nota", type="primary", use_container_width=True,
                 disabled=not testo.strip(), key=f"nota_salva_{g}"):
        sid = None
        if not sedute.empty:
            m = sedute[pd.to_datetime(sedute["data"]).dt.date == giorno]
            if not m.empty:
                sid = m.iloc[0]["id"]
        ok, msg = salva_nota(coach_id, aid, giorno, tipo, testo,
                             "direttore" if admin else "coach", sid)
        if ok:
            st.session_state["pres_flash"] = f"Nota su {nomi[aid]} salvata."
            st.session_state["nota_giro"] += 1
            st.rerun()
        else:
            st.error(msg)

    st.divider()
    st.subheader("Note registrate")
    note = load_note(coach_id)
    if note.empty:
        st.caption("Ancora nessuna nota.")
        return

    f1, f2 = st.columns(2)
    filtro_atl = f1.selectbox("Giocatore", ["__tutti__"] + list(nomi.keys()),
                              format_func=lambda k: "Tutti" if k == "__tutti__"
                              else nomi[k], key="nota_filtro_atl")
    filtro_tipo = f2.selectbox("Tipo", ["__tutti__"] + list(TIPI_NOTA.keys()),
                               format_func=lambda k: "Tutti" if k == "__tutti__"
                               else TIPI_NOTA[k], key="nota_filtro_tipo")
    vis = note
    if filtro_atl != "__tutti__":
        vis = vis[vis["atleta_id"] == filtro_atl]
    if filtro_tipo != "__tutti__":
        vis = vis[vis["tipo"] == filtro_tipo]
    if vis.empty:
        st.caption("Nessuna nota con questi filtri.")
        return

    for _, n in vis.iterrows():
        colore = COLORE_NOTA.get(n["tipo"], TESTO_2)
        quando = pd.to_datetime(n["data"]).strftime("%d/%m/%Y")
        chi = nomi.get(n["atleta_id"], n["atleta_id"])
        st.markdown(
            f'<div style="border-left:3px solid {colore};padding:6px 12px;'
            f'margin:8px 0 2px;background:rgba(255,255,255,0.03)">'
            f'<div style="font-size:12px;color:{TESTO_2}">'
            f'<b style="color:{colore}">{TIPI_NOTA.get(n["tipo"], n["tipo"]).upper()}'
            f'</b> · {_html.escape(chi)} · {quando} · '
            f'{AUTORI.get(n["autore"], n["autore"])}</div>'
            f'<div style="font-size:14px;color:{TESTO};margin-top:3px">'
            f'{_html.escape(_testo(n["testo"])).replace(chr(10), "<br>")}</div></div>',
            unsafe_allow_html=True)
        if admin or n["autore"] == "coach":
            if st.button("Elimina", key=f"nota_del_{n['id']}"):
                elimina_nota(n["id"])
                st.rerun()


# ==============================================================================
# 5. RIEPILOGO
# ==============================================================================

def _scheda_riepilogo(coach_id, atleti: pd.DataFrame, sedute: pd.DataFrame):
    if sedute.empty:
        st.caption("Nessun foglio presenze salvato.")
        return

    date_sedute = pd.to_datetime(sedute["data"]).dt.date
    c1, c2 = st.columns(2)
    dal = c1.date_input("Dal", value=min(date_sedute), format="DD/MM/YYYY",
                        key="riep_dal")
    al = c2.date_input("Al", value=max(max(date_sedute), oggi()),
                       format="DD/MM/YYYY", key="riep_al")

    nel = sedute[(date_sedute >= dal) & (date_sedute <= al)].copy()
    if nel.empty:
        st.caption("Nessun allenamento nel periodo scelto.")
        return
    nel["giorno"] = pd.to_datetime(nel["data"]).dt.date
    nel = nel.sort_values("giorno")
    pr = load_presenze(tuple(int(i) for i in nel["id"]))
    note = load_note(coach_id)
    if not note.empty:
        gn = pd.to_datetime(note["data"]).dt.date
        note = note[(gn >= dal) & (gn <= al)]

    giorno_di = dict(zip(nel["id"].astype(int), nel["giorno"]))
    st.caption(f"{len(nel)} allenamenti registrati nel periodo.")

    tot, griglia = [], []
    for _, a in atleti.iterrows():
        mie = pr[pr["atleta_id"] == a["id"]] if not pr.empty else pr
        pres = int((mie["stato"] == "presente").sum()) if not mie.empty else 0
        ass = int((mie["stato"] == "assente").sum()) if not mie.empty else 0
        rit = int(mie["ora_ingresso"].apply(lambda v: bool(_ora_breve(v))).sum()) \
            if not mie.empty else 0
        segnati = pres + ass
        mn = note[note["atleta_id"] == a["id"]] if not note.empty else note
        tot.append({
            "Atleta": _nome(a),
            "Presenze": pres,
            "di cui in ritardo": rit,
            "Assenze": ass,
            "% presenza": round(100 * pres / segnati) if segnati else None,
            "Meriti": int((mn["tipo"] == "merito").sum()) if not mn.empty else 0,
            "Demeriti": int((mn["tipo"] == "demerito").sum()) if not mn.empty else 0,
        })

        riga = {"Atleta": _nome(a)}
        for sid, gg in giorno_di.items():
            r = mie[mie["allenamento_id"] == sid] if not mie.empty else mie
            col = gg.strftime("%d/%m")
            if r.empty:
                riga[col] = ""
            elif r.iloc[0]["stato"] == "assente":
                riga[col] = "A"
            elif _ora_breve(r.iloc[0]["ora_ingresso"]):
                riga[col] = "R " + _ora_breve(r.iloc[0]["ora_ingresso"])
            else:
                riga[col] = "P"
        griglia.append(riga)

    st.subheader("Per atleta")
    st.dataframe(pd.DataFrame(tot), hide_index=True, use_container_width=True,
                 column_config={"% presenza": st.column_config.NumberColumn(
                     format="%d%%")})

    st.subheader("Allenamento per allenamento")
    st.caption("P presente · R ritardo con ora d'ingresso · A assente · "
               "vuoto: non segnato")
    st.dataframe(pd.DataFrame(griglia), hide_index=True, use_container_width=True)

    # motivi delle assenze e note di seduta, per chi legge dal direttore tecnico
    if not pr.empty:
        motivi = pr[(pr["stato"] == "assente")
                    & pr["motivo_assenza"].apply(lambda v: bool(_testo(v)))]
        if not motivi.empty:
            nomi = {r["id"]: _nome(r) for _, r in atleti.iterrows()}
            with st.expander(f"Motivi delle assenze ({len(motivi)})"):
                for _, m in motivi.sort_values("allenamento_id").iterrows():
                    gg = giorno_di.get(int(m["allenamento_id"]))
                    st.markdown(f"- {gg.strftime('%d/%m') if gg else ''} · "
                                f"**{nomi.get(m['atleta_id'], m['atleta_id'])}** — "
                                f"{_testo(m['motivo_assenza'])}")
    con_note = nel[nel["note"].apply(lambda v: bool(_testo(v)))]
    if not con_note.empty:
        with st.expander(f"Note sulle sedute ({len(con_note)})"):
            for _, s in con_note.iterrows():
                st.markdown(f"- {s['giorno'].strftime('%d/%m')} — {_testo(s['note'])}")


# ==============================================================================
# 6. PAGINA
# ==============================================================================

def pagina_presenze(coach_id, atleti: pd.DataFrame, admin: bool = False):
    st.title("Presenze e note")

    if coach_id is None:
        st.info("Seleziona una squadra specifica nella barra laterale: presenze "
                "e note sono tenute squadra per squadra.")
        return

    flash = st.session_state.pop("pres_flash", None)
    if flash:
        st.success(flash)

    try:
        sedute = load_allenamenti(coach_id)
    except Exception as e:
        if _tabelle_mancanti(e):
            st.error(MSG_MIGRAZIONE)
        else:
            st.error(f"Lettura non riuscita: {e}")
        return

    t1, t2, t3 = st.tabs(["Foglio presenze", "Note sui giocatori", "Riepilogo"])
    with t1:
        _scheda_foglio(coach_id, atleti, sedute, admin)
    with t2:
        _scheda_note(coach_id, atleti, sedute, admin)
    with t3:
        _scheda_riepilogo(coach_id, atleti, sedute)
