# Turing machines — Neural Turing Machines (Graves, Wayne, Danihelka, DeepMind, 2014)
URL: https://ar5iv.labs.arxiv.org/html/1410.5401

## Miről szól a forrás?
A DeepMind kutatói egy olyan architektúrát mutatnak be, amely egy neurális hálózatot külső memóriával egészít ki, hasonlóan ahhoz, ahogy egy számítógép a RAM-ot használja. A hálózat (a "vezérlő") olvasó- és írófejeken keresztül fér hozzá a memóriához, és mivel az egész rendszer differenciálható, a szokásos tanítási módszerekkel, példákból tanul. A kísérletekben a rendszer egyszerű algoritmusokat sajátított el pusztán bemenet-kimenet párokból: másolást, ismételt másolást, asszociatív felidézést és prioritás szerinti rendezést. A megtanult eljárások ráadásul általánosítottak is, például a másolást a tanítottnál jóval hosszabb sorozatokon is helyesen végezte el, ahol egy sima LSTM hálózat elbukott.

## Miért hivatkozik rá a cikk?
A szekció a konnekcionisták (az agy mint statisztikai tanulógép) és a szimbolisták (az agy mint szimbólumokon műveleteket végző Turing-gép) régi vitáját írja le, és amellett érvel, hogy a két nézet nem áll szemben egymással. A Neural Turing Machines cikk erre konkrét bizonyíték: megmutatja, hogy egy statisztikailag tanuló neurális hálózat képes Turing-gépszerű, algoritmikus műveleteket megtanulni és végrehajtani.

## Mit érdemes ebből megérteni?
A neurális hálózatok és a szimbolikus számítás nem két összeegyeztethetetlen világ: egy tanuló hálózat képes belül algoritmusokat, akár programszerű eljárásokat kialakítani. Ez alátámasztja az esszé tágabb gondolatmenetét, miszerint az agy egyszerre lehet statisztikai tanulógép és szimbolikus műveletek végrehajtója, a kettő ugyanannak a gépezetnek két arca.
