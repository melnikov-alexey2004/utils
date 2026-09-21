from my_datasets.dataset import Data
import os

# gzip_fp -> extract_dir/data_dir/data_dir.log
# источник всех датасетов https://www.usenix.org/cfdr-data
# вместо логхаба
class BGL(Data):
    def __init__(self, train_ratio: float, use_in_colab: bool=False):
        url = r'http://0b4af6cdc2f0c5998459-c0245c5c937c5dedcca3f1764ecc9b2f.r43.cf2.rackcdn.com/hpc4/bgl2.gz'
        super().__init__(url, train_ratio, dataset_dir='bgl', use_in_colab=use_in_colab)

        self.path_to_log_dir = os.path.join(self.extract_dir, self.dataset_dir)
        self.path_to_log = os.path.join(self.path_to_log_dir, self.dataset_dir + ".log")

class Tbird(Data):
    def __init__(self, train_ratio: float, use_in_colab: bool=False):
        url = r'http://0b4af6cdc2f0c5998459-c0245c5c937c5dedcca3f1764ecc9b2f.r43.cf2.rackcdn.com/hpc4/tbird2.gz'
        super().__init__(url, train_ratio, dataset_dir='tbird', use_in_colab=use_in_colab)

        self.path_to_log_dir = os.path.join(self.extract_dir, self.dataset_dir)
        self.path_to_log = os.path.join(self.path_to_log_dir, self.dataset_dir + ".log")

class Spirit(Data):
    def __init__(self, train_ratio: float, use_in_colab: bool=False):
        url = r'http://0b4af6cdc2f0c5998459-c0245c5c937c5dedcca3f1764ecc9b2f.r43.cf2.rackcdn.com/hpc4/spirit2.gz'
        super().__init__(url, train_ratio, dataset_dir='spirit', use_in_colab=use_in_colab)

        self.path_to_log_dir = os.path.join(self.extract_dir, self.dataset_dir)
        self.path_to_log = os.path.join(self.path_to_log_dir, self.dataset_dir + ".log")

class Liberty(Data):
    def __init__(self, train_ratio: float, use_in_colab: bool=False):
        url = r'http://0b4af6cdc2f0c5998459-c0245c5c937c5dedcca3f1764ecc9b2f.r43.cf2.rackcdn.com/hpc4/liberty2.gz'
        super().__init__(url, train_ratio, dataset_dir='liberty', use_in_colab=use_in_colab)

        self.path_to_log_dir = os.path.join(self.extract_dir, self.dataset_dir)
        self.path_to_log = os.path.join(self.path_to_log_dir, self.dataset_dir + ".log")
