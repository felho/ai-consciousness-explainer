# mesa-optimization — Amikor a betanított modell maga is optimalizálóvá válik

URL: https://arxiv.org/abs/1906.01820

## Miről szól a forrás?
Ez a tanulmány (Hubinger és társai) vezeti be a "mesa-optimalizáció" fogalmát: azt az esetet, amikor egy betanított modell (például egy neurális háló) maga is optimalizálóvá válik a tanítás során. Két fő kérdést jár körül: milyen feltételek mellett jelenik meg ez a jelenség, és ha megjelenik, mennyiben tér el a modell saját célja attól a veszteségfüggvénytől, amelyre tanították. Ez a belső célok illesztésének (inner alignment) problémája.

## Miért hivatkozik rá a cikk?
A szerző ezzel támasztja alá, hogy a kontextusban tanuló, célkövető ágensek maguk is optimalizálók, ezért a külső optimalizálónak (evolúció vagy gradiensereszkedés) szüksége van valamilyen mechanizmusra a belső illesztés kikényszerítésére.

## Mit érdemes ebből megérteni?
Egy optimalizáló betanítása nem garantálja, hogy a keletkező optimalizáló a szándékolt célt fogja követni, és éppen ez a rés indokolja a fájdalomhoz hasonló valenciák szerepét.
