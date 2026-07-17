# more coherent self-model — Amikor a modell felismeri a saját szövegét

URL: https://arxiv.org/abs/2605.25459

## Miről szól a forrás?
A tanulmány ("From Simulation to Enaction") azt vizsgálja, hogy a poszt-tréninggel finomhangolt nyelvi modellek belső jelekben megkülönböztetik, mikor a saját generált szövegüket folytatják, és mikor kívülről kapott inputot dolgoznak fel. A szerzők szerint a modell a saját folytatásainál 3-4-szer alacsonyabb bizonytalanságot (entrópiát) mutat, és nyomon követi az utolsó bemeneti token meglepetés-értékét. A poszt-tréninges modellek ráadásul már az első kimeneti token előtt "eldöntik" a válasz témáját, mintha szándékot formálnának arról, mit fognak mondani.

## Miért hivatkozik rá a cikk?
A szerző ezzel támasztja alá, hogy a hosszú távú érvelésre és autonómiára irányuló poszt-tréning egy erősebb, koherensebb önmodellt hív életre a modellben, nem csak jobb szövegjóslást.

## Mit érdemes ebből megérteni?
A modell nem pusztán passzív szövegfolytató: kimutatható belső reprezentációja van arról, hogy éppen "saját maga" beszél, ami az önmodell egyik mérhető nyoma.
