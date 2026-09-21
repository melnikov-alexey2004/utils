from my_datasets.dataset import *
import torch
import torch.nn as nn
import torch.functional as F


class Trainer:
    def __init__(self, batch_size: int, load_trained: bool = True, ):
        self.batch_size = batch_size

    def train(self):
        ds = SuperComputerDataset()

