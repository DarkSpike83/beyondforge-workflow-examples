# Verifica iscrizione Albo Gestori Ambientali prima dell’affidamento

Cerca un’impresa negli elenchi dell’Albo per nome e sezione. Un esempio per chi qualifica fornitori e vuole risalire alle categorie restituite dalla fonte ufficiale.

![Albo Gestori Ambientali — parametri della ricerca](figures/albo-gestori-ambientali.png)

## Come provarlo

1. Apri l’esempio con la ricerca per denominazione. L’input allegato limita l’estrazione a un risultato in Emilia Romagna.
2. Confronta denominazione, identificativi, sezione e categorie della riga con il fornitore che devi valutare. In caso di omonimia ripeti una ricerca mirata con il codice fiscale o la partita IVA dell’impresa.
3. Annota la data e controlla la scheda negli elenchi ufficiali prima della decisione. Nel `RUN_SUMMARY`, `maxResults` indica che il limite ha interrotto la ricerca. `endOfResults` identifica la fine dei risultati.

La figura mostra i parametri della ricerca di esempio. Il registro può cambiare; una singola riga non costituisce certificazione e il filtro per nome può includere omonimi.

## Piani e addebiti

Il piano Free ammette fino a 10 record. Il limite richiesto può arrivare a 10.000 su Paid. Il listino prevede 0,005 USD per record e 0,00005 USD per avvio a 256 MB.

**Una ricerca vuota basta per escludere un fornitore?** Verifica l’esito della run, la sezione e gli identificativi. Una fonte indisponibile richiede un nuovo controllo. Per l’atto di qualificazione consulta il registro ufficiale.

## API e agenti AI

Questa richiesta GET legge la scheda pubblica senza avviare il servizio.

```sh
curl --fail --silent --show-error "https://api.apify.com/v2/actors/beyondforge~albo-gestori-ambientali"
```

Con Apify MCP puoi chiedere

> Usa fetch-actor-details per beyondforge/albo-gestori-ambientali. Riassumi filtri di ricerca, limiti e tariffa dell’Actor. Mostrami lo schema senza avviare una run.

[Apri la ricerca per nome in Emilia Romagna](https://apify.com/beyondforge/albo-gestori-ambientali/examples/cerca-azienda-albo-gestori-ambientali-emilia-romagna) · [Input di esempio](inputs/albo-gestori-ambientali.json) · [Apify Store](https://apify.com/beyondforge/albo-gestori-ambientali) · [Apify MCP](https://docs.apify.com/mcp) · [Elenchi ufficiali dell’Albo](https://www.albonazionalegestoriambientali.it/Public/ElenchiIscritti)

Prima di avviare l’Example Task, verifica che il campo `maxResults` sia impostato a **1**. La lettura della guida e dell’input è gratuita.

## Dal primo controllo al lotto professionale

Con i prezzi pubblici verificati il 27 novembre 2026, ogni record di iscrizione distinto salvato costa **0,005 USD**. A 256 MiB l’avvio costa **0,00005 USD**. Un’impresa può avere più record. Gli esempi sotto ipotizzano un’unica esecuzione e il numero indicato di record effettivamente consegnati. [Scheda e prezzi Apify](https://apify.com/beyondforge/albo-gestori-ambientali)

| Record consegnati | Calcolo degli eventi commerciali | Totale nominale | Piano sufficiente per il limite |
|---:|---|---:|---|
| 1 | 1 × 0,005 + 0,00005 | **0,00505 USD** | Free |
| 10 | 10 × 0,005 + 0,00005 | **0,05005 USD** | Free |
| 100 | 100 × 0,005 + 0,00005 | **0,50005 USD** | Paid |

Il piano Free consente fino a 10 record per run e usa lo stesso listino. Il piano Paid consente di richiederne fino a 10.000 per run. Per un incarico superiore a 10 record scegli un’unica ricerca Paid con il limite e il budget necessari. Prima di un lotto verificare in Console il credito, il preventivo per le impostazioni selezionate e il numero massimo di risultati.

### Dalla riga alla scheda fornitore

Estratto **interamente sintetico** di una riga del dataset. Il nome e il numero sono dimostrativi.

```json
{
  "companyName": "Società Dimostrativa A",
  "registrationNumber": "DEMO-001",
  "categories": ["4"],
  "hasSuspendedCategory": false,
  "retrievedAt": "2026-01-15T09:00:00Z",
  "sourceUrl": "https://www.albonazionalegestoriambientali.it/Public/ElenchiIscritti"
}
```

L’ufficio acquisti associa la riga alla pratica solo dopo avere confrontato denominazione e numero con i documenti del fornitore. In caso di omonimia usa il codice fiscale o la partita IVA in una ricerca puntuale. `retrievedAt` è la data di consultazione. Per accertare validità, scadenze e idoneità della categoria all’attività da affidare, apri la scheda ufficiale e registra il riscontro nella pratica. `hasSuspendedCategory: false` indica soltanto che nelle categorie restituite non è stata rilevata una dicitura di sospensione.

Per qualificare un portafoglio, puoi ottenere in un’unica ricerca Paid le iscrizioni della regione o provincia pertinente e riconciliarle con gli identificativi dei tuoi fornitori nel tuo gestionale. Se l’incarico richiede verifiche nominative, la modalità `company` accetta una sola `query` per avvio. Il costo di 100 righe in tabella vale per **una sola ricerca** che consegna 100 iscrizioni. Più ricerche distinte hanno ciascuna il proprio avvio.

## Quando ripetere la verifica

Un controllo ha senso quando entra un nuovo trasportatore, cambia il servizio richiesto o scade la qualifica interna del fornitore. Conserva nel fascicolo aziendale la data e la scheda ufficiale consultata. Al controllo successivo acquisisci una nuova osservazione e documenta le differenze pertinenti. Per provare il servizio basta una verifica mirata su un’impresa e sui dati necessari all’affidamento.


[Leggere il riepilogo in n8n](../delivery-receipts/README.md#n8n)
