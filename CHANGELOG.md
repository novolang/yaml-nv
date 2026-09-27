# Changelog

All notable changes to yaml-nv are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
package follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the pre-1.0 rule that a breaking change bumps the MINOR number.

## 0.1.0 — 2026-09-27

The first implementation of the interface published as 0.0.1: YAML 1.2
read by recursive descent over chapters 6 to 9 of the specification,
with the safety policy applied while the tree is built, and written in
block style.  Every case of the yaml-test-suite is read as the suite
says, except two that bind one key twice.

### Changed, breaking

- `YamlError` gains `ComplexKey(line, col)`, the refusal of a mapping
  key that is a collection under a policy that does not allow one.
- `YamlReader`'s fields are the state the reader keeps: `line`,
  `doc_index`, `partial`, `pending`, `in_doc`, `doc_lines`,
  `doc_line`, `marked`, `directives`, `anchors` and `failure`.  The
  interface's `col`, `indents`, `nodes`, `failed`, `failed_line` and
  `failed_col` are gone; `failure` holds the refusal whole.
- `yamlkeys.merge` answers a `YamlValue` rather than a `Result`: two
  trees always merge.
- `hardened()` sets `max_alias_uses` to 0, since it turns aliases off.

### Behaviour the interface left open

- A directive other than `%YAML` and `%TAG` is ignored, as section
  6.8.1 says of reserved directives; `BadDirective` is a `%YAML` for a
  version other than 1.x, a second `%YAML`, a malformed `%TAG`, or a
  directive with no document after it.
- An alias under a policy with aliases off is `AliasRepeatExceeded`
  with a limit of 0.  A scalar past `max_scalar_bytes` is
  `UnterminatedQuote` for a quoted one and `BadBlockScalar` otherwise.
- `feed` reads the open document as far as it has arrived, so a
  refusal in its complete lines is reported at once; an unclosed quote
  or bracket waits for the next chunk.
- A reader built with a negative budget refuses the first document that
  reaches it.
- The writer writes a string of several lines as a literal block
  scalar when its first line with text starts with no whitespace, and
  double-quoted otherwise; a mapping is always written in block style.

## 0.0.3 — 2026-09-15

README rewritten to the package README style guide (docs/writing-a-readme.md); no change to the interface.

## 0.0.2 — 2026-09-10

- **Toolchain floor is 0.8.9**: the bodies and signatures use what 0.8.9 added (`todo()`, a bound effect parameter, the four layers), and the manifest says so instead of letting an older toolchain fail on an undefined function.  No signature changed.

## [0.0.1] — 2026-09-09

**The interface, published before anyone implements it.** Every public
type and function carries its full signature, its effect row and its
doc comment; every body is `todo()`; the release is recorded
`implemented = false`.

### Added

- `yamlsafe` — the load-bearing interface. There is no unsafe loader
  to be the default of: one reader, its safety a `YamlLimits` value,
  and that value's `standard()` refusing every tag the core schema does
  not define. Widening it is `allowing(p, ["!Ref"])` — a call with a
  literal list, so the widening appears in the caller's diff. Three
  budgets stop a billion-laughs document: a depth bound, a node bound
  that answers the expansion directly, and a per-anchor bound so the
  refusal can name the anchor doing the damage. `hardened()` turns
  aliases off entirely, which is the right policy for a document that
  arrived from somewhere you do not control.
- `yamlnode` — `YamlValue` with the core schema's six kinds and null,
  `YamlPair` whose key is a NODE because YAML permits a collection as
  one, and `YamlSchema` for which resolution rules apply. `resolve` is
  public, because the rule that keeps Norway a country should be
  testable and quotable rather than buried in a parser.
- `yamlread` — the feed-and-drain reader. A YAML stream is a sequence
  of documents each complete at its terminator, so `feed` hands back
  finished documents while the rest of the stream is still arriving —
  which is why this package has a chunked reader and toml-nv does not.
  `read_all<S: Read[e]>` is the same machine with the pump inside it,
  charged whatever the caller's stream costs (SPEC § 5.6). `parse`
  refuses a multi-document stream rather than silently keeping the
  first, because picking one is how a deployment applies half a
  manifest.
- `yamlkeys` — path access in two channels, a `Result` form that tells
  `NoSuchKey` from `WrongKind` and a `?T` form for optional settings.
  A numeric segment indexes a sequence, which toml-nv's path language
  deliberately does not do. `is_null_at` separates "explicitly
  blanked" from "absent". `merge` does at a call site what YAML 1.1's
  `<<` key does invisibly.
- `yamlwrite` — block style out, under a `YamlWidth` policy that is
  three named cases rather than an integer, because a plain scalar
  with no spaces cannot be folded without changing its value and a
  caller should have said yes to that. `needs_quote` and
  `scalar_to_string` expose the rule a round trip is correct because
  of.
- `yamlerror` — twenty-two reasons, each carrying the line and the byte
  column, or `-1` where there is no such place. `is_safety_refusal`
  separates a file to go and fix from an input that may be hostile.

### Known

- `novo test` is red, and that is the release's expected state: every
  assertion in the API suite reaches `not implemented:
  yaml-nv.<module>.<fn>`. Run it with `--isolate` for one verdict per
  test naming the function it stopped at.
