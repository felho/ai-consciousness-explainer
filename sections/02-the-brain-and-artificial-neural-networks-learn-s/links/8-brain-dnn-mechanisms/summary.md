# mechanisms — A megerősítéses tanulás közös mechanizmusai agyban és gépben

URL: https://www.sciencedirect.com/science/article/pii/S2772528625000354

## Miről szól a forrás?
Alkam, Van Benschoten és Tarshizi áttekintő tanulmánya (2025) arról, hogyan fonódik össze a megerősítéses tanulás (RL) a neurobiológiával. A cikk bemutatja az RL alapfogalmait (ágens, környezet, jutalom, policy, érték-függvény, model-free és model-based tanulás), majd párhuzamba állítja őket az agy konkrét folyamataival. A központi tétel, hogy a dopamin a "jutalom-előrejelzési hibát" (reward prediction error) kódolja, ugyanazt a jelet, amit a gépi TD-tanulás használ, és hogy az RL számítási logikája konkrét agyi áramkörökben (bazális ganglionok, prefrontális kéreg, hippokampusz) is felismerhető.

## Miért hivatkozik rá a cikk?
A szerző ezzel támasztja alá, hogy az agy nemcsak felszíni reprezentációkat, hanem konkrét, működő mechanizmusokat is megoszt a mély neurális hálókkal. A tanulmány jó példa az "aktor-kritikus" architektúrára: a gépi modellben szétválik a döntéshozó és az értékelő, és ugyanez a kettősség megtalálható a bazális ganglionokban (a dorzális striatum választ cselekvést, a középagyi dopamin számol hibajelet).

## Mit érdemes ebből megérteni?
A kulcs, hogy a hasonlóság nem csupán analógia: ugyanaz a számítási elv (a jutalom-előrejelzési hiba alapján való tanulás) hajtja a gépi és a biológiai rendszert is. A cikk ugyanakkor óvatosságra int, mert az agy sokkal kevesebb tapasztalatból, több párhuzamos időskálán és gazdagabb jutalomjelekkel tanul, mint a mai mesterséges RL-rendszerek.
