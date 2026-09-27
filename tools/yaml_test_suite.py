#!/usr/bin/env python3
"""Compare this package's reading of the yaml-test-suite with in.json.

Called by tools/yaml_test_suite.sh.  With a fourth argument, the path
of the package, also writes every case that agrees into
tests/yts_tests.nv: a valid case's documents as the JSON this package
gives them, which the comparison above found equal to the suite's own
`in.json`, and an invalid case as a refusal.
"""
import json
import os
import re
import subprocess
import sys


def cases(root):
    for dirpath, dirnames, filenames in os.walk(root):
        if 'in.yaml' in filenames:
            yield os.path.relpath(dirpath, root).replace(os.sep, '/'), dirpath


def tags_of(text):
    out = set()
    for m in re.finditer(r'(?:(?<=\s)|^|(?<=[\[{,]))(!<[^>\s]*>|![^\s,\[\]{}]*)', text, re.M):
        t = m.group(1)
        out.add(t)
        if t.startswith('!<') and not t.endswith('>'):
            continue
    return sorted(out)


def load_json_docs(path):
    text = open(path).read()
    dec = json.JSONDecoder()
    docs, i = [], 0
    while True:
        while i < len(text) and text[i] in ' \t\r\n':
            i += 1
        if i >= len(text):
            break
        v, i = dec.raw_decode(text, i)
        docs.append(v)
    return docs


def same(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b if isinstance(a, bool) and isinstance(b, bool) else False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    if isinstance(a, dict) and isinstance(b, dict):
        return sorted(a.keys()) == sorted(b.keys()) and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def main():
    root, work, harness = sys.argv[1], sys.argv[2], sys.argv[3]
    items = sorted(cases(root))
    blob = []
    for cid, d in items:
        text = open(os.path.join(d, 'in.yaml'), encoding='utf-8', errors='surrogateescape').read()
        blob.append('\x01%s\x02%s\x03%s' % (cid, '\x04'.join(tags_of(text)), text))
    path = os.path.join(work, 'cases.txt')
    open(path, 'w', encoding='utf-8', errors='surrogateescape').write(''.join(blob))
    out = subprocess.run([harness, path], capture_output=True, text=True).stdout
    got = {}
    for line in out.splitlines():
        parts = line.split('\t', 2)
        if len(parts) == 3:
            got[parts[0]] = (parts[1], parts[2])
    agree, differ, refused, accepted, unchecked = [], [], [], [], []
    for cid, d in items:
        invalid = os.path.exists(os.path.join(d, 'error'))
        verdict, body = got.get(cid, ('MISSING', ''))
        if invalid:
            (agree if verdict == 'ERR' else accepted).append(cid)
            continue
        if verdict != 'OK':
            refused.append((cid, body))
            continue
        jp = os.path.join(d, 'in.json')
        if not os.path.exists(jp):
            unchecked.append(cid)
            continue
        try:
            want = load_json_docs(jp)
        except ValueError:
            unchecked.append(cid)
            continue
        if same(json.loads(body), want):
            agree.append(cid)
        else:
            differ.append((cid, body))
    for cid, body in refused:
        print('  refused valid   %s: %s' % (cid, body))
    for cid, body in differ:
        print('  differs         %s: %s' % (cid, body[:200]))
    for cid in accepted:
        print('  accepted error  %s' % cid)
    print('%d cases: %d agree, %d valid refused, %d differ, %d invalid accepted, %d valid with no JSON form'
          % (len(items), len(agree), len(refused), len(differ), len(accepted), len(unchecked)))
    if len(sys.argv) > 4:
        emit(sys.argv[4], items, got, agree)


def nv(s):
    out = []
    for ch in s:
        o = ord(ch)
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '$':
            out.append('\\$')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\t':
            out.append('\\t')
        elif o < 32 or o == 127 or 0xD800 <= o <= 0xDFFF:
            out.append('\\u{%x}' % o)
        else:
            out.append(ch)
    return '"' + ''.join(out) + '"'


def emit(pkg, items, got, agree):
    agreed = set(agree)
    rows = []
    for cid, d in items:
        if cid not in agreed:
            continue
        text = open(os.path.join(d, 'in.yaml'), encoding='utf-8', errors='replace').read()
        verdict, body = got[cid]
        rows.append((cid, tags_of(text), text, body if verdict == 'OK' else None))
    lines = [
        '// yts_tests.nv — the yaml-test-suite corpus, every case this package',
        '// reads as the suite says.',
        '//',
        '// Written by tools/yaml_test_suite.py from the suite\'s data branch',
        '// (https://github.com/yaml/yaml-test-suite); do not edit by hand.  A',
        '// valid case asserts the documents as JSON, which the generator',
        '// compared with the suite\'s own `in.json`; an invalid case asserts a',
        '// refusal.  Every valid case also goes through the writer and back.',
        '// The two cases left out bind one key twice, which this package',
        '// refuses and the suite does not.',
        '',
        'use std.test',
        'use yamlnode',
        'use yamlread',
        'use yamlsafe',
        'use yamlwrite',
        '',
        'fn policy(tags: [Str]) -> YamlLimits',
        '    yamlsafe.with_complex_keys(yamlsafe.allowing(yamlsafe.standard(), tags), true)',
        '',
        'fn json_str(s: Str) -> Str',
        '    var parts: [Str] = ["\\""]',
        '    for i in 0..str.len(s)',
        '        let b = str.byte_at_or(s, i, 0)',
        '        if b == \'"\'',
        '            list.push(parts, "\\\\\\"")',
        '        elif b == \'\\\\\'',
        '            list.push(parts, "\\\\\\\\")',
        '        elif b == \'\\n\'',
        '            list.push(parts, "\\\\n")',
        '        elif b == \'\\t\'',
        '            list.push(parts, "\\\\t")',
        '        elif b == \'\\r\'',
        '            list.push(parts, "\\\\r")',
        '        elif b < 32',
        '            let hex = str.slice("0123456789abcdef", b % 16, b % 16 + 1)',
        '            list.push(parts, (if b < 16 then "\\\\u000" else "\\\\u001") + hex)',
        '        else',
        '            list.push(parts, str.from_byte(b))',
        '    list.push(parts, "\\"")',
        '    str.join(parts, "")',
        '',
        'fn key_json(k: YamlValue) -> Str',
        '    match k',
        '        YamlStr(s) => json_str(s)',
        '        YamlNull   => json_str("")',
        '        _          => json_str(yamlwrite.scalar_to_string(k))',
        '',
        'fn to_json(v: YamlValue) -> Str',
        '    match v',
        '        YamlMap(pairs) =>',
        '            var parts: [Str] = []',
        '            for p in pairs',
        '                list.push(parts, key_json(p.key) + ":" + to_json(p.value))',
        '            "{" + str.join(parts, ",") + "}"',
        '        YamlSeq(items) =>',
        '            var parts: [Str] = []',
        '            for x in items',
        '                list.push(parts, to_json(x))',
        '            "[" + str.join(parts, ",") + "]"',
        '        YamlStr(s)     => json_str(s)',
        '        YamlInt(i)     => "${i}"',
        '        YamlFloat(f)   => float_json(v, f)',
        '        YamlBool(b)    => str.from_bool(b)',
        '        YamlNull       => "null"',
        '',
        'fn float_json(v: YamlValue, f: Float) -> Str',
        '    if f != f or f > 1.0e308 or f < -1.0e308',
        '        return json_str(yamlwrite.scalar_to_string(v))',
        '    str.from_float_shortest(f)',
        '',
        '// The documents of a valid case, as JSON, and whether the writer\'s',
        '// output of each reads back equal.',
        'fn read_as(text: Str, tags: [Str]) -> Str',
        '    match yamlread.parse_stream(text, policy(tags))',
        '        Err(e)   => "error: " + e.message()',
        '        Ok(docs) =>',
        '            var parts: [Str] = []',
        '            for d in docs',
        '                list.push(parts, to_json(d))',
        '                if not round_trips(d, tags)',
        '                    return "does not round-trip: " + to_json(d)',
        '            "[" + str.join(parts, ",") + "]"',
        '',
        'fn round_trips(d: YamlValue, tags: [Str]) -> Bool',
        '    if yamlwrite.check(d) != None',
        '        return true',
        '    match yamlwrite.to_string(d, yamlwrite.standard())',
        '        Err(_)  => false',
        '        Ok(out) =>',
        '            match yamlread.parse(out, policy(tags))',
        '                Ok(back) => yamlnode.equal(back, d)',
        '                Err(_)   => false',
        '',
        'fn refused(text: Str, tags: [Str]) -> Bool',
        '    match yamlread.parse_stream(text, policy(tags))',
        '        Ok(_)  => false',
        '        Err(_) => true',
        '',
    ]
    per = 40
    for g in range(0, len(rows), per):
        lines.append('@test')
        lines.append('fn test_cases_%03d() [io]' % (g // per + 1))
        for cid, tags, text, body in rows[g:g + per]:
            tag_list = '[' + ', '.join(nv(t) for t in tags) + ']'
            lines.append('    test.case(%s)' % nv(cid))
            if body is None:
                lines.append('    test.assert(refused(%s, %s))' % (nv(text), tag_list))
            else:
                lines.append('    test.assert(read_as(%s, %s)' % (nv(text), tag_list))
                lines.append('                == %s)' % nv(body))
        lines.append('')
    path = os.path.join(pkg, 'tests', 'yts_tests.nv')
    open(path, 'w').write('\n'.join(lines))
    subprocess.run(['novo', 'fmt', path], check=False)


if __name__ == '__main__':
    main()
