"""Reviewed model registry; batches share one engine and retain separate snapshots."""
BATCHES = {
    'batch1': ['lenet', 'resnet', 'densenet', 'unet', 'vae', 'lstm'],
    'batch2': ['alexnet', 'mobilenetv2', 'nin', 'textcnn', 'convae', 'dcgan'],
    'batch3': ['vgg16', 'resnet50', 'convvae', 'ccvae', 'gru', 'bilstm'],
    'batch4': ['mobilenetv3', 'resnet101', 'vgg19', 'convgan', 'dcwgan', 'graphnet'],
    'cell_examples': ['lstmcell'],
}
BATCH_LABELS = {'batch1': '第一批', 'batch2': '第二批', 'batch3': '第三批', 'batch4': '第四批', 'cell_examples': '循环单元专题'}
KEYS = [key for batch in BATCHES.values() for key in batch]
VIEWS = ['overview', 'modules', 'detailed']


def selected(batch='all', model='all'):
    if model != 'all':
        if batch != 'all' and model not in BATCHES[batch]:
            raise ValueError(f'{model} does not belong to {batch}')
        return [model]
    return KEYS if batch == 'all' else BATCHES[batch]
