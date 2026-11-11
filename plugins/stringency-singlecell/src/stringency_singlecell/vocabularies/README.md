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
replicate's label whose organs exclude the project's organ (`spec/predicates.md`). Four
vocabularies carry the map: `tissue_structures_mouse@1` and `@2`, and `cell_types_mouse@2` and
`@3` (copied from the `organs` column of the Xenium method's
`annotate-clusters/cell_types_mouse.csv`, `all` written `[any]`). A map changes no label, so it
needs no new vocabulary version.

`cell_types_mouse@3` and `tissue_structures_mouse@2` (0.10.7, 2026-11-11) add seven organs:
large intestine, kidney, heart, skin, lymph node, the female reproductive tract and brain. Both
files are written by the Xenium method's `tools/build_vocabulary_tables.py` from its two tables,
which are in turn written from the lists the owner approved organ by organ
(`docs/cell-type-corpus/` there); do not edit them by hand. The organ names `lymph_node` and
`female_reproductive_tract` are new in `ORGANS`.
