# Literature search for related work and novelty (23 Oct 2026)

Web search (not a Scopus/Web of Science search; one should still be run before
submission, since several Elsevier pages could not be opened and were read from their
abstracts on IDEAS/RePEc, TRID or SINTEF).

## Closest prior work

| Work | What it did | How WAKE differs |
| --- | --- | --- |
| Zissis, Chatzikokolakis, Spiliopoulos & Vodas (2020), "A distributed spatial method for modeling maritime routes", *IEEE Access* | Route model from global AIS; flagged 313 of 335 incidents from the European Marine Casualty Information Platform (EMCIP) as anomalous (>93%) | Reports detection of incident vessels only, with no rate for ordinary vessels and no controls. WAKE measures the incident vessel against exposure-matched controls, which is what turns a hit rate into evidence. |
| HawaiiCoast_GT: "Correlating real-world incidents with vessel traffic off the coast of Hawaii, 2017–2020", *Discover Oceans* 1 (2024), Sandia report SAND2024-00729J; dataset on Zenodo (record 8253611) | 88.7 M AIS points, 2,622 vessels, 208 tracks labelled with 154 documented incidents; presented as the first public AIS dataset with real incidents | A labelled dataset for one region, with no detector evaluation reported. WAKE is national-scale (2015–2025, 257 vessel events) and does the evaluation. Cite it as a direct neighbour; it may be worth running the WAKE detectors on it as external validation. |
| Wolsing, Roepert, Bauer & Wehrle (2022), "Anomaly Detection in Maritime AIS Tracks: A Review of Recent Approaches", *J. Mar. Sci. Eng.* 10, 112 | Review of 44 papers: "no established dataset that also includes labeled anomalies as ground truth"; only 8 have a decent ground truth, 11 a makeshift one | **Correction to earlier notes:** the review does not say that none of the 44 used real events; 8 had a decent ground truth (e.g. Zissis et al., real incidents). The supportable claim is that very few evaluations use confirmed events, and (as far as found) none compare incident vessels with exposure-matched controls. |
| Du, Goerlandt & Kujala (2020), "Review and analysis of methods for assessing maritime waterway risk based on non-accident critical events detected from AIS data", *RESS* 200, 106933 | Near-miss indicators from AIS; concludes that "focus is needed to build evidence of the validity of the models' results" and that the link to accident involvement needs work | WAKE supplies that kind of evidence for anomaly detectors. |
| Aalberg, Bye & Ellevseth (2022), "Risk factors and navigation accidents: ... comparing accident-free and accident-prone vessels using indicators from AIS data and vessel databases", *Maritime Transport Research* 3, 100062 | Norwegian cargo ships 2010–2019; vessels with a grounding or collision vs none; AIS indicators (distance sailed, speed) and vessel data | Vessel-level, years-long risk factors, not behaviour in the hours before an event, and no detector evaluation. Accident/non-accident comparison is not new and must not be claimed. |
| Dugan & Utne (2025), "Improved identification of maritime risk-influencing factors using AIS data in regression analysis", *RESS* 262, 111156 | AIS activity as an exposure offset (accident rate) for loss of propulsion, power or steering, Norway 2017–2021; exposure improves model fit | Shows exposure control is established in risk modelling. WAKE's contribution is to apply exposure matching to the evaluation of anomaly detectors, not to invent exposure control. |
| Liang, Chen, Cai, Wang & Meng (2026), "Sailing in Dangerous Waters: Advanced Vessel Operation Features Extraction for Global Maritime Accident Analysis", *RESS* 275, 112740 | Global accidents with AIS 2016–2022; operational features (distance, port calls) and association rules | Risk-factor mining, no pre-event detector evaluation. |

## Context on missing ground truth (for the introduction)

- Hwang et al. (2026), "Redefining Maritime Anomaly Detection via Equation-Grounded Synthetic Anomalies", KDD '26 (arXiv 2606.29721): public AIS datasets lack anomaly labels, so studies use rarity or expert labels; they inject synthetic anomalies.
- Kim et al. (2025), "Spatio-Temporal Graphs Beyond Grids: Benchmark for Maritime Anomaly Detection", NeurIPS 2025 workshop (arXiv 2512.20086): benchmark built on synthetic SOG/COG perturbations because no labels exist.
- Singh & Heymann (DLR), "Machine Learning-Assisted Anomaly Detection in Maritime Navigation Using AIS Data" (arXiv 2002.05013): labels from the authors' own dropout rule plus synthetic samples, so accuracy reflects the rule rather than real events.
- Welch et al. (2022), "Hot spots of unseen fishing vessels", *Science Advances*: AIS-disabling events, relevant for the AIS-gap detector.

## What the novelty can and cannot be

Can claim (hedged "to our knowledge", pending a database search):
1. A national-scale evaluation of standard AIS anomaly detectors against confirmed oil-incident vessels (257 vessel events, 2015–2025, two public incident sources, blind two-rater confirmation of the vessel match with kappa reported).
2. Exposure-matched controls as the comparison, with placebo dates, pre-registration and published deviations. The contrast with hit-rate evaluations such as Zissis et al. (2020) is the clearest argument for why this matters.
3. The result itself: a small signal that is concentrated at the incident time (speed drop in the last 3 hours, early3 drop to 0.56) and no improvement in flag rates at operational alarm levels.

Must not claim: new detectors; exposure control as an idea; the first comparison of accident vessels with others; the first use of real incidents to test AIS anomaly detection.

Watch: the naive (unmatched) AUCs were close to the matched ones, so "matching changes the answer" is not a finding here. The finding is that the evaluation is fair and that the remaining signal is small and late.

## Sources

- [Zissis et al. 2020 (Kpler page)](https://www.kpler.com/publications/a-distributed-spatial-method-for-modeling-maritime-routes)
- [Correlating real-world incidents with vessel traffic off the coast of Hawaii (OSTI)](https://www.osti.gov/pages/biblio/2282184-correlating-real-world-incidents-vessel-traffic-off-coast-hawaii)
- [HawaiiCoast_GT dataset (Zenodo)](https://zenodo.org/record/8253611)
- [Wolsing et al. 2022 (PDF)](https://www.comsys.rwth-aachen.de/fileadmin/papers/2022/2022-wolsing-aistracks.pdf)
- [Du, Goerlandt & Kujala 2020 (IDEAS)](https://ideas.repec.org/a/eee/reensy/v200y2020ics0951832018305386.html)
- [Aalberg, Bye & Ellevseth 2022 (SINTEF)](https://sintef.brage.unit.no/sintef-xmlui/handle/11250/3055118?show=full)
- [Dugan & Utne 2025 (IDEAS)](https://ideas.repec.org/a/eee/reensy/v262y2025ics0951832025003576.html)
- [Liang et al. 2026 (TRID)](https://trid.trb.org/View/2692973)
- [Hwang et al. 2026 (arXiv)](https://arxiv.org/html/2606.29721v1)
- [Kim et al. 2025 (arXiv)](https://arxiv.org/pdf/2512.20086)
- [Singh & Heymann (arXiv)](https://arxiv.org/pdf/2002.05013)
- [Welch et al. 2022 (PDF)](https://www.seafdec.or.th/iuu-events/estimate-iuu-fishing-losses-2026/download/references/Welch%20et%20al%202022%20Hot%20spots%20of%20unseen%20fishing%20vessels.pdf)
