# Come verificare l’iscrizione RUI di una società di intermediazione

Un broker riceve il numero RUI di una società con cui sta per lavorare. Prima di aprire la pratica deve verificare che il numero corrisponda alla denominazione comunicata, che la società risulti operativa e a quale data si riferisca il riscontro. Per una verifica singola può consultare gratuitamente il registro intermediari assicurativi di IVASS. BeyondForge restituisce gli stessi riferimenti della fonte in campi strutturati, utili a chi deve documentare il controllo nel proprio gestionale. [Registro ufficiale IVASS](https://www.ivass.it/consumatori/rui/)

## Verifica una società con il suo numero di iscrizione RUI

1. Apri la pagina dell’Actor, seleziona la modalità di verifica e la ricerca per numero RUI. Inserisci il solo numero societario fornito dalla controparte. Mantieni attivi i metadati della fonte. Per utilizzare la versione provata su questo percorso, apri direttamente l’Actor e lascia la build predefinita 0.2.1. [Apri RUI IVASS](https://apify.com/beyondforge/rui-ivass-insurance-intermediaries)
2. Prima dell’avvio controlla listino e limite di spesa. Nel caso verificato a 1.024 MiB gli eventi nominali sono **0,030 USD per l’avvio** e **0,001 USD per una verifica con una sola unità**, anche con un esito valido senza corrispondenze. Il totale di questo caso è **0,031 USD**. Una verifica con più corrispondenze può comportare più unità. Controlla memoria, prezzi, condizioni del tuo account e risorse applicabili prima di avviare lavori diversi. [Listino BeyondForge su Apify](https://apify.com/beyondforge/rui-ivass-insurance-intermediaries/pricing)
3. Leggi `matchStatus`, `matchCount` e il primo elemento di `matches`. Per il caso univoco controlla che `matchStatus` valga `exact_unique`, che `matchCount` sia 1 e che `entityType` sia `company`. Confronta `ruiNumber`, `displayName`, `section` e `operational` con la pratica. Se uno di questi dati diverge, passa la pratica a una persona che possa riscontrarla sul portale IVASS.
4. Annota `source.provider`, `source.snapshotDate` e `source.retrievedAt`. Il primo identifica la fonte. Il secondo indica la data dei dati. Il terzo indica quando l’Actor li ha acquisiti. Conserva i soli campi necessari, con accessi e scadenza stabiliti dalla tua organizzazione.

### Quale build usare per questa pratica

Le Task con selettore 0.2.1 sono `cerca-iscritti-rui-ivass`, `esporta-il-registro-rui-ivass`. Il tag `latest` (build storica 0.0.17) resta fissato su `crea-profilo-completo-intermediario-rui`, `esporta-relazioni-e-collaboratori-rui`, `monitora-variazioni-rui-ivass`, `verifica-iscrizione-rui-per-numero`. Il preset pubblico di verifica per numero riguarda una persona fisica. Per il controllo descritto qui usa direttamente l’Actor con la build predefinita 0.2.1 e il numero della società ricevuto dalla tua controparte.

### Come leggere l’assenza di risultati

Una verifica per dominio con `matchStatus=not_found` e `matchCount=0` indica che il dominio non compare nell’elenco dei siti di quello snapshot. L’impresa può comunque essere iscritta al RUI. Usa il numero societario e verifica presso IVASS prima di una decisione sulla controparte. Un errore o un timeout della fonte lascia la pratica in stato **verifica da effettuare**. [Fonte IVASS](https://www.ivass.it/consumatori/rui/)

### Esempi gratuiti offline

La [ricevuta sintetica](verifica-societaria-sintetica.json) illustra i campi utili di un esito positivo e di un dominio assente. La [scheda per la pratica](scheda-verifica-societaria.xlsx) e il [caso DEMO-01](caso-societario.json) illustrano anche il precedente esempio di ricerca di una sola società operativa. Tale ricerca generica estrae una riga dal registro e richiede un confronto successivo con l’identità dichiarata dalla controparte. Tutti questi file si aprono senza account e senza costi.

### Fonte e portata delle prove

IVASS pubblica i dati del RUI con aggiornamento giornaliero. BeyondForge è il fornitore indipendente dell’Actor e dichiara nel README le normalizzazioni e le unioni dei dati. Conserva la titolarità IVASS, la provenienza, la licenza e l’indicazione delle trasformazioni quando condividi dati adattati. La verifica cloud documentata sulla build 0.2.1 ha riguardato un solo numero univoco di società operativa e un solo dominio riservato senza risultati su account Free. Il percorso Paid non è stato collaudato in cloud. L’uso nella propria organizzazione è soggetto alle condizioni del conto Apify. Per le decisioni professionali consulta il registro ufficiale. [Scheda dell’Actor e nove distribuzioni](https://apify.com/beyondforge/rui-ivass-insurance-intermediaries) · [Licenza CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.it)
