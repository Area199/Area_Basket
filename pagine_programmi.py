"""
================================================================================
AREA199 HUMAN PERFORMANCE LAB — PAGINE DI PROGRAMMAZIONE
================================================================================
Due schermate:

  pagina_programmazione   direttore tecnico: analizza, genera, rivede, pubblica
  pagina_schede           coach: consulta e stampa solo cio' che e' pubblicato

Il coach non vede le bozze. Non e' un filtro dell'interfaccia: interroga una
vista del database che le bozze non le contiene proprio.

Versione 1.0 — Agosto 2026
================================================================================
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

import db_basket as db
import motore_programmi as mp

ORO = "#C9A227"
GRIGIO = "#1A1A1E"
VERDE = "#2FBF71"
ROSSO = "#E03131"
TESTO = "#E8E8EE"
TESTO_2 = "#B4B4C0"
TESTO_3 = "#9A9AA6"

ATTREZZI = {
    "elastico": "Elastici (loop band e therabend)",
    "palla_medica": "Palle mediche",
    "tappetino": "Tappetini",
    "panca": "Panca o rialzo",
}


# ==============================================================================
# DIRETTORE TECNICO — PROGRAMMAZIONE
# ==============================================================================

def pagina_programmazione(atleti, norme, targets, coach_id, logo_b64=""):
    st.title("Programmazione")

    if coach_id is None:
        st.info("Seleziona una squadra specifica nella barra laterale "
                "per generare o rivedere un programma.")
        return

    t1, t2 = st.tabs(["Programmi esistenti", "Genera nuovo programma"])

    with t1:
        _elenco_programmi(coach_id, atleti, logo_b64)
    with t2:
        _genera(atleti, norme, targets, coach_id)


def _genera(atleti, norme, targets, coach_id):
    if atleti.empty:
        st.info("Serve una rosa caricata per generare un programma.")
        return

    st.markdown("**1 · Analisi della rosa**")
    sessione = st.selectbox("Sessione di test di riferimento",
                            ["T0", "T1", "T2", "T3"],
                            help="I gruppi nascono dai risultati di questa sessione.")

    analisi = mp.analizza_squadra(atleti, norme, targets, sessione)
    testati = int(analisi["testato"].sum())

    c = st.columns(4)
    with c[0]:
        st.metric("Atleti", len(analisi))
    with c[1]:
        st.metric("Con test", testati)
    with c[2]:
        st.metric("Caviglie rigide", int(analisi["flag_mob"].sum()))
    with c[3]:
        st.metric("Asimmetrie", int(analisi["flag_asi"].sum()
                                    + analisi["flag_mob_diff"].sum()))

    if testati == 0:
        st.warning("Nessun atleta testato in questa sessione: il programma "
                   "nascerebbe generico. Meglio inserire prima la batteria "
                   "di test.")

    with st.expander("Divari rispetto al target di ruolo"):
        vis = analisi[["nome", "ruolo", "deficit_primario"]
                      + [f"gap_{a}" for a in db.ASSI]].copy()
        vis.columns = ["Atleta", "Ruolo", "Lacuna principale"] + list(db.ASSI)
        st.dataframe(vis, use_container_width=True, hide_index=True)
        st.caption("Valori positivi = quanto manca al target del ruolo. "
                   "Il divario conta più del punteggio assoluto: un centro con "
                   "70 di agilità può essere in linea, un playmaker no.")

    st.divider()
    st.markdown("**2 · Vincoli operativi**")

    c1, c2, c3 = st.columns(3)
    data_inizio = c1.date_input("Data di inizio", date.today(), format="DD/MM/YYYY")
    settimane = c2.number_input("Settimane", 1, 24, 3, step=1,
        help="Sotto le 4 settimane il sistema pianifica una verifica parziale "
             "invece del test completo.")
    sedute = c3.number_input("Sedute a settimana", 1, 6, 3, step=1)

    c4, c5 = st.columns(2)
    minuti = c4.slider("Minuti di atletica per seduta", 10, 60, 25, step=5,
        help="Il tempo dedicato alla preparazione dentro l'allenamento.")
    if minuti < mp.MINUTI_BLOCCO_MINIMI:
        st.warning(
            f"Con {minuti} minuti il blocco di attivazione arriva a circa "
            f"{minuti*0.35:.0f} minuti. La dose documentata come efficace per la "
            "prevenzione neuromuscolare è di 10-15 minuti, due o tre volte a "
            "settimana, che richiede almeno 30 minuti di blocco. Sotto quella "
            "soglia il lavoro resta pienamente valido, ma l'effetto protettivo "
            "va sostenuto dai correttivi individuali quotidiani.")
    nome = c5.text_input("Nome del programma",
                         f"Preparazione {data_inizio.strftime('%B %Y')}")

    st.markdown("**Attrezzatura disponibile**")
    st.caption("Corpo libero, muro, campo, cinesini e cronometro sono sempre "
               "considerati disponibili.")
    scelte, cols = [], st.columns(4)
    for i, (chiave, etichetta) in enumerate(ATTREZZI.items()):
        if cols[i % 4].checkbox(etichetta, value=(chiave == "elastico"),
                                key=f"attr_{chiave}"):
            scelte.append(chiave)

    obiettivo = st.text_area("Obiettivo del blocco (opzionale)", height=70,
        placeholder="Es. arrivare alla prima giornata con la squadra in grado "
                    "di reggere tre partite in due settimane.")

    st.divider()
    st.markdown("**3 · Gruppi di lavoro proposti**")

    gruppi = mp.costruisci_gruppi(analisi)
    nomi = {r["atleta_id"]: r["nome"] for _, r in analisi.iterrows()}

    for g in gruppi:
        elenco = ", ".join(nomi.get(a, a) for a in g["atleti_ids"])
        st.markdown(
            f'<div style="background:{GRIGIO};border:1px solid #33333B;'
            f'border-left:3px solid {ORO};border-radius:6px;padding:14px 18px;'
            f'margin-bottom:10px">'
            f'<div style="color:{ORO};font-weight:700;font-size:14px">{g["nome"]}</div>'
            f'<div style="color:{TESTO_2};font-size:12.5px;margin:6px 0;'
            f'line-height:1.5">{g["descrizione"]}</div>'
            f'<div style="color:{TESTO_3};font-size:11.5px">{elenco}</div></div>',
            unsafe_allow_html=True)

    st.caption("Massimo tre gruppi: oltre, un allenatore da solo in palestra "
               "non riesce a seguirli e la qualità di esecuzione crolla.")

    st.markdown("**4 · Calendario dei controlli**")
    piano = mp.pianifica_test(data_inizio, int(settimane), int(sedute))
    for p in piano:
        sigle = " · ".join(db.META_TEST[t]["sigla"] for t in p["test_da_fare"])
        st.markdown(
            f'<div style="background:rgba(201,162,39,0.07);border-left:3px solid {ORO};'
            f'padding:11px 15px;margin-bottom:8px;font-size:12.5px;color:{TESTO};'
            f'line-height:1.5"><b>{p["etichetta"]} — settimana {p["settimana"]}, '
            f'{p["data_prevista"].strftime("%d/%m/%Y")}</b> · {sigle}<br>'
            f'<span style="color:{TESTO_2};font-size:11.5px">{p["motivo"]}</span></div>',
            unsafe_allow_html=True)

    st.divider()
    if st.button("Genera il programma in bozza", type="primary",
                 use_container_width=True):
        if not gruppi:
            st.error("Nessun gruppo costruibile.")
            return
        with st.spinner("Costruzione del programma..."):
            ok, res = mp.genera_programma(
                coach_id=coach_id, nome=nome, data_inizio=data_inizio,
                settimane=int(settimane), sedute_settimana=int(sedute),
                minuti_blocco=int(minuti), attrezzatura=scelte,
                gruppi=gruppi, analisi=analisi, sessione_base=sessione,
                obiettivo=obiettivo)
        if ok:
            st.success("Programma generato in bozza. Rivedilo nella scheda "
                       "«Programmi esistenti» e pubblicalo quando sei d'accordo.")
            st.rerun()
        else:
            st.error(f"Generazione non riuscita: {res}")


def _elenco_programmi(coach_id, atleti, logo_b64):
    progs = mp.load_programmi(coach_id)
    if progs.empty:
        st.info("Nessun programma per questa squadra. "
                "Creane uno dalla scheda accanto.")
        return

    et = {}
    for _, p in progs.iterrows():
        stato = {"bozza": "BOZZA", "pubblicato": "pubblicato",
                 "archiviato": "archiviato"}.get(p["stato"], p["stato"])
        et[f"{p['nome']} — {p['data_inizio'].strftime('%d/%m/%Y')} [{stato}]"] = p["id"]

    pid = et[st.selectbox("Programma", list(et.keys()))]
    prog = progs[progs["id"] == pid].iloc[0].to_dict()

    c = st.columns(4)
    with c[0]:
        st.metric("Stato", prog["stato"].capitalize())
    with c[1]:
        st.metric("Settimane", prog["settimane"])
    with c[2]:
        st.metric("Sedute/sett.", prog["sedute_settimana"])
    with c[3]:
        st.metric("Minuti", prog["minuti_blocco"])

    if prog["stato"] == "bozza":
        st.markdown(
            f'<div style="background:rgba(224,49,49,0.1);border-left:3px solid {ROSSO};'
            f'padding:11px 15px;font-size:12.5px;color:#FFB0B0">'
            f'<b>Bozza.</b> Il coach non la vede. Rivedi il contenuto e pubblica '
            f'quando sei d\'accordo: esce con la tua firma.</div>',
            unsafe_allow_html=True)

    dett = mp.load_dettaglio(int(pid))
    st.write("")
    _mostra_dettaglio(prog, dett, atleti, logo_b64, revisione=True)

    st.divider()
    g1, g2, g3 = st.columns(3)
    with g1:
        if prog["stato"] == "bozza":
            if st.button("Pubblica al coach", type="primary"):
                if mp.pubblica(int(pid), True):
                    st.success("Pubblicato. Ora è visibile nel gestionale del coach.")
                    st.rerun()
        elif prog["stato"] == "pubblicato":
            if st.button("Riporta in bozza"):
                if mp.pubblica(int(pid), False):
                    st.success("Ritirato. Non è più visibile al coach.")
                    st.rerun()
    with g2:
        if prog["stato"] == "pubblicato":
            if st.button("Archivia"):
                if mp.archivia(int(pid)):
                    st.rerun()
    with g3:
        with st.popover("Elimina"):
            st.caption("Elimina definitivamente il programma, le schede e i "
                       "correttivi. I dati dei test non vengono toccati.")
            if st.button("Confermo l'eliminazione"):
                if mp.elimina(int(pid)):
                    st.success("Programma eliminato.")
                    st.rerun()


# ==============================================================================
# COACH — SCHEDE DI LAVORO
# ==============================================================================

def pagina_schede(coach_id, atleti, logo_b64=""):
    st.title("Schede di lavoro")

    if coach_id is None:
        st.info("Seleziona una squadra nella barra laterale.")
        return

    progs = mp.load_programmi(coach_id, solo_pubblicati=True)
    if progs.empty:
        st.info("Nessuna scheda disponibile al momento. Le schede compaiono qui "
                "quando la programmazione viene rilasciata da AREA199.")
        return

    et = {f"{p['nome']} — dal {p['data_inizio'].strftime('%d/%m/%Y')}": p["id"]
          for _, p in progs.iterrows()}
    pid = et[st.selectbox("Programma", list(et.keys()))]
    prog = progs[progs["id"] == pid].iloc[0].to_dict()

    if prog.get("obiettivo"):
        st.markdown(
            f'<div style="background:rgba(201,162,39,0.08);border-left:3px solid {ORO};'
            f'padding:13px 16px;font-size:13px;color:{TESTO};line-height:1.55">'
            f'<b>OBIETTIVO DEL BLOCCO</b><br>{prog["obiettivo"]}</div>',
            unsafe_allow_html=True)
        st.write("")

    dett = mp.load_dettaglio(int(pid))
    _mostra_dettaglio(prog, dett, atleti, logo_b64, revisione=False)


# ==============================================================================
# VISTA CONDIVISA
# ==============================================================================

def _mostra_dettaglio(prog, dett, atleti, logo_b64, revisione=False):
    gruppi, sedute = dett["gruppi"], dett["sedute"]
    correttivi, piano = dett["correttivi"], dett["piano"]

    nomi = {r["id"]: f"{r['cognome']} {r['nome']}" for _, r in atleti.iterrows()} \
        if not atleti.empty else {}

    tabs = st.tabs(["Sedute", "Correttivi individuali", "Calendario test"])

    # ---------------- SEDUTE ----------------
    with tabs[0]:
        if sedute.empty:
            st.warning("Nessuna seduta generata.")
        else:
            settimane = sorted(sedute["settimana"].unique())
            sett = st.select_slider("Settimana", settimane,
                                    value=settimane[0]) if len(settimane) > 1 \
                else settimane[0]
            pos = ((int(sett) - 1) % mp.SETTIMANE_MESOCICLO) + 1
            fase = mp.ETICHETTA_SETTIMANA.get(pos, "")
            carico = mp.CARICO_SETTIMANA.get(pos, 1.0)

            colore = ORO if pos == 4 else VERDE
            testo_fase = (
                "Volume ridotto del 40%: è la settimana in cui l'adattamento si "
                "esprime. Non aggiungere lavoro, non recuperare sedute saltate."
                if pos == 4 else
                f"Volume al {int(carico*100)}% della base. Rispettare i recuperi "
                "indicati: sono parte dell'esercizio.")
            st.markdown(
                f'<div style="background:{GRIGIO};border-left:3px solid {colore};'
                f'padding:11px 15px;margin-bottom:14px;font-size:12.5px;'
                f'color:{TESTO};line-height:1.5"><b>Settimana {sett} — '
                f'{fase}.</b> {testo_fase}</div>', unsafe_allow_html=True)

            html = mp.genera_scheda_html(prog, dett, int(sett), atleti, logo_b64)
            st.download_button(
                f"Scarica la scheda della settimana {sett}", data=html,
                file_name=f"AREA199_scheda_sett{sett}.html", mime="text/html",
                use_container_width=True)
            st.caption("Si apre nel browser: in alto a destra c'è STAMPA.")
            st.write("")

            for _, g in gruppi.iterrows():
                elenco = ", ".join(nomi.get(a, a) for a in (g["atleti_ids"] or []))
                st.markdown(f"### {g['nome']}")
                st.caption(f"{g.get('descrizione','')}")
                st.caption(f"**Atleti:** {elenco or '—'}")

                sg = sedute[(sedute["gruppo_id"] == g["id"])
                            & (sedute["settimana"] == int(sett))]
                if sg.empty:
                    st.info("Nessuna seduta per questa settimana.")
                    continue

                sub = st.tabs([f"Seduta {int(s)}"
                               for s in sorted(sg["seduta"].unique())])
                for i, s in enumerate(sorted(sg["seduta"].unique())):
                    with sub[i]:
                        ss = sg[sg["seduta"] == s]
                        for blocco in ["attivazione", "centrale", "chiusura"]:
                            bb = ss[ss["blocco"] == blocco]
                            if bb.empty:
                                continue
                            st.markdown(
                                f'<div style="color:{ORO};font-size:11px;'
                                f'letter-spacing:1.8px;text-transform:uppercase;'
                                f'margin:12px 0 6px">'
                                f'{mp.BLOCCO_LABEL[blocco]}</div>',
                                unsafe_allow_html=True)
                            for _, e in bb.iterrows():
                                _riga_esercizio(e)
                st.write("")

    # ---------------- CORRETTIVI ----------------
    with tabs[1]:
        if correttivi.empty:
            st.success("Nessun correttivo individuale assegnato: nessun atleta "
                       "presenta marcatori di rischio oltre soglia.")
        else:
            st.caption("Lavoro individuale da svolgere a casa. In seduta "
                       "collettiva non c'è tempo; a casa costa cinque minuti "
                       "al giorno ed è lì che la mobilità si guadagna.")
            for aid in correttivi["atleta_id"].unique():
                sub = correttivi[correttivi["atleta_id"] == aid]
                with st.expander(f"{nomi.get(aid, aid)} — "
                                 f"{len(sub)} esercizi assegnati"):
                    st.markdown(
                        f'<div style="background:rgba(224,49,49,0.1);'
                        f'border-left:3px solid {ROSSO};padding:9px 13px;'
                        f'font-size:12px;color:#FFB0B0;margin-bottom:10px">'
                        f'{sub.iloc[0]["motivo"]}</div>', unsafe_allow_html=True)
                    for _, e in sub.iterrows():
                        st.markdown(f"**{e.get('nome','')}** · "
                                    f"{e['serie']} × {e['ripetizioni']} · "
                                    f"{e['frequenza']}")
                        st.caption(f"{e.get('setup','')} {e.get('esecuzione','')}")
                        st.caption(f"↳ {e.get('focus','')}")

    # ---------------- CALENDARIO ----------------
    with tabs[2]:
        if piano.empty:
            st.info("Nessun controllo pianificato.")
        else:
            for _, p in piano.iterrows():
                sigle = " · ".join(db.META_TEST[t]["sigla"]
                                   for t in (p["test_da_fare"] or [])
                                   if t in db.META_TEST)
                nomi_test = ", ".join(db.META_TEST[t]["label"]
                                      for t in (p["test_da_fare"] or [])
                                      if t in db.META_TEST)
                fatto = p.get("eseguito")
                colore = VERDE if fatto else ORO
                st.markdown(
                    f'<div style="background:{GRIGIO};border-left:3px solid {colore};'
                    f'padding:13px 16px;margin-bottom:10px;border-radius:4px">'
                    f'<div style="color:{colore};font-weight:700;font-size:13px">'
                    f'{p["etichetta"]} — settimana {p["settimana"]} · '
                    f'{pd.to_datetime(p["data_prevista"]).strftime("%d/%m/%Y")}'
                    f'{" (eseguito)" if fatto else ""}</div>'
                    f'<div style="color:{TESTO};font-size:12.5px;margin:5px 0">'
                    f'{sigle}</div>'
                    f'<div style="color:{TESTO_2};font-size:11.5px;line-height:1.5">'
                    f'{p.get("motivo","")}</div></div>', unsafe_allow_html=True)
            st.caption(f"Test da svolgere: {nomi_test}" if not piano.empty else "")


def _riga_esercizio(e):
    unil = " · per lato" if e.get("unilaterale") else ""
    st.markdown(
        f'<div style="background:{GRIGIO};border:1px solid #33333B;'
        f'border-radius:6px;padding:12px 16px;margin-bottom:8px">'
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:baseline;gap:12px">'
        f'<span style="color:{TESTO};font-weight:600;font-size:13.5px">'
        f'{e.get("nome","")}</span>'
        f'<span style="color:{ORO};font-size:13px;white-space:nowrap">'
        f'{e.get("serie","")} × {e.get("ripetizioni","")}{unil} · '
        f'rec {e.get("recupero_sec","")}"</span></div>'
        f'<div style="color:{TESTO_2};font-size:11.5px;margin-top:6px;'
        f'line-height:1.5"><b>Setup.</b> {e.get("setup","")}</div>'
        f'<div style="color:{TESTO_2};font-size:11.5px;margin-top:3px;'
        f'line-height:1.5"><b>Esecuzione.</b> {e.get("esecuzione","")}</div>'
        f'<div style="color:{ORO};font-size:11.5px;margin-top:5px;'
        f'line-height:1.5">↳ {e.get("focus","")}</div>'
        + (f'<div style="color:#D08A8A;font-size:11px;margin-top:4px">'
           f'Errore comune: {e.get("errori_comuni")}</div>'
           if e.get("errori_comuni") else "")
        + '</div>', unsafe_allow_html=True)
