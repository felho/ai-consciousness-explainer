# gradient learning — A transzformerek kontextuson belüli gradiens-tanulása

URL: https://arxiv.org/abs/2212.07677

## Miről szól a forrás?
A tanulmány (von Oswald és munkatársai) azt mutatja meg, hogy a transzformerek kontextuson belüli tanulása (in-context learning) matematikailag egyenértékű a gradiensalapú optimalizálással. Bizonyítják, hogy egyetlen lineáris önfigyelmi (self-attention) réteg által végzett adattranszformáció megfelel egy gradiens-lépésnek a regressziós hibán. A betanított transzformerek "mesa-optimalizálóvá" válnak, vagyis a saját előreterjesztési lépésükön belül gradiens-tanulást hajtanak végre.

## Miért hivatkozik rá a cikk?
A szerző ezzel támasztja alá, hogy a transzformer erős kontextuson belüli tanulási képessége az önfigyelmi mechanizmusban rejlik, amely lényegében gradiens-tanulást valósít meg a kontextuson belül, valódi súlyfrissítés nélkül.

## Mit érdemes ebből megérteni?
A modell képes menet közben, egyetlen lefutáson belül "tanulni" úgy, hogy közben a súlyai nem változnak, ami közeli párhuzama az agy pillanatnyi, munkamemóriára támaszkodó tanulásának.
