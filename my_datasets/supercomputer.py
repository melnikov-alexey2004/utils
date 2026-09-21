import datetime
import typing

from my_datasets.dataset import Data
import os

# gzip_fp -> extract_dir/data_dir/data_dir.log
# источник всех датасетов https://www.usenix.org/cfdr-data
# вместо логхаба
class BGL(Data):
    def __init__(self, use_in_colab: bool=True):
        url = r'http://0b4af6cdc2f0c5998459-c0245c5c937c5dedcca3f1764ecc9b2f.r43.cf2.rackcdn.com/hpc4/bgl2.gz'
        super().__init__(url, dataset_dir='bgl', use_in_colab=use_in_colab)

        log_format = '<Label> <Id> <Date> <Code1> <Time> <Code2> <Component1> <Component2> <Level> <Content>'.split()
        self.cnt_ind = log_format.index("<Content>")
        self.path_to_log_dir = os.path.join(self.extract_dir, self.dataset_dir)
        self.path_to_log = os.path.join(self.path_to_log_dir, self.dataset_dir + ".log")

    def get_time_content_label(self, raw_log: str) -> tuple[typing.Optional[datetime.datetime],
                                                            str, int]:
        s=raw_log.split()
        label=1
        try:
            if s[0] == "-": label = 0
            t = s[4]
            dt = datetime.datetime.strptime(t, "%Y-%m-%d-%H.%M.%S.%f")
            cnt = ""
            if len(s) > self.cnt_ind:
                cnt = " ".join(s[self.cnt_ind:])
        except Exception:
            return None, "", 0

        return dt, cnt, label


class Tbird(Data):
    def __init__(self, use_in_colab: bool=True):
        url = r'http://0b4af6cdc2f0c5998459-c0245c5c937c5dedcca3f1764ecc9b2f.r43.cf2.rackcdn.com/hpc4/tbird2.gz'
        super().__init__(url, dataset_dir='tbird', use_in_colab=use_in_colab)

        log_format = '<Label> <Id> <Date> <Admin> <Month> <Day> <Time> <AdminAddr> <Content>'.split()
        self.cnt_ind = log_format.index("<Content>")

        self.path_to_log_dir = os.path.join(self.extract_dir, self.dataset_dir)
        self.path_to_log = os.path.join(self.path_to_log_dir, self.dataset_dir + ".log")

class Spirit(Data):
    def __init__(self, use_in_colab: bool=True):
        url = r'http://0b4af6cdc2f0c5998459-c0245c5c937c5dedcca3f1764ecc9b2f.r43.cf2.rackcdn.com/hpc4/spirit2.gz'
        super().__init__(url, dataset_dir='spirit', use_in_colab=use_in_colab)

        log_format = '<Label> <Id> <Date> <Admin> <Month> <Day> <Time> <AdminAddr> <Content>'.split()
        self.cnt_ind = log_format.index("<Content>")

        self.path_to_log_dir = os.path.join(self.extract_dir, self.dataset_dir)
        self.path_to_log = os.path.join(self.path_to_log_dir, self.dataset_dir + ".log")


class Liberty(Data):
    def __init__(self, use_in_colab: bool=True):
        url = r'http://0b4af6cdc2f0c5998459-c0245c5c937c5dedcca3f1764ecc9b2f.r43.cf2.rackcdn.com/hpc4/liberty2.gz'
        super().__init__(url, dataset_dir='liberty', use_in_colab=use_in_colab)

        log_format = '<Label> <Id> <Date> <Admin> <Month> <Day> <Time> <AdminAddr> <Content>'.split()
        self.cnt_ind = log_format.index("<Content>")

        self.path_to_log_dir = os.path.join(self.extract_dir, self.dataset_dir)
        self.path_to_log = os.path.join(self.path_to_log_dir, self.dataset_dir + ".log")

