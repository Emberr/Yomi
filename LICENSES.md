# Third-Party Licenses and Attribution

Yomi source code is licensed under the GNU Affero General Public License v3.0
(AGPL-3.0-or-later). See `LICENSE` in the repository root.

This file records licenses and required attributions for all third-party
content datasets and runtime dependencies bundled with or downloaded by Yomi.
Add a new section whenever a new source is introduced.

---

## Content Datasets

### Hanabira Japanese Content

- **Repository:** https://github.com/tristcoil/hanabira.org-japanese-content
- **Used for:** Grammar point definitions (N5–N1), formation patterns, example sentences
- **Files ingested:** `grammar_json/grammar_ja_{N5,N4,N3,N2,N1}_full_alphabetical_0001.json`
- **License:** Creative Commons License (exact variant not published in repository;
  README states content is under a Creative Commons License requiring attribution
  to hanabira.org). Treated conservatively as CC BY-SA.
- **Attribution required:** Include a visible link to https://hanabira.org in the
  application About page and in relevant content footers.
- **Distribution note:** Source files are downloaded at ingestion time and not
  committed to this repository.

### JMDict / JMDict Simplified

- **Original project:** JMdict by Jim Breen and the Electronic Dictionary Research
  and Development Group (EDRDG) — https://www.edrdg.org/jmdict/j_jmdict.html
- **Simplified format by:** Dmitry Shpika (scriptin)
  — https://github.com/scriptin/jmdict-simplified
- **Version pinned:** 3.6.2+20260511143416
- **Used for:** Japanese–English vocabulary browser (`vocab_items` table)
- **License:** EDRDG License — https://www.edrdg.org/edrdg/licence.html
  The EDRDG License is a permissive share-alike license. Derived files must be
  distributed under the same license with the following attribution.
- **Required attribution (verbatim):**
  > This application uses the JMdict dictionary file. This file is the property
  > of the Electronic Dictionary Research and Development Group, and is used in
  > conformance with the Group's licence.
  > (https://www.edrdg.org/edrdg/licence.html)
- **Additional credit:** Dmitry Shpika's jmdict-simplified project for the
  machine-readable JSON format.
- **Distribution note:** Source ZIP is downloaded at ingestion time and not
  committed to this repository.

---

## Deferred / Excluded Sources

### bunpou/japanese-grammar-db

- **Repository:** https://github.com/bunpou/japanese-grammar-db
- **License:** GPL-3.0 (confirmed)
- **Status:** **Excluded from M3.1.** The interaction between GPL-3.0 data
  content and AGPL-3.0 code distribution requires legal review before ingestion.
  Do not ingest from this source until compatibility is confirmed and documented
  here.

---

## Runtime Dependencies

Runtime dependency licenses are recorded in each service's `pyproject.toml`
or `package.json`. All selected dependencies are AGPL-3.0 compatible (MIT,
Apache-2.0, LGPL, or AGPL). A full SBOM will be generated before the v1.0
release (Phase 6).
