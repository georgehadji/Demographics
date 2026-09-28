# ADR 0005: Αρχιτεκτονική λογισμικού, παραδείγματα προγραμματισμού και σχεδιαστικά μοτίβα ανά module

- **Ημερομηνία:** 2026-09-28
- **Κατάσταση:** αποδεκτή (έγκριση από τον υπεύθυνο έκδοσης, 2026-09-28)· σχέδιο υλοποίησης: [`docs/IMPLEMENTATION-PLAN.md`](../IMPLEMENTATION-PLAN.md)
- **Σχέση:** εξειδικεύει την ADR 0001 και το PROPOSAL §9. Αλλάζει μία επιλογή του §9.1 (εργαλείο site).

## Πλαίσιο: τι «βελτιστοποιούμε»

Το «βέλτιστο» ορίζεται από τους περιορισμούς του έργου, όχι γενικά:

1. **Αξιοπιστία και ελεγξιμότητα** πάνω από ταχύτητα και ευελιξία. Κάθε αριθμός πρέπει να ανιχνεύεται μέχρι το αρχείο της πηγής (κανόνες του `CLAUDE.md`).
2. **Αναπαραγωγιμότητα:** το ίδιο input και ο ίδιος κώδικας δίνουν byte-προς-byte το ίδιο output.
3. **Ένας συγγραφέας (Claude) χωρίς ανεξάρτητο ελεγκτή:** τα tests είναι ο κύριος μηχανισμός ποιότητας (ADR 0001). Η αρχιτεκτονική πρέπει να κάνει τα λάθη **ελέγξιμα από μηχανή**.
4. **Μικρά δεδομένα, batch, στατική έξοδος:** MB, όχι TB· ετήσια/μηνιαία ενημέρωση· κανένας server (ADR 0001).
5. **Ελάχιστη επιφάνεια:** κάθε εργαλείο και κάθε αφαίρεση είναι επιπλέον σημείο αποτυχίας που κανείς άνθρωπος δεν θα συντηρήσει.

## Απόφαση: συνολική αρχιτεκτονική

**Στατικό, batch «data product» με διαδοχικά στρώματα αμετάβλητων δεδομένων. Λειτουργικός πυρήνας με I/O μόνο στα άκρα** (*functional core, imperative shell*). **Ports & adapters μόνο στα σύνορα με τον έξω κόσμο.**

Η έκδοση (build) είναι καθαρή συνάρτηση: `έξοδος = f(snapshots πηγών, κώδικας@commit, reference data)`.

```
 Πηγές ──► L1 Raw snapshots ──► L2 Observations ──► L3 Harmonized ──► L4 Indicators / Models ──► L5 Data product ──► L6 Site / Papers
(adapters)  (bytes, sha256,      (long format,        (NUTS/δήμοι       (derived / projected /       (Parquet+CSV+JSON,     (μόνο ανάγνωση,
            αμετάβλητα)          contract)            concordance)      scenario, contract)          manifest, DOI)         καμία πράξη)
```

**Κανόνας εξάρτησης:** κάθε στρώμα διαβάζει μόνο το προηγούμενο. Η παρουσίαση (L6) **δεν υπολογίζει τίποτα**: διαβάζει έτοιμες τιμές από το L5. Έτσι επιβάλλεται μηχανικά ο κανόνας «κανένας αριθμός πληκτρολογημένος σε κείμενο».

**Σε κάθε σύνορο στρώματος τρέχει ένα contract** (`pandera`, `validate_observations`). Ό,τι δεν περνά σταματά το build. Δεν υπάρχει σιωπηρή διόρθωση (*fail loudly*, όπως ήδη ορίζει το `coerce=False`).

## Απόφαση: παράδειγμα και μοτίβα ανά module

| Module | Ευθύνη | Παράδειγμα | Μοτίβα | Tests |
|---|---|---|---|---|
| `sources/` (connectors) | Λήψη bytes + μεταδεδομένων λήψης. **Καμία ανάλυση.** | Imperative shell | **Adapter** ανά πηγή· **Strategy** ανά `access`/`probe_kind`· **Registry** οδηγούμενο από δεδομένα (`registry.yaml`)· retry με backoff | Καταγεγραμμένα responses (fixtures· τα χειρόγραφα δηλώνονται με `_comment`) |
| `snapshots/` | Αποθήκευση raw αρχείων | Append-only, αμετάβλητο | **Content-addressed storage** (sha256)· **Repository** πάνω από αρχεία / GitHub Releases· manifest JSON· οι αναθεωρήσεις είναι νέα snapshots, το ιστορικό προκύπτει (event-sourcing «lite») | Ίδιο hash ⇒ ίδιο αρχείο· απαγόρευση overwrite |
| `parse/` (JSON-stat, ELSTAT xlsx) | bytes → long-format πίνακας | **Καθαρές συναρτήσεις** | **Anti-corruption layer:** κωδικοί/flags της πηγής → δικό μας λεξιλόγιο (π.χ. `p` → `provisional`)· *parse, don't validate* | Fixtures· `hypothesis` για τη δομή JSON-stat· ένας parser ανά γνωστή διάταξη αρχείου, με τεστ που σπάει αν αλλάξει η διάταξη |
| `provenance/` (contracts) | Ορισμός του τι είναι «τιμή» | Δηλωτικό | **Design by contract**· **Value objects** (frozen dataclasses/enums: `definition_id@vN`, `geo_code`+`geo_vintage`) | Τα υπάρχοντα tests· property tests για τα cross-field rules |
| `harmonize/` | NUTS 2016/2021/2024, Καλλικράτης → Κλεισθένης | Καθαρές σχεσιακές μετατροπές | **Concordance ως δεδομένα** (CSV στο `data/`), όχι ως κώδικας· join-based mapping | **Invariants:** τα σύνολα διατηρούνται μετά την αντιστοίχιση· κάθε κωδικός αντιστοιχίζεται ακριβώς μία φορά |
| `indicators/` | Οι 12 δείκτες του §4 και οι επόμενοι | Δηλωτικό + καθαρές συναρτήσεις | **Specification + Registry:** κάθε δείκτης είναι εγγραφή (`id@version`, inputs, μονάδα, `nature`, επίσημο αντίστοιχο) με τύπο ως καθαρή έκφραση Polars. Αλλαγή τύπου ⇒ νέα έκδοση (`transform_version`) | **Τα acceptance tests παράγονται από την προδιαγραφή:** για κάθε δείκτη με επίσημο αντίστοιχο, συμφωνία με την Eurostat εντός στρογγυλοποίησης |
| `models/` (cohort-component, small-area, nowcasting) | Προβολές και εκτιμήσεις | **Λειτουργικός αριθμητικός πυρήνας** (NumPy, καμία I/O, καμία κατάσταση) | Αμετάβλητα αντικείμενα υποθέσεων (`Assumptions`, `Scenario` → `scenario_id` = hash)· **Strategy** ανά συνιστώσα (γονιμότητα / θνησιμότητα / μετανάστευση) | **Property tests** (διατήρηση πληθυσμού, μη αρνητικότητα)· **test αναπαραγωγής EUROPOP2025 ως πύλη**· backtests (ADR 0004) |
| `bridge_r/` (bayesPop) | Πιθανοτικές προβολές ΟΗΕ | Εξωτερική διεργασία | **Anti-corruption layer** με διεπαφή μόνο αρχείων (Parquet in/out)· κλειδωμένο περιβάλλον R (`renv`)· τρέχει μόνο στο CI | Η έξοδος περνά το ίδιο contract με όλα τα άλλα |
| `build/` | Σειρά εκτέλεσης | Ρητό DAG καθαρών βημάτων | **Pipes and filters**· memoization με hash των inputs (λογική Make)· idempotent CLI `grpop build` | Δύο διαδοχικά builds δίνουν ίδια hashes εξόδου |
| `publish/` | Data product και εκδόσεις | Δηλωτικό | **Manifest** (ποια αρχεία, ποιο hash, ποιες πηγές)· semver για data releases· DOI μέσω Zenodo | Κάθε αρχείο στο manifest· κάθε τιμή περνά το contract |
| `design/` (tokens) | Χρώματα, τυπογραφία, διαστήματα | Δεδομένα | **Single source of truth + code generation:** ένα αρχείο tokens (JSON) → CSS variables, JS module και Quarto `_brand.yml` | Validators ως tests: αντίθεση WCAG 2.2 AA, διακρισιμότητα παλετών |
| `charts/` (βιβλιοθήκη γραφημάτων) | Όλοι οι τύποι του §7A | **Λειτουργική σύνθεση** σε JS (ES module πάνω στο Observable Plot) | `chart = f(data, spec)`· η **επιστημική γραμματική** είναι *μία* καθαρή συνάρτηση `(nature, status) → στυλ`· κάθε γράφημα επιστρέφει σύνθετο αντικείμενο: σχήμα + πίνακας + alt text + CSV | Unit tests της γραμματικής· Playwright visual regression (light/dark/print) |
| `site/` και `publications/` | Observatory, working papers, ετήσια έκθεση | Templates | **Template view**· **Gateway για τιμές:** συνάρτηση `fact(metric, geo, period)` που διαβάζει το L5 και **σταματά το render** αν η τιμή λείπει ή δεν έχει provenance | Το render αποτυγχάνει σε κάθε αριθμό χωρίς πηγή· ο έλεγχος οπτικής παλινδρόμησης τρέχει πριν από κάθε release |
| `bibliography/` | Παραπομπές | Pipeline step | Επίλυση DOI (Crossref/OpenAlex) → CSL-JSON· έλεγχος τίτλου και συγγραφέων | Το build αποτυγχάνει σε μη επιλυμένη παραπομπή |

### Διατρέχοντες κανόνες

- **Ένας κινητήρας ανά ρόλο.** Polars για όλους τους μετασχηματισμούς. DuckDB μόνο ως μηχανή ερωτημάτων SQL πάνω σε Parquet (ιστορικό snapshots, ad hoc ανάλυση), ποτέ για τον ίδιο μετασχηματισμό με την Polars. Parquet ως μορφή αποθήκευσης.
- **Τύποι:** πλήρη type hints· προσθήκη στατικού ελέγχου τύπων (`pyright` ή `mypy --strict`) στο CI για τα `provenance/`, `indicators/` και `models/`.
- **Κανένα global state:** κάθε βήμα παίρνει ρητή ρύθμιση· καμία ανάγνωση περιβάλλοντος μέσα στον πυρήνα.
- **Αριθμοί:** οι μονάδες και οι στρογγυλοποιήσεις ορίζονται στην προδιαγραφή του δείκτη, ποτέ στην παρουσίαση.
- **Αντικειμενοστραφής σχεδίαση μόνο όπου υπάρχει κατάσταση ή πολυμορφισμός στα άκρα** (connectors, repository). Ο πυρήνας είναι δεδομένα + συναρτήσεις.

## Απόφαση: εργαλείο site (αλλαγή του PROPOSAL §9.1)

**Quarto για site και δημοσιεύσεις, με τη βιβλιοθήκη γραφημάτων ως ανεξάρτητο ES module.**

| Επιλογή | Ευρήματα (2026-09-28) | Εκτίμηση |
|---|---|---|
| Observable Framework (τρέχουσα επιλογή) | Τελευταία release με νέες δυνατότητες: v1.13.0 (11/2024). Έκτοτε μόνο releases διόρθωσης εξαρτήσεων (τελευταία v1.13.4, 3/2026). Issue #2045 (3/2026): «is Observable Framework actually being maintained anymore?» Η Observable στρέφεται στο Notebooks 2.0 (VERIFIED). | Κατάσταση συντήρησης, όχι ανάπτυξης (INFERENCE). Υψηλό ρίσκο για έργο με ορίζοντα ετών. |
| **Quarto** | Releases ανά λίγες εβδομάδες (v1.11.5, 9/2026)· OJS cells με Observable Plot/D3 σε στατικά sites· `ojs_define()` για πέρασμα δεδομένων από Python· `_brand.yml` για HTML **και** Typst (VERIFIED, τεκμηρίωση Quarto). | **Ένα εργαλείο** για observatory, working papers και PDF. Είναι ήδη επιλογή του PROPOSAL για τις δημοσιεύσεις. |
| Astro + Observable Plot | Πολύ ενεργό (VERIFIED)· μέγιστη ευελιξία σχεδίασης. | Μια ολόκληρη JS εφαρμογή ακόμη προς συντήρηση και tests. Κρατιέται ως **έξοδος διαφυγής**. |

**Αντιστάθμιση ρίσκου:** η βιβλιοθήκη γραφημάτων και τα design tokens δεν εξαρτώνται από το Quarto (καθαρό ES module + JSON). Αν το Quarto περιορίσει τον σχεδιασμό του observatory, μόνο το «κέλυφος» μεταφέρεται σε Astro. Τα γραφήματα, τα tokens και το data product μένουν ίδια.

## Δομή repository (ενημέρωση του PROPOSAL §9.2)

```
pipeline/src/grpop/
  sources/      # adapters + registry.yaml (υπάρχει)
  snapshots/    # content-addressed αποθήκη, manifest
  parse/        # jsonstat.py (υπάρχει, μετακινείται), elstat_xlsx.py
  provenance.py # contract (υπάρχει)
  harmonize/    # concordance
  indicators/   # προδιαγραφές + εκφράσεις Polars
  models/       # cohort-component, SAE, nowcasting
  bridge_r/     # διεπαφή αρχείων προς R (μόνο CI)
  build.py      # DAG + CLI
  publish/      # manifest, data release
data/reference/ # concordance, peer groups (μικρά CSV, versioned)
design/         # tokens.json + generators + validators
charts/         # ES module (Observable Plot), tests, visual regression
site/           # Quarto website (observatory)
publications/   # Quarto: working papers, ετήσια έκθεση
docs/
```

## Εναλλακτικές που απορρίφθηκαν

| Εναλλακτική | Λόγος απόρριψης |
|---|---|
| Rich domain model (ιεραρχίες κλάσεων για δείκτες, περιοχές, πληθυσμούς) | Τα δεδομένα είναι πίνακες και οι πράξεις μετασχηματισμοί. Οι κλάσεις κρύβουν την κατάσταση και δυσκολεύουν τα property tests. |
| Orchestrators (Dagster, Airflow, Prefect) | Λειτουργικό βάρος (server, UI, βάση) για DAG λίγων δεκάδων βημάτων. Ο προγραμματισμός γίνεται ήδη από το GitHub Actions. Επανεξέταση μόνο αν το DAG ξεπεράσει ~50 κόμβους. |
| dbt (με DuckDB) | SQL-κεντρικό· διπλασιάζει τους κινητήρες μετασχηματισμού δίπλα στην Polars και χρειάζεται Python models για τα μοντέλα προβολών. |
| Jupyter notebooks ως pipeline | Κρυφή κατάσταση και μη ντετερμινιστική σειρά εκτέλεσης. Επιτρέπονται μόνο για διερεύνηση, ποτέ ως πηγή δημοσιευμένης τιμής. |
| Streamlit / δυναμικό dashboard | Απαιτεί server· απορρίφθηκε στην ADR 0001. Το παλιό `Software/` το χρησιμοποιούσε και ήταν μη αναπαραγώγιμο. |
| Παραμονή στο Observable Framework | Βλ. πίνακα εργαλείου site. |

## Συνέπειες

- **Φάση 1:** υλοποίηση κατά σειρά: `snapshots/` → `parse/` (μετακίνηση του `jsonstat.py`) → `indicators/` με παραγόμενα acceptance tests → `build.py` → `publish/`. Παράλληλα: `design/` και `charts/` με visual regression.
- **CI:** νέα βήματα για στατικό έλεγχο τύπων, tests της βιβλιοθήκης γραφημάτων και Playwright. Το Quarto render τρέχει στο CI και αποτυγχάνει σε αριθμό χωρίς provenance.
- **PROPOSAL §9.1–9.2:** ενημερώθηκαν σύμφωνα με αυτή την ADR.
- **Κίνδυνος:** το Quarto είναι λιγότερο ευέλικτο από μια custom JS εφαρμογή για editorial σχεδιασμό. Μετριάζεται από την ανεξαρτησία της βιβλιοθήκης γραφημάτων (βλ. παραπάνω).

## Πηγές

- Observable Framework, releases και issue #2045: https://github.com/observablehq/framework
- Observable, Notebooks 2.0: https://observablehq.com/blog/previewing-notebooks-2
- Quarto, Observable JS: https://quarto.org/docs/interactive/ojs/
- Quarto, brand.yml: https://quarto.org/docs/authoring/brand.html
- Quarto releases: https://github.com/quarto-dev/quarto-cli/releases
