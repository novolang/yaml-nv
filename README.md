# yaml-nv

**Status: NOT IMPLEMENTED — interface only.**

Every public function below is published with its signature and its
effect row, and every body is `todo()`. Installing this package works;
calling it panics with `not implemented`.

## What this is

The safe subset of YAML 1.2, read and written by a package that
performs nothing itself. Block and flow collections, the core schema's
scalar resolution, anchors and aliases behind a budget that stops a
billion-laughs document, multi-document streams, block scalars — and an
explicit, loud refusal of the tags a safe loader must never honour. The
reader is a feed-and-drain state machine you hand chunks to; the writer
emits block style under a named line-width policy.

It is for the program that reads YAML somebody else wrote: a deployment
tool reading manifests, a CI runner reading a pipeline file, a service
reading its own configuration, an admission controller reading a request
body it did not ask for.

```
novo pkg add yaml-nv
novo pkg build
novo test
```

## The one example that will work

```novo
use yamlread
use yamlsafe
use yamlkeys

fn replicas_of(text: Str) -> Result<Int, YamlError>
    let doc = yamlread.parse(text, yamlsafe.standard())!
    Ok(yamlkeys.opt_int(doc, "spec.replicas") ?? 1)
```

A malformed document stops with a `YamlError` that carries the line and
the column — `yamlerror.render(e, "deploy.yaml")` produces
`deploy.yaml:2:1: a tab where YAML requires a space`, which is the
message the format's users have spent twenty years not getting.

## The load-bearing interface: there is no unsafe loader

YAML's danger is not its syntax, it is its extensibility. A tag tells a
loader to *construct* something, and the loaders that honour that
generally — PyYAML's `load`, `Psych.load` before it was changed,
SnakeYAML's default constructor — turn a document into remote code
execution. The industry's answer has been a second function called
`safe_load`, and the failure mode of that answer is that the unsafe one
is still the shorter name and still the default in the examples people
copy.

So this package has no unsafe loader to be the default of. There is one
reader, its safety is a value it takes, and that value's default
refuses every tag the core schema does not define:

```novo
pub struct YamlLimits
    max_depth: Int
    max_nodes: Int
    max_alias_uses: Int
    max_scalar_bytes: Int
    allowed_tags: [Str]
    allow_aliases: Bool
    allow_complex_keys: Bool

pub fn standard() -> YamlLimits
pub fn hardened() -> YamlLimits
pub fn allowing(p: YamlLimits, tags: [Str]) -> YamlLimits
```

Widening the loader means writing down which tags you are allowing, at
the call site, in a list someone reviewing the diff can see:

```novo
let p = yamlsafe.allowing(yamlsafe.standard(), ["!Ref", "!GetAtt"])
```

A caller who wanted CloudFormation's tags has said so; a caller who
wanted `!!python/object/apply` has to name it, and no reviewer will let
that through. And an allowed tag is honoured by being *ignored* — the
node resolves as if the tag were not there. Nothing in this package
constructs anything, which is what makes "allowing a tag" a safe thing
to be able to do at all.

A tag that is not allowed is `UnsafeTag` with a position, **not a
silence**. A loader that quietly dropped `!!python/object/apply` would
leave its caller believing the input had been checked.

### The three budgets

The other half of safety is arithmetic. An alias is a reference and
expanding it copies, so:

```yaml
a: &a ["x","x","x","x","x","x","x","x","x"]
b: &b [*a,*a,*a,*a,*a,*a,*a,*a,*a]
c: &c [*b,*b,*b,*b,*b,*b,*b,*b,*b]
```

grows by nine per line — the billion laughs, and twenty lines reach a
terabyte. Three counters stop it, and each answers a different question:

| budget | question | refusal |
| --- | --- | --- |
| `max_depth` | how deep may collections nest? | `TooDeep` |
| `max_nodes` | how many nodes may the *expanded* document hold? | `AliasBudgetExceeded` |
| `max_alias_uses` | how many times may *one* anchor be expanded? | `AliasRepeatExceeded` |

Two expansion bounds rather than one because `max_nodes` alone reports
"this document is too big", which is true and useless, while
`max_alias_uses` reports "`&b` was expanded 812 times", which is the
line to go and look at.

`hardened()` turns aliases off entirely rather than budgeting them: for
a document that arrived from somewhere you do not control, the simplest
correct policy is that backreferences do not exist, and a webhook body
has no legitimate use for one.

## The layer, and why

`core` — no effects at all, on a package whose whole subject is a file.

A YAML scanner is arithmetic over bytes the caller already holds:
nothing is opened, nothing is waited for, and the state carried between
chunks is a few integers and two strings. The host owns the stream;
this package owns the grammar. Crucially, **nothing here resolves a tag
by looking something up** — that is what "safe loader" means, and it is
also why the package can honestly claim `[]`.

The one function that meets a stream stays inside the budget by
**binding** its cost rather than spending one:

```novo
pub fn read_all<S: Read[e]>(src: S, p: YamlLimits) -> Result<[YamlValue], YamlError> [e]
```

`S: Read[e]` binds the effect parameter of the standard library's
`Read` trait and the clause uses it, so the row means *whatever the
impl behind `S` supplies*. A file charges its caller `[io, fs]`; an
in-memory buffer charges nothing; `yaml-nv` is charged neither.

## Why this has a feed-and-drain reader and toml-nv does not

The difference is where a document ends. A TOML document is not complete
until its last line, because a `[table]` header at the bottom can add
keys to a table defined at the top — so a chunk-at-a-time TOML reader
would buffer the whole file and only be lying about it in its type. A
YAML **stream** is a sequence of documents separated by `---`, and each
is complete at its terminator. So `feed` here can hand back finished
documents while the rest of the stream is still arriving:

```novo
pub fn reader(p: YamlLimits) -> YamlReader
pub fn feed(r: YamlReader, chunk: Bytes) -> (YamlReader, [YamlValue])
pub fn finish(r: YamlReader) -> Result<[YamlValue], YamlError>
```

which is what a caller tailing a manifest stream, reading a
multi-document config from a pipe, or parsing a log of YAML records
wants. `feed` returns a *new* reader rather than mutating one, because
`[mutate]` is a host effect and this package has none.

## The Norway problem is not a bug here

YAML 1.1 resolved `no` to false, which is why a country list containing
Norway loses a country. YAML 1.2's core schema does not: `no` is the
string `"no"`, and so are `NO`, `off`, `on`, `y` and `n`. Only
`true`/`True`/`TRUE` and `false`/`False`/`FALSE` are booleans.

This package implements 1.2. The 1.1 reading exists — some files were
written for a 1.1 loader and have to be read — but it is
`SchemaLegacy11`, named so that the call site says what it is opting
into, because a default that loses Norway should be one you chose.

## How this differs from `std.yaml`

`std.yaml` reads a **flat** subset: mappings and sequences of scalars,
no nesting, no flow style, no anchors, no multi-document streams. Its
whole error channel is `?T`, so a failure is `None` with no reason and
no position. Under `novo run` it can shell out to `yq` for full
fidelity; under LLVM it is the C subset only. It is not available at
`@tier(embedded)`.

`yaml-nv` is **the library a program depends on**:

- **A native parser.** No subprocess anywhere — which is the difference
  that matters most, because a library whose behaviour depends on what
  is in `$PATH` cannot be depended on, and cannot be reviewed.
- **The safety policy above**, which `std.yaml` has no notion of.
- **Positions.** Every refusal names the line and the byte column.
- **The whole safe subset**: nesting, flow style, anchors, block
  scalars, multi-document streams.
- **`core`**, so it builds for embedded and for wasm.

## The reference implementation

`libyaml` for the scanner's state machine and for the block-context
rules, and `go-yaml` for the shape of a reading API that people have
actually been able to use. PyYAML for the list of what a safe loader
must refuse, which is a list learned the hard way and worth taking
whole. The YAML 1.2.2 specification is the oracle and the
`yaml-test-suite` corpus is the vector set the implementation will be
measured against.

Deliberately not ported: YAML 1.1's `<<` merge key, which is a
resolution rule that silently rewrites a document — `yamlkeys.merge`
does the same job at a call site where a reader can see it happen;
`!!binary` and the other type-specific tags beyond the core schema,
which a caller allows by name if it wants them; and any form of
construction from a tag, which is the feature this package exists to
not have.

## Status

Every function is `todo()`. `novo test --isolate` runs the API suite
and every assertion reaches `not implemented: yaml-nv.<module>.<fn>`,
which is the expected result until the bodies land.

| module | public types | functions | implemented |
| --- | --- | --- | --- |
| `yamlnode` | `YamlValue`, `YamlPair`, `YamlKind`, `YamlSchema` | 9 | no |
| `yamlerror` | `YamlError` (+ `impl Error`) | 4 | no |
| `yamlsafe` | `YamlLimits` | 11 | no |
| `yamlread` | `YamlReader` | 11 | no |
| `yamlkeys` | — | 24 | no |
| `yamlwrite` | `YamlStyle`, `YamlWidth` | 10 | no |

Nine public types, 69 public functions and one trait impl.

## Licence

Apache-2.0.
