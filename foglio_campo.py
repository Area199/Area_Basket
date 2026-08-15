"""
================================================================================
AREA199 HUMAN PERFORMANCE LAB — FOGLIO DI CAMPO STAMPABILE
================================================================================
Genera un documento HTML pronto da stampare, con una griglia per ogni test
selezionato e le righe dei soli atleti convocati.

RAGIONE D'ESSERE
----------------
Sul campo i risultati si scrivono a penna. Il software si compila dopo, con
calma. Cosi' un crash, una connessione assente o una batteria scarica non
fanno perdere nulla: il dato primario e' sulla carta.

Il foglio riporta anche il promemoria di protocollo per ogni test, cosi' chi
somministra non deve ricordarselo a memoria.

Versione 2.0 — Agosto 2026
================================================================================
"""

from datetime import date

import db_basket as db


def _intestazione_prove(col: str) -> list[str]:
    """Colonne da stampare per un test, in base alle prove previste."""
    meta = db.META_TEST[col]
    if col == "asi_monopodalico":
        return ["DX 1", "DX 2", "SX 1", "SX 2", "MIGLIOR DX", "MIGLIOR SX"]
    if col == "mob_kneewall":
        return ["DX 1", "DX 2", "SX 1", "SX 2", "MIGLIOR DX", "MIGLIOR SX"]
    n = meta["prove"]
    if n == 1:
        return ["RISULTATO"]
    return [f"PROVA {i}" for i in range(1, n + 1)] + ["MIGLIORE"]


def _tabella_test(col: str, atleti) -> str:
    meta = db.META_TEST[col]
    colonne = _intestazione_prove(col)

    th = "".join(f'<th class="c">{c}</th>' for c in colonne)
    righe = ""
    for i, (_, a) in enumerate(atleti.iterrows(), start=1):
        celle = "".join('<td class="v"></td>' for _ in colonne)
        righe += (f'<tr><td class="n">{i}</td>'
                  f'<td class="a">{a["cognome"]} {a["nome"]}</td>'
                  f'<td class="r">{str(a["ruolo"])[:3].upper()}</td>{celle}</tr>')

    return f"""
<section class="blocco">
  <div class="titolo">
    <span class="sigla">{meta['sigla']}</span>
    <span class="nome">{meta['label']}</span>
    <span class="unita">valori in {meta['unita']}</span>
  </div>
  <div class="proto">
    <b>{meta['protocollo']}</b> · prove: {meta['prove']} · recupero: {meta['recupero']}<br>
    {meta['promemoria']}
  </div>
  <table>
    <thead><tr><th class="n">#</th><th class="a">Atleta</th>
    <th class="r">Ruolo</th>{th}</tr></thead>
    <tbody>{righe}</tbody>
  </table>
</section>"""


def genera_foglio(atleti, test_scelti: list[str], data_test: date,
                  sessione: str, squadra: str = "", logo_b64: str = "") -> str:
    """Documento HTML completo, gia' impaginato per la stampa A4."""
    blocchi = "".join(_tabella_test(c, atleti)
                      for c in db.ORDINE_TEST if c in test_scelti)

    ordine = " → ".join(db.META_TEST[c]["sigla"]
                        for c in db.ORDINE_TEST if c in test_scelti)

    logo_html = (f'<img src="{logo_b64}" class="logo-soc">' if logo_b64 else "")

    return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8">
<title>AREA199 — Foglio di campo {data_test.strftime('%d-%m-%Y')}</title>
<style>
@page {{ size: A4; margin: 12mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: Arial, Helvetica, sans-serif; color: #111;
        font-size: 11px; margin: 0; background: #fff; }}

.testata {{ display: flex; justify-content: space-between; align-items: center;
            border-bottom: 3px solid #C9A227; padding-bottom: 9px;
            margin-bottom: 14px; gap: 16px; }}
.marchio {{ font-size: 21px; font-weight: bold; letter-spacing: 2px;
            white-space: nowrap; }}
.marchio small {{ display: block; font-size: 8.5px; font-weight: normal;
                  letter-spacing: 2.4px; color: #666; margin-top: 3px; }}
.logo-soc {{ max-height: 58px; max-width: 150px; object-fit: contain; }}
.dati {{ text-align: right; font-size: 11px; line-height: 1.7; }}
.dati b {{ font-size: 13px; }}

.avviso {{ background: #FAF6E8; border-left: 3px solid #C9A227;
           padding: 8px 11px; margin-bottom: 15px; font-size: 10px;
           line-height: 1.5; }}

.blocco {{ margin-bottom: 20px; page-break-inside: avoid; break-inside: avoid; }}
.titolo {{ display: flex; align-items: baseline; gap: 9px;
           border-bottom: 1px solid #333; padding-bottom: 3px; margin-bottom: 5px; }}
.sigla {{ background: #111; color: #fff; padding: 2px 8px;
          font-weight: bold; font-size: 11px; letter-spacing: 1px; }}
.nome {{ font-size: 14px; font-weight: bold; text-transform: uppercase; }}
.unita {{ font-size: 10px; color: #777; margin-left: auto; }}
.proto {{ font-size: 9.5px; color: #333; line-height: 1.45;
          margin-bottom: 6px; padding-left: 2px; }}

table {{ width: 100%; border-collapse: collapse; }}
th {{ background: #F2F2F2; border: 1px solid #999; padding: 4px 3px;
      font-size: 9px; text-transform: uppercase; letter-spacing: 0.4px; }}
td {{ border: 1px solid #999; padding: 0; height: 21px; }}
td.n {{ width: 22px; text-align: center; font-size: 10px; color: #555;
        padding: 3px; }}
td.a {{ width: 150px; padding: 3px 6px; font-size: 11px; }}
td.r {{ width: 42px; text-align: center; font-size: 9px; color: #444; padding: 3px; }}
th.n {{ width: 22px; }} th.a {{ width: 150px; text-align: left; padding-left: 6px; }}
th.r {{ width: 42px; }}
td.v {{ background: #FFF; }}
tbody tr:nth-child(even) td.a, tbody tr:nth-child(even) td.n,
tbody tr:nth-child(even) td.r {{ background: #FAFAFA; }}

.firma {{ margin-top: 26px; display: flex; justify-content: space-between;
          font-size: 10px; page-break-inside: avoid; }}
.firma div {{ border-top: 1px solid #999; padding-top: 4px; width: 30%;
              text-align: center; color: #555; }}
.pie {{ margin-top: 16px; text-align: center; font-size: 8px; color: #777;
        letter-spacing: 1px; text-transform: uppercase;
        border-top: 1px solid #DDD; padding-top: 7px; }}

.stampa {{ position: fixed; top: 14px; right: 14px; background: #C9A227;
           color: #111; border: none; padding: 11px 22px; font-weight: bold;
           font-size: 13px; border-radius: 4px; cursor: pointer; z-index: 99; }}
@media print {{ .stampa {{ display: none; }} }}
</style></head>
<body>

<button class="stampa" onclick="window.print()">STAMPA</button>

<div class="testata">
  <div class="marchio">AREA199<small>HUMAN PERFORMANCE LAB</small></div>
  {logo_html}
  <div class="dati">
    <b>FOGLIO DI RILEVAZIONE — {sessione}</b><br>
    {squadra or 'Squadra'} · {data_test.strftime('%d/%m/%Y')}<br>
    Atleti convocati: {len(atleti)}
  </div>
</div>

<div class="avviso">
  <b>Ordine di esecuzione: {ordine}</b> — dal meno al piu' affaticante.
  Invertirlo altera i risultati e rende il confronto con il retest privo di valore.<br>
  Riscaldamento standardizzato di 15 minuti prima del primo test,
  <b>identico anche al retest</b>. Si registra la prova migliore.
  Una prova nulla si ripete, non si stima.
</div>

{blocchi}

<div class="firma">
  <div>Rilevatore</div><div>Cronometrista</div><div>Data e ora fine sessione</div>
</div>

<div class="pie">
  AREA199 — Human Performance Lab · Dott. Antonio Petruzzi ·
  Documento di lavoro, da trascrivere nel sistema a fine sessione
</div>

</body></html>"""
