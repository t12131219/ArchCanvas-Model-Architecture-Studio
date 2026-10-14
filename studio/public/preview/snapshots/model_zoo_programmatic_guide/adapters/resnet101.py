"""Reviewed CIFAR-10 ResNet101 with [3,4,23,3] Bottlenecks and train-mode BatchNorm."""
from spec import chain, op, parallel, ref


SOURCE = "deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-resnet101-cifar10.py"
COUNTS = [3, 4, 23, 3]
PLANES = [64, 128, 256, 512]
SPATIAL = [8, 4, 2, 1]


def build():
    init = ref(SOURCE, "ResNet.__init__")
    forward = ref(SOURCE, "ResNet.forward")
    block_init = ref(SOURCE, "Bottleneck.__init__")
    block_forward = ref(SOURCE, "Bottleneck.forward")
    make = ref(SOURCE, "ResNet._make_layer")
    roles, fill = {}, []
    def conv(identity, scope, cin, cout, kernel, stride, spatial):
        roles[identity] = "conv" if kernel == 3 else "linear"
        return op(identity, "Conv%dx%d %d -> %d%s" % (kernel,kernel,cin,cout," / s2" if stride == 2 else ""),
                  "conv2d", block_init, "[B,%d,%d,%d]" % (cout,spatial,spatial),
                  ["padding=%d; bias=False; stride=%d" % (1 if kernel == 3 else 0,stride)],
                  parameter=scope, in_channels=cin, out_channels=cout,kernel_size=kernel,stride=stride,bias=False)
    def bn(identity,scope,channels,side):
        roles[identity]="norm"
        return op(identity,"BatchNorm2d","batch_norm2d",block_init,
                  "[B,%d,%d,%d]"%(channels,side,side),["train: per-batch statistics; running statistics updated; affine=True"],parameter=scope)
    def relu(identity,shape):
        roles[identity]="activation"
        return op(identity,"ReLU","relu",block_forward,shape,["inplace=True; same parameter-free self.relu called at 3 positions"])
    def main_path(prefix,scope,cin,planes,stride,size_in,size_out):
        inner_shape="[B,%d,%d,%d]"%(planes,size_in,size_in)
        reduced_shape="[B,%d,%d,%d]"%(planes,size_out,size_out)
        items=[conv(prefix+".conv1",scope+".conv1",cin,planes,1,1,size_in),
               bn(prefix+".bn1",scope+".bn1",planes,size_in),relu(prefix+".relu1",inner_shape),
               conv(prefix+".conv2",scope+".conv2",planes,planes,3,stride,size_out),
               bn(prefix+".bn2",scope+".bn2",planes,size_out),relu(prefix+".relu2",reduced_shape),
               conv(prefix+".conv3",scope+".conv3",planes,planes*4,1,1,size_out),
               bn(prefix+".bn3",scope+".bn3",planes*4,size_out)]
        roles[prefix]="inner"
        return chain(prefix,"Bottleneck convolution path",items,[block_init,block_forward],
                     "[B,%d,%d,%d]"%(planes*4,size_out,size_out),
                     ["1x1 reduce ->3x3 spatial ->1x1 expand4", "stride, if2, is in conv2 not conv1"],expand=2)
    def first_block(stage,cin,planes,stride,size_in,size_out,expand):
        p="r101.stage%d.first"%stage;scope="layer%d.0"%stage;cout=planes*4
        shape="[B,%d,%d,%d]"%(cout,size_out,size_out)
        main=main_path(p+".main",scope,cin,planes,stride,size_in,size_out)
        shortcut=chain(p+".shortcut","Projection shortcut",[
            op(p+".projection","Conv1x1 %d -> %d / s%d"%(cin,cout,stride),"conv2d",[make,block_forward],shape,
               ["bias=False; stride matches main conv2"],parameter=scope+".downsample.0",
               in_channels=cin,out_channels=cout,kernel_size=1,stride=stride,bias=False),
            op(p+".projection_bn","BatchNorm2d","batch_norm2d",[make,block_forward],shape,
               parameter=scope+".downsample.1"),
        ],[make,block_forward],shape,expand=2)
        paths=parallel(p+".paths","Main / projected shortcut",[main,shortcut],[make,block_forward],
                       "two matching operands",["both receive same x; parallel grouping is not an arithmetic Add"],
                       expand=2,dispatch=False,semantic_mode="operand_bundle",literal_tuple=False,
                       child_inputs={
                           main["id"]:dict(role="value",producer=p,src_port="in"),
                           shortcut["id"]:dict(role="value",producer=p,src_port="in"),
                       })
        roles.update({p:"conv",p+".paths":"group",p+".shortcut":"inner",
                      p+".projection":"linear",p+".projection_bn":"norm",p+".add":"norm"})
        fill.append(p)
        return chain(p,"First Bottleneck · projection",[paths,
            op(p+".add","Add two paths","add",block_forward,shape,["out += residual"]),
            relu(p+".relu3",shape),
        ],[block_init,block_forward,make],shape,
           ["stride=%d; input channels=%d; output=%d"%(stride,cin,cout),
            "stage1 projection is required even at stride1 because64!=256" if stage==1 else "both paths downsample; no identity shortcut"],
           expand=expand,parameter_scope=scope,use_projection=True,stride=stride,
           bottleneck_planes=planes,output_channels=cout,block_count=1,instance_indices=[0])
    def identity_template(stage,planes,side,count,expand):
        p="r101.stage%d.identities"%stage;scope="layer%d.{j}"%stage;cout=planes*4
        shape="[B,%d,%d,%d]"%(cout,side,side)
        main=main_path(p+".main",scope,cout,planes,1,side,side)
        main["items"].append(op(p+".add","Add identity input","add",block_forward,shape,["out += original x"]))
        main["residual"]=True;main["label"]="Three convolutions + identity"
        roles[p+".add"]="norm";roles[p]="conv";fill.append(p)
        return chain(p,"Identity Bottleneck x %d"%count,[main,relu(p+".relu3",shape)],
                     [make,block_init,block_forward],shape,
                     ["template j=1...%d; every instance has separate Conv/BN weights"%count,
                      "final ReLU follows Add; no projection; stride1"],expand=expand,
                     parameter_scope=scope,repeat=dict(count=count,index="j",instance_indices=list(range(1,count+1)),independent_parameters=True),
                     instance_indices=list(range(1,count+1)),block_count=count,
                     use_projection=False,stride=1,bottleneck_planes=planes,output_channels=cout)
    def folded_first(stage,cin,planes,stride,side):
        p="r101.stage%d.first"%stage;scope="layer%d.0"%stage;roles[p]="conv"
        return op(p,"First Bottleneck · projection","bottleneck",[make,block_init,block_forward],
                  "[B,%d,%d,%d]"%(planes*4,side,side),
                  ["main:1x1-BN-ReLU ->3x3(s2)-BN-ReLU ->1x1-BN",
                   "shortcut:Conv1x1(s2)+BN; then Add ->ReLU", "separate weights; %d->%d channels"%(cin,planes*4)],
                  parameter_scope=scope,parameter_members=[scope+"."+attr for attr in ["conv1","bn1","conv2","bn2","conv3","bn3","downsample.0","downsample.1"]],
                  use_projection=True,stride=stride,bottleneck_planes=planes,output_channels=planes*4,
                  block_count=1,instance_indices=[0])
    def folded_identities(stage,planes,side,count):
        p="r101.stage%d.identities"%stage;scope="layer%d.{j}"%stage;roles[p]="conv"
        return op(p,"Identity Bottleneck x %d"%count,"bottleneck",[make,block_init,block_forward],
                  "[B,%d,%d,%d]"%(planes*4,side,side),
                  ["1x1-BN-ReLU ->3x3-BN-ReLU ->1x1-BN ->Add original x ->ReLU",
                   "j=1...%d; independent weights; stride1; no projection"%count],
                  parameter_scope=scope,parameter_members=[scope+"."+attr for attr in ["conv1","bn1","conv2","bn2","conv3","bn3"]],
                  repeat=dict(count=count,index="j",instance_indices=list(range(1,count+1)),independent_parameters=True),
                  instance_indices=list(range(1,count+1)),block_count=count,use_projection=False,stride=1,
                  bottleneck_planes=planes,output_channels=planes*4)
    stem=chain("r101.stem","Conv stem",[
        op("r101.stem.conv","Conv7x7 3 ->64 / s2","conv2d",[init,forward],"[B,64,16,16]",
           ["padding3; bias=False"],parameter="conv1",kernel_size=7,stride=2),
        op("r101.stem.bn","BatchNorm2d","batch_norm2d",[init,forward],"[B,64,16,16]",
           ["train: batch statistics; no eval call in this notebook"],parameter="bn1"),
        op("r101.stem.relu","ReLU","relu",forward,"[B,64,16,16]",["inplace=True"]),
        op("r101.stem.pool","MaxPool3x3 / s2","max_pool2d",[init,forward],"[B,64,8,8]",["padding1"]),
    ],[init,forward],"[B,64,8,8]",expand=1)
    stages=[];cin,size_in=64,8
    for i,(count,planes,side) in enumerate(zip(COUNTS,PLANES,SPATIAL),1):
        stride=1 if i==1 else 2
        first=first_block(i,cin,planes,stride,size_in,side,2) if i<=2 else folded_first(i,cin,planes,stride,side)
        identities=identity_template(i,planes,side,count-1,2) if i==1 else folded_identities(i,planes,side,count-1)
        stages.append(chain("r101.stage%d"%i,"Stage%d · %d Bottlenecks"%(i,count),[first,identities],
                            [init,make,forward],"[B,%d,%d,%d]"%(planes*4,side,side),
                            ["planes=%d; expansion4; first stride%d"%(planes,stride)],expand=1,
                            parameter_scope="layer%d"%i,block_count=count))
        roles["r101.stage%d"%i]="encoder";fill.append("r101.stage%d"%i);cin,size_in=planes*4,side
    head=chain("r101.head","Classifier head",[
        op("r101.flatten","Flatten","tensor",forward,"[B,2048]",["x.view(B,-1); final spatial1x1; avgpool call commented"]),
        op("r101.fc","Linear2048 ->10","linear",[init,forward],"[B,10]",parameter="fc"),
        parallel("r101.returns","Return logits / probabilities",[
            op("r101.logits","Retain logits","identity",forward,"[B,10]"),
            op("r101.softmax","Softmax","softmax",forward,"[B,10]",["F.softmax(logits,dim=1)"]),
        ],forward,"(logits, probas)",expand=2,dispatch=False),
    ],[init,forward],"2 x [B,10]",expand=1)
    tree=chain("r101.root","ResNet101 · CIFAR-10",[
        op("r101.input","CIFAR-10 image","input",forward,"[B,3,32,32]",["native CIFAR-10 32x32; grayscale=False; no Resize"]),
        stem,*stages,head,
        op("r101.output","Forward return tuple","output",forward,"2 x [B,10]",["return logits,probas"]),
    ],[ref(SOURCE,"resnet101"),ref(SOURCE,"ResNet")],"2 x [B,10]",expand=0)
    roles.update({"r101.root":"root","r101.input":"input","r101.output":"output",
                  "r101.stem":"conv","r101.stem.conv":"conv","r101.stem.bn":"norm",
                  "r101.stem.relu":"activation","r101.stem.pool":"pool","r101.head":"ffn",
                  "r101.flatten":"tensor","r101.fc":"linear","r101.returns":"group",
                  "r101.logits":"tensor","r101.softmax":"softmax"})
    return dict(key="resnet101",name="ResNet101 (CIFAR-10 notebook)",source_project="deeplearning-models-batch4",
                entry=ref(SOURCE,"ResNet"),
                profile=dict(task="CIFAR-10 classification",mode="train",input_channels=3,input_size=[32,32],num_classes=10,
                             source_factory="resnet101",factory_comment="ResNet-101",factory_num_classes_argument_used=False,factory_grayscale_argument_used=True,actual_block="Bottleneck",expansion=4,
                             stage_blocks=COUNTS,bottleneck_planes=PLANES,stage_output_channels=[256,512,1024,2048],
                             stage_spatial=SPATIAL,total_bottlenecks=33,projection_blocks=4,identity_blocks=29,
                             stride_location="Bottleneck.conv2",avgpool_constructed=True,avgpool_called=False,avgpool_kernel=7,avgpool_stride=1,avgpool_padding=2,
                             batchnorm_statistics="training batch statistics",source_has_eval_call=False,
                             classifier=[2048,10],batch_size_setting=128,output="(logits, probas)",
                             config_source=SOURCE+" notebook cells10,12,15,16"),
                profile_label="CIFAR-10 32x32 · [3,4,23,3] Bottlenecks · no AvgPool · train / BN batch stats",
                tree=tree,aux_inputs=[],extra_edges=[],visual_roles=roles,fill_width=fill+["r101.stem","r101.head"],
                facts=[
                    "The actual resnet101 factory constructs33 Bottleneck(expansion4) blocks with [3,4,23,3]; stage3 has23 independent blocks.",
                    "The factory reads global NUM_CLASSES=10 instead of its num_classes parameter, but actually uses its grayscale argument (False in caller).",
                    "The source never calls model.eval(): model.train() stays active during compute_accuracy; no_grad does not change BatchNorm mode.",
                    "Input[B,3,32,32] becomes64x16x16 after7x7 stride2 Conv, then64x8x8 after3x3 stride2 MaxPool.",
                    "Four stages contain3,4,23,3 independent Bottlenecks, with output channels256,512,1024,2048 and spatial sizes8,4,2,1.",
                    "Each Bottleneck executes Conv1x1-BN-ReLU ->Conv3x3-BN-ReLU ->Conv1x1-BN ->Add shortcut ->ReLU.",
                    "Stride2 is on conv2, not conv1; projection shortcut uses matching stride. Stage1 also requires projection because64!=64*4 even at stride1.",
                    "There are4 learned projection shortcuts and29 identity shortcuts; no across-block weight sharing.",
                    "AvgPool2d(7,stride1,padding2) exists in __init__ but its forward call is commented; flatten directly receives2048x1x1.",
                    "The classifier is Linear2048->10; forward computes Softmax and returns logits and probas.",
                    "Stage1 projection/identity and stage2 downsampling projection expand as representative patterns; later templates preserve instance counts, scopes and parameter members.",
                ],
                corrections=[
                    "Preserve the real resnet101 factory and its [3,4,23,3] counts, not the earlier [3,4,6,3] model.",
                    "Do not label the selected source caller eval: no_grad leaves BN in train mode and compute_accuracy does not call eval.",
                    "Use CIFAR-10 RGB32x32 rather than MNIST grayscale or ImageNet224x224; do not add executed average pooling.",
                    "Draw stage1 projection despite stride1: expansion4 changes64 channels to256.",
                    "Place downsampling in the3x3 conv2 and the shortcut1x1, not in the main conv1.",
                    "Draw Bottleneck three-convolution structure, not ResNet18's two-convolution BasicBlock.",
                    "Final ReLU follows residual Add; BN follows conv3 before Add; preserve both forward return fields.",
                ],
                symbols={SOURCE:["conv3x3","Bottleneck","Bottleneck.__init__","Bottleneck.forward",
                                 "ResNet","ResNet.__init__","ResNet._make_layer","ResNet.forward","resnet101","compute_accuracy"]},
                config_files=[SOURCE],
                legend=["B batch; CIFAR-10 RGB32x32; expansion4; [3,4,23,3] blocks",
                        "source factory=resnet101; train profile / BN batch statistics; no AvgPool call",
                        "input pink / Conv blue / pointwise projection purple / BN and Add yellow / ReLU gray",
                        "repeat j selects distinct block parameters; both projected paths consume same input"])


def validate_ir(ir):
    nodes={n["id"]:n for n in ir["nodes"]};edges=ir["edges"];p=ir["profile"];labels=[]
    def check(value,label):
        if not value:raise ValueError("resnet101: "+label)
        labels.append(label)
    def has(src,dst,role=None):return any(e["src"]==src and e["dst"]==dst and (role is None or e["role"]==role) for e in edges)
    check(p["source_factory"]=="resnet101" and p["actual_block"]=="Bottleneck" and p["expansion"]==4,"real ResNet101 factory and Bottleneck expansion4")
    check(p["stage_blocks"]==COUNTS and p["stage_output_channels"]==[256,512,1024,2048] and p["stage_spatial"]==SPATIAL,"four stage counts,expanded channels and CIFAR shapes")
    check(p["mode"]=="train" and p["source_has_eval_call"] is False and p["batchnorm_statistics"]=="training batch statistics", "caller remains in training BN mode even under no_grad")
    check(p["input_size"]==[32,32] and p["input_channels"]==3 and p["factory_grayscale_argument_used"] is True and p["factory_num_classes_argument_used"] is False, "CIFAR-10 RGB and real factory argument use")
    blocks=[n for n in nodes.values() if "use_projection" in n]
    check(sum(n["block_count"] for n in blocks)==33 and sum(n["block_count"] for n in blocks if n["use_projection"])==4,"33 independent blocks include4 learned projections")
    for i,count in enumerate(COUNTS,1):
        prefix="r101.stage%d"%i
        check(nodes[prefix]["block_count"]==count and nodes[prefix+".identities"]["repeat"]["count"]==count-1 and nodes[prefix+".identities"]["repeat"]["independent_parameters"],"stage%d independent identity repetitions"%i)
    for i in (1,2):
        prefix="r101.stage%d.first"%i
        paths=nodes[prefix+".paths"]
        check(paths["semantic_mode"]=="operand_bundle" and not paths["literal_tuple"] and
              has(prefix,prefix+".main","value_operand") and has(prefix,prefix+".shortcut","value_operand") and
              all(paths["child_inputs"][prefix+suffix]==dict(role="value",producer=prefix,src_port="in") for suffix in (".main",".shortcut")),
              "stage%d shared block input feeds typed main/projection operands, not source tuple"%i)
        check(nodes[prefix+".main.conv1"]["stride"]==1 and nodes[prefix+".main.conv2"]["stride"]==(1 if i==1 else 2) and nodes[prefix+".projection"]["stride"]==(1 if i==1 else 2),"stage%d stride on conv2 and matching projection"%i)
        check(has(prefix+".main.bn3",prefix+".main","boundary") and has(prefix+".add",prefix+".relu3"),"stage%d BN3 before Add and final ReLU after Add"%i)
    check(nodes["r101.stage1.first.projection"]["out_channels"]==256 and nodes["r101.stage1.first.projection"]["stride"]==1,"stage1 channel-changing projection at stride1")
    check(has("r101.stage1.identities.main","r101.stage1.identities.add","residual") and has("r101.stage1.identities.main","r101.stage1.identities.relu3"),"identity input reaches Add before final ReLU")
    check(nodes["r101.flatten"]["shape"]=="[B,2048]" and nodes["r101.fc"]["parameter"]=="fc" and p["avgpool_constructed"] and not p["avgpool_called"] and p["avgpool_padding"]==2,"2048 flatten without executing constructed avgpool")
    check(has("r101.returns","r101.logits","fork") and has("r101.returns","r101.softmax","fork"),"logits and Softmax probabilities are both returned")
    return labels
