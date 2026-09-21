import torch
import torch.nn as nn
import torch.nn.functional as F


def period_candidates(x, k):
    spectrum = torch.fft.rfft(x, dim=1)
    amplitude = abs(spectrum).mean(0).mean(-1)
    _, selected = torch.topk(amplitude, k)
    return selected, abs(spectrum).mean(-1)


class InceptionBlock(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, x):
        return x


class TimesBlock(nn.Module):
    def __init__(self, configs):
        super().__init__()
        self.k = configs.top_k
        self.conv = nn.Sequential(InceptionBlock(), nn.GELU(), InceptionBlock())

    def forward(self, x):
        periods, weights = period_candidates(x, self.k)
        results = []
        for i in range(self.k):
            period = periods[i]
            out = x.reshape(x.shape[0], -1, period, x.shape[2]).permute(0, 3, 1, 2)
            out = self.conv(out)
            out = out.permute(0, 2, 3, 1).reshape(x.shape[0], -1, x.shape[2])
            results.append(out)
        results = torch.stack(results, dim=-1)
        weights = F.softmax(weights, dim=1)
        results = torch.sum(results * weights.unsqueeze(1).unsqueeze(1), -1)
        return results + x


class TimesNet(nn.Module):
    def __init__(self, configs):
        super().__init__()
        self.model = nn.ModuleList([TimesBlock(configs) for _ in range(configs.e_layers)])

    def forward(self, x):
        for block in self.model:
            x = block(x)
        return x
