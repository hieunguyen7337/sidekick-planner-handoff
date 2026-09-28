# arXiv Submission Metadata Template

This document provides the fill-in template for arXiv submission form fields.
The project-specific draft values and extended analysis for this paper are in a private
release note, `paper/release/metadata.md`, which is not published.

Tags: `[OBSERVED <source>]` denotes a fact checked against the source. The arXiv help pages
were fetched on 2026-09-28 (`help/prep.html`, `help/license/index.html`,
`help/endorsement.html`, `help/submit_tex.html`); quotes below are from those copies.
`[INFERRED]` denotes reasoning or a recommendation.

**Every metadata field is ASCII-only**: "Our metadata fields only accept ASCII input. Unicode
characters should be converted to its TeX equivalent" `[OBSERVED help/prep.html]`. The build
writes ASCII copies of the three text fields; paste those, not text copied from the PDF (curly
quotes, long dashes and ligatures copied from a PDF viewer are the usual "Bad character(s)"
error `[OBSERVED help/prep.html]`):

| Field | File (in `<outdir>/`) | Checked by |
| :--- | :--- | :--- |
| Title | `title.txt` | `check_tex.sh` [8/8]: FAIL on non-ASCII or all-uppercase |
| Authors | `authors.txt` (from YAML `author`: `Name (Affiliation), ...`) | FAIL on non-ASCII; WARN on a group name |
| Abstract | `abstract.txt` | FAIL on non-ASCII or more than 1920 characters |

---

## 0. Before submitting: endorsement

- "arXiv requires that users be endorsed before submitting their first paper to arXiv or a new category" `[OBSERVED help/endorsement.html]`.
- Automatic endorsement applies when "your email address meets the institutional email criteria"; otherwise "you can seek personal endorsement from an established arXiv author" `[OBSERVED help/endorsement.html]`. "First time submitters to arXiv are encouraged to associate an institutional email address if they have one ... This will expedite the endorsement process" `[OBSERVED help/endorsement.html]`.
- A first submission from a personal (non-institutional) address may therefore wait on an endorser: associate the institutional address with the arXiv account, or line up an endorser in the target category, before the paper is ready `[INFERRED]`.

---

## 1. Title

```text
[paste <outdir>/title.txt]
```

- "Do not use all uppercase letters. Do not use unicode characters. Some LaTeX is supported through MathJax" `[OBSERVED help/prep.html]`.
- "Expand out TeX macros that are mystifying" `[OBSERVED help/prep.html]`.
- Verify that the title matches the title in the compiled PDF `[INFERRED]`.

---

## 2. Authors

```text
[paste <outdir>/authors.txt, e.g. Firstname Lastname (Affiliation)]
```

- "Names must be given in the order: Firstname Lastname or Firstname Middlename Lastname" and "Do not include honorifics, such as "Dr.", "Professor", etc." `[OBSERVED help/prep.html]`.
- "Multiple author names should be separated with a comma ... or with the word "and"" `[OBSERVED help/prep.html]`.
- "Affiliations must be placed within parentheses. Do not enter full mailing address"; at most a city and country; several authors from the same institution may use the numbered footnote style `Author One (1), Author Two (1 and 2) ((1) Institution One, (2) Institution Two)` `[OBSERVED help/prep.html]`.
- "Anonymous submissions are not accepted. Complete, and accurate author information is required." A named collaboration may appear alone in the metadata, but "a complete list of all authors and their affiliations must be contained in the full printed text" `[OBSERVED help/prep.html]`.
- "Generative AI language tools should not be listed as an author" `[OBSERVED help/prep.html]`.
- Email addresses belong in the PDF (YAML `author[].email`), not in this field `[INFERRED]`.
- YAML forms that compile: `author: "Firstname Lastname"`, or a list of maps with `name`, `affiliation` (string or list) and `email`; each author becomes one column of the title block and `pdfauthor` lists the names `[OBSERVED paper/arxiv/template.tex; v2_fixed_authortest]`.

---

## 3. Abstract

```text
[paste <outdir>/abstract.txt]
```

- "abstracts longer than 1920 characters will not be accepted" `[OBSERVED help/prep.html]`. The build counts characters *after* ASCII folding (a TeX replacement such as `$\delta$` is longer than the character it replaces); `check_tex.sh` FAILs above 1920 and prints how many characters to cut `[OBSERVED paper/arxiv/check_tex.sh]`.
- "Do not include the word "Abstract"" `[OBSERVED help/prep.html]`.
- "Carriage returns will be stripped unless they are followed by leading white spaces"; "Avoid unnecessary blank lines" `[OBSERVED help/prep.html]`. `meta_ascii.pl` writes one line per paragraph and indents every paragraph after the first `[OBSERVED paper/arxiv/meta_ascii.pl]`.
- "unicode character entry is not supported"; omit TeX-isms such as `~` and font commands `[OBSERVED help/prep.html]`. The build extracts with `-f markdown-smart` (straight quotes, no no-break space after "et al.") and maps minus signs, dashes, `×`, `≥` and Greek letters to ASCII or TeX; anything else non-ASCII makes the build and the check FAIL, naming the code point `[OBSERVED paper/arxiv/build.sh step 7]`.
- Count: `abstract chars: N` in `<outdir>/build.log`, or `Abstract: N characters` in `check_report.txt`.

---

## 4. Comments

```text
N pages, M figures
```

- "Indicate number of pages and number of figures" `[OBSERVED help/prep.html]`. The counts come from `check_report.txt` (`arXiv Comments: N pages, M figures`) `[OBSERVED paper/arxiv/check_tex.sh]`.

---

## 5. Primary Category & Cross-Lists

*Status: TO BE DECIDED (detailed analysis in `paper/release/metadata.md`, not published) `[INFERRED]`.*

Candidate categories:
- **`cs.AI` (Artificial Intelligence)**: Covers planning, knowledge representation, heuristics, and reasoning architectures; recommended primary `[INFERRED]`.
- **`cs.CL` (Computation and Language)**: Covers natural language processing and LLM-agent reasoning; candidate cross-list `[INFERRED]`.
- **`cs.LG` (Machine Learning)**: Covers learning methodology, fine-tuning, and empirical evaluation; candidate cross-list `[INFERRED]`.
- **`cs.MA` (Multiagent Systems)**: Covers distributed intelligent agents and coordinated agent interactions; candidate cross-list `[INFERRED]`.

Endorsement is per category ("their first paper to arXiv or a new category"), so choose the primary before asking an endorser `[OBSERVED help/endorsement.html; INFERRED]`.

---

## 6. License Options

The six licenses listed on the license page `[OBSERVED help/license/index.html]`:

1. **CC BY 4.0** (Creative Commons Attribution). The page notes: "Many publishers allow preprints to be deposited with a CC BY license. Check directly with the journal" `[OBSERVED]`.
2. **CC BY-SA 4.0** (Creative Commons Attribution-ShareAlike) `[OBSERVED]`.
3. **CC BY-NC-SA 4.0** (Creative Commons Attribution-Noncommercial-ShareAlike) `[OBSERVED]`.
4. **CC BY-NC-ND 4.0** (Creative Commons Attribution-Noncommercial-NoDerivatives); "Many publishers allow "accepted manuscripts" to be deposited with a CC BY-NC-ND license, but there may be an embargo period" `[OBSERVED]`.
5. **arXiv.org perpetual, non-exclusive license 1.0** `[OBSERVED]`: grants arXiv the right to distribute while the author keeps the rest; the conservative choice when a later venue's policy is unknown `[INFERRED]`.
6. **CC0 1.0** (public domain dedication): "allows creators to give up their copyright and put their works into the worldwide public domain" `[OBSERVED]`.

- "The license chosen is irrevocable and cannot be changed", and it is chosen per version `[OBSERVED help/license/index.html]`.
- "A Creative Commons CC0 1.0 Universal Public Domain Dedication will apply to all metadata" whatever the paper's license `[OBSERVED help/license/index.html]`.

---

## 7. Fields Left Blank

| Field | Value | Reason |
| :--- | :--- | :--- |
| **Report-no** | *(blank)* | "required only when supplied by author's institution"; none assigned `[OBSERVED help/prep.html]`. |
| **Journal-ref** | *(blank)* | "reserved for publication info" of an already published version `[OBSERVED help/prep.html]`. |
| **DOI** | *(blank)* | "reserved publication DOI" of a published version `[OBSERVED help/prep.html]`. |
| **MSC-class** | *(blank)* | "math archives only" `[OBSERVED help/prep.html]`. |
| **ACM-class** | *(blank or e.g. `I.2.7; I.2.8`)* | "cs archives only", optional `[OBSERVED help/prep.html]`; the classes are a suggestion `[INFERRED]`. |

---

## 8. TeX Live

"arXiv offers currently TeX Live 2023 and 2025 (the default)" `[OBSERVED help/submit_tex.html]`.
The build uses TinyTeX / TeX Live 2026; `package.sh` therefore compiles the tarball a second
time in a clean room on TeX Live 2025 (`$PUBTOOLS/tl2025`) and FAILs on errors or a page-count
change `[OBSERVED paper/arxiv/package.sh]`. arXiv's exact TL2025 snapshot date is unknown; the
local TL2025 is the final 2025 release `[INFERRED small residual risk]`.
