"""
================================================================================
AREA199 BASKET LAB — APPLICAZIONE
================================================================================
File richiesti nella stessa cartella:
    db_basket.py      livello dati, punteggi, utenti e licenze
    foglio_campo.py   generatore del foglio stampabile

Versione 3.1 — Agosto 2026
Dott. Antonio Petruzzi — Senior Human Performance Specialist
================================================================================
"""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import db_basket as db
from foglio_campo import genera_foglio

try:
    import openai
except ImportError:
    openai = None


st.set_page_config(page_title="AREA199 | Basket Lab", page_icon="🏀",
                   layout="wide", initial_sidebar_state="expanded")

ORO = "#C9A227"
NERO = "#0D0D0F"
GRIGIO = "#1A1A1E"
VERDE = "#2FBF71"
ROSSO = "#E03131"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap');
.stApp {{ background: {NERO}; }}
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
h1, h2, h3 {{ font-family: 'Barlow Condensed', sans-serif !important;
              letter-spacing: 0.5px; text-transform: uppercase; }}
.stButton>button {{ background: {ORO}; color: {NERO}; border: none; font-weight: 700;
    border-radius: 4px; padding: 0.5rem 1.2rem; letter-spacing: 0.5px;
    text-transform: uppercase; font-size: 13px; }}
.stButton>button:hover {{ background: #E0B830; color: {NERO}; }}
.stDownloadButton>button {{ background: transparent; color: {ORO};
    border: 1px solid {ORO}; font-weight: 700; text-transform: uppercase;
    font-size: 13px; border-radius: 4px; }}

.a199-card {{ background: linear-gradient(160deg, {GRIGIO} 0%, #101014 100%);
    border: 1px solid rgba(201,162,39,0.35); border-radius: 10px;
    padding: 22px; position: relative; overflow: hidden; }}
.a199-card::before {{ content: ""; position:absolute; top:0; left:0; right:0;
    height:3px; background: linear-gradient(90deg,{ORO},rgba(201,162,39,0.1)); }}
.a199-head {{ display:flex; justify-content:space-between; align-items:flex-start;
    margin-bottom:18px; }}
.a199-nome {{ font-family:'Barlow Condensed',sans-serif; font-size:30px;
    font-weight:700; color:#fff; line-height:1; text-transform:uppercase; }}
.a199-meta {{ font-size:11px; color:#7A7A85; letter-spacing:1.5px;
    text-transform:uppercase; margin-top:5px; }}
.a199-ovr {{ text-align:center; min-width:78px; }}
.a199-ovr-val {{ font-family:'Barlow Condensed',sans-serif; font-size:52px;
    font-weight:700; color:{ORO}; line-height:0.85; }}
.a199-ovr-lbl {{ font-size:9px; color:#7A7A85; letter-spacing:2.5px; }}
.a199-riga {{ margin-bottom:13px; }}
.a199-riga-top {{ display:flex; justify-content:space-between;
    align-items:baseline; margin-bottom:5px; }}
.a199-sigla {{ font-size:11px; font-weight:700; color:#C8C8D0; letter-spacing:2px; }}
.a199-grezzo {{ font-size:11px; color:#6E6E78; }}
.a199-punteggio {{ font-family:'Barlow Condensed',sans-serif; font-size:19px;
    font-weight:700; color:#fff; margin-left:9px; }}
.a199-barra {{ height:7px; background:#26262C; border-radius:4px; position:relative; }}
.a199-fill {{ height:100%; border-radius:4px;
    background: linear-gradient(90deg,#8A6D14,{ORO}); }}
.a199-target {{ position:absolute; top:-3px; width:2px; height:13px;
    background:#fff; opacity:0.75; }}
.a199-vuoto {{ font-size:11px; color:#55555E; font-style:italic; }}
.a199-alert {{ background:rgba(224,49,49,0.1); border-left:3px solid {ROSSO};
    padding:9px 13px; margin-top:15px; font-size:12px; color:#FF9B9B; }}
.a199-nota {{ background:rgba(201,162,39,0.07); border-left:3px solid {ORO};
    padding:13px 16px; margin-top:15px; font-size:13px; color:#D8D8E0;
    line-height:1.55; }}
.a199-kpi {{ background:{GRIGIO}; border:1px solid #26262C; border-radius:8px;
    padding:15px 18px; text-align:center; }}
.a199-kpi-val {{ font-family:'Barlow Condensed',sans-serif; font-size:32px;
    font-weight:700; line-height:1; }}
.a199-kpi-lbl {{ font-size:10px; color:#7A7A85; letter-spacing:1.8px;
    text-transform:uppercase; margin-top:6px; }}

.a199-slot {{ background:{GRIGIO}; border:1px solid #26262C; border-radius:8px;
    padding:14px 18px; margin-bottom:16px; }}
.a199-slot-top {{ display:flex; justify-content:space-between; align-items:baseline;
    margin-bottom:9px; }}
.a199-slot-n {{ font-family:'Barlow Condensed',sans-serif; font-size:24px;
    font-weight:700; color:#fff; }}
.a199-slot-l {{ font-size:10px; color:#7A7A85; letter-spacing:1.8px;
    text-transform:uppercase; }}
.a199-slot-barra {{ height:9px; background:#26262C; border-radius:5px; overflow:hidden; }}
.a199-slot-fill {{ height:100%; border-radius:5px; }}

.a199-pin {{ background:#12240F; border:1px solid {VERDE}; border-radius:8px;
    padding:18px 22px; margin:14px 0; }}
.a199-pin-cod {{ font-family:'Barlow Condensed',sans-serif; font-size:40px;
    font-weight:700; color:{VERDE}; letter-spacing:9px; }}

.a199-foot {{ text-align:center; color:#4A4A52; font-size:10px; letter-spacing:1.5px;
    margin-top:45px; padding-top:18px; border-top:1px solid #1E1E24;
    text-transform:uppercase; }}
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# COMPONENTI
# ==============================================================================

def kpi(valore, etichetta, colore="#FFFFFF"):
    st.markdown(f'<div class="a199-kpi"><div class="a199-kpi-val" '
                f'style="color:{colore}">{valore}</div>'
                f'<div class="a199-kpi-lbl">{etichetta}</div></div>',
                unsafe_allow_html=True)


def barra_slot(info, titolo="Slot atleti della licenza"):
    if info["max"] is None:
        return
    usati, massimo = info["usati"], info["max"]
    pct = min(100, int(usati / massimo * 100)) if massimo else 0
    colore = ROSSO if info["pieno"] else (ORO if pct >= 80 else VERDE)
    st.markdown(
        f'<div class="a199-slot"><div class="a199-slot-top">'
        f'<span class="a199-slot-l">{titolo}</span>'
        f'<span class="a199-slot-n">{usati}<span style="font-size:15px;'
        f'color:#7A7A85"> / {massimo}</span></span></div>'
        f'<div class="a199-slot-barra"><div class="a199-slot-fill" '
        f'style="width:{pct}%;background:{colore}"></div></div></div>',
        unsafe_allow_html=True)


def render_scheda(atleta, punteggi, overall, grezzi, targets, asimmetria=None):
    nome = f"{atleta['nome']} {atleta['cognome']}"
    meta = (f"{atleta['ruolo']} · {atleta.get('anno_nascita','')} · "
            f"{atleta.get('altezza','—')} cm")
    righe = ""
    for asse, col in db.ASSI.items():
        p, tgt = punteggi.get(asse), targets.get(asse, 70)
        if p is None:
            righe += ('<div class="a199-riga"><div class="a199-riga-top">'
                      f'<span class="a199-sigla">{asse}</span>'
                      '<span class="a199-vuoto">non rilevato</span></div>'
                      '<div class="a199-barra"></div></div>')
        else:
            righe += (f'<div class="a199-riga"><div class="a199-riga-top">'
                      f'<span class="a199-sigla">{asse}</span><span>'
                      f'<span class="a199-grezzo">'
                      f'{db.formatta_valore(col, grezzi.get(col))}</span>'
                      f'<span class="a199-punteggio">{p}</span></span></div>'
                      f'<div class="a199-barra"><div class="a199-fill" '
                      f'style="width:{p}%"></div><div class="a199-target" '
                      f'style="left:{tgt}%"></div></div></div>')
    alert = ""
    if asimmetria is not None and db.flag_asimmetria(asimmetria):
        alert = (f'<div class="a199-alert"><b>ASIMMETRIA {float(asimmetria):.1f}%</b>'
                 ' — oltre la soglia del 10%. '
                 'Previsto lavoro correttivo unilaterale.</div>')
    st.markdown(f'<div class="a199-card"><div class="a199-head"><div>'
                f'<div class="a199-nome">{nome}</div>'
                f'<div class="a199-meta">{meta}</div></div>'
                f'<div class="a199-ovr"><div class="a199-ovr-val">'
                f'{overall if overall is not None else "—"}</div>'
                f'<div class="a199-ovr-lbl">OVERALL</div></div></div>'
                f'{righe}{alert}</div>', unsafe_allow_html=True)


def render_radar(punteggi, targets, titolo="Profilo vs target di ruolo"):
    assi = list(db.ASSI.keys())
    vals = [punteggi.get(a) or 0 for a in assi]
    tgts = [targets.get(a, 70) for a in assi]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=tgts + [tgts[0]], theta=assi + [assi[0]],
        fill="toself", name="Target ruolo",
        line=dict(color="#5A5A64", width=1.5, dash="dot"),
        fillcolor="rgba(90,90,100,0.13)"))
    fig.add_trace(go.Scatterpolar(r=vals + [vals[0]], theta=assi + [assi[0]],
        fill="toself", name="Attuale", line=dict(color=ORO, width=2.5),
        fillcolor="rgba(201,162,39,0.22)"))
    fig.update_layout(
        title=dict(text=titolo, font=dict(size=13, color="#9A9AA4")),
        polar=dict(bgcolor="rgba(0,0,0,0)", gridshape="linear",
            radialaxis=dict(visible=True, range=[0, 100], gridcolor="#26262C",
                            tickfont=dict(color="#55555E", size=9)),
            angularaxis=dict(gridcolor="#26262C",
                             tickfont=dict(color="#C8C8D0", size=12))),
        paper_bgcolor="rgba(0,0,0,0)", height=370,
        margin=dict(t=55, b=45, l=55, r=55),
        legend=dict(orientation="h", y=-0.10, x=0.5, xanchor="center",
                    font=dict(color="#9A9AA4", size=10)))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ==============================================================================
# LOGIN
# ==============================================================================

def schermata_login():
    _, c, _ = st.columns([1, 1.1, 1])
    with c:
        st.markdown(f"<div style='text-align:center;margin-top:52px'>"
                    f"<div style='font-family:Barlow Condensed;font-size:46px;"
                    f"font-weight:700;color:{ORO};letter-spacing:3px'>AREA199</div>"
                    f"<div style='color:#7A7A85;font-size:11px;letter-spacing:5px;"
                    f"margin-bottom:34px'>BASKET LAB</div></div>",
                    unsafe_allow_html=True)
        with st.form("login"):
            pin = st.text_input("Codice", type="password",
                                label_visibility="collapsed",
                                placeholder="Codice di accesso")
            if st.form_submit_button("Entra", use_container_width=True):
                esito = db.verifica_accesso(pin)
                if esito and esito.get("errore"):
                    st.error(esito["errore"])
                elif esito:
                    st.session_state["ruolo"] = esito["ruolo"]
                    st.session_state["utente_id"] = esito["utente_id"]
                    st.session_state["utente_nome"] = esito["nome"]
                    st.rerun()
                else:
                    st.error("Codice non riconosciuto.")
        st.markdown("<div style='text-align:center;color:#3A3A42;font-size:10px;"
                    "letter-spacing:2px;margin-top:26px'>ACCESSO RISERVATO</div>",
                    unsafe_allow_html=True)


# ==============================================================================
# PAGINA — AMMINISTRAZIONE (solo admin)
# ==============================================================================

def pagina_admin():
    st.title("Amministrazione")
    utenti = db.load_utenti()

    c = st.columns(4)
    with c[0]: kpi(len(utenti), "Coach registrati")
    with c[1]:
        att = int(utenti["attivo"].sum()) if not utenti.empty else 0
        kpi(att, "Licenze attive", VERDE)
    with c[2]:
        kpi(int(utenti["slot_max"].sum()) if not utenti.empty else 0, "Slot concessi")
    with c[3]:
        kpi(int(utenti["slot_usati"].sum()) if not utenti.empty else 0,
            "Slot occupati", ORO)

    # --- PIN appena generato ---
    if st.session_state.get("pin_nuovo"):
        p = st.session_state["pin_nuovo"]
        st.markdown(
            f'<div class="a199-pin"><div style="color:{VERDE};font-size:11px;'
            f'letter-spacing:2px;margin-bottom:7px">CODICE PER {p["nome"].upper()}</div>'
            f'<div class="a199-pin-cod">{p["pin"]}</div>'
            f'<div style="color:#8FBF8F;font-size:12px;margin-top:9px">'
            f'Comunicalo adesso. Non viene salvato in chiaro e non è più '
            f'recuperabile: se si perde, si rigenera.</div></div>',
            unsafe_allow_html=True)
        if st.button("Ho annotato il codice"):
            del st.session_state["pin_nuovo"]
            st.rerun()

    st.divider()

    t1, t2 = st.tabs(["Licenze attive", "Nuovo coach"])

    with t1:
        if utenti.empty:
            st.info("Nessun coach registrato. Creane uno dalla scheda accanto.")
        else:
            vis = utenti.copy()
            vis["Utilizzo"] = vis.apply(
                lambda r: f"{r['slot_usati']}/{r['slot_max']}", axis=1)
            vis["Stato"] = vis["attivo"].map({True: "Attiva", False: "Sospesa"})
            st.dataframe(
                vis[["nome", "organizzazione", "Utilizzo", "Stato", "scadenza",
                     "ultimo_accesso"]],
                use_container_width=True, hide_index=True,
                column_config={"nome": "Coach", "organizzazione": "Società",
                               "scadenza": "Scadenza",
                               "ultimo_accesso": "Ultimo accesso"})

            st.write("")
            et = {f"{r['nome']}"
                  + (f" — {r['organizzazione']}" if r["organizzazione"] else ""):
                  r["coach_id"] for _, r in utenti.iterrows()}
            scelto = st.selectbox("Gestisci licenza", list(et.keys()))
            uid = et[scelto]
            riga = utenti[utenti["coach_id"] == uid].iloc[0]

            barra_slot({"usati": int(riga["slot_usati"]), "max": int(riga["slot_max"]),
                        "liberi": int(riga["slot_liberi"]),
                        "pieno": riga["slot_usati"] >= riga["slot_max"]},
                       f"Slot di {riga['nome']}")

            g1, g2, g3 = st.columns(3)
            with g1:
                nuovi = st.number_input("Slot concessi", 1, 200,
                                        int(riga["slot_max"]), step=1)
                if st.button("Aggiorna slot"):
                    if nuovi < int(riga["slot_usati"]):
                        st.error(f"Non si può scendere sotto i "
                                 f"{int(riga['slot_usati'])} slot già occupati. "
                                 "Rimuovere prima degli atleti.")
                    elif db.aggiorna_licenza(uid, slot_max=nuovi):
                        st.success("Slot aggiornati.")
                        st.rerun()
                    else:
                        st.error("Aggiornamento non riuscito.")
            with g2:
                st.write("")
                st.write("")
                if st.button("Rigenera codice"):
                    ok, res = db.rigenera_pin(uid)
                    if ok:
                        st.session_state["pin_nuovo"] = {"nome": riga["nome"],
                                                         "pin": res}
                        st.rerun()
                    else:
                        st.error(res)
                st.caption("Il codice precedente smette subito di funzionare.")
            with g3:
                st.write("")
                st.write("")
                if riga["attivo"]:
                    if st.button("Sospendi licenza"):
                        db.aggiorna_licenza(uid, attivo=False)
                        st.rerun()
                else:
                    if st.button("Riattiva licenza"):
                        db.aggiorna_licenza(uid, attivo=True)
                        st.rerun()

    with t2:
        with st.form("nuovo_coach", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome e cognome")
            org = c2.text_input("Società o squadra",
                                help="Comparirà come squadra predefinita quando "
                                     "questo coach inserisce i suoi atleti.")
            c3, c4 = st.columns(2)
            slot = c3.number_input("Slot atleti", 1, 200, db.SLOT_DEFAULT, step=1,
                                   help="Numero massimo di atleti che potrà "
                                        "avere in rosa contemporaneamente.")
            usa_scad = c4.checkbox("Imposta una scadenza")
            scad = st.date_input("Scadenza licenza",
                                 date.today() + timedelta(days=365),
                                 format="DD/MM/YYYY") if usa_scad else None
            note = st.text_area("Note interne", height=70)

            if st.form_submit_button("Crea coach e genera codice", type="primary"):
                if not nome.strip():
                    st.error("Il nome è obbligatorio.")
                else:
                    ok, msg, pin = db.crea_utente(nome, org, slot, scad, note)
                    if ok:
                        st.session_state["pin_nuovo"] = {"nome": nome, "pin": pin}
                        st.rerun()
                    else:
                        st.error(msg)


# ==============================================================================
# PAGINA — SESSIONE TEST
# ==============================================================================

def pagina_sessione(atleti):
    st.title("Sessione di test")
    if atleti.empty:
        st.info("Inserire prima la rosa nella sezione **Rosa**.")
        return

    c1, c2, _ = st.columns([1, 1, 2])
    data_test = c1.date_input("Data", date.today(), format="DD/MM/YYYY")
    sessione = c2.selectbox("Sessione", ["T0", "T1", "T2", "T3"],
        help="T0 baseline · T1 fine pre-season · T2 e oltre in season")

    st.markdown("**Test da somministrare**")
    scelti, cols = [], st.columns(3)
    for i, col_test in enumerate(db.ORDINE_TEST):
        m = db.META_TEST[col_test]
        if cols[i % 3].checkbox(f"{m['sigla']} — {m['label']}", key=f"chk_{col_test}"):
            scelti.append(col_test)

    if not scelti:
        st.info("Seleziona almeno un test per generare le griglie.")
        return

    ordinati = [c for c in db.ORDINE_TEST if c in scelti]
    st.caption("Ordine di esecuzione: **"
               + " → ".join(db.META_TEST[c]["sigla"] for c in ordinati)
               + "** — dal meno al più affaticante.")

    with st.expander("🖨️  Foglio di campo da stampare"):
        st.markdown("Da stampare **prima** della sessione. Sul campo si scrive a "
                    "penna, poi si trascrive qui con calma. Se l'app o la "
                    "connessione cadono durante i test, il dato è già al sicuro.")
        html = genera_foglio(atleti, ordinati, data_test, sessione,
                             squadra=str(atleti.iloc[0].get("squadra") or ""))
        st.download_button(
            "Scarica il foglio", data=html,
            file_name=f"AREA199_foglio_{sessione}_{data_test.strftime('%d-%m-%Y')}.html",
            mime="text/html", use_container_width=True)
        st.caption("Si apre nel browser: in alto a destra c'è il pulsante STAMPA.")

    st.divider()

    esistenti = db.load_test()
    if not esistenti.empty:
        esistenti = esistenti[(esistenti["data_test"].dt.date == data_test)
                              & (esistenti["sessione"] == sessione)]

    def gia_salvato(aid, col):
        if esistenti.empty:
            return None
        r = esistenti[esistenti["atleta_id"] == aid]
        if r.empty:
            return None
        v = r.iloc[0].get(col)
        return None if pd.isna(v) else v

    st.session_state.setdefault("griglie", {})

    for col_test in ordinati:
        m = db.META_TEST[col_test]
        st.markdown(f"### {m['sigla']} — {m['label']}")
        st.caption(f"{m['protocollo']} · {m['promemoria']}")

        if col_test == "asi_monopodalico":
            base = pd.DataFrame({
                "Atleta": [f"{r['cognome']} {r['nome']}" for _, r in atleti.iterrows()],
                "Ruolo": [r["ruolo"][:3].upper() for _, r in atleti.iterrows()],
                "Destra (cm)": [None] * len(atleti),
                "Sinistra (cm)": [None] * len(atleti)})
            cfg = {"Atleta": st.column_config.TextColumn(disabled=True, width="medium"),
                   "Ruolo": st.column_config.TextColumn(disabled=True, width="small"),
                   "Destra (cm)": st.column_config.NumberColumn(format="%.0f",
                       min_value=50, max_value=350),
                   "Sinistra (cm)": st.column_config.NumberColumn(format="%.0f",
                       min_value=50, max_value=350)}
        else:
            base = pd.DataFrame({
                "Atleta": [f"{r['cognome']} {r['nome']}" for _, r in atleti.iterrows()],
                "Ruolo": [r["ruolo"][:3].upper() for _, r in atleti.iterrows()],
                f"Risultato ({m['unita']})":
                    [gia_salvato(r["id"], col_test) for _, r in atleti.iterrows()]})
            fmt = "%d" if m["decimali"] == 0 else f"%.{m['decimali']}f"
            cfg = {"Atleta": st.column_config.TextColumn(disabled=True, width="medium"),
                   "Ruolo": st.column_config.TextColumn(disabled=True, width="small"),
                   f"Risultato ({m['unita']})": st.column_config.NumberColumn(
                       format=fmt, min_value=m["min"], max_value=m["max"],
                       step=m["step"], help="Si inserisce la prova migliore.")}

        st.session_state["griglie"][col_test] = st.data_editor(
            base, use_container_width=True, hide_index=True, num_rows="fixed",
            key=f"ed_{col_test}_{data_test}_{sessione}", column_config=cfg)
        st.write("")

    st.divider()
    if st.button("💾 Salva la sessione", type="primary", use_container_width=True):
        salva_sessione(atleti, ordinati, data_test, sessione)


def salva_sessione(atleti, test_scelti, data_test, sessione):
    ok, errori, vuoti = 0, [], 0
    barra = st.progress(0.0, "Salvataggio in corso...")

    for i, (_, a) in enumerate(atleti.iterrows()):
        misure = {}
        for col_test in test_scelti:
            griglia = st.session_state["griglie"].get(col_test)
            if griglia is None:
                continue
            riga = griglia.iloc[i]
            if col_test == "asi_monopodalico":
                asi = db.calcola_asimmetria(riga["Destra (cm)"], riga["Sinistra (cm)"])
                if asi is not None:
                    misure["asi_monopodalico"] = asi
            else:
                v = riga[f"Risultato ({db.META_TEST[col_test]['unita']})"]
                if v is not None and not pd.isna(v):
                    misure[col_test] = (int(v) if db.META_TEST[col_test]["decimali"] == 0
                                        else float(v))

        if not misure:
            vuoti += 1
            barra.progress((i + 1) / len(atleti))
            continue

        esito, msg = db.salva_misure(
            a["id"], data_test, sessione, misure,
            meta={"eta": db.eta_da_anno(a["anno_nascita"], data_test),
                  "peso": float(a["peso"]) if pd.notna(a.get("peso")) else None,
                  "altezza": int(a["altezza"]) if pd.notna(a.get("altezza")) else None})
        if esito:
            ok += 1
        else:
            errori.append(f"{a['cognome']}: {msg}")
        barra.progress((i + 1) / len(atleti))

    barra.empty()
    db.invalidate_cache()

    if ok:
        st.success(f"Salvati {ok} atleti."
                   + (f" {vuoti} righe vuote ignorate." if vuoti else ""))
        st.caption("I test salvati in precedenza per questa stessa sessione "
                   "non sono stati toccati.")
    if errori:
        st.error("Errori:\n" + "\n".join(f"- {e}" for e in errori))
    if not ok and not errori:
        st.warning("Nessun dato da salvare: le griglie sono vuote.")


# ==============================================================================
# PAGINA — ROSTER
# ==============================================================================

def pagina_roster(atleti, norme, info_slot):
    st.title("Roster squadra")
    barra_slot(info_slot)

    if atleti.empty:
        st.info("Nessun atleta in archivio.")
        return

    test = db.load_test()
    righe, senza = [], 0
    for _, a in atleti.iterrows():
        suoi = test[test["atleta_id"] == a["id"]] if not test.empty else pd.DataFrame()
        if suoi.empty:
            senza += 1
            righe.append({"Atleta": f"{a['cognome']} {a['nome']}", "Ruolo": a["ruolo"],
                          "Ultimo test": "—", "OVR": None,
                          **{k: None for k in db.ASSI}})
            continue
        u = suoi.iloc[0]
        p = db.calcola_tutti(u, a["ruolo"], norme)
        righe.append({"Atleta": f"{a['cognome']} {a['nome']}", "Ruolo": a["ruolo"],
                      "Ultimo test": u["data_test"].strftime("%d/%m/%y")
                                     if pd.notna(u["data_test"]) else "—",
                      "OVR": db.calcola_overall(p), **p})

    df = pd.DataFrame(righe).sort_values("OVR", ascending=False, na_position="last")

    c = st.columns(4)
    with c[0]: kpi(len(atleti), "Atleti in rosa")
    with c[1]: kpi(len(atleti) - senza, "Testati", VERDE if senza == 0 else ORO)
    with c[2]:
        m = df["OVR"].dropna()
        kpi(int(m.mean()) if len(m) else "—", "OVR medio")
    with c[3]:
        kpi(test["sessione"].nunique() if not test.empty else 0, "Sessioni")

    st.write("")
    st.dataframe(df, use_container_width=True, hide_index=True, column_config={
        "OVR": st.column_config.NumberColumn("OVR", format="%d", width="small"),
        **{k: st.column_config.ProgressColumn(k, min_value=0, max_value=99,
                                              format="%d") for k in db.ASSI}})
    if senza:
        st.warning(f"{senza} atleti senza sessioni registrate.")
    st.caption("ELE elevazione · ACC accelerazione · AGI agilità · "
               "RES resistenza · FOR forza")


# ==============================================================================
# PAGINA — SCHEDA ATLETA
# ==============================================================================

def pagina_atleta(atleti, norme, targets):
    st.title("Scheda atleta")
    if atleti.empty:
        st.info("Nessun atleta in archivio.")
        return

    et = {f"{r['cognome']} {r['nome']} ({r['ruolo']})": r["id"]
          for _, r in atleti.iterrows()}
    aid = et[st.selectbox("Atleta", list(et.keys()))]
    atleta = atleti[atleti["id"] == aid].iloc[0]
    suoi = db.load_test(aid)

    t1, t2, t3 = st.tabs(["Profilo", "Storico test", "Dati anagrafici"])

    with t1:
        if suoi.empty:
            st.warning("Nessuna sessione registrata per questo atleta.")
        else:
            opz = {f"{r['sessione']} — {r['data_test'].strftime('%d/%m/%Y')}": idx
                   for idx, r in suoi.iterrows() if pd.notna(r["data_test"])}
            riga = suoi.loc[opz[st.selectbox("Sessione", list(opz.keys()))]]
            p = db.calcola_tutti(riga, atleta["ruolo"], norme)
            tgt = targets.get(atleta["ruolo"], {k: 70 for k in db.ASSI})
            grezzi = {c: riga.get(c) for c in db.ASSI.values()}

            st.write("")
            ca, cb = st.columns(2)
            with ca:
                render_scheda(atleta, p, db.calcola_overall(p), grezzi, tgt,
                              riga.get("asi_monopodalico"))
            with cb:
                render_radar(p, tgt)

            if riga.get("note"):
                st.markdown(f'<div class="a199-nota"><b>NOTE DI CAMPO</b><br>'
                            f'{riga["note"]}</div>', unsafe_allow_html=True)
            if riga.get("ai_comment"):
                st.markdown(f'<div class="a199-nota"><b>LETTURA TECNICA</b><br>'
                            f'{riga["ai_comment"]}</div>', unsafe_allow_html=True)
            elif openai and db.puo("usa_ai"):
                if st.button("Genera lettura tecnica", key=f"ai_{aid}"):
                    genera_commento(atleta, p, db.calcola_overall(p), grezzi, riga)

    with t2:
        if suoi.empty:
            st.info("Nessun risultato da mostrare.")
        else:
            storico = suoi.sort_values("data_test")
            tab = pd.DataFrame({"Data": storico["data_test"].dt.strftime("%d/%m/%Y"),
                                "Sessione": storico["sessione"]})
            for asse, col in db.ASSI.items():
                tab[asse] = storico[col].apply(lambda v, c=col: db.formatta_valore(c, v))
            tab["ASI"] = storico["asi_monopodalico"].apply(
                lambda v: db.formatta_valore("asi_monopodalico", v))
            st.dataframe(tab, use_container_width=True, hide_index=True)

            if len(storico) > 1:
                st.subheader("Andamento dei punteggi")
                serie = []
                for _, r in storico.iterrows():
                    pp = db.calcola_tutti(r, atleta["ruolo"], norme)
                    serie.append({"Data": r["data_test"],
                                  "OVR": db.calcola_overall(pp), **pp})
                st.line_chart(pd.DataFrame(serie).set_index("Data"), height=280)

            if db.puo("elimina"):
                with st.expander("Eliminazione sessione"):
                    scelta = st.selectbox("Sessione da eliminare",
                        [f"{r['sessione']} — {r['data_test'].strftime('%d/%m/%Y')}"
                         f" [id {int(r['id'])}]" for _, r in storico.iterrows()])
                    if st.button("Elimina definitivamente"):
                        sid = int(scelta.split("[id ")[1].rstrip("]"))
                        if db.elimina_test(sid):
                            st.success("Sessione eliminata.")
                            st.rerun()
                        else:
                            st.error("Eliminazione non riuscita.")

    with t3:
        c = st.columns(3)
        c[0].metric("Ruolo", atleta["ruolo"])
        c[1].metric("Anno", int(atleta["anno_nascita"]))
        c[2].metric("Età", db.eta_da_anno(atleta["anno_nascita"]))
        c = st.columns(4)
        c[0].metric("Altezza", f"{atleta['altezza']} cm"
                    if pd.notna(atleta.get("altezza")) else "—")
        c[1].metric("Peso", f"{atleta['peso']:.1f} kg"
                    if pd.notna(atleta.get("peso")) else "—")
        c[2].metric("Standing reach", f"{atleta['reach']} cm"
                    if pd.notna(atleta.get("reach")) else "—")
        c[3].metric("Apertura", f"{atleta['apertura']} cm"
                    if pd.notna(atleta.get("apertura")) else "—")
        st.caption(f"Codice atleta: {atleta['id']} · "
                   f"Squadra: {atleta.get('squadra') or '—'} · "
                   f"Mano: {atleta.get('mano','—')}")
        if pd.isna(atleta.get("reach")):
            st.warning("Standing reach mancante: senza questo dato l'elevazione "
                       "non è misurabile correttamente.")


def genera_commento(atleta, punteggi, ovr, grezzi, riga):
    """
    Commento sui SOLI numeri rilevati. Il modello non prescrive esercizi:
    quella parte arrivera' dalla libreria proprietaria, per costruzione.
    """
    sistema = (
        "Sei un preparatore atletico esperto di pallacanestro che scrive una lettura "
        "tecnica per l'allenatore. Commenti ESCLUSIVAMENTE i punteggi forniti. "
        "Non prescrivi esercizi, non nomini attrezzi, non inventi dati assenti. "
        "Un valore indicato come 'non rilevato' non va commentato ne' stimato. "
        "Colleghi ogni deficit a una conseguenza concreta in partita per il ruolo. "
        "Tono asciutto e professionale. Massimo 130 parole, in italiano.")
    misure = "\n".join(
        f"- {a} ({db.META_TEST[c]['label']}): "
        f"{'non rilevato' if punteggi[a] is None else str(punteggi[a]) + '/99'}"
        f" — grezzo {db.formatta_valore(c, grezzi.get(c))}"
        for a, c in db.ASSI.items())
    asi = riga.get("asi_monopodalico")
    extra = (f"\nAsimmetria: {asi}% "
             f"({'OLTRE soglia 10%' if db.flag_asimmetria(asi) else 'nella norma'})"
             if pd.notna(asi) else "")

    with st.spinner("Elaborazione..."):
        try:
            chiave = (st.secrets.get("openai_key") or st.secrets.get("openai_api_key")
                      or st.secrets.get("OPENAI_API_KEY"))
            if not chiave:
                st.error("Chiave OpenAI non configurata.")
                return
            resp = openai.OpenAI(api_key=chiave).chat.completions.create(
                model="gpt-4o", temperature=0.3,
                messages=[{"role": "system", "content": sistema},
                          {"role": "user", "content":
                           f"Atleta: {atleta['nome']} {atleta['cognome']}\n"
                           f"Ruolo: {atleta['ruolo']}\nOverall: {ovr}\n\n{misure}{extra}"}])
            testo = resp.choices[0].message.content
            st.markdown(f'<div class="a199-nota">{testo}</div>', unsafe_allow_html=True)
            if pd.notna(riga.get("id")):
                db.salva_commento_ai(int(riga["id"]), testo)
        except Exception as e:
            st.error(f"Generazione non riuscita: {e}")


# ==============================================================================
# PAGINA — CONFRONTO
# ==============================================================================

def pagina_confronto(coach_id, tutte):
    st.title("Confronto T0 → T1")
    st.caption("Delta orientati al miglioramento: un valore positivo indica sempre "
               "un progresso, anche dove il tempo basso è migliore.")

    conf = db.load_confronto(coach_id, tutte)
    if conf.empty:
        st.info("Il confronto compare quando esistono sia una sessione T0 che una T1.")
        return

    assi = {"ELE": ("ele_delta", "ele_salto"), "ACC": ("acc_delta", "acc_10m"),
            "AGI": ("agi_delta", "agi_lane"), "RES": ("res_delta", "res_navetta"),
            "FOR": ("for_delta", "for_piegamenti")}

    c = st.columns(5)
    for i, (asse, (dcol, tcol)) in enumerate(assi.items()):
        with c[i]:
            v = conf[dcol].dropna()
            if len(v):
                kpi(db.formatta_delta(tcol, v.mean()), f"{asse} medio",
                    VERDE if v.mean() > 0 else ROSSO)
            else:
                kpi("—", f"{asse} medio")

    st.write("")
    tab = pd.DataFrame({"Atleta": conf["cognome"] + " " + conf["nome"],
                        "Ruolo": conf["ruolo"]})
    for asse, (dcol, tcol) in assi.items():
        tab[asse] = conf[dcol].apply(lambda x, c=tcol: db.formatta_delta(c, x))
    st.dataframe(tab, use_container_width=True, hide_index=True)

    st.subheader("Chi è migliorato di più")
    scelto = st.selectbox("Parametro", list(assi.keys()), index=2)
    dcol, tcol = assi[scelto]
    cl = conf[["cognome", "nome", dcol]].dropna().sort_values(dcol, ascending=False)
    if not cl.empty:
        fig = go.Figure(go.Bar(
            x=cl[dcol], y=cl["cognome"] + " " + cl["nome"], orientation="h",
            marker_color=[ORO if v > 0 else ROSSO for v in cl[dcol]],
            text=[db.formatta_delta(tcol, v) for v in cl[dcol]], textposition="auto"))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#C8C8D0"), height=max(280, 34 * len(cl)),
            margin=dict(t=15, b=35, l=15, r=15),
            xaxis=dict(gridcolor="#26262C", zerolinecolor="#3A3A44"),
            yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ==============================================================================
# PAGINA — ROSA
# ==============================================================================

def pagina_rosa(atleti, coach_id, info_slot, squadra_default=""):
    """
    squadra_default arriva dalla licenza del coach: e' il campo
    "Societa' o squadra" indicato al momento della registrazione.
    Resta modificabile, cosi' un coach che segue piu' formazioni
    (prima squadra e under, per esempio) puo' distinguerle.
    """
    st.title("Rosa")
    barra_slot(info_slot)

    pieno = info_slot["max"] is not None and info_slot["pieno"]
    if pieno:
        st.error(f"Tutti i {info_slot['max']} slot della licenza sono occupati. "
                 "Per inserire un nuovo atleta occorre prima rimuoverne uno "
                 "dalla rosa: lo storico dei suoi test resta comunque salvato.")

    with st.form("nuovo_atleta", clear_on_submit=True):
        st.markdown("**Nuovo atleta**")
        c1, c2, c3 = st.columns([2, 2, 1])
        nome = c1.text_input("Nome")
        cognome = c2.text_input("Cognome")
        anno = c3.number_input("Anno nascita", 1960, date.today().year, 2000, step=1)

        c4, c5, c6 = st.columns(3)
        squadra = c4.text_input("Squadra", value=squadra_default,
                                help="Precompilata dalla tua licenza. Modificala "
                                     "solo se questo atleta appartiene a una "
                                     "formazione diversa.")
        ruolo = c5.selectbox("Ruolo", db.RUOLI)
        mano = c6.selectbox("Mano", ["Dx", "Sx", "Ambidestro"])

        c7, c8, c9, c10 = st.columns(4)
        peso = c7.number_input("Peso (kg)", 40.0, 160.0, 78.0, step=0.5)
        altezza = c8.number_input("Altezza (cm)", 150, 230, 185, step=1)
        reach = c9.number_input("Standing reach (cm)", 180, 290, 240, step=1,
            help="Massima altezza raggiunta con braccio esteso a piedi a terra. "
                 "Necessario per misurare l'elevazione.")
        apertura = c10.number_input("Apertura braccia (cm)", 150, 250, 188, step=1)

        if st.form_submit_button("Aggiungi alla rosa", type="primary",
                                 disabled=pieno):
            if not nome or not cognome:
                st.error("Nome e cognome sono obbligatori.")
            else:
                ok, msg = db.salva_atleta({
                    "nome": nome.strip(), "cognome": cognome.strip(),
                    "anno_nascita": int(anno),
                    "squadra": squadra.strip() or squadra_default or None,
                    "ruolo": ruolo, "mano": mano, "peso": peso,
                    "altezza": int(altezza), "reach": int(reach),
                    "apertura": int(apertura), "attivo": True},
                    coach_id=coach_id)
                if ok:
                    st.success(f"Atleta aggiunto — codice {msg}")
                    st.rerun()
                else:
                    st.error(msg)

    st.divider()
    st.markdown("**Rosa attuale**")
    if atleti.empty:
        st.caption("Nessun atleta inserito.")
        return

    st.dataframe(atleti[["id", "cognome", "nome", "ruolo", "anno_nascita",
                         "altezza", "reach", "peso"]],
        use_container_width=True, hide_index=True,
        column_config={"id": "Codice", "cognome": "Cognome", "nome": "Nome",
                       "ruolo": "Ruolo", "anno_nascita": "Anno",
                       "altezza": "H (cm)", "reach": "Reach", "peso": "Peso"})

    mancanti = atleti[atleti["reach"].isna()]
    if not mancanti.empty:
        st.warning(f"{len(mancanti)} atleti senza standing reach: "
                   "l'elevazione non sarà misurabile correttamente per loro.")

    with st.expander("Rimuovi un atleta dalla rosa"):
        st.caption("L'atleta esce dalla rosa attiva e lo slot torna libero. "
                   "Lo storico dei suoi test resta nel database.")
        et = {f"{r['cognome']} {r['nome']}": r["id"] for _, r in atleti.iterrows()}
        scelto = st.selectbox("Atleta", list(et.keys()))
        if st.button("Rimuovi dalla rosa"):
            if db.disattiva_atleta(et[scelto]):
                st.success("Atleta rimosso. Slot liberato.")
                st.rerun()
            else:
                st.error("Operazione non riuscita.")


# ==============================================================================
# PAGINA — NORME
# ==============================================================================

def pagina_norme(norme):
    st.title("Norme di riferimento")
    st.caption("Valori fissi contro cui vengono calcolati i punteggi. "
               "Non vengono modificati dai dati reali degli atleti.")
    st.markdown('<div class="a199-nota">Riferimenti interni AREA199 su base '
                'letteratura per pallacanestro amatoriale e semi-professionistica. '
                '<b>Non sono standard normativi certificati</b> e vanno dichiarati '
                'come tali in ogni referto.</div>', unsafe_allow_html=True)

    if norme.empty:
        st.error("Nessuna norma caricata.")
        return

    st.write("")
    vis = norme[["ruolo", "test", "media", "dev_st", "direzione"]].copy()
    vis["test"] = vis["test"].map(lambda t: db.META_TEST.get(t, {}).get("label", t))
    st.dataframe(vis.sort_values(["ruolo", "test"]), use_container_width=True,
                 hide_index=True,
                 column_config={"ruolo": "Ruolo", "test": "Test", "media": "Media",
                                "dev_st": "Dev. standard", "direzione": "Direzione"})

    if not db.puo("modifica_norme"):
        return

    with st.expander("Modifica una norma"):
        c1, c2 = st.columns(2)
        ruolo = c1.selectbox("Ruolo", db.RUOLI)
        test = c2.selectbox("Test",
            [c for c in db.ORDINE_TEST if c != "asi_monopodalico"],
            format_func=lambda t: db.META_TEST[t]["label"])
        att = norme[(norme["ruolo"] == ruolo) & (norme["test"] == test)]
        if att.empty:
            st.warning("Norma non trovata.")
            return
        r = att.iloc[0]
        c3, c4 = st.columns(2)
        media = c3.number_input("Media", value=float(r["media"]), step=0.01,
                                format="%.2f")
        dev = c4.number_input("Deviazione standard", value=float(r["dev_st"]),
                              min_value=0.01, step=0.01, format="%.2f")
        st.caption("Una deviazione standard più ampia rende i punteggi più "
                   "conservativi: gli scostamenti pesano meno.")
        if st.button("Aggiorna norma"):
            if db.aggiorna_norma(ruolo, test, media, dev):
                st.success("Norma aggiornata.")
                st.rerun()
            else:
                st.error("Aggiornamento non riuscito.")


# ==============================================================================
# ROUTER
# ==============================================================================

def squadra_di(coach_id) -> str:
    """
    Nome squadra registrato sulla licenza del coach: serve a precompilare
    il campo 'Squadra' nell'inserimento atleti, invece di proporre un
    valore fisso scollegato dall'account.
    """
    if coach_id is None:
        return ""
    u = db.load_utenti()
    if u.empty:
        return ""
    r = u[u["coach_id"] == coach_id]
    if r.empty:
        return ""
    return str(r.iloc[0].get("organizzazione") or "")


def main():
    if "ruolo" not in st.session_state:
        schermata_login()
        return

    admin = db.puo("vede_tutte_squadre")
    coach_id = st.session_state.get("utente_id")
    tutte = False

    with st.sidebar:
        st.markdown(f"<h2 style='color:{ORO};margin-bottom:0'>AREA199</h2>"
                    f"<div style='color:#7A7A85;font-size:10px;letter-spacing:2.5px'>"
                    f"BASKET LAB</div>"
                    f"<div style='color:{ORO};font-size:12px;margin-top:9px'>"
                    f"{st.session_state.get('utente_nome','')}</div>"
                    f"<div style='color:#55555E;font-size:10px;letter-spacing:1.5px'>"
                    f"{db.etichetta_ruolo().upper()}</div><br>", unsafe_allow_html=True)

        if admin:
            utenti = db.load_utenti()
            opzioni = {"Tutte le squadre": "__tutte__"}
            for _, u in utenti.iterrows():
                opzioni[f"{u['nome']}"
                        + (f" — {u['organizzazione']}" if u["organizzazione"] else "")
                        ] = u["coach_id"]
            opzioni["Atleti senza coach"] = None
            scelta = st.selectbox("Squadra attiva", list(opzioni.keys()))
            sel = opzioni[scelta]
            if sel == "__tutte__":
                tutte, coach_id = True, None
            else:
                coach_id = sel
            st.divider()

        voci = ["Sessione test", "Roster squadra", "Scheda atleta",
                "Confronto T0/T1", "Rosa"]
        if db.puo("vede_norme"):
            voci.append("Norme")
        if db.puo("gestisce_utenti"):
            voci.append("Amministrazione")
        pagina = st.radio("Sezione", voci, label_visibility="collapsed")

        st.divider()
        if st.button("Verifica connessione"):
            ok, msg = db.check_connessione()
            (st.success if ok else st.error)(msg)
        if st.button("Ricarica dati"):
            db.invalidate_cache()
            st.rerun()
        if st.button("Esci"):
            st.session_state.clear()
            st.rerun()

    norme = db.load_norme()
    if norme.empty:
        st.error("Tabella delle norme vuota: eseguire lo schema SQL su Supabase.")
        st.stop()

    atleti = db.load_atleti(coach_id=coach_id, tutte_squadre=tutte)
    targets = db.load_targets()
    info_slot = db.slot_info(coach_id) if not tutte else \
        {"usati": len(atleti), "max": None, "liberi": None, "pieno": False}

    if pagina == "Sessione test":
        pagina_sessione(atleti)
    elif pagina == "Roster squadra":
        pagina_roster(atleti, norme, info_slot)
    elif pagina == "Scheda atleta":
        pagina_atleta(atleti, norme, targets)
    elif pagina == "Confronto T0/T1":
        pagina_confronto(coach_id, tutte)
    elif pagina == "Rosa":
        if tutte:
            st.title("Rosa")
            st.info("Seleziona una squadra specifica nella barra laterale "
                    "per gestirne la rosa.")
        else:
            pagina_rosa(atleti, coach_id, info_slot, squadra_di(coach_id))
    elif pagina == "Norme":
        pagina_norme(norme)
    elif pagina == "Amministrazione":
        pagina_admin()

    st.markdown('<div class="a199-foot">AREA199 — Biomechanical Lab · '
                'Dott. Antonio Petruzzi · Riferimenti interni, '
                'non standard normativi certificati</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
