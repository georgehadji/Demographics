# Σχέδιο υλοποίησης: κλείσιμο Φάσης 0 και Φάση 1

- **Ημερομηνία:** 2026-09-28
- **Βάση:** [ADR 0005](decisions/0005-software-architecture.md) (αρχιτεκτονική), [ADR 0004](decisions/0004-municipal-level-go-no-go.md) (δημοτικό επίπεδο), PROPOSAL §10 (κριτήρια φάσεων)
- **Κανόνας:** κάθε βήμα είναι ένα pull request με πράσινο CI. Ένα βήμα θεωρείται ολοκληρωμένο μόνο όταν ικανοποιείται ο έλεγχός του, όχι όταν γραφτεί ο κώδικας.

Τα βήματα είναι σε σειρά εξάρτησης. Όσα έχουν την ίδια σημείωση «παράλληλα» μπορούν να γίνουν ταυτόχρονα.

## Μέρος Α: κλείσιμο Φάσης 0

| # | Βήμα | Παραδοτέο | Έλεγχος ολοκλήρωσης |
|---|---|---|---|
| A1 | Άδειες πηγών | Πεδίο `licence` με πραγματικούς όρους για τις 23 εγγραφές του registry, με σύνδεσμο στους όρους κάθε πάροχου | Καμία εγγραφή με `licence: to_verify`· test που το επιβάλλει |
| A2 | Spike ingestion ELSTAT | Σημείωμα `docs/spikes/elstat-ingestion.md`: διάταξη των xlsx (SPO18 πίνακας 10, SPO03 πίνακας 06, Απογραφή 2021), σταθερότητα των URLs του portal (`documentID`), εκτίμηση κόστους parsing | Ένας πρωτότυπος parser διαβάζει έναν πίνακα σε long format και περνά το contract |
| A3 | Σάρωση υπαρχόντων έργων | Σημείωμα `docs/landscape.md`: ελληνικά και ευρωπαϊκά δημογραφικά παρατηρητήρια (π.χ. ΠΑΝΔΩΡΑ / ΕΔΚΑ, άτλαντες ΕΚΚΕ), επικαλύψεις, πιθανοί εξωτερικοί reviewers | Κάθε ισχυρισμός με πηγή και βαθμό (VERIFIED / INFERENCE / UNKNOWN) |
| A4 | Κλείσιμο Φάσης 0 | Ενημέρωση του PROPOSAL §10 με τα αποτελέσματα των A1–A3 | Και τα τρία κριτήρια της Φάσης 0 ικανοποιούνται (το registry και η ADR 0004 ήδη ναι) |
| A5 | Αφαίρεση διπλοεγγραφών (ADR 0006) | Οι διπλοεγγραφές της λίστας της ADR 0006 αντικαθίστανται με παραπομπές ή με αρχεία που παράγονται αυτόματα | Test που συγκρίνει τη λίστα domains του README με τα `probe_url` του registry· καμία τιμή του registry, του `definitions.yaml` ή του `provenance.py` αντιγραμμένη σε κείμενο |

## Μέρος Β: Φάση 1, πυρήνας δεδομένων

| # | Βήμα | Παραδοτέο | Έλεγχος ολοκλήρωσης |
|---|---|---|---|
| B1 | Αναδιάρθρωση πακέτου | `jsonstat.py` → `grpop/parse/`· κενά modules κατά την ADR 0005· `pyright` (ή `mypy --strict`) στο CI για `provenance`, `parse` | Υπάρχοντα tests πράσινα, έλεγχος τύπων πράσινος |
| B2 | `snapshots/` | Content-addressed αποθήκη (sha256) + manifest JSON· απαγόρευση overwrite· αποθήκευση ως GitHub Release assets στο CI | Tests: ίδιο περιεχόμενο ⇒ ίδιο hash· δεύτερη εγγραφή ίδιου hash δεν αλλάζει τίποτα· διαφορετικό περιεχόμενο με ίδιο κλειδί πηγής ⇒ νέα έκδοση, όχι αντικατάσταση |
| B3 | Connector Eurostat | Adapter που κατεβάζει τα datasets της Φάσης 1 σε snapshots, με retry/backoff και το `User-Agent` του probe | Τρέχει στο GitHub Actions· fixtures καταγεγραμμένα από πραγματικές απαντήσεις (όχι χειρόγραφα) |
| B4 | `parse/`: JSON-stat → observations | Μετατροπή σε πίνακα του contract: flags της Eurostat → `status`, `retrieved_at` από το snapshot, `source_url`, `vintage` | Κάθε έξοδος περνά το `validate_observations`· test για κάθε flag της Eurostat που εμφανίζεται στα datasets |
| B5 | `harmonize/` | Concordance NUTS 2016/2021/2024 ως CSV στο `data/reference/` για τους ελληνικούς κωδικούς | Invariants: τα σύνολα διατηρούνται· κάθε κωδικός αντιστοιχίζεται ακριβώς μία φορά |
| B6 | `indicators/`: μηχανισμός | Προδιαγραφή δείκτη (`id@version`, inputs, μονάδα, `nature`, επίσημο αντίστοιχο) και γεννήτρια acceptance tests | Ένας δείκτης-δείγμα (π.χ. #12 δείκτης γήρανσης) περνά από άκρη σε άκρη, με test συμφωνίας με το `demo_pjanind` |
| B7 | `indicators/`: οι 12 δείκτες του §4 | Εθνικό επίπεδο και NUTS 2 | **Όλοι οι `derived` δείκτες συμφωνούν με την Eurostat εντός στρογγυλοποίησης** (κριτήριο Φάσης 1) |
| B8 | `build.py` + `publish/` | CLI `grpop build`, ρητό DAG με memoization βάσει hash· manifest του data product (Parquet + CSV) | **Δύο builds από το μηδέν δίνουν ίδια hashes εξόδου** (κριτήριο Φάσης 1)· καμία τιμή χωρίς μεταδεδομένα |

## Μέρος Γ: Φάση 1, design system και γραφήματα (παράλληλα με το Β από το B1 και μετά)

| # | Βήμα | Παραδοτέο | Έλεγχος ολοκλήρωσης |
|---|---|---|---|
| Γ1 | `design/` tokens | `tokens.json` (χρώματα, τυπογραφία, διαστήματα)· γεννήτριες για CSS variables, JS module και Quarto `_brand.yml` | Validators ως tests: αντίθεση WCAG 2.2 AA σε light/dark, διακρισιμότητα παλετών, αριθμητική μορφή `el-GR` (`10.372.335`, `−0,03%`) |
| Γ2 | `charts/` βάση | ES module πάνω στο Observable Plot· η συνάρτηση επιστημικής γραμματικής `(nature, status) → στυλ`· κάθε γράφημα επιστρέφει σχήμα + πίνακα + alt text + CSV | Unit tests για κάθε συνδυασμό `nature` × `status` |
| Γ3 | Τύποι γραφημάτων | Γραμμή, πυραμίδα με overlay, fan chart, tile-grid small multiples, choropleth + cartogram, Lexis surface | Playwright visual regression σε light/dark/print· **έλεγχοι προσβασιμότητας και αντίθεσης για όλους τους τύπους** (κριτήριο Φάσης 1) |
| Γ4 | Σκελετός `site/` (Quarto) | Quarto website με `_brand.yml` από το Γ1, μία σελίδα-δείγμα με γράφημα από το L5, συνάρτηση `fact(metric, geo, period)` | Το render στο CI **αποτυγχάνει** αν μια σελίδα ζητήσει τιμή που λείπει ή δεν έχει provenance (test με σκόπιμα λάθος σελίδα) |

## Κριτήρια ολοκλήρωσης Φάσης 1 (PROPOSAL §10) και πού ελέγχονται

| Κριτήριο | Βήμα |
|---|---|
| Όλοι οι `derived` δείκτες συμφωνούν με την Eurostat | B7 |
| Καμία τιμή χωρίς μεταδεδομένα | B4, B8, Γ4 |
| Το pipeline αναπαράγεται από το μηδέν | B8 |
| Όλοι οι τύποι γραφημάτων περνούν τους ελέγχους προσβασιμότητας και αντίθεσης | Γ1, Γ3 |

## Εκτός εύρους αυτού του σχεδίου

- **Φάση 2:** Observatory v1, working paper R1, μεθοδολογικό εγχειρίδιο, data release με DOI.
- **Φάση 3:** NUTS 3, δημοτικά δεδομένα και small-area estimation (ADR 0004), cohort-component simulator, R bridge (`bayesPop`), βιβλιογραφία.
- **Ανοιχτό θέμα που επηρεάζει τη Φάση 2:** εξωτερικός reviewer (PROPOSAL §1B, §12). Η σάρωση A3 προτείνει υποψηφίους, αλλά την επαφή την κάνει ο υπεύθυνος έκδοσης.
