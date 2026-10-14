"""One source Fire block: squeeze then independent expand branches."""
from module_adapters._vision_common import Author,shape,validate_declaration
SOURCE='torchvision-v0.9.0-vision-extended/torchvision/models/squeezenet.py'
def build():
 a=Author('fire',SOURCE,'Fire');z=shape(16,32)
 squeeze=a.chain('squeeze','Squeeze 1x1',[a.conv('squeeze.conv','squeeze',64,16,out=z),a.relu('squeeze.relu',z,True)],z,expand=2,role='conv')
 branches=[]
 for name,k,p in [('expand1x1',1,0),('expand3x3',3,1)]:
  branches.append(a.chain(name,name,[a.conv(name+'.conv',name,16,64,k,p=p,out=shape(64,32)),a.relu(name+'.relu',shape(64,32),True)],shape(64,32),expand=2,role='conv'))
 fork=a.parallel('expand','Two independent expansions',branches,'2 x [B,64,32,32]',expand=1)
 cat=a.node('concat','Concat channel dim=1','concat',shape(128,32),role='concat',dim=1,ordered_inputs=[b['id'] for b in branches],learnable=False)
 body=a.chain('module','Fire',[squeeze,fork,cat],shape(128,32),expand=1,role='encoder')
 return a.model('Fire squeeze/expand','Fire.md',body,shape(64,32),shape(128,32),dict(scope='One Fire block only',constructor='Fire(64,16,64,64)',inplanes=64,squeeze_planes=16,expand_channels=[64,64]),['Squeeze Conv/ReLU runs before both independent expand paths.','All three Conv use bias=True; no BN, pooling or residual.','Two expanded tensors concatenate in 1x1 then3x3 order;128 channels.'],['The expand paths consume squeezed x, not raw64-channel x.','Same16->64 channel change is not shared weights.'])
def validate_ir(ir):return validate_declaration(ir,build())
