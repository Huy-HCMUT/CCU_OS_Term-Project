# Final report (M4)

IEEE conference-format report: `main.tex` with one file per section in `sections/`,
references in `references.bib`, and the compiled `main.pdf`. Figures are read
directly from `results/phase6b/` and `results/phase5d/`.

```bash
cd paper_ieee
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

Section owners (WBS): `sections/system.tex` is Huy's (P7.1) and was drafted for his
review; the statistical analysis, discussion, limitations and conclusion are
An-Rui's (P7.2). Every table names the result file its numbers come from.
