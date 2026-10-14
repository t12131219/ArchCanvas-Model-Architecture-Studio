# %% Notebook cell 3
# NOTEBOOK_MAGIC %load_ext watermark
# NOTEBOOK_MAGIC %watermark -a 'Sebastian Raschka' -v -p torch


import torch
import torch.nn.functional as F
from torchtext import data
from torchtext import datasets
import time
import random
import pandas as pd
import numpy as np

torch.backends.cudnn.deterministic = True

# %% Notebook cell 5
RANDOM_SEED = 123
torch.manual_seed(RANDOM_SEED)

VOCABULARY_SIZE = 5000
LEARNING_RATE = 1e-3
BATCH_SIZE = 128
NUM_EPOCHS = 50
DROPOUT = 0.5
DEVICE = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

EMBEDDING_DIM = 128
BIDIRECTIONAL = True
HIDDEN_DIM = 256
NUM_LAYERS = 2
OUTPUT_DIM = 4

# %% Notebook cell 8
# !tar xvzf  ag_news_csv.tar.gz

# %% Notebook cell 9
# NOTEBOOK_MAGIC !cat ag_news_csv/classes.txt

# %% Notebook cell 11
df = pd.read_csv('ag_news_csv/train.csv', header=None, index_col=None)
df.columns = ['classlabel', 'title', 'content']
df['classlabel'] = df['classlabel']-1
df.head()

# %% Notebook cell 12
np.unique(df['classlabel'].values)

# %% Notebook cell 13
np.bincount(df['classlabel'])

# %% Notebook cell 14
df[['classlabel', 'content']].to_csv('ag_news_csv/train_prepocessed.csv', index=None)

# %% Notebook cell 15
df = pd.read_csv('ag_news_csv/test.csv', header=None, index_col=None)
df.columns = ['classlabel', 'title', 'content']
df['classlabel'] = df['classlabel']-1
df.head()

# %% Notebook cell 16
np.unique(df['classlabel'].values)

# %% Notebook cell 17
np.bincount(df['classlabel'])

# %% Notebook cell 18
df[['classlabel', 'content']].to_csv('ag_news_csv/test_prepocessed.csv', index=None)

# %% Notebook cell 19
del df

# %% Notebook cell 21
TEXT = data.Field(sequential=True,
                  tokenize='spacy',
                  include_lengths=True) # necessary for packed_padded_sequence

LABEL = data.LabelField(dtype=torch.float)


# If you get an error [E050] Can't find model 'en'
# you need to run the following on your command line:
#  python -m spacy download en

# %% Notebook cell 23
fields = [('classlabel', LABEL), ('content', TEXT)]

train_dataset = data.TabularDataset(
    path="ag_news_csv/train_prepocessed.csv", format='csv',
    skip_header=True, fields=fields)

test_dataset = data.TabularDataset(
    path="ag_news_csv/test_prepocessed.csv", format='csv',
    skip_header=True, fields=fields)

# %% Notebook cell 25
train_data, valid_data = train_dataset.split(
    split_ratio=[0.95, 0.05],
    random_state=random.seed(RANDOM_SEED))

print(f'Num Train: {len(train_data)}')
print(f'Num Valid: {len(valid_data)}')

# %% Notebook cell 27
TEXT.build_vocab(train_data,
                 max_size=VOCABULARY_SIZE,
                 vectors='glove.6B.100d',
                 unk_init=torch.Tensor.normal_)

LABEL.build_vocab(train_data)

print(f'Vocabulary size: {len(TEXT.vocab)}')
print(f'Number of classes: {len(LABEL.vocab)}')

# %% Notebook cell 28
list(LABEL.vocab.freqs)[-10:]

# %% Notebook cell 31
train_loader, valid_loader, test_loader = data.BucketIterator.splits(
    (train_data, valid_data, test_dataset), 
    batch_size=BATCH_SIZE,
    sort_within_batch=True, # necessary for packed_padded_sequence
    sort_key=lambda x: len(x.content),
    device=DEVICE)

# %% Notebook cell 33
print('Train')
for batch in train_loader:
    print(f'Text matrix size: {batch.content[0].size()}')
    print(f'Target vector size: {batch.classlabel.size()}')
    break
    
print('\nValid:')
for batch in valid_loader:
    print(f'Text matrix size: {batch.content[0].size()}')
    print(f'Target vector size: {batch.classlabel.size()}')
    break
    
print('\nTest:')
for batch in test_loader:
    print(f'Text matrix size: {batch.content[0].size()}')
    print(f'Target vector size: {batch.classlabel.size()}')
    break

# %% Notebook cell 35
import torch.nn as nn


class RNN(nn.Module):
    def __init__(self, input_dim, embedding_dim, bidirectional, hidden_dim, num_layers, output_dim, dropout, pad_idx):
        
        super().__init__()
        
        self.embedding = nn.Embedding(input_dim, embedding_dim, padding_idx=pad_idx)
        self.rnn = nn.LSTM(embedding_dim, 
                           hidden_dim,
                           num_layers=num_layers,
                           bidirectional=bidirectional, 
                           dropout=dropout)
        self.fc1 = nn.Linear(hidden_dim * num_layers, 64)
        self.fc2 = nn.Linear(64, output_dim)
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, text, text_length):

        embedded = self.dropout(self.embedding(text))
        packed_embedded = nn.utils.rnn.pack_padded_sequence(embedded, text_length)
        packed_output, (hidden, cell) = self.rnn(packed_embedded)
        # output, output_lengths = nn.utils.rnn.pad_packed_sequence(packed_output)
        hidden = self.dropout(torch.cat((hidden[-2,:,:], hidden[-1,:,:]), dim=1))
        hidden = self.fc1(hidden)
        hidden = self.dropout(hidden)
        hidden = self.fc2(hidden)
        return hidden

# %% Notebook cell 36
INPUT_DIM = len(TEXT.vocab)

PAD_IDX = TEXT.vocab.stoi[TEXT.pad_token]

torch.manual_seed(RANDOM_SEED)
model = RNN(INPUT_DIM, EMBEDDING_DIM, BIDIRECTIONAL, HIDDEN_DIM, NUM_LAYERS, OUTPUT_DIM, DROPOUT, PAD_IDX)
model = model.to(DEVICE)
optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

# %% Notebook cell 38
def compute_accuracy(model, data_loader, device):
    model.eval()
    correct_pred, num_examples = 0, 0
    with torch.no_grad():
        for batch_idx, batch_data in enumerate(data_loader):
            text, text_lengths = batch_data.content
            logits = model(text, text_lengths)
            _, predicted_labels = torch.max(logits, 1)
            num_examples += batch_data.classlabel.size(0)
            correct_pred += (predicted_labels.long() == batch_data.classlabel.long()).sum()
        return correct_pred.float()/num_examples * 100

# %% Notebook cell 39
start_time = time.time()

for epoch in range(NUM_EPOCHS):
    model.train()
    for batch_idx, batch_data in enumerate(train_loader):
        
        text, text_lengths = batch_data.content
        
        ### FORWARD AND BACK PROP
        logits = model(text, text_lengths)
        cost = F.cross_entropy(logits, batch_data.classlabel.long())
        optimizer.zero_grad()
        
        cost.backward()
        
        ### UPDATE MODEL PARAMETERS
        optimizer.step()
        
        ### LOGGING
        if not batch_idx % 50:
            print (f'Epoch: {epoch+1:03d}/{NUM_EPOCHS:03d} | '
                   f'Batch {batch_idx:03d}/{len(train_loader):03d} | '
                   f'Cost: {cost:.4f}')

    with torch.set_grad_enabled(False):
        print(f'training accuracy: '
              f'{compute_accuracy(model, train_loader, DEVICE):.2f}%'
              f'\nvalid accuracy: '
              f'{compute_accuracy(model, valid_loader, DEVICE):.2f}%')
        
    print(f'Time elapsed: {(time.time() - start_time)/60:.2f} min')
    
print(f'Total Training Time: {(time.time() - start_time)/60:.2f} min')
print(f'Test accuracy: {compute_accuracy(model, test_loader, DEVICE):.2f}%')

# %% Notebook cell 42
import spacy
nlp = spacy.load('en')


map_dictionary = {
    0: "World",
    1: "Sports",
    2: "Business",
    3:"Sci/Tech",
}


def predict_class(model, sentence, min_len=4):
    # Somewhat based on
    # https://github.com/bentrevett/pytorch-sentiment-analysis/
    # blob/master/5%20-%20Multi-class%20Sentiment%20Analysis.ipynb
    model.eval()
    tokenized = [tok.text for tok in nlp.tokenizer(sentence)]
    if len(tokenized) < min_len:
        tokenized += ['<pad>'] * (min_len - len(tokenized))
    indexed = [TEXT.vocab.stoi[t] for t in tokenized]
    length = [len(indexed)]
    tensor = torch.LongTensor(indexed).to(DEVICE)
    tensor = tensor.unsqueeze(1)
    length_tensor = torch.LongTensor(length)
    preds = model(tensor, length_tensor)
    preds = torch.softmax(preds, dim=1)
    
    proba, class_label = preds.max(dim=1)
    return proba.item(), class_label.item()

# %% Notebook cell 43
text = """
The windfall follows a tender offer by Z Holdings, which is controlled by SoftBank’s domestic wireless unit, 
for half of Zozo’s shares this month.
"""

proba, pred_label = predict_class(model, text)

print(f'Class Label: {pred_label} -> {map_dictionary[pred_label]}')
print(f'Probability: {proba}')

# %% Notebook cell 44
text = """
EU data regulator issues first-ever sanction of an EU institution, 
against the European parliament over its use of US-based NationBuilder to process voter data 
"""

proba, pred_label = predict_class(model, text)

print(f'Class Label: {pred_label} -> {map_dictionary[pred_label]}')
print(f'Probability: {proba}')

# %% Notebook cell 45
text = """
LG announces CEO Jo Seong-jin will be replaced by Brian Kwon Dec. 1, amid 2020 
leadership shakeup and LG smartphone division's 18th straight quarterly loss
"""

proba, pred_label = predict_class(model, text)

print(f'Class Label: {pred_label} -> {map_dictionary[pred_label]}')
print(f'Probability: {proba}')

# %% Notebook cell 46
# NOTEBOOK_MAGIC %watermark -iv

# %% Notebook cell 47

