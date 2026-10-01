from torch import nn


class Model:
    def __init__(self):
        self.recurrent = nn.LSTM(16, 32, batch_first=True)

    def forward(self, inputs):
        sequence, (hn, cn) = self.recurrent(inputs)
        _ = (hn, cn)
        return sequence
