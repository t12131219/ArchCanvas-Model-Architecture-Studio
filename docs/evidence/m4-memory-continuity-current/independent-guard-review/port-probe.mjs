import { buildScene } from '../../../../studio/src/core/scene.ts';
import { buildScene as beforeScene } from '../before-change/inputs/studio/src/core/scene.ts';
const ports=[{id:'in',name:'in',direction:'in',role:'data',ordinal:0},{id:'out',name:'out',direction:'out',role:'data',ordinal:0},{id:'alt',name:'alt',direction:'out',role:'data',ordinal:1}];
const n=(id,extra={})=>({id,label:id,kind:'Linear',category:'linear',children:[],ports:structuredClone(ports),parameters:{},evidence:'source',...extra});
const e=(id,s,t,extra={})=>({id,source:{nodeId:s,portId:'out'},target:{nodeId:t,portId:'in'},tensorId:'same-name',role:'memory',...extra});
const architecture={schemaVersion:1,id:'independent-multiple-consumer',entry:'literal:Independent',label:'Literal',sourceDigest:'not-executed',irDigest:'literal-independent',diagnostics:[],sources:[],nodes:[
  n('a'),n('b',{children:['b1','b2']}),n('b1',{parentId:'b'}),n('b2',{parentId:'b'}),
  n('c',{children:['c1']}),n('c1',{parentId:'c'}),n('d'),n('e')],edges:[
  e('accepted-first','a','b1'),e('retained-expanded','a','c1'),e('retained-style','a','d'),e('accepted-later','a','b2'),
  e('data-consumer','a','d',{role:'data'}),e('distinct-binding-equal-name','a','e',{source:{nodeId:'a',portId:'alt'}})]};
const document={schemaVersion:1,id:'literal-port',title:'Literal',revision:0,sourceBindingDigest:'not-executed',architecture,
  displayAliases:{},nodeStyleOverrides:{},edgeStyleOverrides:{'retained-style':{dashed:true,width:2.25}},legendItems:[],annotations:[],pageSpec:{widthMm:180,background:'#fff',preset:'paper'},
  expandedIds:['c'],layout:{a:{x:0,y:0,width:200,height:100},b:{x:300,y:10,width:200,height:100},c:{x:600,y:500,width:280,height:220},c1:{x:50,y:60,width:180,height:100},d:{x:600,y:900,width:200,height:100},e:{x:900,y:1200,width:200,height:100}},layoutByFrontier:{},pinnedObjects:[]};
const old=beforeScene(document),current=buildScene(document);
console.log(JSON.stringify({document,old,current},null,2));
