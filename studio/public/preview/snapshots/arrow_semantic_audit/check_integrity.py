#!/usr/bin/env python3
"""Read-only cross audit of preserved source bytes, SVG scope and local links.

Default: inspect and print a compact result; write no output. --write-report
refreshes integrity_checks.json/.md and shared_before_after.json only. Never imports
upstream models, executes notebooks, renders diagrams, or changes baselines.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
TOPICS=('model_zoo_programmatic_guide','module_programmatic_guide',
        'timeseries_programmatic_guide','transformer_programmatic_guide')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


class HTMLLinks(HTMLParser):
    def __init__(self):
        super().__init__();self.targets=[]
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if value and (key in ('href','src') or key=='data' and tag=='object'):
                self.targets.append(value)


def file_links(path):
    text=path.read_text(encoding='utf-8',errors='replace')
    if path.suffix=='.html':
        parser=HTMLLinks();parser.feed(text);return parser.targets
    text=re.sub(r'```[^\n]*\n.*?```','',text,flags=re.S)
    text=re.sub(r'`[^`\n]*`','',text)
    pattern=r'!?(?<!\\)\[[^\]\n]*(?<!\\)\]\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+[^)]*)?\)'
    targets=[a or b for a,b in re.findall(pattern,text)]
    pattern=r'^\s*(?<!\\)\[[^\]]+(?<!\\)\]:\s*(?:<([^>]+)>|([^\s]+))'
    return targets+[a or b for a,b in re.findall(pattern,text,flags=re.M)]


def check_links(root,audit_documents=False):
    documents=[];references=[]
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.suffix not in ('.md','.html'):continue
        relative=path.relative_to(root);parts=relative.parts
        if audit_documents:
            if parts[0]!='arrow_semantic_audit' or 'before' in parts:continue
        elif parts[0] in ('arrow_semantic_audit','pytorch_transformer_original'):continue
        if any(p in parts for p in ('snapshots','sources','upstream')):continue
        documents.append(str(relative))
        for value in file_links(path):
            value=html.unescape(value.strip())
            if not value or value.startswith('#'):continue
            if re.match(r'^(?:https?|mailto|data|javascript|app|codex|plugin|tel):',value):continue
            if any(token in value for token in ('${','{{','}}')):continue
            target=re.sub(r':\d+(?:-\d+)?$','',unquote(urlsplit(value).path))
            if not target:continue
            resolved=Path(target) if Path(target).is_absolute() else path.parent/target
            references.append(dict(document=str(relative),target=value,
                                   resolved=str(resolved.resolve()),exists=resolved.exists()))
    broken=[row for row in references if not row['exists']]
    return dict(documents=len(documents),local_references=len(references),
                broken_count=len(broken),broken=broken,scanned_documents=documents,
                passed=not broken,
                method='HTMLParser attrs + Markdown destinations excluding fenced/inline code and escaped brackets; file/directory existence only',
                excluded='before backup; historical snapshots; upstream/source README text; remote URL availability, fragment anchors and runtime dynamic JS targets not checked')


def artifact_receipts(root):
    rows=[];reports=[]
    for relative in ('modules/after_endpoint_audit.json','modelzoo/full_actual_svg_audit.json'):
        record=json.loads((root/'arrow_semantic_audit'/relative).read_text())
        reports.append(dict(report=relative,views=len(record['views']),passed=record.get('passed') is True))
        for view in record['views']:
            metadata=view['artifacts'];parts=Path(metadata['SVG']).parts
            topic=next(topic for topic in TOPICS[:2] if topic in parts)
            # Absolute and repo-relative saved receipts both map to the selected
            # prototype root; --root does not inspect a different original tree.
            svg=root/Path(*parts[parts.index(topic):])
            paths={'SVG':svg,'IR':svg.parent/'semantic_ir.json',
                   'layout':svg.parent/f'layout_{view["view"]}.json'}
            for kind,path in paths.items():
                current=sha(path);expected=metadata[kind+'_sha256']
                rows.append(dict(report=relative,view=view['view'],example=view['module'],
                                 kind=kind,path=str(path.relative_to(root)),
                                 receipt_sha256=expected,current_sha256=current,
                                 passed=current==expected))
    return dict(passed=all(r['passed'] for r in rows+reports),views_checked=sum(r['views'] for r in reports),
                hashes_checked=len(rows),reports=reports,rows=rows,
                method='saved per-view actual SVG / semantic_ir.json / layout_{view}.json SHA-256 compared with current bytes')


def actual_svg_inventory(root,inventory):
    expected={TOPICS[0]:(75,1446),TOPICS[1]:(228,2407),TOPICS[2]:(12,608),
              'transformer_current':(3,147),'transformer_compact':(3,147),
              'mini_annotations':(2,6)}
    grouped=defaultdict(lambda:dict(svg=0,paths=0));records=[]
    for relative in sorted(sum((inventory[key] for key in ('main_views','active_compact','active_mini')),[])):
        parts=Path(relative).parts
        if relative in inventory['active_mini']:group='mini_annotations'
        elif relative in inventory['active_compact']:group='transformer_compact'
        elif parts[0]==TOPICS[3]:group='transformer_current'
        else:group=parts[0]
        document=ET.parse(root/relative).getroot();ids=[];anonymous=[];metadata=Counter()
        def walk(element,in_defs=False):
            tag=element.tag.rsplit('}',1)[-1];in_defs=in_defs or tag=='defs'
            if not in_defs and tag=='path':
                identity=element.get('data-route-id')
                if identity:
                    ids.append(identity)
                    if element.get('data-endpoint-binding'):metadata['endpoint_binding']+=1
                    elif element.get('data-semantic-trace'):metadata['semantic_trace']+=1
                    elif element.get('data-semantic-edges'):metadata['semantic_edges']+=1
                    elif element.get('data-role') and element.get('data-src') and element.get('data-dst'):metadata['typed_annotation']+=1
                    else:metadata['no_explicit_binding']+=1
                elif element.get('fill')=='none':anonymous.append(element.get('d'))
            for child in element:walk(child,in_defs)
        walk(document)
        duplicates=[identity for identity,n in Counter(ids).items() if n>1]
        grouped[group]['svg']+=1;grouped[group]['paths']+=len(ids)
        records.append(dict(svg=relative,sha256=sha(root/relative),group=group,
                            route_ids=len(ids),duplicate_ids=duplicates,
                            anonymous_drawn_paths=anonymous,binding_metadata=dict(metadata),
                            passed=not(duplicates or anonymous or metadata['no_explicit_binding'])))
    group_checks=[]
    for group,(svg,paths) in expected.items():
        actual=grouped[group]
        group_checks.append(dict(group=group,expected_svg=svg,expected_paths=paths,
                                 actual_svg=actual['svg'],actual_paths=actual['paths'],
                                 passed=actual==dict(svg=svg,paths=paths)))
    return dict(passed=all(r['passed'] for r in records+group_checks),
                active_svg=sum(v['svg'] for v in grouped.values()),
                actual_data_route_id_paths=sum(v['paths'] for v in grouped.values()),
                method='actual XML path data-route-id outside defs; duplicate IDs, anonymous drawn paths and explicit binding metadata checked',
                groups=group_checks,records=records)


def transformer_artifact_receipts(root):
    directory=root/'arrow_semantic_audit/transformer';rows=[]
    report=json.loads((directory/'actual_transformer_audit.json').read_text())
    for view in report['views']:
        base=root/TOPICS[3]
        if view['variant']!='current':base=base/'variants'/'compact_mixed_flow'
        folder=base/'generated';number={'overview':1,'modules':2,'detailed':3}[view['view']]
        stem=f'figure{number}_{view["view"]}'
        paths=dict(svg=folder/(stem+'.svg'),png=folder/(stem+'.png'),
                   layout=folder/f'layout_{view["view"]}.json',
                   ir=folder/'semantic_ir.json',evidence=folder/'source_evidence.json')
        expected=view.get('sha256',{})
        for kind,path in paths.items():
            saved=expected.get(kind)
            if saved is None:
                saved=view.get('artifacts',{}).get(dict(svg='SVG_sha256',png='PNG_sha256',
                    layout='layout_sha256',ir='IR_sha256',evidence='evidence_sha256')[kind])
            current=sha(path)
            rows.append(dict(variant=view['variant'],view=view['view'],kind=kind,
                             path=str(path.relative_to(root)),receipt_sha256=saved,
                             current_sha256=current,passed=saved is not None and saved==current))
    mini=json.loads((directory/'mini/actual_mini_residual_audit.json').read_text())
    for annotation in mini['records']:
        folder=root/TOPICS[3]
        if annotation['variant']!='current':folder=folder/'variants'/'compact_mixed_flow'
        for kind,path in dict(svg=folder/'mini_residual.svg',layout=folder/'mini_residual_layout.json').items():
            saved=annotation.get(kind+'_sha256');current=sha(path)
            rows.append(dict(variant=annotation['variant'],view='mini',kind=kind,
                             path=str(path.relative_to(root)),receipt_sha256=saved,
                             current_sha256=current,passed=saved is not None and saved==current))
    return dict(passed=report.get('passed') is True and mini.get('passed') is True and all(r['passed'] for r in rows),
                views_checked=len(report['views'])+len(mini['records']),hashes_checked=len(rows),rows=rows,
                method='actual Transformer current/compact and teaching mini saved artifact digests compared with current bytes')


def audit(root):
    directory=root/'arrow_semantic_audit'
    shared=json.loads((directory/'shared_before_manifest.json').read_text())
    specialized=json.loads((directory/'timeseries_transformer/before_manifest.json').read_text())['files']
    baseline=shared+specialized
    if len({row['path'] for row in baseline})!=len(baseline):
        raise ValueError('duplicate baseline path')
    backups=[];sources=[];historical=[];indices=[]
    for row in baseline:
        relative=row['path'];snapshot=root/row.get('snapshot','arrow_semantic_audit/before/'+relative)
        saved=sha(snapshot)
        backups.append(dict(path=relative,snapshot=str(snapshot.relative_to(root)),
                            expected_sha256=row['sha256'],snapshot_exists=snapshot.is_file(),
                            snapshot_sha256=saved,passed=saved==row['sha256']))
        if any(part in Path(relative).parts for part in ('sources','snapshots','upstream')):
            current=root/relative;digest=sha(current)
            record=dict(path=relative,before_sha256=row['sha256'],current_exists=current.is_file(),
                        current_sha256=digest,passed=digest==row['sha256'])
            if 'sources' in Path(relative).parts:sources.append(record)
            if 'snapshots' in Path(relative).parts:historical.append(record)
            if 'upstream' in Path(relative).parts:indices.append(record)
    inventory=[]
    for topic in TOPICS:
        old={row['path'] for row in sources if row['path'].startswith(topic+'/')}
        current={str(path.relative_to(root)) for path in (root/topic).rglob('*')
                 if path.is_file() and 'sources' in path.relative_to(root).parts}
        inventory.append(dict(topic=topic,current_files=len(current),before_files=len(old),
                              added=sorted(current-old),missing=sorted(old-current),passed=current==old))
    svg_inventory=defaultdict(list)
    for path in sorted(root.rglob('*.svg')):
        relative=path.relative_to(root);parts=relative.parts
        if parts[0]=='arrow_semantic_audit':continue
        if parts[0]=='pytorch_transformer_original':category='provided_source_figure'
        elif 'snapshots' in parts:category='historical_snapshots'
        elif parts[0]=='transformer_programmatic_guide' and 'variants' in parts:
            category='active_compact' if path.name.startswith('figure') else 'active_mini'
        elif path.name=='mini_residual.svg':category='active_mini'
        elif 'generated' in parts:category='main_views'
        else:category='other'
        svg_inventory[category].append(str(relative))
    main_topics=Counter(path.split('/')[0] for path in svg_inventory['main_views'])
    migration=json.loads((root/'migration_audit.json').read_text())
    archives=[]
    for row in migration['source_archives_carried_to_new_root']:
        original=sha(Path(row['source']));current=sha(root/row['name'])
        archives.append(dict(name=row['name'],original_sha256=original,current_sha256=current,
                             expected_sha256=row['sha256'],
                             passed=original==current==row['sha256']))
    references=[]
    for relative in svg_inventory['provided_source_figure']:
        old=migration['current_file_sha256'].get(relative);current=sha(root/relative)
        references.append(dict(path=relative,before_sha256=old,current_sha256=current,
                               passed=old is not None and old==current))
    primary_links=check_links(root)
    audit_links=check_links(root,audit_documents=True)
    receipts=artifact_receipts(root)
    actual_xml=actual_svg_inventory(root,svg_inventory)
    transformer_receipts=transformer_artifact_receipts(root)
    expected_counts=dict(main_views=318,provided_source_figure=1,active_mini=2,
                         historical_snapshots=7,active_compact=3)
    expected_topics=dict(zip(TOPICS,(75,228,12,3)))
    scope_passed={k:len(v) for k,v in svg_inventory.items()}==expected_counts and dict(main_topics)==expected_topics
    intact=all(row['passed'] for row in backups+sources+historical+indices+archives+references+inventory) and receipts['passed'] and scope_passed and actual_xml['passed'] and transformer_receipts['passed']
    return dict(schema='archcanvas-arrow-integrity-crossaudit/2',
                checked_at=datetime.now(timezone.utc).isoformat(),read_only=True,
                upstream_model_execution=False,root=str(root),
                reproduction_command='python3 prototype/arrow_semantic_audit/check_integrity.py --write-report',
                backup_preservation=dict(files=len(backups),passed=all(r['passed'] for r in backups),rows=backups),
                source_preservation=dict(files=len(sources),passed=all(r['passed'] for r in sources+inventory),topics=inventory,rows=sources),
                historical_preservation=dict(files=len(historical),passed=all(r['passed'] for r in historical),rows=historical),
                upstream_index_preservation=dict(files=len(indices),passed=all(r['passed'] for r in indices),rows=indices),
                original_archives=dict(files=len(archives),passed=all(r['passed'] for r in archives),rows=archives),
                provided_reference_preservation=dict(files=len(references),passed=all(r['passed'] for r in references),rows=references),
                svg_inventory=dict(passed=scope_passed,total=sum(map(len,svg_inventory.values())),
                                   counts={k:len(v) for k,v in svg_inventory.items()},
                                   main_topics=dict(main_topics),paths=dict(svg_inventory),
                                   expected_counts=expected_counts,expected_main_topics=expected_topics),
                active_link_check=primary_links,audit_report_link_check=audit_links,
                saved_artifact_receipt_check=receipts,
                actual_svg_route_inventory=actual_xml,
                transformer_artifact_receipt_check=transformer_receipts,
                overall_integrity_passed=intact,
                delivery_navigation_ready=primary_links['passed'] and audit_links['passed'])


def shared_inventory(root):
    """Preserve every before record; refresh current hashes, list additions."""
    directory=root/'arrow_semantic_audit'
    before=json.loads((directory/'shared_before_manifest.json').read_text())
    previous=json.loads((directory/'shared_before_after.json').read_text())
    if len(before)!=2387:raise ValueError('shared manifest should retain 2,387 original records')
    if [r['path'] for r in previous['records']] != [r['path'] for r in before]:
        raise ValueError('before/current report record order differs from original manifest')
    records=[];known=set();counts=Counter()
    for saved,old in zip(before,previous['records']):
        if old['before_sha256']!=saved['sha256']:raise ValueError('previous before hash differs from original manifest')
        snapshot=sha(directory/'before'/saved['path']);current=sha(root/saved['path'])
        status='missing' if current is None else 'unchanged' if current==saved['sha256'] else 'modified'
        record=dict(path=saved['path'],before_sha256=saved['sha256'],after_sha256=current,
                    status=status,snapshot_sha256=snapshot,snapshot_passed=snapshot==saved['sha256'])
        records.append(record);counts[status]+=1;known.add(saved['path'])
    additions=[]
    for topic in TOPICS[:2]:
        for path in sorted((root/topic).rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:continue
            relative=str(path.relative_to(root))
            if relative not in known:
                additions.append(dict(path=relative,after_sha256=sha(path),size_bytes=path.stat().st_size))
    return dict(scope=previous['scope'],checked_at=datetime.now(timezone.utc).isoformat(),
                counts={key:counts[key] for key in ('unchanged','modified','missing')},
                before_records=len(records),before_preserved=all(r['snapshot_passed'] for r in records),
                before_manifest_sha256=sha(directory/'shared_before_manifest.json'),
                records=records,new_file_count=len(additions),new_files=additions,
                new_file_exclusion='__pycache__; original before records remain complete')


def markdown(result):
    def yn(condition):return '通过' if condition else '失败，见 JSON 明细'
    counts=result['svg_inventory']['counts'];links=result['active_link_check'];audit_links=result['audit_report_link_check']
    lines=['# 箭头审查：独立文件完整性与交付范围核对','',
           '本检查只读取现有文件。默认运行不写入结果；显式 `--write-report` 仅刷新本页、`integrity_checks.json` 和 `shared_before_after.json`，不修改源码、SVG、before 或历史基线，也不导入或执行上游模型。','',
           '| 核对对象 | 文件数量 | 结果 |','|---|---:|---|']
    for key,label in [('backup_preservation','修改前 before 备份'),('source_preservation','四专题 source 副本'),('historical_preservation','Transformer 历史 snapshots'),('upstream_index_preservation','固定 upstream 索引'),('original_archives','原始压缩包与 prototype 携带副本'),('provided_reference_preservation','随附原始参考 SVG')]:
        value=result[key];lines.append(f'| {label} | {value["files"]:,} | {yn(value["passed"])}，逐文件 SHA-256 一致 |')
    lines+=['','source 数量按专题为：'+ '、'.join(f'{r["topic"]} {r["current_files"]}' for r in result['source_preservation']['topics'])+'；文件无增删，所有修改前/后摘要见机器记录。`sources` 与 `snapshots` 范围可能包含同一文件，各项不能直接相加。',
            '','当前图像、适配器和说明允许有意更新，其旧内容均在 before 保留。current / compact / mini 图像不按旧字节相同判定；历史 snapshots 的原文件则逐一要求原字节不变。',
            '',f'另核对 module 与 model-zoo 已保存审计记录的 {result["saved_artifact_receipt_check"]["views_checked"]} 个视图，逐项比较 SVG、IR 与布局文件共 **{result["saved_artifact_receipt_check"]["hashes_checked"]} 个摘要**，结果：**{yn(result["saved_artifact_receipt_check"]["passed"])}**。此项检查收据对应当前产物，不重复执行语义验收。',
            '',f'Transformer 当前/compact 六视图与两个 mini 的审计产物再核对 **{result["transformer_artifact_receipt_check"]["hashes_checked"]} 个摘要**（SVG、PNG、IR、布局、evidence，以及 mini 的 SVG/布局），结果：**{yn(result["transformer_artifact_receipt_check"]["passed"])}**。',
            '','## SVG 范围','',f'排除审计 before 备份和额外展开 fixture 后，共 **{result["svg_inventory"]["total"]} 个 SVG**。','',
            '| 范围 | SVG 数量 |','|---|---:|']
    for key,value in result['svg_inventory']['main_topics'].items():lines.append(f'| {key} 正式主视图 | {value} |')
    for key,label in [('active_compact','活跃 compact 版'),('active_mini','活跃 mini 示例'),('historical_snapshots','历史 snapshots'),('provided_source_figure','随附源码参考图')]:
        lines.append(f'| {label} | {counts.get(key,0)} |')
    lines+=['',f'主视图 **{counts.get("main_views",0)}** 张；加活跃 compact / mini 后 **{sum(counts.get(k,0) for k in ("main_views","active_compact","active_mini"))}** 张。历史与随附原图文件保留不代表本轮真实端点认证。逐 SVG 路径列表在 JSON 中。',
            '',f'独立读取 **{result["actual_svg_route_inventory"]["active_svg"]} 张活跃 SVG** 的实际 XML，计 **{result["actual_svg_route_inventory"]["actual_data_route_id_paths"]:,} 条 `data-route-id` 路径**。逐文件检查无重复 ID、无匿名绘制路径，并有显式语义绑定或教学 annotation 字段；不以 layout 自报路径数代替实际 XML。分组统计见机器记录。',
            '','## 导航与复现','',
            f'四专题与迁移入口 {links["documents"]} 份活跃 Markdown/HTML，核对 {links["local_references"]:,} 个本地引用，断链 **{links["broken_count"]}**。另扫描 {audit_links["documents"]} 份活跃审计说明中的 {audit_links["local_references"]:,} 个本地引用，断链 **{audit_links["broken_count"]}**。',
            '','排除 before 备份、历史 snapshots、上游/source README；忽略代码块与正确转义的方括号。此次只检查文件/目录存在性，不检查远端 URL、fragment anchor 或运行时 JavaScript 动态目标。源码完整性与导航就绪分别记录，缺失路径会逐项列出。',
            '','从 ArchCanvas 工作区根目录运行：','',
            '```bash','python3 prototype/arrow_semantic_audit/check_integrity.py',
            'python3 prototype/arrow_semantic_audit/check_integrity.py --write-report','```','',
            '第一条仅检查并打印，不写文件；第二条只更新审计结果，并为共享专题清单保留原始 2,387 条 before 记录、验证每份备份、重算当前摘要，另列新增文件（不计 __pycache__）。脚本按自身位置解析 prototype，不依赖当前工作目录；也可通过 `--root` 显式指定副本目录。',
            '',f'检查时间：`{result["checked_at"]}`。完整性：**{yn(result["overall_integrity_passed"])}**；导航：**{yn(result["delivery_navigation_ready"])}**。逐文件结果见 [integrity_checks.json](integrity_checks.json)，复现脚本为 [check_integrity.py](check_integrity.py)。','']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=HERE.parent)
    parser.add_argument('--write-report',action='store_true')
    args=parser.parse_args();root=args.root.resolve();result=audit(root)
    inventory=shared_inventory(root)
    result['shared_before_after_refresh']=dict(before_records=inventory['before_records'],
        before_preserved=inventory['before_preserved'],counts=inventory['counts'],new_file_count=inventory['new_file_count'])
    if args.write_report:
        directory=root/'arrow_semantic_audit'
        (directory/'shared_before_after.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        # The Markdown itself contains local links. Count those final links,
        # rather than retaining counts from its previous formatting version.
        (directory/'integrity_checks.md').write_text(markdown(result),encoding='utf-8')
        result['audit_report_link_check']=check_links(root,audit_documents=True)
        result['delivery_navigation_ready']=result['active_link_check']['passed'] and result['audit_report_link_check']['passed']
        (directory/'integrity_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (directory/'integrity_checks.md').write_text(markdown(result),encoding='utf-8')
    summary={key:{k:v for k,v in value.items() if k in ('files','passed','total','counts','main_topics','documents','local_references','broken_count','broken','views_checked','hashes_checked','active_svg','actual_data_route_id_paths','groups')}
             for key,value in result.items() if isinstance(value,dict)}
    summary.update(overall_integrity_passed=result['overall_integrity_passed'],
                   delivery_navigation_ready=result['delivery_navigation_ready'],reports_written=args.write_report)
    summary['shared_before_after']=result['shared_before_after_refresh']
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if not(result['overall_integrity_passed'] and result['delivery_navigation_ready']):raise SystemExit(1)


if __name__=='__main__':main()
