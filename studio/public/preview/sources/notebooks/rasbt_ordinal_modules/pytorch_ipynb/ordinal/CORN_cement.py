# %% Notebook cell 4
import pandas as pd
import numpy as np


data_df = pd.read_csv("https://raw.githubusercontent.com/gagolews/ordinal_regression_data/master/cement_strength.csv")
 
data_df["response"] = data_df["response"]-1 # labels should start at 0

data_labels = data_df["response"]
data_features = data_df.loc[:, ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"]]

print('Number of features:', data_features.shape[1])
print('Number of examples:', data_features.shape[0])
print('Labels:', np.unique(data_labels.values))

# %% Notebook cell 6
from sklearn.model_selection import train_test_split


X_train, X_test, y_train, y_test = train_test_split(
    data_features.values,
    data_labels.values,
    test_size=0.2,
    random_state=1,
    stratify=data_labels.values)

# %% Notebook cell 8
from sklearn.preprocessing import StandardScaler


sc = StandardScaler()
X_train_std = sc.fit_transform(X_train)
X_test_std = sc.transform(X_test)

# %% Notebook cell 11
import torch


##########################
### SETTINGS
##########################

# Hyperparameters
random_seed = 1
learning_rate = 0.001
num_epochs = 50
batch_size = 128

# Architecture
NUM_CLASSES = 5

# Other
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print('Training on', DEVICE)

# %% Notebook cell 12
from torch.utils.data import Dataset


class MyDataset(Dataset):

    def __init__(self, feature_array, label_array, dtype=np.float32):
    
        self.features = feature_array.astype(np.float32)
        self.labels = label_array

    def __getitem__(self, index):
        inputs = self.features[index]
        label = self.labels[index]
        return inputs, label

    def __len__(self):
        return self.labels.shape[0]

# %% Notebook cell 13
import torch
from torch.utils.data import DataLoader


# Note transforms.ToTensor() scales input images
# to 0-1 range
train_dataset = MyDataset(X_train_std, y_train)
test_dataset = MyDataset(X_test_std, y_test)


train_loader = DataLoader(dataset=train_dataset,
                          batch_size=batch_size,
                          shuffle=True, # want to shuffle the dataset
                          num_workers=0) # number processes/CPUs to use

test_loader = DataLoader(dataset=test_dataset,
                         batch_size=batch_size,
                         shuffle=False,
                         num_workers=0)

# Checking the dataset
for inputs, labels in train_loader:  
    print('Input batch dimensions:', inputs.shape)
    print('Input label dimensions:', labels.shape)
    break

# %% Notebook cell 16
class MLP(torch.nn.Module):

    def __init__(self, in_features, num_classes, num_hidden_1=300, num_hidden_2=300):
        super().__init__()
        
        self.my_network = torch.nn.Sequential(
            
            # 1st hidden layer
            torch.nn.Linear(in_features, num_hidden_1, bias=False),
            torch.nn.LeakyReLU(),
            torch.nn.Dropout(0.2),
            torch.nn.BatchNorm1d(num_hidden_1),
            
            # 2nd hidden layer
            torch.nn.Linear(num_hidden_1, num_hidden_2, bias=False),
            torch.nn.LeakyReLU(),
            torch.nn.Dropout(0.2),
            torch.nn.BatchNorm1d(num_hidden_2),
            
            ### Specify CORN layer
            torch.nn.Linear(num_hidden_2, (num_classes-1))
            ###--------------------------------------------------------------------###
        )
                
    def forward(self, x):
        logits = self.my_network(x)
        return logits
    
    
    
torch.manual_seed(random_seed)
model = MLP(in_features=8, num_classes=NUM_CLASSES)
model.to(DEVICE)

optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

# %% Notebook cell 19
#!pip install coral-pytorch

# %% Notebook cell 20
from coral_pytorch.losses import corn_loss


for epoch in range(num_epochs):
    
    model = model.train()
    for batch_idx, (features, class_labels) in enumerate(train_loader):

        class_labels = class_labels.to(DEVICE)
        features = features.to(DEVICE)
        logits = model(features)
        
        #### CORN loss 
        loss = corn_loss(logits, class_labels, NUM_CLASSES)
        ###--------------------------------------------------------------------###   
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        ### LOGGING
        if not batch_idx % 200:
            print ('Epoch: %03d/%03d | Batch %03d/%03d | Cost: %.4f' 
                   %(epoch+1, num_epochs, batch_idx, 
                     len(train_loader), loss))

# %% Notebook cell 22
from coral_pytorch.dataset import corn_label_from_logits


def compute_mae_and_mse(model, data_loader, device):

    with torch.no_grad():
    
        mae, mse, acc, num_examples = 0., 0., 0., 0

        for i, (features, targets) in enumerate(data_loader):

            features = features.to(device)
            targets = targets.float().to(device)

            logits = model(features)
            predicted_labels = corn_label_from_logits(logits).float()

            num_examples += targets.size(0)
            mae += torch.sum(torch.abs(predicted_labels - targets))
            mse += torch.sum((predicted_labels - targets)**2)

        mae = mae / num_examples
        mse = mse / num_examples
        return mae, mse

# %% Notebook cell 23
train_mae, train_mse = compute_mae_and_mse(model, train_loader, DEVICE)
test_mae, test_mse = compute_mae_and_mse(model, test_loader, DEVICE)

# %% Notebook cell 24
print(f'Mean absolute error (train/test): {train_mae:.2f} | {test_mae:.2f}')
print(f'Mean squared error (train/test): {train_mse:.2f} | {test_mse:.2f}')

# %% Notebook cell 28
logits = model(features)

with torch.no_grad():
    probas = torch.sigmoid(logits)
    probas = torch.cumprod(probas, dim=1)
    print(probas)

# %% Notebook cell 29

