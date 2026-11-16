# Ricerche pezzi scooter

Ogni ricerca è un titolo `##` seguito da un elenco. Modifica, aggiungi o cancella
liberamente: il file viene riletto a ogni giro (una volta all'ora).

Campi disponibili:

- `cerca` — le parole da cercare sui siti; più varianti separate da `;`
- `spagnolo` — varianti in spagnolo, cercate solo su Vinted e Wallapop
  (molti venditori sono spagnoli); più varianti separate da `;`
- `wallapop` (o `vinted`, `subito`, `ebay`) — varianti in più solo per quel sito
- `prezzo` — fascia in euro, es. `20-80`; un solo numero vale come massimo
- `siti` — facoltativo, es. `vinted, subito`; se manca cerca su tutti e quattro
- `escludi` — facoltativo, parole che NON devono comparire nel titolo
- `obbligatorie` — facoltativo, altre parole che DEVONO comparire nel titolo;
  `polini/malossi` significa "almeno una delle due"
- `titolo: libero` — facoltativo, toglie la regola qui sotto

Regola di pertinenza: un annuncio passa solo se nel titolo ci sono TUTTE le parole
della variante di `cerca` che lo ha trovato (singolare/plurale è uguale, `50` vale anche `50cc` ma non `150`).
Quindi in `cerca` metti solo le parole che identificano il pezzo: ogni parola in
più restringe i risultati.

## Regole per tutte le ricerche

Non è una ricerca: le parole qui sotto vengono escluse da TUTTE le ricerche.
Servono a togliere scooter grossi, Vespa/Ape/Ciao, moto a marce e roba che non c'entra.

- escludi: tmax, xmax, vespa, ape, ciao, sh, beverly, majesty, burgman, 125, 150, 155, 180, 200, 250, 300, 400, 500, 530, 560, 600, am6, derbi, kawasaki, ninja, auto, mercedes

Accessori: se una di queste parole compare nel titolo PRIMA del pezzo cercato, l'annuncio viene
scartato ("Rulli variatore Malossi", "Molla per variatore", "Collettore carburatore 21").
Se viene dopo resta ("Variatore Malossi con rulli").

- accessori: rulli, rullo, molla, molle, cinghia, semipuleggia, puleggia, mozzo, guida, cursori, boccola, calotta, coperchio, copri, tappo, guarnizione, guarnizioni, paraolio, cuscinetto, cuscinetti, getti, getto, spillo, galleggiante, vaschetta, collettore, manicotto, funghetto, filtro, cornetto, staffa, attacco, supporto, protezione, paracalore, silenziatore, adesivo, adesivi, estrattore, chiave, attrezzo, blocca, bullone, viti, vite, perno, dado, pistone, fasce, segmenti, spinotto, gabbia, testa, testata, tubo, tubi, ventola, convogliatore, sensore, termostato, pompa, revisione, cavo, candela, pipetta, rodillos, muelle, muelles, correa, junta, juntas, tapa, soporte, chicle, chicles, colector, protector, pegatina, piston

## Variatore Malossi

- cerca: variatore malossi
- spagnolo: variador malossi
- prezzo:

## Marmitta Shot V4

- cerca: shot v4
- prezzo:

## Marmitta Polini

- cerca: marmitta polini; espansione polini
- spagnolo: escape polini
- escludi: protezione, paracalore, guarnizione, molla, staffa, protector, junta, muelle, soporte
- prezzo:

## Marmitta da restaurare

- cerca: marmitta da restaurare
- spagnolo: escape para restaurar
- obbligatorie: scooter/50/70/minarelli/piaggio/aerox/booster/zip/nrg/runner/typhoon/f12/f10/phantom/bws/nitro/stalker/neos/jog/2t
- prezzo:

## Marmitta Arrow

- cerca: marmitta arrow; espansione arrow
- spagnolo: escape arrow
- obbligatorie: scooter/50/70/minarelli/piaggio/aerox/booster/zip/nrg/runner/typhoon/f12/f10/phantom/bws/nitro/stalker/neos/jog/2t
- prezzo:

## Marmitta Leovince ZX

- cerca: leovince zx; marmitta zx
- spagnolo: escape leovince zx
- prezzo:

## Marmitta Leovince TT

- cerca: leovince tt; marmitta tt
- spagnolo: escape leovince tt
- prezzo:

## Marmitta Roost

- cerca: roost
- obbligatorie: marmitta/espansione/scarico/escape/silenziatore
- prezzo:

## Carburatore 21

- cerca: carburatore 21
- spagnolo: carburador 21
- escludi: collettore, funghetto, coperchio, manicotto, guarnizione, getti, cavo, revisione, colector, tapa, junta, chicle, admision
- prezzo:

## Carburatore 19

- cerca: carburatore 19
- spagnolo: carburador 19
- escludi: collettore, funghetto, coperchio, manicotto, guarnizione, getti, cavo, revisione, colector, tapa, junta, chicle, admision
- prezzo:

## Carburatore Dellorto VHST 24 / 26 / 28

- cerca: vhst 24; vhst 26; vhst 28
- prezzo:

## Carburatore PWK 24 / 26 / 28 / 30

- cerca: pwk 24; pwk 26; pwk 28; pwk 30
- prezzo:

## Carburatore Lectron

- cerca: lectron
- obbligatorie: carburatore/carburador/carb/carbu
- prezzo:

## Carburatore Dellorto VHSH

- cerca: vhsh
- prezzo:

## Campana Polini 107

- cerca: campana polini 107
- prezzo:

## Campana Stage6

- cerca: campana stage 6
- prezzo:

## Correttore di coppia Malossi

- cerca: correttore malossi
- spagnolo: corrector malossi
- prezzo:

## Correttore di coppia Polini

- cerca: correttore polini
- spagnolo: corrector polini
- prezzo:

## Correttore di coppia 2Fast

- cerca: correttore 2fast
- spagnolo: corrector 2fast
- prezzo:

## Correttore di coppia Stage6

- cerca: correttore stage 6
- spagnolo: corrector stage 6
- prezzo:

## Radiatore Aerox

- cerca: radiatore aerox
- spagnolo: radiador aerox
- prezzo:

## Accensione Selettra / rotore interno

- cerca: selettra; accensione rotore interno malossi; accensione rotore interno italkit
- spagnolo: encendido rotor interno malossi; encendido rotor interno italkit
- obbligatorie: malossi/italkit/accensione/rotore/statore/mhr
- escludi: pane, selettrice
- prezzo:

## Accensione PVL

- cerca: pvl
- spagnolo: encendido pvl
- obbligatorie: accensione/rotore/statore/encendido/stage6/polini/minarelli/piaggio
- prezzo:

## Accensione Italkit

- cerca: accensione italkit
- spagnolo: encendido italkit
- prezzo:

## Carter Piaggio braccio lungo a disco

- cerca: carter piaggio braccio lungo; carter piaggio disco
- spagnolo: carter piaggio brazo largo
- escludi: copri, coperchio, tamburo, aria, tapa, tambor, aire
- prezzo:

## Carter Minarelli orizzontale a disco

- cerca: carter minarelli disco
- escludi: copri, coperchio, tapa
- prezzo:

## Carter Zip SP

- cerca: carter zip sp
- escludi: copri, coperchio, tapa
- prezzo:

## Cilindro DR

- cerca: cilindro dr; gruppo termico dr
- prezzo:

## Cilindro Malossi MHR 6 travasi

- cerca: cilindro malossi 6t; cilindro malossi 6 travasi; gruppo termico malossi 6t
- spagnolo: kit cilindro malossi 6 transfer
- prezzo:

## Cilindro Malossi 7 travasi

- cerca: cilindro malossi 7t; cilindro malossi 7 travasi; gruppo termico malossi 7t
- spagnolo: kit cilindro malossi 7 transfer
- prezzo:

## Cilindro Polini Evolution (1 e 3)

- cerca: cilindro polini evolution; cilindro polini evo; gruppo termico polini evo
- prezzo:

## Cilindro Top Performances Due Plus

- cerca: cilindro due plus; cilindro 2 plus; gruppo termico due plus
- spagnolo: kit cilindro top 2 plus
- prezzo:

## Cilindro Stage6 Streetrace

- cerca: cilindro street race; cilindro streetrace; gruppo termico street race
- prezzo:

## Cilindro Polini Corsa

- cerca: cilindro polini corsa; gruppo termico polini corsa
- prezzo:
