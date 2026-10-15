# %% Notebook cell 3
# NOTEBOOK_MAGIC %load_ext watermark
# NOTEBOOK_MAGIC %watermark -a 'Sebastian Raschka' -v -p torch

import torch
import torch.nn.functional as F
from torchtext import data
from torchtext import datasets
import time
import random

torch.backends.cudnn.deterministic = True

# %% Notebook cell 5
RANDOM_SEED = 123
torch.manual_seed(RANDOM_SEED)

VOCABULARY_SIZE = 20000
LEARNING_RATE = 1e-4
BATCH_SIZE = 128
NUM_EPOCHS = 15
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

EMBEDDING_DIM = 128
HIDDEN_DIM = 256
OUTPUT_DIM = 1

# %% Notebook cell 8
TEXT = data.Field(tokenize='spacy',
                  include_lengths=True) # necessary for packed_padded_sequence
LABEL = data.LabelField(dtype=torch.float)
train_data, test_data = datasets.IMDB.splits(TEXT, LABEL)
train_data, valid_data = train_data.split(random_state=random.seed(RANDOM_SEED),
                                          split_ratio=0.8)

print(f'Num Train: {len(train_data)}')
print(f'Num Valid: {len(valid_data)}')
print(f'Num Test: {len(test_data)}')

# %% Notebook cell 10
TEXT.build_vocab(train_data, max_size=VOCABULARY_SIZE)
LABEL.build_vocab(train_data)

print(f'Vocabulary size: {len(TEXT.vocab)}')
print(f'Number of classes: {len(LABEL.vocab)}')

# %% Notebook cell 13
train_loader, valid_loader, test_loader = data.BucketIterator.splits(
    (train_data, valid_data, test_data), 
    batch_size=BATCH_SIZE,
    sort_within_batch=True, # necessary for packed_padded_sequence
    device=DEVICE)

# %% Notebook cell 15
print('Train')
for batch in train_loader:
    print(f'Text matrix size: {batch.text[0].size()}')
    print(f'Target vector size: {batch.label.size()}')
    break
    
print('\nValid:')
for batch in valid_loader:
    print(f'Text matrix size: {batch.text[0].size()}')
    print(f'Target vector size: {batch.label.size()}')
    break
    
print('\nTest:')
for batch in test_loader:
    print(f'Text matrix size: {batch.text[0].size()}')
    print(f'Target vector size: {batch.label.size()}')
    break

# %% Notebook cell 17
import torch.nn as nn

class RNN(nn.Module):
    def __init__(self, input_dim, embedding_dim, hidden_dim, output_dim):
        
        super().__init__()
        
        self.embedding = nn.Embedding(input_dim, embedding_dim)
        self.rnn = nn.LSTM(embedding_dim, hidden_dim)
        self.fc = nn.Linear(hidden_dim, output_dim)
        
    def forward(self, text, text_length):

        #[sentence len, batch size] => [sentence len, batch size, embedding size]
        embedded = self.embedding(text)
        
        packed = torch.nn.utils.rnn.pack_padded_sequence(embedded, text_length)
        
        #[sentence len, batch size, embedding size] => 
        #  output: [sentence len, batch size, hidden size]
        #  hidden: [1, batch size, hidden size]
        packed_output, (hidden, cell) = self.rnn(packed)
        
        return self.fc(hidden.squeeze(0)).view(-1)

# %% Notebook cell 18
INPUT_DIM = len(TEXT.vocab)

torch.manual_seed(RANDOM_SEED)
model = RNN(INPUT_DIM, EMBEDDING_DIM, HIDDEN_DIM, OUTPUT_DIM)
model = model.to(DEVICE)
optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

# %% Notebook cell 20
def compute_binary_accuracy(model, data_loader, device):
    model.eval()
    correct_pred, num_examples = 0, 0
    with torch.no_grad():
        for batch_idx, batch_data in enumerate(data_loader):
            text, text_lengths = batch_data.text
            logits = model(text, text_lengths)
            predicted_labels = (torch.sigmoid(logits) > 0.5).long()
            num_examples += batch_data.label.size(0)
            correct_pred += (predicted_labels == batch_data.label.long()).sum()
        return correct_pred.float()/num_examples * 100

# %% Notebook cell 21
start_time = time.time()

for epoch in range(NUM_EPOCHS):
    model.train()
    for batch_idx, batch_data in enumerate(train_loader):
        
        text, text_lengths = batch_data.text
        
        ### FORWARD AND BACK PROP
        logits = model(text, text_lengths)
        cost = F.binary_cross_entropy_with_logits(logits, batch_data.label)
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
              f'{compute_binary_accuracy(model, train_loader, DEVICE):.2f}%'
              f'\nvalid accuracy: '
              f'{compute_binary_accuracy(model, valid_loader, DEVICE):.2f}%')
        
    print(f'Time elapsed: {(time.time() - start_time)/60:.2f} min')
    
print(f'Total Training Time: {(time.time() - start_time)/60:.2f} min')
print(f'Test accuracy: {compute_binary_accuracy(model, test_loader, DEVICE):.2f}%')

# %% Notebook cell 22
import spacy
nlp = spacy.load('en')

def predict_sentiment(model, sentence):
    # based on:
    # https://github.com/bentrevett/pytorch-sentiment-analysis/blob/
    # master/2%20-%20Upgraded%20Sentiment%20Analysis.ipynb
    model.eval()
    tokenized = [tok.text for tok in nlp.tokenizer(sentence)]
    indexed = [TEXT.vocab.stoi[t] for t in tokenized]
    length = [len(indexed)]
    tensor = torch.LongTensor(indexed).to(DEVICE)
    tensor = tensor.unsqueeze(1)
    length_tensor = torch.LongTensor(length)
    prediction = torch.sigmoid(model(tensor, length_tensor))
    return prediction.item()

# %% Notebook cell 23
print('Probability positive:')
predict_sentiment(model, "I really love this movie. This movie is so great!")

# %% Notebook cell 24

