# yaml-nv

YAML is a human-readable data format, specified in
[YAML 1.2.2](https://yaml.org/spec/1.2.2/). This package reads and
writes the **safe subset** of it in novo-lang, with no dependencies:
block and flow collections, the core schema's scalars, anchors and
aliases under a budget, block scalars, multi-document streams, and a
named refusal of every tag a safe loader must not honour. Nothing here
opens a file, and nothing here constructs a value from a tag.

**Status: NOT IMPLEMENTED — interface only.** Every function is
declared with its full signature, but every body is a `todo()` that
panics when called. The package is published so its design can be
reviewed and depended on before it is implemented. Version 0.1.0 will
be the first working release.

## What it is

A YAML **stream** is a sequence of **documents** separated by `---`. A
document is one node: a **scalar**, a **sequence** or a **mapping**.
Collections are written in **block style**, by indentation, or in
**flow style**, with `[…]` and `{…}`.

An **anchor**, written `&name`, labels a node. An **alias**, written
`*name`, refers back to it. A **tag**, written `!name` or `!!name`,
tells a loader what kind of thing a node is.

A **schema** is the set of rules that decides what an unquoted scalar
means. YAML 1.2 defines three and this package adds one for old files.

| Schema | What resolves |
| --- | --- |
| `SchemaFailsafe` | Strings, sequences and mappings. Every scalar is a string. |
| `SchemaJson` | JSON's types with JSON's spellings, and nothing else. |
| `SchemaCore` | JSON's, plus `Null`, `NULL`, `~`, `True`, `TRUE`, `0o` and `0x` integers, `.inf` and `.nan`. The default. |
| `SchemaLegacy11` | YAML 1.1's, in which `yes`, `no`, `on` and `off` are booleans and `1:30` is 90. |

Under the core schema `no` is the string `"no"`, and so are `NO`,
`off`, `on`, `y` and `n`. Only `true`, `True`, `TRUE`, `false`, `False`
and `FALSE` are booleans. That is the rule under which a list of
countries keeps Norway.

A **policy**, `YamlLimits`, is the value that says what this loader
will do. It is passed to every reading function, so two callers in one
program can hold different ones and neither can change the other's.

| Field | `standard()` | `hardened()` |
| --- | --- | --- |
| `max_depth` | 64 | 16 |
| `max_nodes` | 1 000 000 | 10 000 |
| `max_alias_uses` | 1 000 | — |
| `max_scalar_bytes` | 4 194 304 | 65 536 |
| `allowed_tags` | none | none |
| `allow_aliases` | true | false |
| `allow_complex_keys` | false | false |

## Install

```
novo pkg add yaml-nv
```

## Example

```novo
use yamlerror
use yamlkeys
use yamlread
use yamlsafe

fn main() [io]
    let text = "spec:\n  replicas: 3\n  image: nginx\n"

    // `standard()` refuses every tag the core schema does not define,
    // and bounds how far aliases may be expanded.
    match yamlread.parse(text, yamlsafe.standard())
        // A refusal names the line and the column to go and look at.
        Err(e)  => println(yamlerror.render(e, "deploy.yaml"))
        Ok(doc) =>
            // A dotted path. The `??` supplies a value when the key is
            // absent, because an absent key is not a failure.
            println("${yamlkeys.opt_int(doc, "spec.replicas") ?? 1}")
            println(yamlkeys.opt_str(doc, "spec.image") ?? "nginx")
```

`yamlerror.render(e, "deploy.yaml")` produces
`deploy.yaml:2:1: a tab where YAML requires a space`, which is the shape
an editor's error list parses.

Build and test with `novo pkg build` and `novo test`. Today `novo test`
fails on purpose: every test reaches a `not implemented:
yaml-nv.<module>.<fn>` panic. The tests are the specification the
implementation will have to satisfy.

## What the package contains

| Module | Contents |
| --- | --- |
| `yamlnode` | The value tree, the kinds, the four schemas, scalar resolution, equality, and the depth and node count a budget is measured in. |
| `yamlsafe` | The policy: the two ready-made ones, the calls that widen or tighten one, the core schema's tags, and a check of a tree against a policy. |
| `yamlread` | Reading: a chunk at a time, a whole string, a whole stream, bytes, or a stream the caller opened. |
| `yamlkeys` | Dotted-key access: lookups, typed reads that answer a result, optional reads for a default, and the edits over a tree. |
| `yamlwrite` | Writing: a document or a stream, two styles, the line-width policy, and the quoting rule on its own. |
| `yamlerror` | Every way a document is refused, each with the line and the column, and which refusals are the safety policy's. |

## How to choose an entry point

**`yamlread.parse` takes a whole document as text** and answers one
value. `parse_stream` answers every document in the text.

**`yamlread.reader`, `feed` and `finish` take chunks.** Each document
in a stream is complete at its terminator, so `feed` hands back
finished documents while the rest is still arriving. Use it for a pipe,
a socket, or a log of YAML records.

**`yamlread.read_all` takes a stream the caller opened.** It is
declared
`read_all<S: Read[e]>(src: S, p: YamlLimits) -> Result<[YamlValue], YamlError> [e]`,
so it costs the caller whatever the caller's stream costs: a file
charges `[io, fs]` and an in-memory buffer charges nothing.

**`yamlsafe.standard` is the policy for a document a person wrote.**
`yamlsafe.hardened` is the policy for a document that arrived from
somewhere you do not control.

**`yamlkeys` reads values out of a tree.** `int_at` and its siblings
answer a result naming the path; `opt_int` and its siblings answer
nothing for an absent key, which is the shape a default wants.

## The rules a user needs

1. **There is no unsafe loader.** A tag tells a loader to construct
   something, and loaders that honour that generally turn a document
   into remote code execution. Here there is one reader, its safety is
   a value it takes, and nothing in the package constructs anything.
2. **A tag outside the core schema is refused, not ignored.**
   `UnsafeTag` carries the position and the tag as written. A loader
   that quietly dropped `!!python/object/apply` would leave its caller
   believing the input had been checked.
3. **Widening the loader is written at the call site.**
   `yamlsafe.allowing(yamlsafe.standard(), ["!Ref", "!GetAtt"])` names
   the tags in a list a reviewer sees in the difference. An allowed tag
   is honoured by being ignored: the node resolves as if the tag were
   not there.
4. **Three budgets bound alias expansion, and each answers a different
   question.**

   | Budget | Question | Refusal |
   | --- | --- | --- |
   | `max_depth` | How deep may collections nest? | `TooDeep` |
   | `max_nodes` | How many nodes may the expanded document hold? | `AliasBudgetExceeded` |
   | `max_alias_uses` | How many times may one anchor be expanded? | `AliasRepeatExceeded` |

   `max_nodes` alone reports that a document is too big, which is true
   and useless. `max_alias_uses` reports which anchor was expanded how
   many times, which is the line to go and look at.
5. **`hardened()` turns aliases off rather than budgeting them.** A
   hostile document's cheapest attack is the one aliases enable, and a
   webhook body has no legitimate use for a backreference.
6. **`no` is a string.** See the schema table. `SchemaLegacy11` is the
   1.1 reading, named so that a call site says what it is opting into.
7. **The same key twice in one mapping is refused.** YAML 1.2 section
   3.2.1.1 makes keys unique. Most loaders keep the last one silently,
   which picks a winner nobody chose; `DuplicateKey` names both lines.
8. **A complex key is refused by default.** `? [a, b]` is legal YAML
   that almost nothing downstream can represent.
   `yamlsafe.with_complex_keys` turns it on.
9. **A tab in indentation has its own refusal.** A tab is invisible in
   the editor that produced it, so a line and column alone would send a
   person looking for something they cannot see.
10. **An anchor must be defined before it is used, and does not cross a
    document boundary.** An alias reaching backwards past a `---` is
    `UnknownAnchor`, the same as a typo.
11. **A scalar is bounded in bytes.** The bound is what keeps a
    document with one unclosed quote from accumulating the whole file
    into one string before the parser notices.
12. **A position points at the opening delimiter.**
    `UnterminatedFlow` reports the `[` or `{`, and `UnterminatedQuote`
    reports the quote. That is the byte a person has to go and fix.
13. **`feed` answers a new reader rather than changing the one you gave
    it.** The state is a value, so a reader can be kept or copied.
14. **`yamlerror.is_safety_refusal` separates the two kinds of
    failure.** A document that is malformed and a document the policy
    refused are different things to report to a person.
15. **`yamlerror.message` does not include the position.**
    `line_of` and `col_of` are separate, so a caller renders
    `file:line:col: message` in whatever shape its own diagnostics
    have. `yamlerror.render` is that shape, already assembled.
16. **The writer emits block style, and folds under a named policy.**
    `WidthUnlimited` never folds, `WidthFold` folds at a space before
    a column, and `WidthQuoteFold` re-spells a scalar as double-quoted
    where folding is otherwise impossible. It is the only policy that
    changes how a value is written to meet a formatting rule.
17. **A `---` is always emitted between the documents of a stream**,
    whatever the style says, because without it there is no stream.

## What is not included

- **Any input or output.** The caller holds the bytes.
  `yamlread.read_all` takes a stream the caller opened.
- **Construction from a tag.** See rule 1. This is the feature the
  package exists not to have.
- **The `<<` merge key.** It is a YAML 1.1 resolution rule that
  silently rewrites a document. `yamlkeys.merge` does the same job at a
  call site where a reader can see it happen.
- **`!!binary` and the other type-specific tags beyond the core
  schema.** A caller that wants one allows it by name; see rule 3.
- **A subprocess.** Nothing here shells out. A library whose behaviour
  depends on what is in the path cannot be depended on and cannot be
  reviewed.
- **Comment-preserving round trips.** A parsed document is a value
  tree, and the writer spells it under a style.
  [toml-nv](https://novo-lang.org/packages/toml-nv)'s editing document
  is the shape for changing one value in a file a person maintains.
- **A microcontroller build.** The tree is an allocation per document
  and the scanner speaks `Str`.

## Related packages

- `std.yaml` in the standard library reads a flat subset: mappings and
  sequences of scalars, with no nesting, no flow style, no anchors and
  no multi-document streams. Its error channel is an optional, so a
  failure has no reason and no position, and under `novo run` it can
  shell out to `yq` for fidelity it does not have itself. This package
  is a native parser with positions, a safety policy and the whole safe
  subset.
- [toml-nv](https://novo-lang.org/packages/toml-nv) is the other
  configuration format with types and nesting. It has a
  comment-preserving editing document, which this package does not, and
  no feed-and-drain reader, because a TOML document is not complete
  until its last line: a `[table]` header at the bottom can add keys to
  a table defined at the top.
- [ini-nv](https://novo-lang.org/packages/ini-nv) and
  [dotenv-nv](https://novo-lang.org/packages/dotenv-nv) are the flat
  configuration formats on the registry.
- [schema-nv](https://novo-lang.org/packages/schema-nv) validates a
  document against JSON Schema. Whether a YAML manifest has the fields
  it should is that question, not this one.

## Tests

```bash
novo test --isolate tests/yamlread_tests.nv    # 13 tests: the grammar and the refusals
novo test --isolate tests/yamlkeys_tests.nv    # 10 tests: dotted paths and typed reads
novo test --isolate tests/yamlnode_tests.nv    #  9 tests: the tree and scalar resolution
novo test --isolate tests/yamlsafe_tests.nv    #  9 tests: the policy and the budgets
novo test --isolate tests/yamlcover_tests.nv   #  8 tests: the corners of the format
```

The YAML 1.2.2 specification is the oracle and the `yaml-test-suite`
corpus is the vector set the implementation will be measured against.
`libyaml` is the reference for the scanner's state machine and the
block-context rules, `go-yaml` for the shape of the reading API, and
PyYAML for the list of what a safe loader must refuse, which is a list
learned the hard way.

The suite asserts that `no` is a string under the core schema and a
boolean under the 1.1 one, that a language-specific tag is refused with
its position, that an allowed tag resolves as if it were absent, that
each of the three budgets refuses the document that exceeds it and
names what it counted, that a duplicate key is refused with both lines,
that a tab in indentation has its own refusal, that an alias cannot
reach past a `---`, and that a chunk may split a document anywhere.

The tests compile today and fail at run, each on the `not implemented`
panic that is its body. That is the expected state of an interface
release. They turn green one at a time as bodies land.

## Implementation status

Nothing is implemented. Every function here is declared with its
signature and its effect row, and every body is a `todo()`.

| Module | Public types | Functions | Implemented |
| --- | --- | --- | --- |
| `yamlnode` | `YamlValue`, `YamlPair`, `YamlKind`, `YamlSchema` | 9 | no |
| `yamlerror` | `YamlError`, with `impl Error` | 4 | no |
| `yamlsafe` | `YamlLimits` | 11 | no |
| `yamlread` | `YamlReader` | 11 | no |
| `yamlkeys` | — | 24 | no |
| `yamlwrite` | `YamlStyle`, `YamlWidth` | 10 | no |

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
