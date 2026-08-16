"""
================================================================================
AREA199 HUMAN PERFORMANCE LAB — PROFILO SOCIETÀ E DOCUMENTI
================================================================================
Il coach compila qui i propri dati anagrafici e fiscali. Da quei dati il
sistema genera il contratto e la dichiarazione sui consensi, che restano
consultabili in piattaforma.

NOTA SULLA FIRMA IN PIATTAFORMA
-------------------------------
L'accettazione registrata dall'applicazione costituisce una FIRMA ELETTRONICA
SEMPLICE ai sensi del Regolamento eIDAS. Non le si puo' negare valore
probatorio, ma il suo peso e' liberamente valutabile dal giudice ed e'
inferiore a quello di una firma autografa o di una firma elettronica
qualificata. Per questo il sistema:

  1. registra data, ora, nome del dichiarante e impronta SHA-256 del testo;
  2. produce comunque il documento scaricabile, da firmare e restituire.

L'accettazione in piattaforma vale come conferma e tracciamento, non come
sostituto della firma sul documento.

Versione 1.0 — Agosto 2026
================================================================================
"""

from datetime import date

import pandas as pd
import streamlit as st

import db_basket as db

VERSIONE_CONTRATTO = "1.0"

ORO = "#C9A227"
GRIGIO = "#1A1A1E"
VERDE = "#2FBF71"
ROSSO = "#E03131"
TESTO = "#E8E8EE"
TESTO_2 = "#B4B4C0"
TESTO_3 = "#9A9AA6"

ETICHETTE = {
    "codice_fiscale": "Codice fiscale", "indirizzo": "Indirizzo",
    "citta": "Città", "email": "Email",
}


# ==============================================================================
# PAGINA PRINCIPALE
# ==============================================================================

def pagina_profilo(coach_id, admin=False):
    st.title("Profilo società")

    if coach_id is None:
        st.info("Seleziona una squadra nella barra laterale per gestirne il profilo.")
        return

    d = db.dati_coach_completi(coach_id)
    mancanti = db.dati_mancanti(coach_id)

    if mancanti:
        st.markdown(
            f'<div style="background:rgba(224,49,49,0.1);border-left:3px solid {ROSSO};'
            f'padding:12px 16px;font-size:13px;color:#FFB0B0;margin-bottom:14px">'
            f'<b>Dati incompleti.</b> Mancano: '
            f'{", ".join(ETICHETTE.get(m, m) for m in mancanti)}. '
            f'Senza questi campi il contratto non può essere compilato.</div>',
            unsafe_allow_html=True)

    tabs = st.tabs(["Logo", "Dati anagrafici", "Contratto e documenti"]
                   + (["Condizioni economiche"] if admin else []))

    with tabs[0]:
        _logo(coach_id, d)
    with tabs[1]:
        _anagrafica(coach_id, d)
    with tabs[2]:
        _documenti(coach_id, d, mancanti, admin)
    if admin:
        with tabs[3]:
            _condizioni(coach_id, d)


# ==============================================================================
# LOGO
# ==============================================================================

def _logo(coach_id, d):
    c1, c2 = st.columns([1, 1.4])
    logo = str(d.get("logo_b64") or "")

    with c1:
        st.markdown("**Logo attuale**")
        if logo:
            st.markdown(f'<div style="background:{GRIGIO};border:1px solid #33333B;'
                        f'border-radius:8px;padding:22px;text-align:center">'
                        f'<img src="{logo}" style="max-height:130px;max-width:100%;'
                        f'object-fit:contain"></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:{GRIGIO};border:1px dashed #44444E;'
                        f'border-radius:8px;padding:44px;text-align:center;'
                        f'color:{TESTO_3};font-size:13px">Nessun logo caricato</div>',
                        unsafe_allow_html=True)

    with c2:
        st.markdown("**Carica un nuovo logo**")
        st.caption("PNG o JPG. Viene ridimensionato automaticamente e comparirà "
                   "sul foglio di campo, sulle schede e nella barra laterale.")
        f = st.file_uploader("Immagine", type=["png", "jpg", "jpeg", "webp"],
                             label_visibility="collapsed")
        if f is not None:
            ok, res = db.prepara_logo(f)
            if not ok:
                st.error(res)
            else:
                st.markdown(f'<img src="{res}" style="max-height:90px;'
                            f'background:{GRIGIO};padding:10px;border-radius:6px">',
                            unsafe_allow_html=True)
                if st.button("Salva logo", type="primary"):
                    if db.salva_logo(coach_id, res):
                        st.success("Logo salvato.")
                        st.rerun()
        if logo:
            st.write("")
            if st.button("Rimuovi il logo"):
                if db.salva_logo(coach_id, ""):
                    st.rerun()


# ==============================================================================
# ANAGRAFICA
# ==============================================================================

def _anagrafica(coach_id, d):
    st.caption("Questi dati compilano automaticamente il contratto e la "
               "dichiarazione sui consensi. Si inseriscono una volta sola.")

    def v(k, default=""):
        x = d.get(k)
        return default if x is None or (isinstance(x, float) and pd.isna(x)) else x

    with st.form("dati_cliente"):
        st.markdown("**Chi sottoscrive**")
        tipo = st.radio(
            "Il contratto è sottoscritto da", ["persona_fisica", "societa"],
            index=0 if v("tipo_soggetto", "persona_fisica") == "persona_fisica" else 1,
            format_func=lambda x: ("Persona fisica (l'allenatore in proprio)"
                                   if x == "persona_fisica"
                                   else "Società sportiva"),
            horizontal=True,
            help="Cambia i ruoli privacy e il foro competente. Se la spesa la "
                 "sostiene l'allenatore, è persona fisica.")

        c1, c2 = st.columns(2)
        organizzazione = c1.text_input("Nome squadra", value=str(v("organizzazione")))
        categoria = c2.text_input("Categoria e campionato",
                                  value=str(v("categoria_squadra")),
                                  placeholder="Es. DR3 Maschile — campionato FIP")

        st.markdown("**Dati del sottoscrittore**")
        c3, c4 = st.columns(2)
        ragione = c3.text_input(
            "Ragione sociale" if tipo == "societa" else "Nome e cognome",
            value=str(v("ragione_sociale")))
        legale = c4.text_input("Legale rappresentante",
                               value=str(v("legale_rappr")),
                               disabled=(tipo == "persona_fisica"),
                               help="Solo se sottoscrive una società.")

        c5, c6 = st.columns(2)
        cf = c5.text_input("Codice fiscale *", value=str(v("codice_fiscale")))
        piva = c6.text_input("Partita IVA", value=str(v("partita_iva")),
                             help="Se assente, lasciare vuoto.")

        st.markdown("**Sede e contatti**")
        indirizzo = st.text_input("Indirizzo *", value=str(v("indirizzo")))
        c7, c8, c9 = st.columns([1, 2, 1])
        cap = c7.text_input("CAP", value=str(v("cap")))
        citta = c8.text_input("Città *", value=str(v("citta")))
        prov = c9.text_input("Provincia", value=str(v("provincia")), max_chars=2)

        c10, c11, c12 = st.columns(3)
        email = c10.text_input("Email *", value=str(v("email")))
        pec = c11.text_input("PEC", value=str(v("pec")))
        tel = c12.text_input("Telefono", value=str(v("telefono")))

        st.markdown("**Rosa e vincoli operativi**")
        c13, c14, c15 = st.columns(3)
        minorenni = c13.number_input(
            "Atleti minorenni in rosa", 0, 60, int(v("atleti_minorenni", 0) or 0),
            step=1,
            help="Se anche uno solo, serve il consenso degli esercenti la "
                 "responsabilità genitoriale prima dei test.")
        sedute = c14.number_input("Sedute a settimana", 0, 7,
                                  int(v("sedute_settimana", 3) or 3), step=1)
        minuti = c15.number_input("Minuti di atletica per seduta", 0, 90,
                                  int(v("minuti_seduta", 25) or 25), step=5)

        c16, c17 = st.columns(2)
        attrezzatura = c16.text_input("Attrezzatura disponibile",
                                      value=str(v("attrezzatura_dich")),
                                      placeholder="Es. elastici, palle mediche")
        spazi = c17.text_input("Spazi", value=str(v("spazi_dich")),
                               placeholder="Es. palestra + esterno nei mesi caldi")

        st.caption("* campi necessari per la compilazione del contratto")

        if st.form_submit_button("Salva dati", type="primary"):
            ok, msg = db.salva_dati_cliente(coach_id, {
                "tipo_soggetto": tipo, "organizzazione": organizzazione,
                "categoria_squadra": categoria, "ragione_sociale": ragione,
                "legale_rappr": legale if tipo == "societa" else None,
                "codice_fiscale": cf, "partita_iva": piva, "indirizzo": indirizzo,
                "cap": cap, "citta": citta, "provincia": prov.upper(),
                "email": email, "pec": pec, "telefono": tel,
                "atleti_minorenni": int(minorenni),
                "sedute_settimana": int(sedute), "minuti_seduta": int(minuti),
                "attrezzatura_dich": attrezzatura, "spazi_dich": spazi})
            if ok:
                st.success("Dati salvati.")
                st.rerun()
            else:
                st.error(msg)

    if int(d.get("atleti_minorenni") or 0) > 0:
        st.markdown(
            f'<div style="background:rgba(201,162,39,0.1);border-left:3px solid {ORO};'
            f'padding:12px 16px;font-size:12.5px;color:{TESTO};line-height:1.55">'
            f'<b>Ci sono {int(d["atleti_minorenni"])} minorenni in rosa.</b> '
            f'Il consenso degli esercenti la responsabilità genitoriale va raccolto '
            f'<b>prima</b> della prima sessione di test, non dopo. Il modulo è '
            f'nella scheda «Contratto e documenti».</div>', unsafe_allow_html=True)


# ==============================================================================
# CONDIZIONI ECONOMICHE — solo direttore tecnico
# ==============================================================================

def _condizioni(coach_id, d):
    st.caption("Visibile solo al direttore tecnico. Il coach le vede compilate "
               "nel contratto, non modificabili.")

    def v(k, default=None):
        x = d.get(k)
        return default if x is None or (isinstance(x, float) and pd.isna(x)) else x

    with st.form("condizioni"):
        c1, c2 = st.columns(2)
        inizio = c1.date_input(
            "Inizio", value=pd.to_datetime(v("contratto_data_inizio", date.today())),
            format="DD/MM/YYYY")
        fine = c2.date_input(
            "Fine", value=pd.to_datetime(v("contratto_data_fine", date.today())),
            format="DD/MM/YYYY")

        c3, c4, c5 = st.columns(3)
        attivazione = c3.number_input("Importo attivazione (€)", 0.0, 100000.0,
                                      float(v("importo_attivazione", 0.0) or 0.0),
                                      step=10.0)
        canone = c4.number_input("Canone (€)", 0.0, 100000.0,
                                 float(v("importo_canone", 0.0) or 0.0), step=10.0)
        period = c5.selectbox(
            "Periodicità", ["mensile", "bimestrale", "trimestrale", "una tantum"],
            index=["mensile", "bimestrale", "trimestrale",
                   "una tantum"].index(v("periodicita_canone", "mensile")
                                       or "mensile"))

        pilota = st.checkbox(
            "Prezzo di primo anno", value=bool(v("prezzo_pilota", False)),
            help="Lo dichiara nel contratto: evita che questa cifra diventi il "
                 "riferimento per i rinnovi.")
        note = st.text_area("Note sulle condizioni",
                            value=str(v("condizioni_note", "") or ""), height=80)

        if st.form_submit_button("Salva condizioni", type="primary"):
            ok, msg = db.salva_dati_cliente(coach_id, {
                "contratto_data_inizio": inizio, "contratto_data_fine": fine,
                "importo_attivazione": attivazione, "importo_canone": canone,
                "periodicita_canone": period, "prezzo_pilota": pilota,
                "condizioni_note": note})
            if ok:
                st.success("Condizioni salvate.")
                st.rerun()
            else:
                st.error(msg)


# ==============================================================================
# DOCUMENTI
# ==============================================================================

def _documenti(coach_id, d, mancanti, admin):
    acc = db.load_accettazioni(coach_id)
    acc_contratto = acc[acc["documento"] == "contratto"] if not acc.empty \
        else pd.DataFrame()

    if not acc_contratto.empty:
        r = acc_contratto.iloc[0]
        quando = pd.to_datetime(r["accettato_il"]).strftime("%d/%m/%Y alle %H:%M")
        st.markdown(
            f'<div style="background:rgba(47,191,113,0.1);border-left:3px solid {VERDE};'
            f'padding:12px 16px;font-size:13px;color:#A8E0BC;margin-bottom:14px">'
            f'<b>Condizioni accettate</b> da {r["nome_dichiarante"]} il {quando} '
            f'(versione {r["versione"]}).</div>', unsafe_allow_html=True)

    if mancanti:
        st.warning("Completa prima i dati anagrafici: "
                   + ", ".join(ETICHETTE.get(m, m) for m in mancanti))
        return

    # Un contratto generato con importi o date vuote e' un contratto che
    # rischia di partire cosi'. Meglio dirlo prima di scaricarlo.
    econ_mancanti = _condizioni_mancanti(d)
    if econ_mancanti:
        if admin:
            st.error("**Condizioni economiche incomplete:** "
                     + ", ".join(econ_mancanti)
                     + ". Compilale nella scheda «Condizioni economiche», "
                       "altrimenti il contratto esce con i campi vuoti.")
        else:
            st.info("Le condizioni economiche non sono ancora state definite da "
                    "AREA199. Il contratto è consultabile, ma importi e durata "
                    "compariranno solo dopo il completamento.")

    testo = _componi_contratto(d)

    st.markdown("**Contratto**")
    st.download_button("Scarica il contratto", data=testo,
                       file_name=f"AREA199_contratto_{_slug(d)}.html",
                       mime="text/html", use_container_width=True)
    st.caption("Si apre nel browser: in alto a destra c'è STAMPA.")

    with st.expander("Consulta il contratto a video"):
        st.components.v1.html(testo, height=620, scrolling=True)

    if acc_contratto.empty:
        st.write("")
        st.markdown(
            f'<div style="background:{GRIGIO};border-left:3px solid {ORO};'
            f'padding:13px 16px;font-size:12.5px;color:{TESTO};line-height:1.55">'
            f'L\'accettazione qui sotto registra data, ora e un\'impronta del '
            f'testo. Vale come conferma tracciata ma <b>non sostituisce la firma '
            f'sul documento</b>: scarica il contratto, firmalo e restituiscilo.'
            f'</div>', unsafe_allow_html=True)
        nome = st.text_input("Nome e cognome di chi accetta",
                             value=str(d.get("ragione_sociale") or d.get("nome") or ""))
        conferma = st.checkbox("Dichiaro di aver letto e di accettare le condizioni")
        if st.button("Registra accettazione", type="primary",
                     disabled=not (conferma and nome.strip())):
            ok, msg = db.registra_accettazione(
                coach_id, "contratto", VERSIONE_CONTRATTO, nome, testo)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    st.divider()
    st.markdown("**Moduli di consenso da distribuire**")
    st.caption("La raccolta e la conservazione competono a te in qualità di "
               "titolare del trattamento. I moduli compilati restano ai tuoi "
               "atti e non vanno trasmessi ad AREA199.")

    minorenni = int(d.get("atleti_minorenni") or 0)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Modulo atleta maggiorenne",
                           data=_modulo_consenso(d, minore=False),
                           file_name="AREA199_consenso_maggiorenne.html",
                           mime="text/html", use_container_width=True)
    with c2:
        st.download_button(
            f"Modulo atleta minorenne{f' ({minorenni})' if minorenni else ''}",
            data=_modulo_consenso(d, minore=True),
            file_name="AREA199_consenso_minorenne.html",
            mime="text/html", use_container_width=True)

    if minorenni > 0:
        st.warning(f"Hai dichiarato {minorenni} minorenni in rosa: il modulo per "
                   "i genitori va raccolto prima della prima sessione di test.")


# ==============================================================================
# COMPOSIZIONE DOCUMENTI
# ==============================================================================

def _condizioni_mancanti(d) -> list:
    """Campi economici e di durata non ancora compilati dal direttore tecnico."""
    fuori = []
    if not d.get("contratto_data_inizio"):
        fuori.append("data di inizio")
    if not d.get("contratto_data_fine"):
        fuori.append("data di scadenza")
    att = d.get("importo_attivazione")
    can = d.get("importo_canone")
    try:
        vuoto = (float(att or 0) == 0) and (float(can or 0) == 0)
    except (TypeError, ValueError):
        vuoto = True
    if vuoto:
        fuori.append("importi")
    return fuori


def _slug(d):
    base = str(d.get("organizzazione") or d.get("nome") or "cliente")
    return "".join(c if c.isalnum() else "_" for c in base)[:40]


def _c(d, k, fallback="—"):
    x = d.get(k)
    if x is None or (isinstance(x, float) and pd.isna(x)) or str(x).strip() == "":
        return fallback
    return str(x).strip()


def _data(d, k):
    x = d.get(k)
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    try:
        return pd.to_datetime(x).strftime("%d/%m/%Y")
    except Exception:
        return "—"


def _durata(d) -> str:
    """Durata in settimane fra le due date, per leggibilita' del contratto."""
    try:
        i = pd.to_datetime(d.get("contratto_data_inizio"))
        f = pd.to_datetime(d.get("contratto_data_fine"))
        if pd.isna(i) or pd.isna(f):
            return "—"
        giorni = (f - i).days
        if giorni <= 0:
            return "—"
        sett = giorni // 7
        return (f"{sett} settimane ({giorni} giorni)" if sett
                else f"{giorni} giorni")
    except Exception:
        return "—"


def _euro(d, k):
    x = d.get(k)
    try:
        v = float(x)
        return f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def _stile():
    return """
@page { size: A4; margin: 18mm; }
body { font-family: Georgia, 'Times New Roman', serif; color:#111; font-size:11pt;
       line-height:1.55; margin:0; background:#fff; }
.testata { border-bottom:3px solid #C9A227; padding-bottom:10px; margin-bottom:22px; }
.marchio { font-family:Arial,sans-serif; font-size:20px; font-weight:bold;
           letter-spacing:2px; }
.marchio small { display:block; font-size:8.5px; font-weight:normal;
                 letter-spacing:2.4px; color:#666; margin-top:3px; }
h1 { font-family:Arial,sans-serif; font-size:15pt; text-transform:uppercase;
     letter-spacing:0.5px; margin:0 0 4px; }
h2 { font-family:Arial,sans-serif; font-size:11pt; text-transform:uppercase;
     letter-spacing:0.5px; margin:20px 0 6px; border-bottom:1px solid #CCC;
     padding-bottom:3px; }
h3 { font-family:Arial,sans-serif; font-size:10pt; margin:14px 0 4px; }
table { width:100%; border-collapse:collapse; margin:10px 0 16px; font-size:10pt; }
th,td { border:1px solid #BBB; padding:6px 9px; text-align:left; vertical-align:top; }
th { background:#F2F2F2; font-family:Arial,sans-serif; font-size:9pt;
     text-transform:uppercase; }
.nota { background:#FAF6E8; border-left:3px solid #C9A227; padding:10px 14px;
        margin:14px 0; font-size:10pt; }
.firme { display:flex; justify-content:space-between; margin-top:40px;
         page-break-inside:avoid; }
.firme div { width:44%; }
.riga-firma { border-top:1px solid #333; margin-top:46px; padding-top:5px;
              font-size:9pt; color:#555; }
.pie { margin-top:26px; border-top:1px solid #DDD; padding-top:8px;
       font-size:8pt; color:#777; text-align:center; font-family:Arial,sans-serif;
       text-transform:uppercase; letter-spacing:1px; }
.stampa { position:fixed; top:14px; right:14px; background:#C9A227; color:#111;
          border:none; padding:11px 22px; font-weight:bold; font-size:13px;
          border-radius:4px; cursor:pointer; z-index:99; font-family:Arial,sans-serif; }
@media print { .stampa { display:none; } }
"""


def _componi_contratto(d) -> str:
    societa = _c(d, "tipo_soggetto") == "societa"
    sede = f"{_c(d,'indirizzo')}, {_c(d,'cap','')} {_c(d,'citta')} ({_c(d,'provincia','')})"
    denom = _c(d, "ragione_sociale", _c(d, "nome"))
    piva = _c(d, "partita_iva", "non soggetto")

    parte_cliente = (
        f"<b>{denom}</b>, con sede in {sede}, Codice Fiscale {_c(d,'codice_fiscale')}, "
        f"Partita IVA {piva}, in persona del legale rappresentante "
        f"{_c(d,'legale_rappr')}, email {_c(d,'email')}"
        if societa else
        f"<b>{denom}</b>, residente in {sede}, Codice Fiscale "
        f"{_c(d,'codice_fiscale')}, email {_c(d,'email')}, in qualità di allenatore "
        f"della squadra {_c(d,'organizzazione')}")

    minorenni = int(d.get("atleti_minorenni") or 0)
    pilota = bool(d.get("prezzo_pilota"))

    riga_pilota = ("<p>4.4 Il corrispettivo indicato costituisce <b>prezzo di primo "
                   "anno</b>, riconosciuto in ragione dell'avvio della collaborazione. "
                   "Non costituisce base di riferimento per i rinnovi.</p>"
                   if pilota else "")

    avviso_minori = (
        f'<div class="nota"><b>Presenza di minori.</b> Il Cliente dichiara che la '
        f'rosa comprende <b>{minorenni}</b> atleti minorenni. Il consenso degli '
        f'esercenti la responsabilità genitoriale deve essere acquisito <b>prima</b> '
        f'della prima rilevazione di dati.</div>' if minorenni else "")

    foro = ("il Foro competente è quello del luogo di residenza o domicilio del "
            "Cliente ove questi rivesta la qualifica di consumatore, e in ogni "
            f"altro caso il Foro di {_c(d,'citta')}"
            if not societa else f"è competente in via esclusiva il Foro di "
            f"{_c(d,'citta')}")

    return f"""<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">
<title>AREA199 — Contratto {denom}</title><style>{_stile()}</style></head><body>
<button class="stampa" onclick="window.print()">STAMPA</button>

<div class="testata">
  <div class="marchio">AREA199<small>HUMAN PERFORMANCE LAB</small></div>
</div>

<h1>Contratto di licenza d'uso e prestazione di servizi</h1>
<p style="color:#666;font-size:9.5pt">Versione {VERSIONE_CONTRATTO} — documento
generato il {date.today().strftime('%d/%m/%Y')}</p>

<h2>Tra le parti</h2>
<p><b>AREA199 Human Performance Lab</b>, nella persona del Dott. Antonio Petruzzi,
di seguito «AREA199» o «il Fornitore»</p>
<p>e</p>
<p>{parte_cliente}, di seguito «il Cliente»</p>

<h2>Art. 1 — Oggetto</h2>
<p>1.1 AREA199 concede al Cliente una licenza d'uso <b>non esclusiva, non
trasferibile e revocabile</b> della piattaforma AREA199 Human Performance Lab e
si obbliga a prestare i servizi di valutazione funzionale, programmazione e
supervisione a distanza.</p>
<table>
<tr><th>Squadra</th><td>{_c(d,'organizzazione')}</td></tr>
<tr><th>Categoria</th><td>{_c(d,'categoria_squadra')}</td></tr>
<tr><th>Atleti massimi</th><td>{_c(d,'slot_max')}</td></tr>
<tr><th>Di cui minorenni</th><td>{minorenni}</td></tr>
<tr><th>Utenze</th><td>una, personale e non cedibile</td></tr>
</table>

<h2>Art. 2 — Natura e limiti della prestazione</h2>
<p>2.1 La prestazione consiste in valutazione funzionale, programmazione
dell'allenamento e supervisione a distanza. <b>Non costituisce prestazione
sanitaria, diagnosi, terapia o riabilitazione</b>, né attività di preparatore
atletico in presenza durante le sedute.</p>
<p>2.2 Gli indicatori di rischio prodotti dalla piattaforma derivano da
associazioni statistiche di popolazione e hanno funzione di <b>segnalazione e
approfondimento</b>. Non costituiscono diagnosi né previsione di infortunio sul
singolo atleta.</p>
<p>2.3 I valori di riferimento sono <b>riferimenti interni AREA199</b> costruiti
sulla base della letteratura disponibile e non costituiscono standard normativi
certificati. La documentazione metodologica è consegnata come allegato e ne
costituisce parte integrante.</p>
<p>2.4 L'idoneità all'attività sportiva è certificata esclusivamente dalla
certificazione medico-sportiva, la cui acquisizione resta a carico del Cliente.</p>

<h2>Art. 3 — Durata</h2>
<table>
<tr><th>Decorrenza</th><td>{_data(d,'contratto_data_inizio')}</td></tr>
<tr><th>Scadenza</th><td>{_data(d,'contratto_data_fine')}</td></tr>
<tr><th>Durata complessiva</th><td>{_durata(d)}</td></tr>
</table>
<p>Alla cessazione l'accesso viene disattivato. Il Cliente può richiedere entro
30 giorni copia dei dati dei propri atleti in formato leggibile.</p>

<h2>Art. 4 — Corrispettivo</h2>
<table>
<tr><th>Voce</th><th>Importo</th></tr>
<tr><td>Attivazione / pacchetto iniziale</td><td>{_euro(d,'importo_attivazione')}</td></tr>
<tr><td>Canone {_c(d,'periodicita_canone','')}</td><td>{_euro(d,'importo_canone')}</td></tr>
</table>
{riga_pilota}
<p>4.5 In caso di ritardo nel pagamento AREA199 può sospendere l'accesso previa
comunicazione scritta, senza che ciò costituisca inadempimento. La sospensione
non comporta perdita dei dati.</p>
{f'<p>4.6 {_c(d,"condizioni_note")}</p>' if _c(d,'condizioni_note','')!='—' else ''}

<h2>Art. 5 — Proprietà intellettuale</h2>
<p>5.1 Restano di proprietà esclusiva di AREA199 il software, i protocolli di
test, la libreria degli esercizi, gli algoritmi di calcolo, i valori di
riferimento, la struttura dei referti e i segni distintivi.</p>
<p>5.2 Restano di titolarità del Cliente i dati anagrafici e i risultati dei
test dei propri atleti.</p>
<p>5.3 Il Cliente si obbliga a <b>non</b>: cedere o sublicenziare la piattaforma
o le credenziali; riprodurre o utilizzare protocolli, libreria e programmi per
squadre o soggetti diversi da quelli indicati all'art. 1; presentare a terzi come
propri i contenuti metodologici forniti; tentare di ricostruire il funzionamento
del sistema.</p>
<p>5.4 La violazione del presente articolo costituisce grave inadempimento e
legittima la risoluzione immediata ai sensi dell'art. 1456 c.c.</p>

<h2>Art. 6 — Obblighi del Cliente</h2>
<p>Il Cliente si obbliga a: somministrare i test secondo i protocolli forniti,
mantenendo costanti riscaldamento, ordine di esecuzione e operatore addetto alla
misurazione; trasmettere dati veritieri; verificare la valida certificazione
medico-sportiva di ogni atleta; <b>raccogliere e conservare a propria cura i
consensi al trattamento dei dati</b>; interrompere il lavoro con l'atleta che
manifesti dolore o malessere e comunicarlo; segnalare ogni infortunio entro 48
ore; custodire le credenziali; non modificare sostanzialmente i programmi senza
preventiva comunicazione.</p>

<h2>Art. 7 — Trattamento dei dati personali</h2>
<p>7.1 Il Cliente opera in qualità di <b>Titolare del trattamento</b>; AREA199 è
designata <b>Responsabile del trattamento</b> ai sensi dell'art. 28 GDPR.</p>
<p>7.2 Il Cliente <b>garantisce e manleva</b> AREA199 in ordine all'esistenza di
una valida base giuridica per ogni dato trasmesso, e in particolare di aver
acquisito, prima di ogni trasmissione, il consenso dell'atleta maggiorenne ovvero
degli esercenti la responsabilità genitoriale per l'atleta minorenne.</p>
<p>7.3 AREA199 riceve i dati facendo affidamento su tale dichiarazione e
<b>non è tenuta a verificare</b> l'acquisizione dei singoli consensi. La raccolta,
la verifica e la conservazione dei consensi competono in via esclusiva al Cliente.</p>
<p>7.4 AREA199 tratta i dati solo su istruzione del Titolare, adotta misure
tecniche adeguate ai sensi dell'art. 32 GDPR, notifica ogni violazione entro 48
ore e, alla cessazione, cancella o restituisce i dati a scelta del Titolare.</p>
{avviso_minori}

<h2>Art. 8 — Responsabilità</h2>
<p>8.1 AREA199 risponde della correttezza metodologica della programmazione
fornita in relazione alle informazioni ricevute.</p>
<p>8.2 Il Cliente risponde della corretta esecuzione sul campo, della sorveglianza
degli atleti, dell'idoneità di spazi e attrezzature.</p>
<p>8.3 AREA199 non risponde di danni derivanti da esecuzione difforme dai
protocolli, da condizioni di salute non comunicate, da infortuni riconducibili
all'attività sportiva in sé, da dati errati trasmessi dal Cliente o da decisioni
tecniche assunte autonomamente dal Cliente.</p>
<p>8.4 Salvi dolo e colpa grave, la responsabilità complessiva di AREA199 non può
eccedere l'importo dei corrispettivi percepiti nei dodici mesi precedenti
l'evento. È esclusa la responsabilità per danni indiretti e mancato guadagno.</p>

<h2>Art. 9 — Recesso e risoluzione</h2>
<p>9.1 Ciascuna Parte può recedere con preavviso scritto di 30 giorni. I
corrispettivi maturati restano dovuti.</p>
<p>9.2 AREA199 può risolvere con effetto immediato in caso di violazione degli
articoli 5 (proprietà intellettuale) e 7 (dati personali).</p>

<h2>Art. 10 — Legge applicabile e foro</h2>
<p>Il contratto è regolato dalla legge italiana. Per ogni controversia {foro}.
Le Parti si impegnano a tentare preventivamente una composizione bonaria.</p>

<h2>Allegati</h2>
<p>A — Vincoli operativi dichiarati · B — Riferimenti scientifici e note
metodologiche · C — Modelli di informativa e consenso (strumento di supporto)</p>

<h3>Vincoli operativi dichiarati dal Cliente</h3>
<table>
<tr><th>Sedute settimanali</th><td>{_c(d,'sedute_settimana')}</td></tr>
<tr><th>Minuti di atletica per seduta</th><td>{_c(d,'minuti_seduta')}</td></tr>
<tr><th>Attrezzatura</th><td>{_c(d,'attrezzatura_dich')}</td></tr>
<tr><th>Spazi</th><td>{_c(d,'spazi_dich')}</td></tr>
</table>
<p style="font-size:10pt;color:#555">Il programma è costruito su questi vincoli.
Variazioni sostanziali vanno comunicate.</p>

<div class="firme">
  <div><div class="riga-firma">Il Cliente — {denom}</div></div>
  <div><div class="riga-firma">AREA199 — Dott. Antonio Petruzzi</div></div>
</div>

{_allegato_b()}

<div class="nota" style="margin-top:26px">
<b>Approvazione specifica ai sensi degli artt. 1341 e 1342 c.c.</b><br>
Il Cliente dichiara di approvare espressamente gli articoli 5 (proprietà
intellettuale e divieti), 7 (dati personali e manleva), 8 (responsabilità e
limitazione), 9 (recesso e risoluzione), 10 (foro competente).
</div>

<div class="firme">
  <div><div class="riga-firma">Il Cliente</div></div><div></div>
</div>

<div class="pie">AREA199 — Human Performance Lab · Dott. Antonio Petruzzi</div>
</body></html>"""


def _allegato_b() -> str:
    """
    Allegato scientifico consegnato con il contratto.

    Non e' un ornamento: l'art. 2.3 dichiara che i valori di riferimento non
    sono standard certificati, e questo allegato e' cio' che rende quella
    dichiarazione verificabile. Distingue in modo esplicito cio' che e'
    sostenuto da studi da cio' che e' convenzione operativa.
    """
    return """
<div style="page-break-before:always"></div>

<h1 style="margin-top:0">Allegato B — Riferimenti scientifici</h1>
<p style="color:#666;font-size:9.5pt">Note metodologiche sui protocolli di
valutazione e sui valori di riferimento impiegati.</p>

<div class="nota">
<b>Tre livelli, dichiarati.</b> Ogni soglia impiegata dal sistema appartiene a
uno di questi livelli, e viene indicata come tale:<br><br>
<b>Evidenza</b> — sostenuta da studi prospettici o meta-analisi.<br>
<b>Convenzione</b> — soglia operativa diffusa nella pratica, non validata come
predittiva.<br>
<b>Riferimento interno</b> — costruito da AREA199 sulla base della letteratura,
non derivato da dati normativi pubblicati.
</div>

<h2>1 · Mobilità di caviglia</h2>
<p><b>Livello: evidenza.</b> Uno studio prospettico su novanta giocatori di
pallacanestro juniores d'élite, seguiti per un anno, ha rilevato che una ridotta
escursione in dorsiflessione di caviglia predispone allo sviluppo di tendinopatia
rotulea.</p>
<p style="font-size:10pt">Backman LJ, Danielson P. <i>Low range of ankle
dorsiflexion predisposes for patellar tendinopathy in junior elite basketball
players: a 1-year prospective study.</i> Am J Sports Med. 2011;39(12):2626-2633.</p>
<p><b>Precisazione.</b> La soglia individuata nello studio è espressa in
<b>gradi</b>; il test impiegato dal sistema misura in <b>centimetri</b>. Le due
scale sono fortemente correlate ma non sono convertibili in modo esatto. La
soglia in centimetri adottata è pertanto una <b>convenzione operativa</b>, non
la trasposizione diretta del dato dello studio.</p>
<p><b>Affidabilità.</b> Il test in distanza mostra affidabilità eccellente
(coefficienti di correlazione intraclasse fra 0,97 e 0,99), superiore a tutti
gli altri test della batteria.</p>
<p style="font-size:10pt">Bennell K, Talbot R, Wajswelner H, et al. <i>Intra-rater
and inter-rater reliability of a weight-bearing lunge measure of ankle
dorsiflexion.</i> Aust J Physiother. 1998;44(3):175-180.</p>

<h2>2 · Asimmetria fra gli arti</h2>
<p><b>Livello: convenzione, con riserve.</b> La soglia del 10% deriva dai criteri
di ritorno allo sport dopo ricostruzione del legamento crociato anteriore
(Limb Symmetry Index ≥ 90%). <b>Non è un valore predittivo validato su atleti
sani</b>: una quota consistente di atleti sani non raggiunge tale soglia, e
l'indice tende a sopravvalutare la funzione dell'arto.</p>
<p style="font-size:10pt">Wellsandt E, Failla MJ, Snyder-Mackler L. <i>Limb
symmetry indexes can overestimate knee function after anterior cruciate ligament
injury.</i> J Orthop Sports Phys Ther. 2017;47(5):334-338.</p>
<p>Nel sistema l'asimmetria <b>non concorre al punteggio complessivo</b> ed è
trattata come innesco di approfondimento, non come diagnosi.</p>

<h2>3 · Prevenzione neuromuscolare</h2>
<p><b>Livello: evidenza.</b> Le meta-analisi su programmi di allenamento
neuromuscolare riportano riduzioni consistenti degli infortuni: circa il 27% per
gli infortuni di ginocchio e circa il 50% per le lesioni del legamento crociato
anteriore.</p>
<p><b>Dose.</b> L'effetto protettivo maggiore si osserva con sedute di 10-15
minuti, due o tre volte a settimana. La struttura delle sedute prodotte dal
sistema è costruita su questo dato.</p>

<h2>4 · Limiti dichiarati della misurazione</h2>
<p>La batteria è progettata per essere somministrata con metro e cronometro.
Ne conseguono limiti che il Cliente prende atto:</p>
<ul style="font-size:10pt;line-height:1.6">
<li>il <b>cronometraggio manuale</b> introduce un errore superiore a quello
delle fotocellule: su distanze brevi l'incidenza proporzionale è rilevante;</li>
<li>su finestre inferiori alle quattro settimane il miglioramento atteso di
sprint ed elevazione è dello stesso ordine dell'errore di misura, ragione per
cui tali test sono <b>esclusi d'ufficio</b> dalle verifiche brevi;</li>
<li>una variazione inferiore a 1,5 cm nel test di mobilità di caviglia rientra
nell'errore dello strumento e non costituisce miglioramento;</li>
<li>il confronto fra rilevazioni è valido solo a parità di riscaldamento,
ordine di esecuzione e operatore addetto alla misurazione.</li>
</ul>

<h2>5 · Valori di riferimento</h2>
<p><b>Livello: riferimento interno.</b> Le medie e le deviazioni standard
impiegate per il calcolo dei punteggi sono riferimenti costruiti da AREA199 sulla
base della letteratura disponibile per pallacanestro amatoriale e
semi-professionistica, corretti per ruolo e per le condizioni di rilevazione.</p>
<div class="nota">
<b>Non esistono dati normativi pubblicati sulla popolazione di categoria
italiana.</b> I valori impiegati non costituiscono pertanto standard normativi
certificati e sono dichiarati come riferimenti interni in ogni referto prodotto.
</div>

<h2>6 · Cosa il sistema non fa</h2>
<ul style="font-size:10pt;line-height:1.6">
<li><b>Non diagnostica.</b> Nessuna soglia costituisce diagnosi clinica.</li>
<li><b>Non predice l'infortunio sul singolo atleta.</b> Gli indicatori derivano
da associazioni di popolazione.</li>
<li><b>Non sostituisce la valutazione strumentale</b> né la certificazione
medico-sportiva.</li>
</ul>

<div class="pie" style="margin-top:30px">AREA199 — Human Performance Lab ·
Allegato tecnico al contratto</div>
"""


def _modulo_consenso(d, minore: bool) -> str:
    titolare = _c(d, "ragione_sociale", _c(d, "nome"))
    squadra = _c(d, "organizzazione")
    contatto = _c(d, "email")

    if minore:
        intestazione = "Informativa e consenso — atleta minorenne"
        apertura = (f"<p>Gentili genitori, vostro figlio parteciperà a un percorso "
                    f"di valutazione funzionale e preparazione atletica curato da "
                    f"AREA199 Human Performance Lab per conto di {squadra}.</p>")
        firme = """
<table>
<tr><th>Genitore / tutore 1</th><th>Genitore / tutore 2</th></tr>
<tr><td style="height:70px">Nome<br><br>Firma</td>
    <td style="height:70px">Nome<br><br>Firma</td></tr>
</table>
<p style="font-size:9.5pt;color:#555">In caso di firma di un solo genitore, il
sottoscrittore dichiara di agire anche in nome e per conto dell'altro esercente
la responsabilità genitoriale.</p>"""
        soggetto = ("Noi sottoscritti, esercenti la responsabilità genitoriale sul "
                    "minore ______________________________, nato/a a "
                    "______________ il ____________")
        conseguenza = ("Vostro figlio non parteciperà alla valutazione funzionale. "
                       "<b>Non ci sarà alcuna conseguenza</b> sulla sua posizione in "
                       "squadra, sulle convocazioni o sul minutaggio.")
    else:
        intestazione = "Informativa e consenso — atleta maggiorenne"
        apertura = (f"<p>Parteciperai a un percorso di valutazione funzionale e "
                    f"preparazione atletica curato da AREA199 Human Performance Lab "
                    f"per conto di {squadra}.</p>")
        firme = """<table><tr><td style="height:70px">Luogo e data<br><br></td>
<td style="height:70px">Firma<br><br></td></tr></table>"""
        soggetto = ("Io sottoscritto/a ______________________________, nato/a a "
                    "______________ il ____________")
        conseguenza = ("Non potrai partecipare alla valutazione funzionale. "
                       "<b>Questo non ha alcuna conseguenza</b> sulla tua posizione "
                       "in squadra, sulla convocazione o sull'impiego in campo.")

    return f"""<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">
<title>AREA199 — {intestazione}</title><style>{_stile()}</style></head><body>
<button class="stampa" onclick="window.print()">STAMPA</button>
<div class="testata">
  <div class="marchio">AREA199<small>HUMAN PERFORMANCE LAB</small></div>
</div>
<h1>{intestazione}</h1>
<p style="font-size:9.5pt;color:#666">
<b>Titolare del trattamento:</b> {titolare} — {contatto}<br>
<b>Responsabile del trattamento:</b> AREA199 Human Performance Lab</p>

{apertura}

<h2>Cosa comporta</h2>
<p>Una serie di test motori semplici — salto verticale al muro, corsa breve,
percorso di agilità sul campo, piegamenti, misurazione della mobilità di caviglia
— eseguiti durante il normale allenamento con metro e cronometro.
<b>Nessuna attrezzatura invasiva, nessun prelievo, nessun esame clinico.</b></p>

<h2>Quali dati raccogliamo</h2>
<p>Nome, cognome, data di nascita, ruolo, altezza, peso, misure antropometriche e
risultati dei test.</p>

<h2>Cosa questi dati NON sono</h2>
<div class="nota"><b>Non sono una valutazione medica.</b> Non diagnosticano nulla
e non sostituiscono la visita medico-sportiva, che resta l'unico atto che
certifica l'idoneità all'attività. Alcuni risultati possono generare una
<b>segnalazione</b>: è un invito ad approfondire, non la diagnosi di un problema.</div>

<h2>Chi vede i dati e per quanto tempo</h2>
<p>L'allenatore e il responsabile tecnico di AREA199. Nessun altro. I dati non
vengono ceduti a terzi né usati per finalità commerciali. Sono conservati per la
durata della collaborazione e per il periodo successivo strettamente necessario.</p>

<h2>Diritti</h2>
<p>È possibile in ogni momento chiedere di accedere ai dati, correggerli,
cancellarli, limitarne l'uso, riceverne copia od opporsi al trattamento,
scrivendo a {contatto}. Il consenso è revocabile in qualsiasi momento. È
ammesso reclamo al Garante per la protezione dei dati personali.</p>

<h2>Se non si acconsente</h2>
<p>{conseguenza}</p>

<h2>Consenso</h2>
<p>{soggetto}, letta l'informativa che precede:</p>
<p>☐ <b>ACCONSENTO / ACCONSENTIAMO</b> al trattamento dei dati per le finalità
indicate<br>
☐ <b>NON ACCONSENTO / NON ACCONSENTIAMO</b></p>
<p style="font-size:10pt">Facoltativo:<br>
☐ uso di immagini e video a fini di analisi tecnica interna<br>
☐ uso di dati anonimi e aggregati per l'elaborazione di valori statistici</p>

{firme}

<div class="pie">AREA199 — Human Performance Lab · Modulo da conservare
agli atti del titolare del trattamento</div>
</body></html>"""
