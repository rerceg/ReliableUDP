# ReliableUDP
Klasa ReliableUDP izrađena je uz diplomski rad "Transportni sloj računalne mreže". Koristimo UDP socket za komunikaciju između dva uređaja, ali nadograđujemo standardno UDP zaglavlje sa sljedećim zaglavljem kojeg pohranjujemo u payload UDP segmenta.
<pre>
                           +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
                           |                        Sequence Number                        |
                           +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
                           |                    Acknowledgment Number                      |
                           +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
                           | Option|A|P|R|S|F|                               |
                           | length|C|S|S|Y|I|        Window size            |
                           |       |K|H|T|N|N|                               |
                           +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
                           |                    Options                    |    Padding    |
                           +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
                           |                             data                              |
                           +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
</pre>
Uz pomoć ovog nadograđenog zaglavlja postižemo sljedeće funkcionalnosti:
<li>potvrda primljenih segmenata</li>
<li>kontrola toka</li>
<li>kontrola veličine segmenta</li>
<li>identificiranje izgubljenih ili korumpiranih segmenata</li>
<br>
Osim navedenih funkcionalnosti, ova implementacija brine o zakrčenosti mreže kao i o ponovnom slanju izgubljenih ili korumpiranih segmenata. Primjer korištenja ove klase može se vidjeti u datotekama "senderMain.py" i "receiverMain.py".
