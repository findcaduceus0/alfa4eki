# Future Tasks

1. **Support additional templates** – analyse other sample PDFs
   (`pdf 17.pdf` … `pdf 20.pdf`) and confirm the generator can reproduce
   them when provided with matching input data.
2. **Automate character map extraction** – build tools to automatically
   derive glyph mappings from any new template.
3. **Parameterize object set** – allow dynamic selection of objects to
   edit while keeping identical byte layout.
4. **Add continuous integration tests** – verify byte equality for all
   reference templates on every commit.
5. **Document font subset logic** – explain how glyph subsets are
   embedded and how to extend them if new characters appear.
6. **Provide CLI for bulk generation** – generate multiple PDFs with
   varying data in one run while preserving identity with templates.

