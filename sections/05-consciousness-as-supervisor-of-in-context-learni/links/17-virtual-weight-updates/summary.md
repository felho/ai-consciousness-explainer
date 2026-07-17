# virtual weight updates — Lineáris transzformerek mint gyorssúly-programozók

URL: https://arxiv.org/abs/2102.11174

## Miről szól a forrás?
A tanulmány (Schlag, Irie, Schmidhuber) formális kapcsolatot mutat ki a modern lineáris figyelmi mechanizmusok és a kilencvenes évekből származó "gyorssúly-programozók" (Fast Weight Programmers) között. Eszerint a lineárisan közelített önfigyelem lényegében egy másik hálózat "gyorssúlyait" programozza át menet közben, azaz virtuális, ideiglenes súlyfrissítéseket hajt végre a kulcs-érték leképezésben, anélkül hogy a modell tényleges (tanított) súlyai megváltoznának.

## Miért hivatkozik rá a cikk?
A szerző erre hivatkozva állítja, hogy a transzformer kontextuson belüli tanulása virtuális súlyfrissítéseken keresztül működik, ami magyarázza, hogyan képes a modell egy egyébként befagyasztott hálózattal is alkalmazkodni.

## Mit érdemes ebből megérteni?
A transzformer úgy "frissíti a súlyait" a kontextuson belül, hogy valójában csak átmeneti, virtuális súlyokat programoz, ami arra utal, hogy a tudatos, pillanatnyi tanulás összeegyeztethető egy változatlan alaphálózattal.
