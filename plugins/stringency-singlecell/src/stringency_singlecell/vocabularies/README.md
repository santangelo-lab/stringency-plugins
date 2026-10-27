Vocabulary files: `<name>.yml` with `name`, `version`, and `labels` (a list). Loaded as
`name@version`. Filled by app-1 session 6.

## Organs (0.10.0)

A vocabulary may also carry `organs:`, a mapping of label to the organs it is found in (the
owner, 2026-10-27: a judgment vocabulary is matched by species and by tissue, "only a kidney has
nephrons"):

```yaml
organs:
  crypt: [small_intestine, large_intestine]
  periportal: [liver]
  mixed: [any]
```

Organ names: `liver`, `lung`, `small_intestine`, `large_intestine`, `spleen`, `kidney`, `heart`,
`skin`, `brain`; `[any]` is every organ. Every key must be one of the vocabulary's labels, and a
label the map leaves out is not judged. The engine reads only `labels` (its `Plugin.vocabularies`
is the flat tuple); the plugin loads the map into `stringency_singlecell.VOCABULARY_ORGANS`
(`name@version -> label -> organs`, validated at import) and `sc.label_outside_organ` flags a
replicate's label whose organs exclude the project's organ (`spec/predicates.md`). Two
vocabularies carry the map: `tissue_structures_mouse@1` and `cell_types_mouse@2` (the latter
copied from the `organs` column of the Xenium method's `annotate-clusters/cell_types_mouse.csv`,
`all` written `[any]`). A map changes no label, so it needs no new vocabulary version.
