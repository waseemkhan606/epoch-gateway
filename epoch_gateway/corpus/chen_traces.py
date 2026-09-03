"""
chen_traces.py — Dr. Sarah Chen's chest-radiograph reasoning, as discrete
diagnostic traces. This is the real source the Trace Layer retrieves over.

Each trace records one pattern the way she teaches it at the reading station:
the finding, the discriminating features she keys on, the reasoning that ties
them together, and the next step she recommends. `related` links form the
Pattern Layer — a small graph traversed one hop on retrieval.

Strict tenant isolation: the base patterns are materialised once per tenant
with a tenant-scoped id (CHEN-A-*, CHEN-B-*). Retrieval never crosses the
boundary, so tenant_A's index and tenant_B's index are wholly separate copies.
Each site also carries its own extra traces — tenant_A is an acute/trauma
service, tenant_B a chronic-disease referral centre.
"""

# --- base patterns: Dr. Chen's core chest-film reasoning --------------------
_BASE = [
    dict(
        key="TECH", pattern="technical adequacy — rotation, inspiration, penetration",
        finding="Before any read: medial clavicle ends equidistant from the spinous "
                "processes (no rotation), 9–10 posterior ribs visible above the "
                "diaphragm (adequate inspiration), lower thoracic discs faintly seen "
                "through the heart (adequate penetration).",
        features=["clavicle-to-spinous symmetry", "posterior rib count at the dome",
                  "retrocardiac vessels visible", "scapulae clear of the lung fields"],
        reasoning="A rotated film shifts the mediastinum and fakes a large hilum or "
                  "unilateral lucency. A shallow inspiration crowds the bases and "
                  "mimics oedema or basal consolidation. Penetration errors hide a "
                  "retrocardiac mass or make the lungs look diffusely abnormal. "
                  "Adequacy is judged first so it is not mistaken for disease.",
        recommendation="If rotated or under-inspired, repeat before calling any "
                       "subtle finding. State the technical limitation in the report.",
        related=["SILH", "CARD"],
    ),
    dict(
        key="SILH", pattern="silhouette sign",
        finding="A normal soft-tissue border — right or left heart margin, an "
                "aortic knuckle, a hemidiaphragm — is effaced by an adjacent opacity "
                "of the same density.",
        features=["loss of a normally sharp border", "opacity is anatomically "
                  "contiguous with that border", "border reappears on the lateral"],
        reasoning="Two structures of water density in direct contact lose their "
                  "interface. The effaced border localises the disease: lost right "
                  "heart border = right middle lobe; lost left heart border = "
                  "lingula; lost hemidiaphragm = a lower lobe. A retrocardiac opacity "
                  "with a preserved heart border sits posteriorly (lower lobe), not "
                  "in the middle lobe or lingula.",
        recommendation="Use the effaced border to name the lobe, then confirm on the "
                       "lateral. Correlate with symptoms before calling it acute.",
        related=["CONS", "ATEL", "TECH"],
    ),
    dict(
        key="ABG", pattern="air bronchogram / airspace filling",
        finding="Branching lucent bronchi stand out against a surrounding opacity; "
                "the affected zone is not shrunken.",
        features=["lucent branching bronchi within opacity", "no volume loss",
                  "ill-defined margins except where a fissure bounds it"],
        reasoning="An air bronchogram means the airspaces around a patent bronchus "
                  "are filled — pus, blood, oedema, or cells — while the airway "
                  "stays open. It separates airspace disease from a mass (which has "
                  "no air bronchogram) and from collapse (which shows volume loss "
                  "and crowded, not patent, bronchi).",
        recommendation="Treat as airspace disease; the clinical context decides "
                       "between pneumonia, haemorrhage, oedema, and — if it "
                       "persists — bronchoalveolar spread.",
        related=["CONS", "EDEMA", "ATEL"],
    ),
    dict(
        key="CONS", pattern="lobar consolidation",
        finding="Homogeneous opacity confined to one lobe, bounded sharply by a "
                "fissure, containing air bronchograms, with no shift of the fissure "
                "or mediastinum.",
        features=["lobar distribution", "fissure-bounded margin", "air bronchograms",
                  "no volume loss", "silhouettes the contiguous heart or diaphragm border"],
        reasoning="Airspace filling that respects a lobar boundary and preserves "
                  "volume is lobar pneumonia until proven otherwise. Absence of "
                  "volume loss distinguishes it from a collapsed lobe; the "
                  "fissure-bounded edge distinguishes it from patchy "
                  "bronchopneumonia.",
        recommendation="Manage as community-acquired pneumonia. Follow-up film at "
                       "6 weeks to confirm clearance and exclude an obstructing "
                       "endobronchial lesion, especially over 50 or if a smoker.",
        related=["ABG", "SILH", "ATEL"],
    ),
    dict(
        key="ATEL", pattern="lobar collapse / atelectasis",
        finding="A wedge or band of increased density with signs of volume loss: "
                "displaced fissure, elevated hemidiaphragm, shifted mediastinum "
                "toward the opacity, crowded ribs, crowded vessels.",
        features=["displaced fissure toward the collapse", "ipsilateral mediastinal "
                  "shift", "raised hemidiaphragm", "compensatory hyperinflation of "
                  "the other lobes"],
        reasoning="Volume loss is the discriminator against consolidation. Each lobe "
                  "collapses in a recognised direction — left lower lobe behind the "
                  "heart as a triangular retrocardiac opacity with a hidden medial "
                  "diaphragm; right middle lobe effacing the right heart border with "
                  "a wedge on the lateral. A central mass or mucus plug is the usual "
                  "cause in an adult.",
        recommendation="Look for a central obstructing lesion. CT with contrast if "
                       "there is no rapid re-expansion after physiotherapy or "
                       "bronchoscopy.",
        related=["CONS", "SILH", "HILAR"],
    ),
    dict(
        key="EFF", pattern="pleural effusion",
        finding="Homogeneous dependent opacity with a meniscus rising into the "
                "lateral costophrenic angle, blunting it; the underlying lung is "
                "not destroyed.",
        features=["meniscus sign", "costophrenic angle blunting", "layering on a "
                  "decubitus or shifting with position", "mediastinum pushed away "
                  "when large"],
        reasoning="A meniscus that shifts with position is free fluid. About "
                  "200–300 mL is needed to blunt the lateral angle on an erect PA; "
                  "less shows only on the lateral posterior angle. A large effusion "
                  "that does NOT shift the mediastinum away implies a fixed lung — "
                  "collapse from an obstructing lesion or a fibrothorax.",
        recommendation="Erect or decubitus view to confirm it is free and estimate "
                       "volume; ultrasound-guided tap for any effusion that is new, "
                       "unilateral, or unexplained.",
        related=["ATEL", "CARD", "EDEMA"],
    ),
    dict(
        key="PTX", pattern="pneumothorax",
        finding="A thin white visceral pleural line paralleling the chest wall, "
                "with no lung markings peripheral to it; often best seen at the apex "
                "on an erect film.",
        features=["visceral pleural white line", "absent vascular markings beyond "
                  "the line", "deep sulcus sign on a supine film", "lung edge moves "
                  "on an expiratory view"],
        reasoning="The pleural line separates aerated lung from the pleural gas. On "
                  "a supine trauma film the gas collects anteriorly and basally, so "
                  "the only clue may be an abnormally deep, lucent costophrenic "
                  "sulcus and a sharp cardiac border. Skin folds mimic the line but "
                  "have lung markings running through them.",
        recommendation="Erect expiratory film if stable and the diagnosis is "
                       "uncertain. Any pneumothorax with breathlessness or a rim "
                       ">2 cm needs drainage.",
        related=["COPD", "LINES", "TECH"],
    ),
    dict(
        key="CARD", pattern="cardiomegaly",
        finding="Cardiothoracic ratio above 0.5 on an adequate erect PA film, with "
                "a globular or chamber-specific contour change.",
        features=["CTR > 0.5 on erect PA", "not attributable to an AP projection or "
                  "poor inspiration", "specific chamber bulges — LV apex down and "
                  "out, LA double density and splayed carina"],
        reasoning="An AP or supine film magnifies the heart by up to 15–20%, so the "
                  "ratio only counts on an erect PA with a good inspiration. A "
                  "globular heart with clear lungs suggests a pericardial effusion; "
                  "chamber-specific enlargement points to the valvular or myocardial "
                  "lesion.",
        recommendation="Correlate with an AP vs PA technique note; echocardiography "
                       "to separate dilatation, hypertrophy, and pericardial fluid.",
        related=["EDEMA", "EFF", "TECH"],
    ),
    dict(
        key="EDEMA", pattern="cardiogenic pulmonary oedema",
        finding="Upper-zone vascular redistribution, peribronchial cuffing, Kerley B "
                "lines, perihilar 'bat-wing' haze, and often small pleural "
                "effusions, on a background of an enlarged heart.",
        features=["upper-lobe diversion", "Kerley B lines at the costophrenic "
                  "angles", "peribronchial cuffing", "bat-wing perihilar opacity",
                  "effusions and cardiomegaly"],
        reasoning="Raised pulmonary venous pressure fills the interstitium first "
                  "(septal and Kerley lines, cuffing) then the airspaces (bat-wing). "
                  "Symmetry, a large heart, and effusions favour a cardiogenic "
                  "cause; a normal heart with sparing of the periphery and no "
                  "effusions favours ARDS or another permeability oedema.",
        recommendation="Treat the failure and repeat the film — cardiogenic oedema "
                       "clears within 24–48 h of diuresis, which itself confirms "
                       "the diagnosis.",
        related=["CARD", "ARDS", "EFF"],
    ),
    dict(
        key="INT", pattern="interstitial pattern",
        finding="A reticular, nodular, or reticulonodular pattern that does not "
                "efface vessels and shows no air bronchograms; lung volumes may be "
                "small (fibrosis) or preserved.",
        features=["reticular or reticulonodular lines", "vessels remain visible "
                  "through the opacity", "no air bronchograms", "distribution — "
                  "basal and peripheral vs upper zone vs perilymphatic"],
        reasoning="Interstitial thickening outlines the lung architecture rather "
                  "than filling it, so vessels stay visible and there are no air "
                  "bronchograms. Distribution narrows the cause: basal peripheral "
                  "with volume loss suggests UIP; upper-zone with preserved volume "
                  "suggests sarcoid or hypersensitivity pneumonitis.",
        recommendation="High-resolution CT to characterise the pattern and "
                       "distribution before labelling it fibrosis.",
        related=["EDEMA", "NODULE", "HILAR"],
    ),
    dict(
        key="NODULE", pattern="solitary pulmonary nodule",
        finding="A single rounded opacity up to 3 cm, surrounded by aerated lung, "
                "with no associated collapse or effusion.",
        features=["margin — smooth, lobulated, or spiculated", "calcification "
                  "pattern — central, laminated, popcorn vs eccentric", "growth "
                  "against any prior film", "size"],
        reasoning="Benign features are dense central or laminated calcification and "
                  "two-year stability. Spiculation, an eccentric calcific fleck, "
                  "upper-lobe location, and growth raise malignancy risk. The single "
                  "most useful test is an old film: a stable nodule over two years "
                  "needs no further work-up.",
        recommendation="Retrieve prior imaging first. If none or if growing, CT with "
                       "nodule protocol and risk-stratified follow-up or biopsy.",
        related=["INT", "HILAR", "ATEL"],
    ),
    dict(
        key="HILAR", pattern="hilar enlargement",
        finding="One or both hila enlarged and denser than normal, with a lobulated "
                "rather than a branching vascular contour.",
        features=["lobulated hilar contour", "increased hilar density (the "
                  "'hilum overlay' and 'hilum convergence' signs)", "uni- vs "
                  "bilateral", "associated lung or mediastinal disease"],
        reasoning="A large pulmonary artery converges with the hilar vessels "
                  "(convergence sign); lymphadenopathy or a mass sits in front of "
                  "or behind them (overlay sign, vessels seen through the opacity). "
                  "Bilateral symmetrical lobulation suggests sarcoid or lymphoma; a "
                  "unilateral lobulated hilum suggests carcinoma or TB.",
        recommendation="Contrast CT of the chest to separate vascular enlargement "
                       "from nodal or mass disease and to stage it.",
        related=["NODULE", "INT", "ATEL"],
    ),
    dict(
        key="COPD", pattern="hyperinflation / COPD",
        finding="Flattened hemidiaphragms, an increased retrosternal air space, a "
                "narrow vertical heart, more than 10 posterior ribs, and "
                "attenuated peripheral vessels.",
        features=["flat or inverted diaphragms", "retrosternal lucency > 2.5 cm on "
                  "the lateral", "small central heart", "bullae or vascular pruning"],
        reasoning="Air trapping lengthens and flattens the diaphragm, dropping its "
                  "mechanical advantage, and expands the retrosternal clear space. "
                  "A long narrow heart is passive, from the low flat diaphragm — "
                  "not true cardiac disease. Focal lucency with a hairline wall is "
                  "a bulla, not a pneumothorax.",
        recommendation="Correlate with spirometry. On an acute presentation, compare "
                       "with old films and look specifically for a superimposed "
                       "pneumothorax or consolidation.",
        related=["PTX", "NODULE", "CARD"],
    ),
    dict(
        key="LINES", pattern="lines and tubes — position check",
        finding="Endotracheal tube tip 3–5 cm above the carina; central venous "
                "catheter tip at the cavoatrial junction; nasogastric tube crossing "
                "the diaphragm in the midline with its tip below the "
                "gastro-oesophageal junction.",
        features=["ETT tip vs carina and neck position", "CVC course and tip",
                  "NGT side-port below the diaphragm", "any new pneumothorax or "
                  "effusion after the procedure"],
        reasoning="An ETT advances ~2 cm on neck flexion and withdraws on "
                  "extension, so it is set high enough to tolerate flexion without "
                  "entering the right main bronchus (which collapses the left lung). "
                  "A CVC tip in the right atrium risks perforation and arrhythmia. "
                  "An NGT seen in a bronchus or coiled in the pharynx must be pulled "
                  "before feeding.",
        recommendation="Reposition any malpositioned device and repeat the film. "
                       "Always scan the apices and costophrenic angles for a "
                       "procedure-related pneumothorax.",
        related=["PTX", "ATEL", "TECH"],
    ),
]

# --- tenant_A: acute / trauma service -------------------------------------
_EXTRA_A = [
    dict(
        key="PTX-TENSION", pattern="tension pneumothorax",
        finding="A large pneumothorax with the mediastinum and trachea pushed to "
                "the opposite side, the ipsilateral hemidiaphragm flattened or "
                "inverted, and widened rib spaces on the affected side.",
        features=["contralateral mediastinal shift", "flattened or inverted "
                  "hemidiaphragm", "splayed ribs", "haemodynamic compromise"],
        reasoning="A one-way pleural leak raises intrapleural pressure through the "
                  "respiratory cycle, collapsing the lung, kinking the great veins, "
                  "and dropping venous return. It is a clinical diagnosis — the "
                  "film only confirms it — and mediastinal shift with diaphragm "
                  "depression is the radiographic signature.",
        recommendation="Immediate needle decompression then a chest drain. Do not "
                       "wait for imaging if the patient is unstable.",
        related=["PTX", "LINES", "RIB"],
    ),
    dict(
        key="RIB", pattern="rib fractures and flail segment",
        finding="Cortical breaks or step-offs in the rib arcs, sometimes with an "
                "extrapleural haematoma; a flail segment is two or more fractures in "
                "three or more contiguous ribs.",
        features=["cortical discontinuity or step", "extrapleural soft-tissue "
                  "bulge", "associated pneumothorax, haemothorax, or lung "
                  "contusion", "lower-rib fractures and upper-abdominal solid organ "
                  "injury"],
        reasoning="Rib detail on a frontal chest film is insensitive; the injuries "
                  "that matter are the complications. First and second rib "
                  "fractures imply high-energy transfer and raise concern for "
                  "aortic and brachial plexus injury; lower rib fractures point to "
                  "liver or splenic injury.",
        recommendation="CT chest (and upper abdomen for lower-rib fractures) to "
                       "assess the lung, pleura, and solid organs; the fractures "
                       "themselves are managed with analgesia.",
        related=["PTX", "MEDIASTINUM", "PTX-TENSION"],
    ),
    dict(
        key="MEDIASTINUM", pattern="widened mediastinum — traumatic aortic injury",
        finding="Mediastinal width over 8 cm at the arch on a supine film, or a "
                "mediastinal-to-chest ratio above 0.25, with loss of the aortic "
                "knuckle, a left apical cap, depression of the left main bronchus, "
                "and rightward tracheal or nasogastric-tube deviation.",
        features=["mediastinal width / ratio", "obscured aortic knuckle",
                  "left apical pleural cap", "left main bronchus depressed below "
                  "40°", "NGT displaced to the right"],
        reasoning="A supine AP film magnifies the mediastinum, so the specific "
                  "signs matter more than width alone. The mechanism (rapid "
                  "deceleration) plus any of the aortic-contour signs is enough to "
                  "proceed to CT; a normal mediastinal contour has a high negative "
                  "predictive value.",
        recommendation="CT aortogram without delay for any concerning contour or "
                       "high-risk mechanism.",
        related=["RIB", "EFF", "TECH"],
    ),
    dict(
        key="PNEUMOMED", pattern="pneumomediastinum",
        finding="Lucent streaks outlining the mediastinal structures — a line "
                "along the left heart border lifting the mediastinal pleura, the "
                "continuous diaphragm sign, gas around the pulmonary artery and "
                "aorta, and often tracking into the neck.",
        features=["mediastinal pleural line lifted by gas", "continuous diaphragm "
                  "sign", "gas tracking into the soft tissues of the neck",
                  "ring-around-the-artery sign"],
        reasoning="Alveolar rupture from barotrauma, asthma, vomiting (Boerhaave), "
                  "or airway injury lets gas dissect along the bronchovascular "
                  "sheaths to the mediastinum. It is distinguished from a medial "
                  "pneumothorax because the gas outlines mediastinal structures and "
                  "does not shift with position.",
        recommendation="Look hard for the cause — oesophageal or tracheobronchial "
                       "injury needs CT and often endoscopy; isolated "
                       "pneumomediastinum from asthma is usually managed "
                       "conservatively.",
        related=["PTX", "LINES", "PTX-TENSION"],
    ),
    dict(
        key="ASPIRATION", pattern="aspiration pneumonia / pneumonitis",
        finding="Patchy or confluent opacity in the dependent segments — posterior "
                "segments of the upper lobes and superior segments of the lower "
                "lobes in a supine patient, basal segments if aspirated upright.",
        features=["dependent-segment distribution", "bilateral but often "
                  "asymmetric", "context of reduced consciousness, dysphagia, or a "
                  "recent procedure", "rapid change over 24–48 h"],
        reasoning="Gravity decides where aspirated material lands; the distribution "
                  "is the diagnostic clue. Chemical pneumonitis appears within "
                  "hours and can clear in 24–48 h; a secondary bacterial pneumonia "
                  "consolidates and cavitates over days.",
        recommendation="Supportive care and airway protection; reserve antibiotics "
                       "for a clinical course that does not settle or for frank "
                       "consolidation. Repeat film at 48 h.",
        related=["CONS", "ABG", "ARDS"],
    ),
]

# --- tenant_B: chronic-disease referral centre -------------------------------
_EXTRA_B = [
    dict(
        key="MASS", pattern="lung mass with post-obstructive collapse",
        finding="An opacity over 3 cm, often central, with lobar volume loss "
                "distal to it; the S-sign of Golden — a central convex mass "
                "bulging the concave collapsed fissure.",
        features=["mass > 3 cm", "distal volume loss", "Golden S sign",
                  "hilar or mediastinal nodal enlargement", "bone or pleural "
                  "involvement"],
        reasoning="A central mass obstructs a lobar bronchus and the lobe collapses "
                  "around it; the fissure is drawn in peripherally but pushed out "
                  "centrally by the mass, giving the reverse-S contour. This "
                  "combination in an adult smoker is bronchogenic carcinoma until "
                  "proven otherwise.",
        recommendation="Staging CT of chest, upper abdomen and adrenals, then "
                       "tissue — bronchoscopy for a central lesion, image-guided "
                       "biopsy for a peripheral one.",
        related=["ATEL", "NODULE", "HILAR"],
    ),
    dict(
        key="EFF-MALIGNANT", pattern="malignant pleural effusion",
        finding="A large unilateral effusion that does NOT push the mediastinum to "
                "the opposite side, sometimes with nodular or circumferential "
                "pleural thickening and rind formation.",
        features=["large effusion without contralateral mediastinal shift",
                  "nodular pleural thickening", "pleural rind encasing the lung",
                  "no shift because the lung is trapped or the hemithorax is fixed"],
        reasoning="A big effusion normally pushes the mediastinum away. When it "
                  "does not, the ipsilateral lung is not expanding — from an "
                  "obstructing central tumour, a trapped lung under a malignant "
                  "rind, or extensive pleural tumour. Nodular thickening on CT "
                  "distinguishes malignant from benign pleural disease.",
        recommendation="Contrast CT of the chest; pleural aspiration with cytology "
                       "and, if non-diagnostic and suspicion persists, image-guided "
                       "or thoracoscopic pleural biopsy.",
        related=["EFF", "MASS", "ATEL"],
    ),
    dict(
        key="MILIARY", pattern="miliary pattern",
        finding="Innumerable 1–3 mm nodules of uniform size distributed evenly "
                "throughout both lungs, including the apices and bases, without "
                "sparing the periphery.",
        features=["uniform 1–3 mm nodules", "even, random distribution",
                  "no zonal or perilymphatic predominance", "may only be visible "
                  "on a well-penetrated film or CT"],
        reasoning="Haematogenous spread seeds the lung uniformly, so the nodules "
                  "are the same size everywhere — unlike sarcoid (perilymphatic, "
                  "upper zone) or metastases (varied size, lower zone). Miliary TB "
                  "is the classic cause; miliary metastases (thyroid, renal, "
                  "melanoma) and fungal disease are the differentials.",
        recommendation="Urgent work-up for disseminated TB — sputum, and treat "
                       "empirically if the patient is unwell; CT and the clinical "
                       "picture guide the alternatives.",
        related=["INT", "NODULE", "SARCOID"],
    ),
    dict(
        key="SARCOID", pattern="sarcoidosis — bilateral hilar lymphadenopathy",
        finding="Symmetrical lobulated enlargement of both hila and often the right "
                "paratracheal region, with clear lungs (stage I) or added "
                "upper-zone reticulonodular disease (stage II).",
        features=["symmetric bilateral hilar lobulation", "right paratracheal "
                  "node ('1-2-3' / Garland triad)", "preserved lung volumes",
                  "upper- and mid-zone predominance if parenchymal"],
        reasoning="Bilateral symmetry is the key: lymphoma tends to be more "
                  "mediastinal and asymmetric, TB is usually unilateral, and "
                  "pulmonary hypertension enlarges the hila smoothly without "
                  "lobulation. Sarcoid nodes stay discrete and symmetric.",
        recommendation="Correlate with serum ACE and a careful history; tissue "
                       "confirmation (endobronchial ultrasound node sampling) "
                       "before immunosuppression.",
        related=["HILAR", "INT", "MILIARY"],
    ),
    dict(
        key="FIBROSIS", pattern="pulmonary fibrosis — UIP pattern",
        finding="Basal and peripheral reticulation with reduced lower-zone volumes, "
                "traction bronchiectasis, and honeycombing; the hemidiaphragms "
                "ride high and the fissures bow.",
        features=["basal, peripheral, subpleural reticulation", "lower-zone volume "
                  "loss", "honeycombing", "traction bronchiectasis", "shaggy heart "
                  "border from adjacent fibrosis"],
        reasoning="A basal peripheral gradient with volume loss and honeycombing is "
                  "the usual-interstitial-pneumonia pattern — most often idiopathic "
                  "pulmonary fibrosis, but also asbestosis or connective-tissue "
                  "disease. Upper-zone fibrosis with preserved volume points "
                  "elsewhere (sarcoid, hypersensitivity pneumonitis, prior TB).",
        recommendation="High-resolution CT to confirm the UIP pattern and estimate "
                       "extent; refer to an interstitial-lung-disease service "
                       "before starting antifibrotic therapy.",
        related=["INT", "SARCOID", "EDEMA"],
    ),
]

# --- ARDS is a base-adjacent pattern both sites keep -----------------------
_BASE.append(dict(
    key="ARDS", pattern="ARDS / permeability oedema",
    finding="Bilateral, fairly symmetric airspace opacity that spares the extreme "
            "periphery, on a background of a normal-sized heart and no pleural "
            "effusions, evolving over 12–48 h and slow to clear.",
    features=["bilateral airspace opacity", "normal heart size", "no or minimal "
              "effusions", "peripheral sparing", "lags the clinical state, clears "
              "over days not hours"],
    reasoning="Increased capillary permeability floods the airspaces without "
              "raised venous pressure, so — unlike cardiogenic oedema — the heart "
              "is normal, effusions are absent, and diuresis does not clear it "
              "quickly. A recognised insult (sepsis, aspiration, pancreatitis, "
              "transfusion) within the preceding week supports it.",
    recommendation="Manage the precipitant and ventilate lung-protectively; the "
                   "film is used to track progression and to catch barotrauma, "
                   "not to grade severity.",
    related=["EDEMA", "CONS", "ABG"],
))


def _materialise(tenant, base, extra):
    suffix = tenant.split("_")[-1].upper()          # tenant_A -> A
    out = []
    for d in list(base) + list(extra):
        tid = f"CHEN-{suffix}-{d['key']}"
        rel = [f"CHEN-{suffix}-{r}" for r in d.get("related", [])]
        out.append({
            "id": tid,
            "tenant": tenant,
            "pattern": d["pattern"],
            "finding": d["finding"],
            "features": d["features"],
            "reasoning": d["reasoning"],
            "recommendation": d["recommendation"],
            "related": rel,
        })
    return out


TRACES = (
    _materialise("tenant_A", _BASE, _EXTRA_A)
    + _materialise("tenant_B", _BASE, _EXTRA_B)
)

# id set per tenant, for quick isolation checks
TENANTS = sorted({t["tenant"] for t in TRACES})
