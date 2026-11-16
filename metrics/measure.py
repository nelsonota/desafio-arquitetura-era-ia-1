import argparse
import ast
import csv
from pathlib import Path


def measure(root):
    paths = {'.'.join(p.relative_to(root).with_suffix('').parts): p for p in root.rglob('*.py') if p.name != '__init__.py'}
    deps, abstract = {}, {}
    for name, path in paths.items():
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        imports = set()
        aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for item in node.names:
                    aliases[item.asname or item.name.split('.')[0]] = item.name
                    if item.name.startswith('helpdesk.'):
                        imports.add(item.name.removeprefix('helpdesk.'))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                if node.level:
                    package = name.split('.')[:-1]
                    base = package[:len(package) - node.level + 1]
                    prefix = '.'.join(base + ([module] if module else []))
                elif module == 'helpdesk' or module.startswith('helpdesk.'):
                    prefix = module.removeprefix('helpdesk').lstrip('.')
                else:
                    prefix = None
                if prefix is not None:
                    imports.add(prefix)
                    imports.update('.'.join(filter(None, (prefix, item.name))) for item in node.names)
                for item in node.names:
                    aliases[item.asname or item.name] = f'{module}.{item.name}'
        deps[name] = (imports & paths.keys()) - {name}
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        def is_abstract(cls):
            for base in cls.bases:
                if isinstance(base, ast.Name) and aliases.get(base.id) in ('typing.Protocol', 'abc.ABC'):
                    return True
                if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) and f'{aliases.get(base.value.id, base.value.id)}.{base.attr}' in ('typing.Protocol', 'abc.ABC'):
                    return True
            return False
        abstract[name] = sum(is_abstract(c) for c in classes) / len(classes) if classes else 0
    rows = []
    for name in sorted(paths):
        ca = sum(name in targets for targets in deps.values())
        ce = len(deps[name])
        i = ce / (ca + ce) if ca + ce else 0
        a = abstract[name]
        rows.append((name, ca, ce, round(i, 2), round(a, 2), round(abs(a + i - 1), 2)))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=Path)
    parser.add_argument('name')
    args = parser.parse_args()
    rows = measure(args.path)
    out = Path(__file__).resolve().parent / 'results'
    out.mkdir(exist_ok=True)
    with (out / f'{args.name}.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(('component', 'ca', 'ce', 'i', 'a', 'd'))
        writer.writerows(rows)
    # SVG keeps the chart reproducible without external dependencies.
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="850" height="600" viewBox="0 0 850 600">', '<rect width="100%" height="100%" fill="white"/>', '<g font-family="sans-serif" font-size="13">', '<text x="70" y="25" font-size="18">Acoplamento: abstração × instabilidade</text>', '<path d="M70 40V540H570 M70 40L570 540" stroke="#555" fill="none"/>', '<text x="300" y="585">Instabilidade (I)</text><text x="10" y="35">A</text>', '<text x="60" y="558">0</text><text x="565" y="558">1</text><text x="48" y="45">1</text>', '<text x="170" y="250" fill="#555">Main Sequence</text>']
    for index, (name, ca, ce, i, a, d) in enumerate(rows):
        x, y = 70 + 500 * i, 540 - 500 * a
        svg.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#1769aa"><title>{name}: I={i}, A={a}</title></circle>')
        svg.append(f'<text x="590" y="{55 + index * 22}" fill="#1769aa">{index+1}. {name}: ({i}, {a})</text>')
        svg.append(f'<text x="{x+6}" y="{y-6}" font-size="10">{index+1}</text>')
    svg.append('</g></svg>')
    (out / f'{args.name}.svg').write_text('\n'.join(svg), encoding='utf-8')


if __name__ == '__main__':
    main()
