
import torch
from torch.utils.data import Dataset

class TorchDataset(Dataset):

    def __init__(self, x, y=None):
        self.x = x
        self.y = y

    def __len__(self):
        return len(self.x)

    def __getitem__(self, item):
        if self.y is None:
            return self.x[item]
        return self.x[item], self.y[item]


def to_torch_dataset(x, y=None):
    return TorchDataset(x, y=y)


class TorchMetrics(object):

    def __init__(self, true, predicted):

        self.true = true
        self.predicted = predicted

    def r2(self):
        # https://stackoverflow.com/a/66992970/5982232
        target_mean = torch.mean(self.predicted)
        ss_tot = torch.sum((self.predicted - target_mean) ** 2)
        ss_res = torch.sum((self.predicted - self.true) ** 2)
        r2 = 1 - ss_res / ss_tot
        return r2

    def mape(self):

        return (self.predicted - self.true).abs() / (self.true.abs() + 1e-8)

    def nse(self):
        _nse = 1 - sum((self.predicted - self.true) ** 2) / sum((self.true - torch.mean(self.true)) ** 2)
        return float(_nse)

    def pbias(self):
        return 100.0 * sum(self.predicted - self.true) / sum(self.true)

    def rmse(self):
        return torch.sqrt(torch.mean(self.true - self.predicted)**2)