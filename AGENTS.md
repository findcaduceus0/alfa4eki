# Project Overview

This repository contains a handcrafted PDF generator that reproduces a
reference template byte-for-byte.  The approach is based on parsing a
sample PDF (`pdf 16.pdf`), extracting all static objects and the
character mapping used by the embedded font.  Only the content stream
(object `9 0`) is recompressed with new values; every other byte is
copied from the original template so that the output matches the sample
when identical field values are supplied.

## Goals

* Reconstruct the structure of the original PDF generator so the
  produced files are binary-identical to provided samples.
* Keep the cross reference table, object order, flate streams and
  subset font exactly as in the template.
* Encode text using the subset font; only glyphs present in the template
  are embedded.
* Provide tests that confirm byte-for-byte equality with the sample
  when using the same input values.

## Usage

```
python generate_pdf.py DATE_TIME OPERATION SBP_ID FILE_ID OUTPUT
```

`FILE_ID` must be a 32‑character hexadecimal string used for the `/ID`
field in the trailer.  Example values matching `pdf 16.pdf` are used in
`tests/test_pdf_generation.py`.

## Testing

Run `pytest` to ensure the generator reproduces the reference PDF.
The test regenerates `pdf 16.pdf` with the same data and compares the
bytes.

## Coding guidelines

* Keep output formatting and line endings exactly as in the template.
* Avoid introducing dependencies beyond `PyPDF2` and testing tools.
* Commit generated binaries only for reference templates; temporary
  output files should not be committed.

