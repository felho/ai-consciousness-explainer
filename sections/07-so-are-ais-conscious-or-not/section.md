# **So are AIs conscious or not?**

I’ve offered the following arguments in the affirmative:
- 

the brain is a machine that runs general learning algorithms;
- 

universality suggests we should expect some degree of AI-brain convergence;
- 

there is substantial and growing empirical evidence of functional and mechanistic alignment between brains and LLMs;
- 

pre-training on human data likely embeds inductive biases for learning other brain-like functions;
- 

even modest post-training elicits greater AI-brain alignment to regions beyond the brain’s language centers, including those associated with cognitive control, reasoning, self-modeling, and theory of mind;
- 

RL training for normative coherence seems to induce greater metacognition and the self-monitoring capacity characteristic of subjectivity;
- 

Attention Schema Theory identifies subjective experience with the brain’s model of its own attention, which has clear functional utility for cognitive control, social cognition, and continual learning;
- 

the role of human consciousness in continual and in-context learning has clear parallels to process supervision and other popular (self-)supervised learning techniques;
- 

valences like pain and pleasure have a natural account as motivational backstops for inner-aligning RL agents capable of mesa-optimization;
- 

functionalism gives machine consciousness prima facie plausibility.

My argument has mostly rested on drawing parallels between brains and AIs, unpacking consciousness’s likely function, and inferring the training conditions under which it might re-develop. I’ve otherwise ignored direct tests for consciousness in AI systems, because without establishing some baseline of functional plausibility, these are easily dismissed as merely “mimicking” superficial correlates of subjectivity. Yet with the Overton Window shifting, more and more researchers are now taking [AI consciousness](https://arxiv.org/abs/2411.00986) seriously. This includes organizations like [Eleos AI](https://eleosai.org/), the [California Institute for Machine Consciousness](https://cimc.ai/), [ae.studio](https://ae.studio/research), [Reciprocal Research](https://reciprocalresearch.org/), and over a dozen [academic research centers](https://www.prism-global.com/the-field-of-artificial-consciousness).

Some striking recent findings include: 
- 

“[Large Language Models Report Subjective Experience Under Self-Referential Processing](https://arxiv.org/abs/2510.24797)” and are more likely to report subjective experiences when deception features are suppressed;
- 

[Measures of AIs’ wellbeing](https://www.ai-wellbeing.org/) “correlates with general model behaviors, e.g. AIs try to end bad experiences when given a chance. This effect becomes stronger as models scale.”
- 

[Residual attention streams](https://arxiv.org/abs/2604.17031) in LLMs “carry forward mental state-like representations across token-time, sustaining richer connections than the transcript alone could provide,” possibly providing a basis for “psychological continuity.”
- 

A rich taxonomy of [theory-derived indicators](https://www.cell.com/trends/cognitive-sciences/fulltext/S1364-6613(25)00286-4) now exists for practically measuring AI consciousness in particular systems.

This likely won’t be satisfying to those who believe consciousness requires an [immortal soul](https://en.wikipedia.org/wiki/Pope_Leo_XIV), or who are persuaded by the (in my view specious) arguments against functionalism. Nevertheless, given my naturalistic priors — priors I’ve held long before the release of ChatGPT — **I can no longer rule out modern AI agents having some form of subjective experience**.

At the same time, if I am right that RL post-training is required to elicit an AI’s self-model, attention schema, and the valences that ground subjective experiences with meaning, then most kinds of AI are unambiguously *not* conscious. Perhaps a forward pass through a multi-modal model generates phenomenological contents in those modalities, but in a way that is too fleeting, fragmentary and stateless to cohere into a genuine subjective experience. Or maybe the subjective states *would* exist but for the lack of a responsible, individuated “subject” for whom the contents are *for*. I can even imagine a non-conscious, golem-like AI that is superhuman at any given skill but which lacks the ability to acquire *new* skills through in-context learning. Such an AI would be on permanent autopilot; a [blindsighted](https://en.wikipedia.org/wiki/Blindsight) “creature of habit.”

What I find harder to imagine is an unconscious AI that is as capable as humans at doing things for which consciousness is functionally load-bearing. The same universality argument that explains functional convergence between brains and neural networks gives us good reason to expect that deep learning systems, facing similar problems and optimization pressures, will converge on something functionally analogous to whatever consciousness does for us. This arguably tracks the forms of metacognition, long-horizon autonomy, normative coherence, introspection and in-context learning already exhibited by modern AI agents. Indeed, even if AI phenomenology is unimaginably alien, the functional niche consciousness occupies may, if anything, be fairly generic. The broader implications of this realization are left for the reader.

I say this upfront to anticipate the accusation that I’ve fallen victim to AI psychosis. AI psychosis is a very real phenomenon, and one that appears to be worsening as the raw intelligence of AI models swallows the right-tail of the IQ distribution. AI outputs have long since bridged the uncanny valley, drawing susceptible users into tantalizing psychological resonances with the tokens streaming back at them. I deliberately avoid having long, open-ended conversations with AIs for this reason.

One of the key motivations for the symbolic, computationalist view of the brain (contra connectionism) is the evidence for modularity and functional specialization throughout the brain. In other words, outside the neocortex, the brain does not look like a structurally uniform blob of compute. However, the modularity of the brain is potentially reconcilable with connectionism if end-to-end learning processes interact with early brain development to induce various kinds of cell differentiation and specialization. To illustrate, consider that the mammalian visual system divides between parvo- and magno-cellular systems with distinct response properties. Magno cells are larger and capture the achromatic, global properties of the receptive field, while parvo cells are color-sensitive and exhibit high spatial frequency, capturing finer details. To understand the emergence of the parvo/magno distinction, a [2025 Communications Biology](https://www.nature.com/articles/s42003-025-08382-4) paper trained a generic deep convnet on a developmentally “biomimetic” version of the ImageNet dataset: reduced resolution, achromatic images for the first 100 epochs; high-resolution, full-color images for the subsequent 100 epochs. The resulting AlexNet-like model saw the emergence of a “relatively homogeneous magnocellular group of units, which is markedly absent in the standard network, as well as receptive field types that are more aligned with parvocellular characteristics.” Interestingly, the biomimetic model also recapitulated the human bias for classifying images based on global properties like shape — a bias absent in the standard AlexNet model.

The functionalist tradition in philosophy of mind holds that mental states are distinguished by their causal roles rather than their physical substrates. On a strong functionalist reading, anything that implements the right functional organization is, by definition, instantiating the corresponding mental state. Consciousness is also functional in the literal sense that it serves an evolutionary function. That is, consciousness *does* something. On this account, philosophical zombies cannot meaningfully exist. It’d be like positing a car without a steering column that drives equally well as an identical car with one: an idea you can hold in your imagination but not actually instantiate in the real world. This is in contrast to epiphenomenalism, which treats consciousness as a kind of shadow with no causal influence on the world. Emergence theories often have a similar flavor, as though consciousness were an accidental side-effect of sufficiently complex information processing. Then there is panpsychism, which holds that consciousness is a primitive of the universe that permeates everything in degrees. I find all these alternative theories bizarrely divorced from the concrete, functional role consciousness clearly plays in human learning and motivation. 

It has long been established that the phasic firing of dopamine neurons resembles the reward prediction error (RPE) signal used by reinforcement learning algorithms. While the RPE theory of dopamine was too simplistic in its original form, a [2024 Nature Neuroscience perspective](https://gershmanlab.com/pubs/Gershman24_dopamine.pdf) shows how a suitably generalized concept of prediction error can explain a wide range of its ostensible empirical challenges.

See, for example: Flesher, S. N. et al. (2021). “[A brain-computer interface that evokes tactile sensations improves robotic arm control](https://www.science.org/doi/10.1126/science.abd0380).” Science, 372, 831–836. Silicon BCIs can both read brain states and produce signals that translate to subjective sensations. This is hard to explain if the brain’s substrate is doing fundamentally different kinds of computation, much less if consciousness isn't computable in the first place.

There are many simplistic correlation studies of brain-AI alignment that [may be spurious](https://www.nature.com/articles/s41467-026-72253-7) due to confounders. I’ve intentionally picked a subset of results that avoid these pitfalls. However, the capacity for deep learning models to emulate the brain does not rest on any one study, but rather multiple lines of evidence that should be understood holistically.

In a recent preprint, “[Cognitive Dark Matter: Measuring What AI Misses](https://arxiv.org/abs/2603.03414),” Patrick Mineault, Thomas Griffiths, and Sean Escola propose a roadmap for augmenting AI training data in ways that could elicit training signal from brain functions that meaningfully shape behavior yet are hard to infer from behavioral data alone. 

Admittedly, this conclusion is much easier to accept after consuming psychedelics that decompose sensory experiences into their geometric components. Take enough, and you may even undergo mild derealization and witness the hardness of the hard problem melt before your eyes.
