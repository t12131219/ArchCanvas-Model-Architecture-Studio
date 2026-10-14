#!/usr/bin/env python3
"""Index frozen README resources and notebook paths without executing upstream code."""
from __future__ import annotations
import csv
import hashlib
import json
import re
from collections import Counter
from html import escape
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
OUT = HERE / 'catalog'
SELECTED = {
    'pytorch_ipynb/cnn/cnn-lenet5-mnist.ipynb': 'lenet',
    'pytorch_ipynb/cnn/cnn-resnet18-mnist.ipynb': 'resnet',
    'pytorch_ipynb/autoencoder/ae-var.ipynb': 'vae',
    'pytorch_ipynb/rnn/rnn_lstm_packed_imdb.ipynb': 'lstm',
    'https://github.com/bamos/densenet.pytorch': 'densenet',
    'https://github.com/mateuszbuda/brain-segmentation-pytorch': 'unet',
    'pytorch_ipynb/cnn/cnn-alexnet-cifar10-grouped.ipynb': 'alexnet',
    'pytorch_ipynb/cnn/cnn-mobilenet-v2-cifar10.ipynb': 'mobilenetv2',
    'pytorch_ipynb/cnn/nin-cifar10.ipynb': 'nin',
    'pytorch_ipynb/cnn-nlp/cnn_imdb.ipynb': 'textcnn',
    'pytorch_ipynb/autoencoder/ae-conv-nneighbor.ipynb': 'convae',
    'pytorch_ipynb/gan/dcgan-celeba.ipynb': 'dcgan',
    'pytorch_ipynb/cnn/cnn-vgg16.ipynb': 'vgg16',
    'pytorch_ipynb/cnn/cnn-resnet50-mnist.ipynb': 'resnet50',
    'pytorch_ipynb/autoencoder/ae-conv-var.ipynb': 'convvae',
    'pytorch_ipynb/autoencoder/ae-cnn-cvae.ipynb': 'ccvae',
    'pytorch_ipynb/rnn/rnn_gru_packed_imdb.ipynb': 'gru',
    'pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.ipynb': 'bilstm',
    'pytorch_ipynb/cnn/cnn-mobilenet-v3-large-cifar10.ipynb': 'mobilenetv3',
    'pytorch_ipynb/cnn/cnn-resnet101-cifar10.ipynb': 'resnet101',
    'pytorch_ipynb/cnn/cnn-vgg19.ipynb': 'vgg19',
    'pytorch_ipynb/gan/gan-conv.ipynb': 'convgan',
    'pytorch_ipynb/gan/dc-wgan-1.ipynb': 'dcwgan',
    'pytorch_ipynb/gnn/gnn-basic-1.ipynb': 'graphnet',
}
# This one link was reviewed against the actual grouped-convolution source.
# Preserve the upstream missing path in paths/path_checks; bind the drawing separately.
REVIEWED_PATH_CORRECTIONS={
    'pytorch_ipynb/cnn/cnn-alexnet-grouped-cifar10.ipynb':
        'pytorch_ipynb/cnn/cnn-alexnet-cifar10-grouped.ipynb',
}
SUPPLEMENTARY = [
    dict(key='lstmcell', model='lstmcell', title='标准 LSTM Cell（显式四门与时间展开）',
         source_project='pytorch-lstmcell-v2.5.1', repository='pytorch/pytorch',
         commit='a8d6afb511a69687bbb2b7e88a3cf67917e1697e', release_tag='v2.5.1',
         path='benchmarks/fastrnns/custom_lstms.py', diagram='lstmcell',
         reason='用户指定的标准 LSTM 内部门结构参考；补充采用 PyTorch 官方仓库的显式 LSTM 实现，来源不属于原先两个仓库的固定 README 或 Notebook 清单。'),
]
SCOPE = (
    'All numbered linked resources in the frozen Awesome README; all notebook-linked '
    'table rows in the frozen rasbt README; every .ipynb blob path in the frozen Git '
    'trees. Entries include libraries, tutorials, methods, datasets and model variants, '
    'not only distinct model architectures. Existing notebook paths are indexed '
    'separately from README references, including missing upstream links. Python '
    'helper/model source files are not separately enumerated. External repositories '
    'are not recursively inventoried. Tree existence is not proof of download or '
    'semantic review; only adapted entries have reviewed drawing adapters. '
    'User-requested source examples outside these two frozen repositories are '
    'recorded separately in supplementary_examples, without changing README '
    'entry or notebook counts.'
)
STYLE = '''<style>
body{font-family:DejaVu Sans,Arial,sans-serif;color:#172336;background:#edf0f5;margin:24px}
main{max-width:1680px;margin:auto}input,select{font:inherit;padding:10px;border:1px solid #718299;border-radius:8px;margin:4px}
input{min-width:260px}table{border-collapse:collapse;background:white;width:100%;margin-top:20px}
th,td{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #dbe3ec;overflow-wrap:anywhere}
a{color:#315479}small{display:block;color:#526170;white-space:pre-line;margin-top:5px}
header{position:sticky;top:0;background:#edf0f5;padding:10px 0;z-index:1}
.bad{color:#a12d37;font-weight:700}.ok{color:#216647}.badge{font-size:12px;border-radius:5px;padding:2px 5px;background:#d9e8f3;display:inline-block}
details{margin-top:7px}summary{cursor:pointer}li{margin:6px 0}code{font-size:12px}nav{margin:12px 0}h1{margin:8px 0}
</style>'''


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def blob_url(revision, path):
    return ('https://github.com/' + revision['repository'] + '/blob/' +
            revision['commit'] + '/' + quote(path, safe='/'))


def framework(path):
    if path.startswith(('pytorch-lightning', 'templates/pytorch_lightning')):
        return 'PyTorch Lightning'
    if path.startswith('pytorch'):
        return 'PyTorch'
    if path.startswith('tensorflow'):
        return 'TensorFlow'
    return 'Other'


def readme_url(revision, start, end):
    return blob_url(revision, 'README.md') + '#L' + str(start) + ('-L' + str(end) if end > start else '')


def path_check(path, blobs, revision):
    blob = blobs.get(path)
    return dict(path=path, status='present_in_frozen_tree' if blob else 'missing_from_frozen_tree',
                exists_in_frozen_tree=bool(blob), git_blob_sha=blob['sha'] if blob else None,
                bytes=blob.get('size') if blob else None, url=blob_url(revision, path))


def path_status(checks):
    present = sum(c['exists_in_frozen_tree'] for c in checks)
    return 'all_present' if present == len(checks) else 'all_missing' if not present else 'some_missing'


def csv_cell(value):
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False, sort_keys=True) if any(isinstance(v, dict) for v in value) else '; '.join(value)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return value


def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_cell(row.get(key)) for key in fields})


def md_cell(value):
    return str(value).replace('|', ' / ').replace('\n', '<br>')


def payload(data):
    # The JSON remains data; escaped closing tags cannot end the script element.
    return json.dumps(data, ensure_ascii=False).replace('</', '<\\/')


def supplementary_examples():
    """Supplementary sources are explicit additions, never fabricated catalog rows."""
    manifest = json.loads((HERE / 'source_manifest.json').read_text())
    result = []
    for example in SUPPLEMENTARY:
        project = manifest[example['source_project']]
        if project['commit'] != example['commit'] or project['repository'].rstrip('/') != 'https://github.com/' + example['repository']:
            raise ValueError('Supplementary source provenance differs: ' + example['key'])
        source = project['files'][example['path']]
        downloaded = (HERE / 'sources' / example['source_project'] / example['path']).read_bytes()
        if hashlib.sha256(downloaded).hexdigest() != source['sha256'] or len(downloaded) != source['bytes']:
            raise ValueError('Supplementary source bytes differ: ' + example['key'])
        result.append({**example, 'status': 'adapted', 'frameworks': ['PyTorch'],
                       'source_url': blob_url(example, example['path']),
                       'diagram_url': '../generated/' + example['diagram'] + '/index.html',
                       'sha256': source['sha256'], 'bytes': len(downloaded),
                       'git_blob_sha': hashlib.sha1(b'blob ' + str(len(downloaded)).encode() + b'\0' + downloaded).hexdigest(),
                       'license_files': project.get('license_files', [])})
    return result


def write_markdown(result):
    entries, notebooks = result['entries'], result['notebooks']
    counts = result['counts']
    lines = ['# 两个仓库的模型与资源清单', '',
             '本清单保留固定提交的 Awesome README 全部编号链接资源、rasbt README 全部 Notebook 链接表行，以及两个固定 Git 树中的全部 Notebook 路径。库、教程、工具、方法和同模型变体分别保留，不能把目录条目数当作独立模型数。', '',
             'Python helper / 模型脚本未另建条目；外部项目的内部模型库不递归枚举。路径核对只证明该文件在固定 Git 树中存在，不代表已下载或已审阅模型语义；只有“已绘图”条目具有本批源码适配器。', '',
             f'目录条目 {counts["entries"]}；实际 Notebook 路径 {counts["notebook_files"]}；其中 README 未列出 {counts["readme_unlisted_notebooks"]} 个；已适配模型合计 {counts["adapted_models"]} 个（原目录 {counts["indexed_adapted_models"]} 个 + 独立补充源码示例 {counts["supplementary_models"]} 个）。', '',
             '| 来源 | 固定提交 | README 条目数 |', '|---|---|---|']
    for slug, provenance in result['provenance'].items():
        lines.append(f'| {slug} | `{provenance["commit"]}` | {counts["by_origin"][slug]} |')
    lines += ['',
              '完整 JSON 保留原始文本、README 起止行、所有 Notebook 引用、路径核对、适配路径及 Git blob SHA。', '',
              '[可搜索资源目录](index.html) · [资源 CSV](models.csv) · [完整 JSON](models.json) · [全部 Notebook 路径](notebooks.html) · [Notebook CSV](notebooks.csv)', '',
              f'**上游错链**：固定 README 引用了 {counts["missing_notebook_references"]} 个未出现在固定 Git 树中的 Notebook 路径。原始条目及链接保留，下面明确标注，不凭名称自动替换文件；分组 AlexNet 经源码审阅后另记真实绘图路径，原始错链仍保留。', '',
              '| 来源分类 | 名称 | 类型 | Notebook 路径核对 | 本批图 |', '|---|---|---|---|---|']
    for entry in entries:
        category = md_cell(entry['origin'] + ' / ' + entry['category'])
        label = md_cell(entry['title'])
        diagram = f'[{entry["diagram"]}](../generated/{entry["diagram"]}/index.html)' if entry['diagram'] else '仅收录'
        missing = [check for check in entry['path_checks'] if not check['exists_in_frozen_tree']]
        if missing:
            status = '**上游错链**：' + '<br>'.join(f'[{check["path"]}]({check["url"]})' for check in missing)
        elif entry['paths']:
            status = '全部引用存在于固定树'
        else:
            status = '外部资源；不递归核对'
        if entry['adapted_paths']:
            status += '<br>绘图来源：' + ', '.join(f'`{path}`' for path in entry['adapted_paths'])
        lines.append(f'| {category} | [{label}]({entry["url"]}) | {entry["resource_type"]} | {status} | {diagram} |')
    lines += ['', '## 用户指定的补充源码示例', '',
              f'以下来源独立于前述两个固定仓库清单；不计入 {counts["entries"]} 条原始资源或 {counts["notebook_files"]} 个 Notebook，不声称在原 README 中列出。其源码、固定提交与绘图适配另行审阅。', '',
              '| 模型 | 官方源码 / 固定提交 | 本批图 | 补充原因 |', '|---|---|---|---|']
    for example in result['supplementary_examples']:
        lines.append(f'| {md_cell(example["title"])} | [{example["repository"]} / {example["path"]}]({example["source_url"]})<br>`{example["commit"]}` | [{example["diagram"]}]({example["diagram_url"]}) | {md_cell(example["reason"])} |')
    lines += ['', '## 附录：固定 Git 树的全部 Notebook 路径', '',
              f'共 {len(notebooks)} 个实际文件，包括 {counts["readme_unlisted_notebooks"]} 个 README 未列出的文件；它们独立于上方 README 条目计数。此表不包含上游错链对应的不存在文件。', '',
              '| 来源 / 框架 | Notebook 路径 | README 收录 | Git blob SHA | 本批图 |', '|---|---|---|---|---|']
    for notebook in notebooks:
        listed = ', '.join(notebook['readme_entries']) if notebook['readme_listed'] else '**README 未列出**'
        diagram = f'[{notebook["diagram"]}](../generated/{notebook["diagram"]}/index.html)' if notebook['diagram'] else '仅收录'
        lines.append(f'| {notebook["origin"]} / {notebook["framework"]} | [{notebook["path"]}]({notebook["url"]}) | {listed} | `{notebook["git_blob_sha"]}` | {diagram} |')
    (OUT / '模型与资源清单.md').write_text('\n'.join(lines) + '\n')


def write_html(entries, notebooks, supplementary):
    doc = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>模型与资源目录</title>
STYLE
<main><header><h1>模型与资源清单</h1><p>固定 README 的编号资源和 Notebook 表行；资源、教程、方法及同模型变体分别保留，条目数不是独立模型数。只有“已绘图”条目完成源码适配。</p><p>Notebook 路径与固定 Git 树核对；红色“上游错链”表示 README 引用的文件未出现在该树中，原始链接仍保留。外部资源不递归核对。</p><nav><a href="../generated/index.html">模型绘图预览</a> · <a href="models.csv">资源 CSV</a> · <a href="models.json">完整 JSON</a> · <a href="notebooks.html">全部 Notebook（含 README 未列出）</a> · <a href="notebooks.csv">Notebook CSV</a></nav><input id="search" placeholder="搜索名称 / 描述 / 分类 / 路径" aria-label="搜索"><select id="origin" aria-label="来源"><option value="">全部来源</option><option>Awesome-pytorch-list</option><option>deeplearning-models</option></select><select id="status" aria-label="绘图状态"><option value="">全部条目</option><option value="adapted">已绘图</option><option value="index_only">仅收录</option></select><select id="path-check" aria-label="路径核对"><option value="">全部路径状态</option><option value="missing">含上游错链</option><option value="all_present">Notebook 引用全部存在</option><option value="not_applicable">外部资源</option></select><p id="count"></p></header><table><thead><tr><th>名称与出处</th><th>来源 / 分类</th><th>条目类型</th><th>路径核对</th><th>图像</th></tr></thead><tbody></tbody></table></main><script>
const entries=PAYLOAD;const body=document.querySelector('tbody');
function link(text,url){const a=document.createElement('a');a.textContent=text;a.href=url;a.target='_blank';a.rel='noopener';return a}
function missing(e){return e.path_checks.some(c=>!c.exists_in_frozen_tree)}
function update(){const q=document.querySelector('#search').value.toLowerCase(),o=document.querySelector('#origin').value,s=document.querySelector('#status').value,p=document.querySelector('#path-check').value;const rows=entries.filter(e=>(!o||e.origin===o)&&(!s||e.status===s)&&(!p||(p==='missing'?missing(e):e.path_status===p))&&[e.title,e.description,e.category,...e.paths].join(' ').toLowerCase().includes(q));body.replaceChildren();document.querySelector('#count').textContent=rows.length+' / '+entries.length+' 目录条目';for(const e of rows){const tr=document.createElement('tr');for(let i=0;i<5;i++)tr.append(document.createElement('td'));tr.children[0].append(link(e.title,e.url));const desc=document.createElement('small');desc.textContent=e.description;tr.children[0].append(desc);tr.children[0].append(link('README L'+e.readme_line+(e.readme_line_end>e.readme_line?'–'+e.readme_line_end:''),e.readme_url));tr.children[1].textContent=e.origin+' / '+e.category;tr.children[2].textContent=e.resource_type;const check=tr.children[3];if(e.paths.length){const label=document.createElement('span');label.textContent=missing(e)?'上游错链：固定树未包含部分引用':'全部 Notebook 引用存在于固定树';label.className=missing(e)?'bad':'ok';check.append(label);const d=document.createElement('details'),summary=document.createElement('summary');summary.textContent='全部 '+e.paths.length+' 个引用及绘图来源';d.append(summary);const ul=document.createElement('ul');for(const c of e.path_checks){const li=document.createElement('li');li.append(link(c.path,c.url));const state=document.createElement('small');state.textContent=c.exists_in_frozen_tree?'固定树中存在':'上游错链：固定树中不存在';state.className=c.exists_in_frozen_tree?'ok':'bad';li.append(state);if(e.adapted_paths.includes(c.path)){const badge=document.createElement('span');badge.className='badge';badge.textContent='本批实际适配路径';li.append(badge)}ul.append(li)}for(const c of e.reviewed_path_corrections||[]){const li=document.createElement('li');li.append(link('审阅后的实际绘图来源：'+c.actual,e.url));const note=document.createElement('small');note.textContent='原始错链保留在上方；对应关系经源码审阅。';li.append(note);ul.append(li)}d.append(ul);check.append(d)}else check.textContent='外部资源；不递归核对';if(e.diagram){const a=link('三种粒度','../generated/'+e.diagram+'/index.html');a.removeAttribute('target');tr.children[4].append(a)}else tr.children[4].textContent='仅收录';body.append(tr)}}document.querySelectorAll('input,select').forEach(e=>e.addEventListener('input',update));update();
</script></html>'''.replace('STYLE', STYLE).replace('PAYLOAD', payload(entries))
    supplement_rows = []
    for example in supplementary:
        supplement_rows.append('<tr><td>' + escape(example['title']) + '</td><td><a href="' + escape(example['source_url'], quote=True) + '">' + escape(example['repository'] + ' / ' + example['path']) + '</a><small>固定提交 <code>' + escape(example['commit']) + '</code></small></td><td>' + escape(example['reason']) + '</td><td><a href="' + escape(example['diagram_url'], quote=True) + '">三种粒度</a></td></tr>')
    indexed_count = len({entry['diagram'] for entry in entries if entry['diagram']})
    supplemental_count = len({example['diagram'] for example in supplementary})
    supplement_html = f'<section><h2>用户指定的补充源码示例</h2><p>独立来源；不计入上方 {len(entries)} 条原始资源或 {len(notebooks)} 个 Notebook，不声称在原 README 中列出。原目录已适配 {indexed_count} 个模型，加以下补充 {supplemental_count} 个，合计 {indexed_count + supplemental_count} 个。</p><table><thead><tr><th>模型</th><th>源码与固定提交</th><th>补充原因</th><th>图像</th></tr></thead><tbody>' + ''.join(supplement_rows) + '</tbody></table></section>'
    doc = doc.replace('</table></main>', '</table>' + supplement_html + '</main>')
    (OUT / 'index.html').write_text(doc)
    notebook_doc = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>全部 Notebook 路径</title>
STYLE
<main><header><h1>固定 Git 树的全部 Notebook 路径</h1><p>实际存在于固定 Git 树的 .ipynb 文件，包括 README 未列出的文件。路径存在不代表已下载或经过语义审阅；“已绘图”仅标记本批适配来源。README 错链在资源目录标注，不增加不存在文件到本表。</p><nav><a href="index.html">README 资源目录</a> · <a href="notebooks.csv">Notebook CSV</a> · <a href="models.json">完整 JSON</a> · <a href="../generated/index.html">模型绘图预览</a></nav><input id="search" placeholder="搜索 Notebook 路径 / 框架" aria-label="搜索"><select id="listed" aria-label="README 收录"><option value="">全部 Notebook</option><option value="unlisted">README 未列出</option><option value="listed">README 已列出</option></select><select id="framework" aria-label="框架"><option value="">全部框架</option><option>PyTorch</option><option>PyTorch Lightning</option><option>TensorFlow</option></select><select id="status" aria-label="绘图状态"><option value="">全部绘图状态</option><option value="adapted">已绘图</option><option value="index_only">仅收录</option></select><p id="count"></p></header><table><thead><tr><th>Notebook 路径与出处</th><th>框架</th><th>README 收录</th><th>固定树证据</th><th>图像</th></tr></thead><tbody></tbody></table></main><script>
const notebooks=PAYLOAD;const body=document.querySelector('tbody');
function link(text,url){const a=document.createElement('a');a.textContent=text;a.href=url;a.target='_blank';a.rel='noopener';return a}
function update(){const q=document.querySelector('#search').value.toLowerCase(),l=document.querySelector('#listed').value,f=document.querySelector('#framework').value,s=document.querySelector('#status').value;const rows=notebooks.filter(n=>(!l||(l==='listed'?n.readme_listed:!n.readme_listed))&&(!f||n.framework===f)&&(!s||n.status===s)&&[n.path,n.framework,n.origin].join(' ').toLowerCase().includes(q));body.replaceChildren();document.querySelector('#count').textContent=rows.length+' / '+notebooks.length+' Notebook 文件；全部文件中 '+notebooks.filter(n=>!n.readme_listed).length+' 个未被 README 列出';for(const n of rows){const tr=document.createElement('tr');for(let i=0;i<5;i++)tr.append(document.createElement('td'));tr.children[0].append(link(n.path,n.url));const origin=document.createElement('small');origin.textContent=n.origin;tr.children[0].append(origin);tr.children[1].textContent=n.framework;tr.children[2].textContent=n.readme_listed?n.readme_entries.join(', '):'README 未列出';const sha=document.createElement('code');sha.textContent=n.git_blob_sha;tr.children[3].append(sha);const bytes=document.createElement('small');bytes.textContent='固定树中存在 · '+n.bytes+' bytes';tr.children[3].append(bytes);if(n.diagram){const d=link('本批实际适配：'+n.diagram,'../generated/'+n.diagram+'/index.html');d.removeAttribute('target');tr.children[4].append(d)}else tr.children[4].textContent='仅收录';body.append(tr)}}document.querySelectorAll('input,select').forEach(e=>e.addEventListener('input',update));update();
</script></html>'''.replace('STYLE', STYLE).replace('PAYLOAD', payload(notebooks))
    (OUT / 'notebooks.html').write_text(notebook_doc)


def inventory():
    entries, notebooks, provenance = [], [], {}
    for slug in ('Awesome-pytorch-list', 'deeplearning-models'):
        folder = OUT / 'upstream' / slug
        revision = json.loads((folder / 'revision.json').read_text())
        content = (folder / 'README.md').read_text()
        tree = json.loads((folder / 'tree.json').read_text())
        if tree.get('truncated'):
            raise ValueError('Incomplete Git tree: ' + slug)
        blobs = {item['path']: item for item in tree['tree'] if item['type'] == 'blob'}
        provenance[slug] = {**revision, 'readme_sha256': hashlib.sha256(content.encode()).hexdigest(),
                            'tree_sha256': hashlib.sha256((folder / 'tree.json').read_bytes()).hexdigest(),
                            'git_tree_entries': len(tree['tree']), 'retrieved_date': '2026-10-11'}
        sections = {}
        readme_lines = content.splitlines()
        for number, line in enumerate(readme_lines, 1):
            heading = re.match(r'^(#{2,6})\s+(.+?)\s*$', line)
            if heading:
                level = len(heading[1])
                sections = {key: value for key, value in sections.items() if key < level}
                sections[level] = heading[2]
            category = ' / '.join(sections.values())
            if slug == 'Awesome-pytorch-list':
                item = re.match(r'^\s*\d+\.\s+(.*)', line)
                if not item:
                    continue
                match = re.search(r'\[([^\]]+)\]\((https?://[^)]+)\)', item[1])
                if not match:
                    continue
                title, url = match.groups()
                tail = re.sub(r'^\*?\*?:?\s*', '', item[1][match.end():]).strip()
                # Preserve continuation prose and links until the next item/heading.
                end = number
                for following in readme_lines[number:]:
                    if re.match(r'^\s*\d+\.\s+', following) or re.match(r'^#{1,6}\s+', following):
                        break
                    end += 1
                while end > number and not readme_lines[end - 1].strip():
                    end -= 1
                continuation = readme_lines[number:end]
                description = '\n'.join([part for part in [tail, *continuation] if part.strip()]).strip()
                kind = 'paper_implementation_reference' if category.startswith('Paper implementations') else 'resource_reference'
                diagram = SELECTED.get(url.rstrip('/'))
                entries.append(dict(id=f'awesome-L{number}', origin=slug, title=title, category=category,
                                    resource_type=kind, description=description, url=url,
                                    readme_line=number, readme_line_end=end,
                                    readme_url=readme_url(revision, number, end),
                                    diagram=diagram, status='adapted' if diagram else 'index_only',
                                    frameworks=['PyTorch'], paths=[], adapted_paths=[], primary_path=None,
                                    path_status='not_applicable', path_checks=[],
                                    raw='\n'.join(readme_lines[number - 1:end])))
            else:
                if not line.startswith('|'):
                    continue
                cells = line.strip().strip('|').split('|')
                title = cells[0].strip()
                if not title or title in ('Title', '---') or re.fullmatch(r'[\s:-]+', title):
                    continue
                paths = re.findall(r'\]\(([^)]+\.ipynb)\)', line)
                if not paths:
                    continue
                adapted_paths = [REVIEWED_PATH_CORRECTIONS.get(path,path) for path in paths
                                 if REVIEWED_PATH_CORRECTIONS.get(path,path) in SELECTED]
                diagrams = sorted({SELECTED[path] for path in adapted_paths})
                primary_path = adapted_paths[0] if adapted_paths else paths[0]
                checks = [path_check(path, blobs, revision) for path in paths]
                entries.append(dict(id=f'rasbt-L{number}', origin=slug, title=title, category=category,
                                    resource_type='model_or_method_example',
                                    description=' | '.join(cell.strip() for cell in cells[1:-1]),
                                    url=blob_url(revision, primary_path), primary_path=primary_path,
                                    readme_line=number, readme_line_end=number,
                                    readme_url=readme_url(revision, number, number),
                                    diagram=diagrams[0] if diagrams else None,
                                    status='adapted' if diagrams else 'index_only',
                                    frameworks=sorted({framework(path) for path in paths}),
                                    paths=paths, adapted_paths=adapted_paths,
                                    reviewed_path_corrections=[dict(original=path,actual=REVIEWED_PATH_CORRECTIONS[path],reason='Reviewed grouped AlexNet source; upstream path order differs') for path in paths if path in REVIEWED_PATH_CORRECTIONS],
                                    path_status=path_status(checks), path_checks=checks, raw=line))
        for path, item in sorted(blobs.items()):
            if not path.endswith('.ipynb'):
                continue
            referenced = [entry['id'] for entry in entries if entry['origin'] == slug and path in entry['paths']]
            notebooks.append(dict(origin=slug, path=path, framework=framework(path),
                                  path_status='present_in_frozen_tree', git_blob_sha=item['sha'], bytes=item.get('size'),
                                  readme_entries=referenced, readme_listed=bool(referenced),
                                  url=blob_url(revision, path), diagram=SELECTED.get(path),
                                  status='adapted' if path in SELECTED else 'index_only'))
    missing = {check['path'] for entry in entries for check in entry['path_checks'] if not check['exists_in_frozen_tree']}
    adapted_models = {entry['diagram'] for entry in entries if entry['diagram']}
    supplementary = supplementary_examples()
    supplemental_models = {example['diagram'] for example in supplementary}
    if adapted_models & supplemental_models:
        raise ValueError('Supplementary examples must not duplicate indexed models')
    result = dict(schema='model-resource-catalog/1', provenance=provenance, entries=entries, notebooks=notebooks,
                  supplementary_examples=supplementary,
                  counts=dict(entries=len(entries), by_origin=dict(Counter(entry['origin'] for entry in entries)),
                              by_resource_type=dict(Counter(entry['resource_type'] for entry in entries)),
                              notebook_files=len(notebooks), readme_unlisted_notebooks=sum(not notebook['readme_listed'] for notebook in notebooks),
                              adapted_models=len(adapted_models | supplemental_models), indexed_adapted_models=len(adapted_models),
                              supplementary_models=len(supplemental_models), missing_notebook_references=len(missing),
                              readme_entries_with_missing_paths=sum(entry['path_status'] in ('some_missing', 'all_missing') for entry in entries)),
                  scope=SCOPE)
    save(OUT / 'models.json', result)
    write_csv(OUT / 'models.csv', entries,
              ['id', 'origin', 'category', 'resource_type', 'title', 'description', 'frameworks', 'status', 'diagram',
               'url', 'readme_line', 'readme_line_end', 'readme_url', 'paths', 'adapted_paths', 'primary_path',
               'path_status', 'path_checks', 'raw'])
    write_csv(OUT / 'notebooks.csv', notebooks,
              ['origin', 'path', 'framework', 'path_status', 'git_blob_sha', 'bytes', 'readme_listed',
               'readme_entries', 'status', 'diagram', 'url'])
    write_markdown(result)
    write_html(entries, notebooks, supplementary)
    print(json.dumps(result['counts'], ensure_ascii=False))
    return result


if __name__ == '__main__':
    inventory()
