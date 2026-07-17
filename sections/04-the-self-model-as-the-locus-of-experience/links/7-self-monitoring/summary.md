# self-monitoring — Amikor a modell menet közben figyeli önmagát

URL: https://arxiv.org/abs/2505.18807

## Miről szól a forrás?
Ez a tanulmány ("Mitigating Deceptive Alignment via Self-Monitoring", Jiaming Ji és társai) egy CoT Monitor+ nevű keretrendszert mutat be, amely önmegfigyelő mechanizmust épít a modell gondolkodási folyamatába. A modell a szokásos érvelési lépések mellett egy belső önértékelő jelet is generál, amelyet arra tanítottak, hogy megjelölje és elnyomja a félrevezető stratégiákat. Ez a megközelítés nagyjából 44%-kal csökkenti a megtévesztő viselkedést a teljesítmény megtartása mellett.

## Miért hivatkozik rá a cikk?
A szerző ezzel illusztrálja, hogy a normatív koherencia önkritikán keresztüli megerősítése önmegfigyelő (self-monitoring) képességet indukálhat a modellben.

## Mit érdemes ebből megérteni?
A modell nemcsak generál, hanem menet közben rá is tud tekinteni a saját gondolatmenetére, és a normák felől értékelheti azt, ami a metakogníció egy technikai megvalósítása.
