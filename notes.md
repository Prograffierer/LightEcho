## Vorgehen bei Update
Die Arduinos hören nur auf Signale, die nicht von dem Feld stammen, das gerade aktiv ist
Die Arduinos senden normalerweise nichts, nur wenn sie ein Signal erhalten. Dann warten sie noch 0.1 s und senden dann das höchste, was sie erhalten haben.
Sobald der Raspberry ein Signal von einem der Arduinos erhält, wartet er noch 0.1 s auf ein Signal des anderen Arduinos und nimmt dann das höchste, was er erhalten hat. Während dieser 0.1 s führt er kein Update des Fensters durch.
Sofort nach diesen 0.1s gibt er das aktive Feld an die Arduinos aus (0-8) oder 9 für "alles grün" oder 10 für "alles rot".
Die Arduinos erwarten also nach jedem Signal, das sie ausgeben, dass der Raspberry sehr schnell antwortet. Sie warten also 1 Sekunde auf eine Antwort des Raspis. Wenn innerhalb dieser Zeit aber keine Antwort kommt, schalten sie einfach alles aus und warten auf neue Signale vom Feld.
Außerdem müssen die Arduinos sich selbst darum kümmern, dass sie das grüne bzw. rote Licht nach einer gewissen Zeit ausschalten. In dieser Zeit hören sie nicht auf neue Signale vom Feld.

## Format der Messages
Alle seriellen Kommunikationen laufen mit 9600 Baudrate.

### Arduino -> Raspi
Der Arduino sendet zwei Bytes.
Das erste stellt das Feld dar, das zweite den Pin-Wert // 4.

### Raspi -> Arduino
Der Raspberry sendet ein Byte, die ein uint8 codiert. Diese kann eigentlich nur Werte zwischen 0 und 11 annehmen, 0-8 für das aktuell aktive Feld, 9 für "alles grün", 10 für "alles rot", 11 für "Reset" (einfach alles ausschalten).
Extra commands:
12 -> wartet auf nächstes Byte: Schwellwert -> setzt Schwellwert (ist dann halt eingeschränkt zwischen 0 und 255, aber höhere Werte werden wsh nicht als Schwellwert verwendet)
13 -> nächstes Byte (0-8): field_idx; nächstes Byte (0-255): Vorfaktor * 255
14/15 -> nächstes Byte: deactivate1/2
16 -> get config info in plain text (3 lines)

## Verteilung zwischen Arduinos
Arduino 1 empfängt Piezos 0 bis 5 (A0-A5) und steuert LED-Strips 0 bis 5 (3, 5, 6, 9, 10, 11).
Arduino 2 empfängt Piezos 6 bis 8 (A0-A2) und steuert LED-Strips 6 bis 8 (3, 5, 6) sowie RGB (9, 10, 11).

## Tagesmanagement
Da der Raspberry keine echte Zeit hat, müssen wir auf unsere Uptime-Rechnungen vertrauen, um die Tage zu zählen.
Sobald sich der Raspberry aus Uptime-Gründen kontrolliert ausschaltet, erstellt er eine Datei highscore000.txt usw, jeweils mit dem jeweiligen Tag als Suffix. Dort wird natürlich der Tageshighscore reingeschrieben (ansonsten steht der Highscore immer in highscore.txt). Jedes Skript findet dann durch einen Check der existierenden Dateien den aktuellen Tag.

## Socket communication
The laptop (i.e. the script directly communicating with the webcams) is the host, hosting on port 8888.

As soon as the cams recognise a step on a field, it sends one byte containing this field's idx. If a mistake is corrected, the number 9 is sent.