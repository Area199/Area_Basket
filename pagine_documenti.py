"""
================================================================================
AREA199 HUMAN PERFORMANCE LAB — DOCUMENTI AL COACH
================================================================================
Canale libero dal direttore tecnico al coach: si incolla un testo, l'app lo
impagina con i segni distintivi AREA199 e il logo della squadra, e lo rende
consultabile e stampabile nel gestionale del coach.

Serve per tutto cio' che non nasce dal motore di programmazione: schede
provvisorie quando i test non sono completi, indicazioni puntuali,
protocolli, comunicazioni tecniche.

FORMATO DEL TESTO
-----------------
    # Titolo grande          ## Sezione          ### Sottosezione
    - voce di elenco         1. voce numerata
    **grassetto**
    > riquadro evidenziato   (nota, promemoria)
    !> riquadro di attenzione (sicurezza, divieti)
    | col | col |            tabella (la prima riga e' l'intestazione)
    ---                      linea di separazione
    ===                      salto pagina in stampa

Nessuna libreria esterna: il convertitore e' interno al modulo, cosi'
requirements.txt non cambia.

Versione 1.0 — Settembre 2026
================================================================================
"""

import html as _html
import re
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import db_basket as db

ORO = "#C9A227"
GRIGIO = "#1A1A1E"
VERDE = "#2FBF71"
ROSSO = "#E03131"
TESTO = "#E8E8EE"
TESTO_2 = "#B4B4C0"

STATI_DOC = {"bozza": "Bozza", "pubblicato": "Pubblicato", "archiviato": "Archiviato"}

GUIDA_FORMATO = """**Come si scrive il testo**

`# Titolo` · `## Sezione` · `### Sottosezione`
`- voce di elenco` · `1. voce numerata`
`**grassetto**`
`> riquadro evidenziato` — per note e promemoria
`!> riquadro di attenzione` — per sicurezza e divieti
`| colonna | colonna |` — tabella, la prima riga fa da intestazione
`---` linea di separazione · `===` salto pagina in stampa

Una riga vuota separa i paragrafi."""


# ==============================================================================
# 1. CONVERTITORE TESTO -> HTML
# ==============================================================================

def _inline(t: str) -> str:
    """Escape HTML e grassetto. L'escape viene prima: il testo incollato non
    puo' iniettare markup nella pagina."""
    t = _html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t


def md_a_html(testo: str) -> str:
    righe = (testo or "").replace("\r\n", "\n").split("\n")
    out, para, lista, tipo_lista, tab, box, tipo_box = [], [], [], None, [], [], None

    def chiudi_para():
        if para:
            out.append("<p>" + "<br>".join(_inline(x) for x in para) + "</p>")
            para.clear()

    def chiudi_lista():
        nonlocal tipo_lista
        if lista:
            tag = "ol" if tipo_lista == "ol" else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(x)}</li>" for x in lista)
                       + f"</{tag}>")
            lista.clear()
        tipo_lista = None

    def chiudi_tab():
        if not tab:
            return
        celle = [[c.strip() for c in r.strip().strip("|").split("|")] for r in tab]
        celle = [r for r in celle
                 if not all(re.fullmatch(r":?-{2,}:?", c or "") for c in r)]
        if celle:
            h = "".join(f"<th>{_inline(c)}</th>" for c in celle[0])
            b = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>"
                        for r in celle[1:])
            out.append(f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>")
        tab.clear()

    def chiudi_box():
        nonlocal tipo_box
        if box:
            cls = "attenzione" if tipo_box == "!" else "nota"
            out.append(f'<div class="{cls}">' + "<br>".join(_inline(x) for x in box)
                       + "</div>")
            box.clear()
        tipo_box = None

    def chiudi_tutto():
        chiudi_para(); chiudi_lista(); chiudi_tab(); chiudi_box()

    for grezza in righe:
        r = grezza.rstrip()
        s = r.strip()

        if not s:
            chiudi_tutto()
            continue

        if s.startswith("|"):
            chiudi_para(); chiudi_lista(); chiudi_box()
            tab.append(s)
            continue
        chiudi_tab()

        if s.startswith("!>"):
            if tipo_box not in (None, "!"):
                chiudi_box()
            chiudi_para(); chiudi_lista()
            tipo_box = "!"
            box.append(s[2:].strip())
            continue
        if s.startswith(">"):
            if tipo_box not in (None, ">"):
                chiudi_box()
            chiudi_para(); chiudi_lista()
            tipo_box = ">"
            box.append(s[1:].strip())
            continue
        chiudi_box()

        if s in ("===",):
            chiudi_tutto()
            out.append('<div class="salto"></div>')
            continue
        if s in ("---", "___", "***"):
            chiudi_tutto()
            out.append("<hr>")
            continue

        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            chiudi_tutto()
            n = len(m.group(1))
            out.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
            continue

        m = re.match(r"^\d+[.)]\s+(.*)$", s)
        if m:
            chiudi_para()
            if tipo_lista not in (None, "ol"):
                chiudi_lista()
            tipo_lista = "ol"
            lista.append(m.group(1))
            continue

        m = re.match(r"^(?:[-•]|\*(?!\*))\s+(.*)$", s)
        if m:
            chiudi_para()
            if tipo_lista not in (None, "ul"):
                chiudi_lista()
            tipo_lista = "ul"
            lista.append(m.group(1))
            continue

        chiudi_lista()
        para.append(s)

    chiudi_tutto()
    return "\n".join(out)


# ==============================================================================
# 2. IMPAGINAZIONE
# ==============================================================================

def render_documento(titolo: str, contenuto: str, dati_coach: dict,
                     data_doc=None) -> str:
    """Documento completo, stampabile A4, con logo AREA199 e logo squadra."""
    logo = str(dati_coach.get("logo_b64") or "")
    squadra = _html.escape(str(dati_coach.get("organizzazione") or ""))
    quando = pd.to_datetime(data_doc).strftime("%d/%m/%Y") if data_doc \
        else datetime.now().strftime("%d/%m/%Y")
    img = f'<img src="{logo}" class="logo-soc">' if logo else ""

    return f"""<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AREA199 — {_html.escape(titolo)}</title><style>
@page {{ size: A4; margin: 14mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: Arial, Helvetica, sans-serif; color:#111; font-size:11.5pt;
        line-height:1.55; margin:0; padding:18px; background:#fff; max-width:820px;
        margin-left:auto; margin-right:auto; }}
@media print {{ body {{ padding:0; max-width:none; }} }}
.testata {{ display:flex; justify-content:space-between; align-items:center; gap:16px;
   border-bottom:3px solid #C9A227; padding-bottom:10px; margin-bottom:18px; }}
.marchio {{ font-size:21px; font-weight:bold; letter-spacing:2px; white-space:nowrap; }}
.marchio small {{ display:block; font-size:8.5px; font-weight:normal;
   letter-spacing:2.4px; color:#666; margin-top:3px; }}
.logo-soc {{ max-height:58px; max-width:150px; object-fit:contain; }}
.dati {{ text-align:right; font-size:10.5pt; line-height:1.6; }}
.dati b {{ font-size:12pt; }}
h1 {{ font-size:18pt; margin:6px 0 10px; text-transform:uppercase; letter-spacing:0.5px; }}
h2 {{ font-size:13pt; margin:22px 0 8px; padding:5px 10px; background:#111; color:#fff;
      text-transform:uppercase; letter-spacing:0.6px; page-break-after:avoid; }}
h3 {{ font-size:11.5pt; margin:16px 0 6px; border-left:4px solid #C9A227;
      padding-left:8px; page-break-after:avoid; }}
p {{ margin:6px 0 10px; }}
ul, ol {{ margin:4px 0 12px; padding-left:22px; }}
li {{ margin:3px 0; }}
table {{ width:100%; border-collapse:collapse; margin:8px 0 14px; font-size:10.5pt;
         page-break-inside:avoid; }}
th, td {{ border:1px solid #BBB; padding:6px 8px; text-align:left; vertical-align:top; }}
th {{ background:#F2F2F2; font-size:9.5pt; text-transform:uppercase; }}
.nota {{ background:#FAF6E8; border-left:4px solid #C9A227; padding:10px 14px;
         margin:10px 0 14px; page-break-inside:avoid; }}
.attenzione {{ background:#FDECEC; border-left:4px solid #D32F2F; padding:10px 14px;
               margin:10px 0 14px; page-break-inside:avoid; }}
hr {{ border:none; border-top:1px solid #CCC; margin:18px 0; }}
code {{ background:#F2F2F2; padding:1px 4px; border-radius:3px; font-size:10pt; }}
.salto {{ page-break-before:always; }}
.pie {{ margin-top:26px; border-top:1px solid #DDD; padding-top:8px; font-size:8pt;
        color:#777; text-align:center; text-transform:uppercase; letter-spacing:1px; }}
.stampa {{ position:fixed; top:12px; right:12px; background:#C9A227; color:#111;
           border:none; padding:10px 20px; font-weight:bold; font-size:13px;
           border-radius:4px; cursor:pointer; z-index:99; }}
@media print {{ .stampa {{ display:none; }} }}
</style></head><body>
<button class="stampa" onclick="window.print()">STAMPA</button>
<div class="testata">
  <div class="marchio">AREA199<small>HUMAN PERFORMANCE LAB</small></div>
  {img}
  <div class="dati"><b>{squadra or "Documento tecnico"}</b><br>{quando}</div>
</div>
<h1>{_html.escape(titolo)}</h1>
{md_a_html(contenuto)}
<div class="pie">AREA199 — Human Performance Lab · Dott. Antonio Petruzzi ·
Documento riservato alla squadra indicata</div>
</body></html>"""


# ==============================================================================
# 3. DATI
# ==============================================================================

@st.cache_data(ttl=60, show_spinner=False)
def load_documenti(coach_id, solo_pubblicati: bool = False) -> pd.DataFrame:
    q = db.get_client().table("documenti_coach").select("*").eq("coach_id", coach_id)
    if solo_pubblicati:
        q = q.eq("stato", "pubblicato")
    return pd.DataFrame(q.order("aggiornato_il", desc=True).execute().data or [])


def salva_documento(coach_id, titolo, contenuto, stato="bozza", doc_id=None):
    try:
        ora = datetime.utcnow().isoformat()
        campi = {"titolo": titolo.strip(), "contenuto": contenuto,
                 "stato": stato, "aggiornato_il": ora}
        if stato == "pubblicato":
            campi["pubblicato_il"] = ora
        cl = db.get_client().table("documenti_coach")
        if doc_id:
            cl.update(campi).eq("id", int(doc_id)).execute()
        else:
            campi["coach_id"] = coach_id
            cl.insert(campi).execute()
        load_documenti.clear()
        return True, "Documento salvato."
    except Exception as e:
        return False, str(e)


def cambia_stato(doc_id, stato):
    try:
        campi = {"stato": stato, "aggiornato_il": datetime.utcnow().isoformat()}
        if stato == "pubblicato":
            campi["pubblicato_il"] = campi["aggiornato_il"]
        db.get_client().table("documenti_coach").update(campi) \
            .eq("id", int(doc_id)).execute()
        load_documenti.clear()
        return True
    except Exception:
        return False


def elimina_documento(doc_id):
    try:
        db.get_client().table("documenti_coach").delete().eq("id", int(doc_id)).execute()
        load_documenti.clear()
        return True
    except Exception:
        return False


def _nome_file(titolo):
    base = re.sub(r"[^A-Za-z0-9]+", "_", titolo or "documento").strip("_")[:50]
    return f"AREA199_{base or 'documento'}.html"


# ==============================================================================
# 4. PAGINA — DIRETTORE TECNICO
# ==============================================================================

def pagina_documenti_admin(coach_id):
    st.title("Documenti al coach")

    if coach_id is None:
        st.info("Seleziona una squadra specifica nella barra laterale: il documento "
                "viene impaginato con il suo logo e pubblicato nel suo gestionale.")
        return

    dati = db.dati_coach_completi(coach_id) or {}
    st.caption(f"Destinatario: **{dati.get('nome', '—')}**"
               + (f" — {dati.get('organizzazione')}" if dati.get("organizzazione") else ""))

    for k, v in [("doc_id", None), ("doc_titolo", ""), ("doc_testo", "")]:
        st.session_state.setdefault(k, v)

    # Streamlit non permette di modificare un campo gia' disegnato nella stessa
    # esecuzione. I pulsanti quindi depositano la richiesta qui e rilanciano:
    # il valore viene applicato adesso, prima che i campi vengano creati.
    pend = st.session_state.pop("doc_pendente", None)
    if pend is not None:
        st.session_state["doc_id"] = pend.get("id")
        st.session_state["doc_titolo"] = pend.get("titolo", "")
        st.session_state["doc_testo"] = pend.get("testo", "")
    flash = st.session_state.pop("doc_flash", None)
    if flash:
        st.success(flash)

    t1, t2 = st.tabs(["Scrivi", "Documenti inviati"])

    with t1:
        if st.session_state["doc_id"]:
            st.info("Stai modificando un documento esistente. "
                    "Salvando lo aggiorni, non ne crei uno nuovo.")
            if st.button("Annulla modifica e inizia un documento nuovo"):
                st.session_state["doc_pendente"] = {}
                st.rerun()

        titolo = st.text_input("Titolo", key="doc_titolo",
                               placeholder="Es. Settimana 1 — Seduta 1")
        testo = st.text_area("Testo", key="doc_testo", height=380,
                             placeholder="Incolla qui il testo del documento.")
        with st.expander("Come si formatta il testo"):
            st.markdown(GUIDA_FORMATO)

        if testo.strip():
            with st.expander("Anteprima impaginata", expanded=True):
                components.html(render_documento(titolo or "Senza titolo", testo, dati),
                                height=620, scrolling=True)

        c1, c2 = st.columns(2)
        pronto = bool(titolo.strip() and testo.strip())
        with c1:
            if st.button("Salva in bozza", disabled=not pronto,
                         use_container_width=True):
                ok, msg = salva_documento(coach_id, titolo, testo, "bozza",
                                          st.session_state["doc_id"])
                if ok:
                    st.session_state["doc_flash"] = ("Bozza salvata. La trovi in "
                                                     "«Documenti inviati».")
                    st.session_state["doc_pendente"] = {}
                    st.rerun()
                else:
                    st.error(msg)
        with c2:
            if st.button("Pubblica al coach", type="primary", disabled=not pronto,
                         use_container_width=True):
                ok, msg = salva_documento(coach_id, titolo, testo, "pubblicato",
                                          st.session_state["doc_id"])
                if ok:
                    st.session_state["doc_pendente"] = {}
                    st.session_state["doc_flash"] = ("Pubblicato: il coach lo trova "
                                                     "nella sezione «Documenti».")
                    st.rerun()
                else:
                    st.error(msg)

    with t2:
        docs = load_documenti(coach_id)
        if docs.empty:
            st.info("Nessun documento per questa squadra.")
            return
        for _, d in docs.iterrows():
            stato = STATI_DOC.get(d["stato"], d["stato"])
            colore = {"pubblicato": VERDE, "bozza": ORO}.get(d["stato"], TESTO_2)
            quando = pd.to_datetime(d["aggiornato_il"]).strftime("%d/%m/%Y %H:%M")
            with st.expander(f"{d['titolo']} — {stato} — {quando}"):
                st.markdown(f'<span style="color:{colore};font-weight:700">'
                            f'{stato.upper()}</span>', unsafe_allow_html=True)
                html_doc = render_documento(d["titolo"], d["contenuto"], dati,
                                            d.get("pubblicato_il") or d["aggiornato_il"])
                b1, b2, b3, b4 = st.columns(4)
                with b1:
                    if st.button("Modifica", key=f"mod_{d['id']}"):
                        st.session_state["doc_pendente"] = {
                            "id": int(d["id"]), "titolo": d["titolo"],
                            "testo": d["contenuto"]}
                        st.rerun()
                with b2:
                    if d["stato"] == "pubblicato":
                        if st.button("Ritira", key=f"rit_{d['id']}"):
                            cambia_stato(d["id"], "bozza"); st.rerun()
                    else:
                        if st.button("Pubblica", key=f"pub_{d['id']}"):
                            cambia_stato(d["id"], "pubblicato"); st.rerun()
                with b3:
                    st.download_button("Scarica", data=html_doc,
                                       file_name=_nome_file(d["titolo"]),
                                       mime="text/html", key=f"dl_{d['id']}")
                with b4:
                    if st.button("Elimina", key=f"del_{d['id']}"):
                        elimina_documento(d["id"]); st.rerun()


# ==============================================================================
# 5. PAGINA — COACH
# ==============================================================================

def pagina_documenti_coach(coach_id):
    st.title("Documenti")

    if coach_id is None:
        st.info("Nessuna squadra associata.")
        return

    docs = load_documenti(coach_id, solo_pubblicati=True)
    if docs.empty:
        st.info("Nessun documento disponibile. Qui compaiono le indicazioni e le "
                "schede che AREA199 ti invia al di fuori del programma.")
        return

    dati = db.dati_coach_completi(coach_id) or {}
    etichette = {
        f"{r['titolo']} — {pd.to_datetime(r['pubblicato_il'] or r['aggiornato_il']).strftime('%d/%m/%Y')}":
        i for i, r in docs.iterrows()}
    scelta = st.selectbox("Documento", list(etichette.keys()))
    d = docs.loc[etichette[scelta]]

    html_doc = render_documento(d["titolo"], d["contenuto"], dati,
                                d.get("pubblicato_il") or d["aggiornato_il"])
    st.download_button("Scarica e stampa", data=html_doc,
                       file_name=_nome_file(d["titolo"]), mime="text/html",
                       use_container_width=True)
    st.caption("Il file si apre nel browser: in alto a destra c'è STAMPA.")
    components.html(html_doc, height=900, scrolling=True)
