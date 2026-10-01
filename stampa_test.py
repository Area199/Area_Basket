"""
================================================================================
AREA199 HUMAN PERFORMANCE LAB — RISULTATI DEI TEST IN FORMATO STAMPABILE
================================================================================
Il foglio di campo serve PRIMA dei test, vuoto, da compilare a penna.
Questo modulo serve DOPO: stampa i risultati gia' caricati nel sistema.

Due documenti, stesso stile del foglio di campo e dei documenti al coach
(A4, intestazione AREA199, logo della squadra, pulsante STAMPA che su telefono
permette anche di salvare in PDF):

    genera_report_squadra   una sessione (T0, T1...) di una stagione per tutta
                            la rosa: risultati, punteggi, segnalazioni, test
                            mancanti; a richiesta una scheda per atleta, una
                            per pagina, da consegnare ai giocatori.
    genera_report_atleta    la scheda di un atleta per la sessione scelta, con
                            lo storico di tutte le sue sessioni in fondo.

Cosa stampa la scheda individuale: per ogni test la misura rilevata sul campo
(lati destro e sinistro, altezza del tocco e reach), il valore calcolato, il
punteggio contro la norma di ruolo con la tacca del target e il giorno in cui
il test e' stato misurato. L'asimmetria monopodalica compare come indicatore
di rischio e non ha punteggio, come nel resto della piattaforma.

Nessuna libreria esterna. I campi vuoti arrivano come None o NaN, e NaN e'
truthy: ogni lettura passa da _vuoto().

Versione 1.0 — Settembre 2026
================================================================================
"""

import html as _html
import json
import re
from datetime import datetime

import pandas as pd

import db_basket as db

ORDINE_SESSIONI = {"T0": 0, "T1": 1, "T2": 2, "T3": 3}


# ==============================================================================
# 1. UTILITA'
# ==============================================================================

def _vuoto(v) -> bool:
    if v is None:
        return True
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def _e(v) -> str:
    """Testo pronto per l'HTML, vuoto se il campo manca."""
    return "" if _vuoto(v) else _html.escape(str(v).strip())


def _num(v):
    if _vuoto(v):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def _cm(v, dec=1) -> str:
    f = _num(v)
    if f is None:
        return "—"
    return f"{f:.0f}" if dec == 0 else f"{f:.{dec}f}"


def _giorno(v) -> str:
    if _vuoto(v):
        return "—"
    try:
        return pd.to_datetime(v).strftime("%d/%m/%Y")
    except Exception:
        return "—"


def _date_misure(riga) -> dict:
    """date_misure e' un jsonb: di norma arriva come dizionario, per sicurezza
    si accetta anche la stringa JSON."""
    dm = riga.get("date_misure") if hasattr(riga, "get") else None
    if isinstance(dm, dict):
        return dm
    if isinstance(dm, str):
        try:
            d = json.loads(dm)
            return d if isinstance(d, dict) else {}
        except ValueError:
            return {}
    return {}


def _giorno_test(riga, col) -> str:
    dm = _date_misure(riga)
    if dm.get(col):
        return _giorno(dm[col])
    # righe precedenti alla 009: un solo giorno per tutta la sessione
    return _giorno(riga.get("data_test")) if not _vuoto(riga.get(col)) else "—"


def _nome(a) -> str:
    return f"{_e(a.get('cognome'))} {_e(a.get('nome'))}".strip()


def nome_file(prefisso: str, *parti) -> str:
    base = "_".join(re.sub(r"[^A-Za-z0-9]+", "_", str(p)).strip("_")
                    for p in parti if str(p or "").strip())
    return f"AREA199_{prefisso}_{base or 'risultati'}.html"


def sessioni_disponibili(test: pd.DataFrame, id_atleti) -> list:
    """Coppie (stagione, sessione) con almeno un test per questi atleti,
    dalla piu' recente."""
    if test is None or test.empty:
        return []
    t = test[test["atleta_id"].isin(list(id_atleti))]
    if t.empty:
        return []
    if "stagione" in t.columns:
        stag = t["stagione"].where(t["stagione"].notna(),
                                   t["data_test"].apply(
                                       lambda d: db.stagione_da_data(d)
                                       if not _vuoto(d) else ""))
    else:
        stag = t["data_test"].apply(
            lambda d: db.stagione_da_data(d) if not _vuoto(d) else "")
    coppie = {(str(s), str(x)) for s, x in zip(stag, t["sessione"]) if s and x}
    return sorted(coppie, key=lambda c: (c[0], ORDINE_SESSIONI.get(c[1], 9), c[1]),
                  reverse=True)


def righe_sessione(test: pd.DataFrame, stagione: str, sessione: str) -> pd.DataFrame:
    if test is None or test.empty:
        return pd.DataFrame()
    t = test[test["sessione"] == sessione]
    if "stagione" in t.columns:
        stag = t["stagione"].where(t["stagione"].notna(), t["data_test"].apply(
            lambda d: db.stagione_da_data(d) if not _vuoto(d) else ""))
        t = t[stag == stagione]
    return t


# ==============================================================================
# 2. STILE COMUNE
# ==============================================================================

CSS = """
@page { size: A4; margin: 12mm; }
* { box-sizing: border-box; -webkit-print-color-adjust: exact;
    print-color-adjust: exact; }
body { font-family: Arial, Helvetica, sans-serif; color: #111; font-size: 10.5px;
       margin: 0 auto; padding: 16px; background: #fff; max-width: 820px; }
@media print { body { padding: 0; max-width: none; } }
.testata { display: flex; justify-content: space-between; align-items: center;
           border-bottom: 3px solid #C9A227; padding-bottom: 9px;
           margin-bottom: 14px; gap: 16px; }
.marchio { font-size: 21px; font-weight: bold; letter-spacing: 2px; white-space: nowrap; }
.marchio small { display: block; font-size: 8.5px; font-weight: normal;
                 letter-spacing: 2.4px; color: #666; margin-top: 3px; }
.logo-soc { max-height: 56px; max-width: 150px; object-fit: contain; }
.dati { text-align: right; font-size: 11px; line-height: 1.6; }
.dati b { font-size: 13px; }
h1 { font-size: 17px; margin: 4px 0 10px; text-transform: uppercase; letter-spacing: .5px; }
h2 { font-size: 11.5px; margin: 18px 0 6px; padding: 4px 9px; background: #111;
     color: #fff; text-transform: uppercase; letter-spacing: .6px;
     page-break-after: avoid; break-after: avoid; }
table { width: 100%; border-collapse: collapse; margin-bottom: 6px; }
th { background: #F2F2F2; border: 1px solid #AAA; padding: 4px 4px; font-size: 8.5px;
     text-transform: uppercase; letter-spacing: .3px; }
td { border: 1px solid #BBB; padding: 4px 5px; vertical-align: middle; }
td.c, th.c { text-align: center; }
td.a { white-space: nowrap; }
td.muto { color: #999; text-align: center; }
tr { page-break-inside: avoid; break-inside: avoid; }
tbody tr:nth-child(even) td { background: #FAFAFA; }
td.rischio { background: #FDECEC !important; color: #B71C1C; font-weight: bold; }
.nota { background: #FAF6E8; border-left: 3px solid #C9A227; padding: 7px 10px;
        margin: 8px 0; font-size: 9.5px; line-height: 1.5; }
.allarme { background: #FDECEC; border-left: 3px solid #D32F2F; padding: 7px 10px;
           margin: 6px 0; font-size: 10px; line-height: 1.5; }
.kpi { display: flex; gap: 8px; margin: 4px 0 8px; }
.kpi div { flex: 1; border: 1px solid #DDD; border-top: 3px solid #C9A227;
           padding: 6px 8px; text-align: center; }
.kpi b { display: block; font-size: 18px; }
.kpi span { font-size: 8px; color: #666; text-transform: uppercase; letter-spacing: 1px; }
.barra { position: relative; height: 8px; background: #E4E4E4; border-radius: 4px;
         min-width: 90px; }
.barra i { position: absolute; left: 0; top: 0; bottom: 0; background: #C9A227;
           border-radius: 4px; }
.barra u { position: absolute; top: -3px; width: 2px; height: 14px; background: #111; }
.punt { font-weight: bold; font-size: 12px; }
.scheda { page-break-before: always; break-before: page; }
.scheda-testa { display: flex; justify-content: space-between; align-items: flex-end;
                border-bottom: 1px solid #333; padding-bottom: 6px; margin-bottom: 8px; }
.scheda-nome { font-size: 20px; font-weight: bold; text-transform: uppercase; }
.scheda-meta { font-size: 9.5px; color: #555; letter-spacing: 1px;
               text-transform: uppercase; margin-top: 3px; }
.ovr { text-align: center; min-width: 70px; }
.ovr b { display: block; font-size: 30px; color: #8A6D14; line-height: 1; }
.ovr span { font-size: 8px; letter-spacing: 2px; color: #666; }
.piccolo { font-size: 8.5px; color: #666; }
.pie { margin-top: 18px; text-align: center; font-size: 7.5px; color: #777;
       letter-spacing: 1px; text-transform: uppercase; border-top: 1px solid #DDD;
       padding-top: 6px; }
.stampa { position: fixed; top: 12px; right: 12px; background: #C9A227; color: #111;
          border: none; padding: 10px 20px; font-weight: bold; font-size: 13px;
          border-radius: 4px; cursor: pointer; z-index: 99; }
@media print { .stampa { display: none; } }
"""

PIE = ("AREA199 — Human Performance Lab · Dott. Antonio Petruzzi · "
       "Punteggi calcolati su riferimenti interni costruiti dalla letteratura, "
       "non standard normativi certificati · Documento riservato alla squadra")


def _testata(titolo_dx: str, sottotitolo: str, logo_b64: str) -> str:
    logo = str(logo_b64 or "")
    img = f'<img src="{logo}" class="logo-soc">' if logo.startswith("data:") else ""
    return (f'<div class="testata"><div class="marchio">AREA199'
            f'<small>HUMAN PERFORMANCE LAB</small></div>{img}'
            f'<div class="dati"><b>{titolo_dx}</b><br>{sottotitolo}</div></div>')


def _pagina(titolo: str, corpo: str) -> str:
    return (f'<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>AREA199 — {_html.escape(titolo)}</title><style>{CSS}</style>'
            f'</head><body><button class="stampa" onclick="window.print()">STAMPA'
            f'</button>{corpo}<div class="pie">{PIE}</div></body></html>')


def _barra(p, tgt) -> str:
    if p is None:
        return '<span class="piccolo">—</span>'
    t = f'<u style="left:{int(tgt)}%"></u>' if tgt is not None else ""
    return f'<div class="barra"><i style="width:{int(p)}%"></i>{t}</div>'


# ==============================================================================
# 3. SCHEDA INDIVIDUALE
# ==============================================================================

def _misura_rilevata(col, riga, atleta) -> str:
    """La misura presa sul campo, prima di ogni calcolo."""
    if col == "mob_kneewall":
        dx, sx = riga.get("mob_dx"), riga.get("mob_sx")
        if _num(dx) is not None or _num(sx) is not None:
            return f"DX {_cm(dx)} · SX {_cm(sx)} cm"
    elif col == "asi_monopodalico":
        dx, sx = riga.get("asi_dx"), riga.get("asi_sx")
        if _num(dx) is not None or _num(sx) is not None:
            return f"DX {_cm(dx, 0)} · SX {_cm(sx, 0)} cm"
    elif col == "ele_salto":
        tocco = _num(riga.get("ele_tocco"))
        reach = _num(atleta.get("reach"))
        if tocco is not None:
            return (f"tocco {_cm(tocco)} − reach {_cm(reach, 0)} cm"
                    if reach is not None else f"tocco {_cm(tocco)} cm")
    return ""


def _righe_scheda(atleta, riga, norme, tgt) -> tuple[str, list, int | None]:
    """Righe della tabella individuale, segnalazioni e overall."""
    punteggi = db.calcola_tutti(riga, atleta.get("ruolo"), norme)
    overall = db.calcola_overall(punteggi)
    sigla_asse = {c: a for a, c in db.ASSI.items()}
    righe, allarmi = "", []

    for col in db.ORDINE_TEST:
        meta = db.META_TEST[col]
        val = riga.get(col)
        rilevata = _misura_rilevata(col, riga, atleta)
        asse = sigla_asse.get(col)
        rischio = False

        if col == "mob_kneewall":
            risultato = db.formatta_valore(col, val)
            if _num(val) is not None:
                risultato += " <span class='piccolo'>lato peggiore</span>"
            diff = riga.get("mob_diff")
            if _num(diff) is not None:
                risultato += (f"<br><span class='piccolo'>differenza lati "
                              f"{_cm(diff)} cm</span>")
            if db.flag_mobilita(val):
                rischio = True
                allarmi.append(f"<b>Caviglia rigida {_cm(val)} cm</b> — sotto i 9 cm "
                               f"di dorsiflessione: fattore di rischio per il ginocchio "
                               f"in atterraggio.")
            if db.flag_mob_diff(diff):
                rischio = True
                allarmi.append(f"<b>Differenza fra le caviglie {_cm(diff)} cm</b> — "
                               f"oltre i 2 cm, fuori dal range di normalità.")
        elif col == "asi_monopodalico":
            risultato = db.formatta_valore(col, val)
            if db.flag_asimmetria(val):
                rischio = True
                allarmi.append(f"<b>Asimmetria arti inferiori {_cm(val)}%</b> — oltre "
                               f"il 10%: da approfondire, non è una diagnosi.")
        elif col == "ele_salto":
            risultato = db.formatta_valore(col, val)
            probl = db.verifica_antropometria(atleta.get("altezza"),
                                              atleta.get("reach"))
            if probl and not _vuoto(val):
                rischio = True
                allarmi.append("<b>Elevazione da verificare</b> — anagrafica non "
                               "plausibile: " + _html.escape("; ".join(probl))
                               + ". Corretto il reach nella Rosa, il valore si "
                               "ricalcola.")
        else:
            risultato = db.formatta_valore(col, val)

        if asse:
            p, t = punteggi.get(asse), tgt.get(asse)
            punt = (f'<span class="punt">{p}</span>' if p is not None
                    else '<span class="piccolo">—</span>')
            barra = _barra(p, t)
        elif db.flag_asimmetria(val):
            punt = '<b style="color:#B71C1C">oltre soglia</b>'
            barra = ('<span class="piccolo">sopra il 10% · indicatore di rischio, '
                     'non entra nell\'overall</span>')
        else:
            punt = '<span style="color:#1B7F3B">entro soglia</span>'
            barra = ('<span class="piccolo">sotto il 10% · indicatore di rischio, '
                     'non entra nell\'overall</span>')

        classe = ' class="c rischio"' if rischio else ' class="c"'
        if _vuoto(val):
            righe += (f'<tr><td><b>{meta["sigla"]}</b> {meta["label"]}</td>'
                      f'<td class="muto" colspan="5">non rilevato</td></tr>')
        else:
            righe += (f'<tr><td><b>{meta["sigla"]}</b> {meta["label"]}'
                      f'<br><span class="piccolo">{meta["protocollo"]}</span></td>'
                      f'<td class="c">{rilevata}</td>'
                      f'<td{classe}>{risultato}</td>'
                      f'<td class="c">{punt}</td><td>{barra}</td>'
                      f'<td class="c">{_giorno_test(riga, col)}</td></tr>')
    return righe, allarmi, overall


def _blocco_scheda(atleta, riga, norme, targets, sessione, stagione,
                   nuova_pagina=True, storico=None, testata="") -> str:
    ruolo = atleta.get("ruolo")
    tgt = targets.get(ruolo, {k: 70 for k in db.ASSI})
    righe, allarmi, overall = _righe_scheda(atleta, riga, norme, tgt)

    meta = " · ".join(x for x in [
        _e(ruolo),
        f"classe {int(_num(atleta.get('anno_nascita')))}"
        if _num(atleta.get("anno_nascita")) else "",
        f"{_cm(atleta.get('altezza'), 0)} cm" if _num(atleta.get("altezza")) else "",
        f"reach {_cm(atleta.get('reach'), 0)} cm" if _num(atleta.get("reach")) else "",
    ] if x)

    # Nel documento di squadra ogni scheda ripete l'intestazione: staccata e
    # consegnata al giocatore, la pagina deve stare in piedi da sola.
    corpo = (f'<div class="{"scheda" if nuova_pagina else ""}">{testata}'
             f'<div class="scheda-testa"><div>'
             f'<div class="scheda-nome">{_nome(atleta)}</div>'
             f'<div class="scheda-meta">{meta}</div>'
             f'<div class="scheda-meta">Sessione {_e(sessione)} · stagione '
             f'{_e(stagione)}</div></div>'
             f'<div class="ovr"><b>{overall if overall is not None else "—"}</b>'
             f'<span>OVERALL</span></div></div>'
             f'<table><thead><tr><th style="text-align:left">Test</th>'
             f'<th class="c">Misura rilevata</th><th class="c">Risultato</th>'
             f'<th class="c">Punteggio</th><th>vs target di ruolo</th>'
             f'<th class="c">Misurato il</th></tr></thead><tbody>{righe}</tbody>'
             f'</table>'
             f'<div class="piccolo">Punteggio da 30 a 99 rispetto alla norma del ruolo. '
             f'La barra nera verticale è il target del ruolo. Overall = media dei '
             f'punteggi rilevati.</div>')

    if allarmi:
        corpo += "".join(f'<div class="allarme">{a}</div>' for a in allarmi)
    if _e(riga.get("note")):
        corpo += (f'<div class="nota"><b>NOTE DI CAMPO</b><br>'
                  f'{_e(riga.get("note")).replace(chr(10), "<br>")}</div>')
    # Solo se scritta sui valori attuali: una lettura superata contraddirebbe
    # la tabella stampata sopra (overall diverso, test mancanti).
    if _e(riga.get("ai_comment")) and db.commento_aggiornato(riga):
        corpo += (f'<div class="nota"><b>LETTURA TECNICA</b><br>'
                  f'{_e(riga.get("ai_comment")).replace(chr(10), "<br>")}</div>')

    if storico is not None and len(storico) > 1:
        corpo += _tabella_storico(atleta, storico, norme)
    return corpo + "</div>"


def _tabella_storico(atleta, storico: pd.DataFrame, norme) -> str:
    s = storico.copy()
    s["_ord"] = s["sessione"].map(lambda x: ORDINE_SESSIONI.get(x, 9))
    s = s.sort_values(["data_test", "_ord"])
    th = "".join(f'<th class="c">{a}</th>' for a in db.ASSI)
    righe = ""
    for _, r in s.iterrows():
        p = db.calcola_tutti(r, atleta.get("ruolo"), norme)
        ovr = db.calcola_overall(p)
        celle = "".join(
            f'<td class="c">{db.formatta_valore(c, r.get(c))}'
            f'<br><span class="piccolo">{p[a] if p[a] is not None else ""}</span></td>'
            for a, c in db.ASSI.items())
        stag = r.get("stagione") if not _vuoto(r.get("stagione")) else \
            (db.stagione_da_data(r["data_test"]) if not _vuoto(r.get("data_test")) else "")
        righe += (f'<tr><td class="a"><b>{_e(r.get("sessione"))}</b> '
                  f'<span class="piccolo">{_e(stag)}</span></td>{celle}'
                  f'<td class="c">{db.formatta_valore("asi_monopodalico", r.get("asi_monopodalico"))}</td>'
                  f'<td class="c"><b>{ovr if ovr is not None else "—"}</b></td></tr>')
    return (f'<h2>Storico delle sessioni</h2>'
            f'<table><thead><tr><th style="text-align:left">Sessione</th>{th}'
            f'<th class="c">ASI</th><th class="c">OVR</th></tr></thead>'
            f'<tbody>{righe}</tbody></table>'
            f'<div class="piccolo">In ogni cella il risultato e, sotto, il punteggio. '
            f'Un confronto fra sessioni regge solo a parità di riscaldamento, ordine '
            f'dei test, operatore, superficie e calzature.</div>')


# ==============================================================================
# 4. DOCUMENTI
# ==============================================================================

def genera_report_atleta(atleta, riga, norme, targets, sessione, stagione,
                         squadra="", logo_b64="", storico=None) -> str:
    """Scheda di un atleta per una sessione, con lo storico in fondo."""
    corpo = _testata(f"RISULTATI DEI TEST — {_e(sessione)}",
                     f"{_e(squadra) or 'Scheda individuale'} · stagione "
                     f"{_e(stagione)}<br>Stampato il "
                     f"{datetime.now().strftime('%d/%m/%Y')}", logo_b64)
    corpo += _blocco_scheda(atleta, riga, norme, targets, sessione, stagione,
                            nuova_pagina=False, storico=storico)
    return _pagina(f"{atleta.get('cognome', '')} {sessione}", corpo)


def genera_report_squadra(atleti: pd.DataFrame, righe_test: pd.DataFrame, norme,
                          targets, sessione, stagione, squadra="", logo_b64="",
                          includi_schede=True) -> str:
    """
    Riepilogo di squadra per una sessione.
    righe_test: le righe di test_sessioni di quella sessione e stagione.
    """
    per_atleta = {r["atleta_id"]: r for _, r in righe_test.iterrows()} \
        if not righe_test.empty else {}
    testati = atleti[atleti["id"].isin(per_atleta.keys())] \
        .sort_values(["cognome", "nome"])
    mancanti_rosa = atleti[~atleti["id"].isin(per_atleta.keys())] \
        .sort_values(["cognome", "nome"])

    # ---- tabella dei risultati e dei punteggi ----
    th_ris = "".join(f'<th class="c">{db.META_TEST[c]["sigla"]}<br>'
                     f'<span style="font-weight:normal">{db.META_TEST[c]["unita"]}'
                     f'</span></th>' for c in db.ORDINE_TEST)
    th_punt = "".join(f'<th class="c">{a}</th>' for a in db.ASSI)
    r_ris, r_punt, allarmi, incompleti, ovr_tutti = "", "", [], [], []
    punti_asse = {a: [] for a in db.ASSI}

    for _, a in testati.iterrows():
        riga = per_atleta[a["id"]]
        p = db.calcola_tutti(riga, a.get("ruolo"), norme)
        ovr = db.calcola_overall(p)
        tgt = targets.get(a.get("ruolo"), {k: 70 for k in db.ASSI})
        if ovr is not None:
            ovr_tutti.append(ovr)
        for k, v in p.items():
            if v is not None:
                punti_asse[k].append(v)

        celle = ""
        for c in db.ORDINE_TEST:
            v = riga.get(c)
            rischio = ((c == "mob_kneewall" and (db.flag_mobilita(v)
                        or db.flag_mob_diff(riga.get("mob_diff"))))
                       or (c == "asi_monopodalico" and db.flag_asimmetria(v))
                       or (c == "ele_salto" and bool(db.verifica_antropometria(
                           a.get("altezza"), a.get("reach")))))
            if _vuoto(v):
                celle += '<td class="muto">·</td>'
            else:
                testo = db.formatta_valore(c, v).split(" ")[0]
                celle += f'<td class="c{" rischio" if rischio else ""}">{testo}</td>'
        r_ris += (f'<tr><td class="a">{_nome(a)}</td>'
                  f'<td class="c">{_e(str(a.get("ruolo") or ""))[:3].upper()}</td>'
                  f'{celle}</tr>')

        celle = ""
        for k in db.ASSI:
            v = p[k]
            if v is None:
                celle += '<td class="muto">·</td>'
            else:
                sotto = v < tgt.get(k, 70)
                celle += (f'<td class="c"{" style=color:#B71C1C" if sotto else ""}>'
                          f'{v}</td>')
        r_punt += (f'<tr><td class="a">{_nome(a)}</td>{celle}'
                   f'<td class="c"><b>{ovr if ovr is not None else "—"}</b></td></tr>')

        nome_a = _nome(a)
        if db.flag_mobilita(riga.get("mob_kneewall")):
            allarmi.append(f"<b>{nome_a}</b> — caviglia rigida "
                           f"({_cm(riga.get('mob_kneewall'))} cm)")
        if db.flag_mob_diff(riga.get("mob_diff")):
            allarmi.append(f"<b>{nome_a}</b> — differenza fra le caviglie "
                           f"({_cm(riga.get('mob_diff'))} cm)")
        if db.flag_asimmetria(riga.get("asi_monopodalico")):
            allarmi.append(f"<b>{nome_a}</b> — asimmetria arti inferiori "
                           f"({_cm(riga.get('asi_monopodalico'))}%)")
        _pr = db.verifica_antropometria(a.get("altezza"), a.get("reach"))
        if _pr and not _vuoto(riga.get("ele_salto")):
            allarmi.append(f"<b>{nome_a}</b> — elevazione da verificare: "
                           + _html.escape("; ".join(_pr)))

        mancano = [db.META_TEST[c]["sigla"] for c in db.ORDINE_TEST
                   if _vuoto(riga.get(c))]
        if mancano:
            incompleti.append(f"<b>{nome_a}</b>: {', '.join(mancano)}")

    # ---- giorni di misura per test ----
    giorni = []
    for c in db.ORDINE_TEST:
        gg = set()
        n = 0
        for r in per_atleta.values():
            if not _vuoto(r.get(c)):
                n += 1
                g = _giorno_test(r, c)
                if g != "—":
                    gg.add(g)
        ordinati = sorted(gg, key=lambda x: datetime.strptime(x, "%d/%m/%Y"))
        giorni.append(f'<tr><td><b>{db.META_TEST[c]["sigla"]}</b> '
                      f'{db.META_TEST[c]["label"]}</td>'
                      f'<td class="c">{n} su {len(atleti)}</td>'
                      f'<td>{", ".join(x[:5] for x in ordinati) or "—"}</td></tr>')

    medie = " · ".join(f"{k} {round(sum(v) / len(v))}" for k, v in punti_asse.items()
                       if v)

    testata = _testata(f"RISULTATI DEI TEST — {_e(sessione)}",
                       f"{_e(squadra) or 'Squadra'} · stagione {_e(stagione)}<br>"
                       f"Stampato il {datetime.now().strftime('%d/%m/%Y')}",
                       logo_b64)
    corpo = testata
    corpo += (f'<h1>Riepilogo di squadra — sessione {_e(sessione)}</h1>'
              f'<div class="kpi">'
              f'<div><b>{len(atleti)}</b><span>in rosa</span></div>'
              f'<div><b>{len(testati)}</b><span>testati</span></div>'
              f'<div><b>{round(sum(ovr_tutti) / len(ovr_tutti)) if ovr_tutti else "—"}'
              f'</b><span>overall medio</span></div>'
              f'<div><b>{len(allarmi)}</b><span>segnalazioni</span></div></div>')
    if medie:
        corpo += f'<div class="piccolo">Punteggio medio per asse: {medie}</div>'

    corpo += (f'<h2>Risultati rilevati</h2><table><thead><tr>'
              f'<th style="text-align:left">Atleta</th><th class="c">Ruolo</th>'
              f'{th_ris}</tr></thead><tbody>{r_ris}</tbody></table>'
              f'<div class="piccolo">MOB lato più limitato · ASI asimmetria in % · '
              f'in rosso i valori oltre soglia · il punto indica test non rilevato.'
              f'</div>')
    corpo += (f'<h2>Punteggi contro la norma di ruolo</h2><table><thead><tr>'
              f'<th style="text-align:left">Atleta</th>{th_punt}'
              f'<th class="c">OVR</th></tr></thead><tbody>{r_punt}</tbody></table>'
              f'<div class="piccolo">Da 30 a 99. In rosso i punteggi sotto il target '
              f'del ruolo. L\'asimmetria non entra nel punteggio.</div>')

    if allarmi:
        corpo += ('<h2>Segnalazioni di rischio</h2><div class="allarme">'
                  + "<br>".join(allarmi) + '</div>'
                  '<div class="piccolo">Soglie: dorsiflessione sotto 9 cm, differenza '
                  'fra le caviglie oltre 2 cm, asimmetria fra gli arti oltre il 10%. '
                  'Sono inneschi di approfondimento, non diagnosi.</div>')

    corpo += (f'<h2>Completezza della sessione</h2><table><thead><tr>'
              f'<th style="text-align:left">Test</th><th class="c">Atleti misurati</th>'
              f'<th style="text-align:left">Giorni di misura</th></tr></thead>'
              f'<tbody>{"".join(giorni)}</tbody></table>')
    if incompleti:
        corpo += ('<div class="nota"><b>Test ancora mancanti</b><br>'
                  + "<br>".join(incompleti) + '</div>')
    if not mancanti_rosa.empty:
        corpo += ('<div class="nota"><b>Senza alcun test in questa sessione:</b> '
                  + ", ".join(_nome(a) for _, a in mancanti_rosa.iterrows())
                  + '</div>')

    if includi_schede:
        for _, a in testati.iterrows():
            corpo += _blocco_scheda(a, per_atleta[a["id"]], norme, targets,
                                    sessione, stagione, nuova_pagina=True,
                                    testata=testata)

    return _pagina(f"Risultati {sessione} {stagione}", corpo)
