from torch.utils.data import Dataset, DataLoader, Sampler
import os
import subprocess
import shutil
import warnings
import gzip
import typing


class Data:
    path_to_log_dir: str
    path_to_log: str

    def __init__(self, downloaded_url: str, train_ratio: float, cache_dir: str = os.path.expanduser('~/.dataset'),
                 dataset_dir:str='hdfs', extract_dir:str='../archive_extracted',
                 repeat_download: bool = False,
                 custom_archive_path: typing.Optional[str] = None, remove_archive: bool = False,
                 archive_type = None, use_in_colab: bool = False, encoding: str="latin-1",
                 errors:str="replace"):
        # gzip_fp -> extract_dir/data_dir/data_dir.log
        # * -> extract_dir/data_dir/*

        assert 0 <= train_ratio <= 1.
        if use_in_colab:
            cache_dir = "/content/"
            extract_dir = cache_dir

        self.train_ratio = train_ratio
        self.cache_dir=cache_dir
        self.dataset_dir=dataset_dir
        self.extract_dir=extract_dir
        self.custom_archive_path=custom_archive_path
        self.downloaded_url=downloaded_url
        self.use_in_colab = use_in_colab
        self.encoding = encoding
        self.errors = errors

        if not os.path.exists(cache_dir): raise FileExistsError
        if not repeat_download and os.path.exists(os.path.join(cache_dir, dataset_dir)):
            print('exist')
        else:
            if custom_archive_path is None:


                if os.path.exists(os.path.join(cache_dir, dataset_dir)):
                    warnings.warn("you use repeat download with downloaded archive, repeat_download=True")

                filepath = os.path.join(cache_dir, f'archive_{dataset_dir}')
                if os.path.exists(filepath) and not repeat_download:
                    print('already downloaded')
                else:
                    print('downloading...')
                    args = ['curl', '-o', filepath, '--retry-delay', '1', '--retry', str(int(100_000)),
                                    '--retry-all-errors', '-L',
                                    downloaded_url]
                    res = subprocess.run(args, capture_output=True, text=True)

                    print('stdout from curl', res.stdout)
                    print('stderr from curl', res.stderr)
                    print('download ends')
            else:
                filepath = custom_archive_path

                assert os.path.exists(filepath)

            print('archive', filepath, 'will extract')
            archive_path = filepath
            # поддерживаются те что втсречались в логхабе. не встречал  “bztar”, “xztar”, or “zstdtar”
            # поэтому их  поддержки нету
            # unpack_archive поддерживает след
            # “zip”, “tar”, “gztar”, “bztar”, “xztar”, or “zstdtar”
            # +gzip

            get_mime_type = lambda fp, p: subprocess.run(['file', f'-{p}', fp], capture_output=True, text=True).stdout.split()[
                1].removesuffix(';').split('/')

            if archive_type is None:
                print("автоопределение типа архива")

                exact_tp = None


                pref, tp = get_mime_type(filepath, 'iz')
                if get_mime_type(filepath, 'i')[1] == "zip":
                    pref = "text"

                if pref == "text":
                    # not tar gz
                    pref2, tp2 = get_mime_type(filepath, 'i')
                    if pref2 == "application":
                        if tp2 == "gzip":
                            # gz
                            exact_tp = "GZIP"
                        elif tp2 == "zip":
                            exact_tp = "zip"
                        elif tp2 == "x-tar":
                            exact_tp = "tar"

                else:
                    if pref == "application" and tp == "x-tar":
                        # tar gz
                        exact_tp = "gztar"
            else:
                exact_tp = archive_type
                assert exact_tp in ["zip", "tar", "gztar", "GZIP"]
                print("тип архива статично указан (archive_type)")

            assert exact_tp is not None, f"{pref=} {tp=}"

            extract_dir = os.path.join(extract_dir, dataset_dir)
            os.makedirs(extract_dir, exist_ok=True)

            print(f"{exact_tp=}, {pref=}, {tp=}, {extract_dir=}")

            if exact_tp == "GZIP":
                # custom
                with gzip.open(filepath, 'rb') as f_in:
                    with open(extract_dir + f"/{dataset_dir}.log", 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                self.archive_type_is_gz = True
            elif exact_tp.isupper():
                raise NotImplementedError
            else:
                shutil.unpack_archive(filepath, extract_dir=extract_dir, format=exact_tp)

            print('extracted in', extract_dir)
            if remove_archive:
                # не удаляем из cache_Dir
                os.remove(archive_path)
                print('archive removed', )



import datetime
import numpy  as np
import typing
import math
class SuperComputerDataset(Dataset):
    def __init__(
            self,
            filepath: str,
            n: int,
            max_lines: typing.Optional[int] = None,
            window_size: int = 200,
            step_size: int = 200,
            train_ratio: float = 0.3,
    ):
        assert n >= 1
        assert window_size >= 1
        assert step_size >= 1
        assert 0.0 < train_ratio <= 1.0

        self.max_lines = max_lines if max_lines is not None else math.inf

        self.filepath = filepath
        self.n = n
        self.window_size = window_size
        self.step_size = step_size
        self.train_ratio = train_ratio

        self.line_positions: list[int] = [] # позиции строк 0, n, 2n, ...
        self.labels: list = [] # метка для каждой строки
        self.total_lines = 0
        self._num_samples = 0

        self._build_index()

    def _line_label(self, line: str) -> int:
        return int(line.lstrip().startswith('-'))


    def _build_index(self) -> None:
        line_idx = 0
        with open(self.filepath, "rb") as f:
            while True:
                pos = f.tell()
                raw = f.readline()

                if not raw or (line_idx >= self.max_lines):
                    break

                if line_idx % self.n == 0:
                    self.line_positions.append(pos)

                line = raw.decode("latin-1", errors="replace")
                self.labels.append(self._line_label(line))

                line_idx += 1

        self.total_lines = line_idx

        if self.total_lines < self.window_size:
            total_samples = 0
        else:
            total_samples = (
                    (self.total_lines - self.window_size) // self.step_size + 1
            )

        self._num_samples = int(total_samples * self.train_ratio)

    def __getitem__(self, start_line: typing.Union[int, np.ndarray]) -> tuple[list, list]:
        if isinstance(start_line, np.ndarray):
            # 0d or scalar array
            start_line = start_line.item()

        if start_line < 0 or start_line + self.window_size > self.total_lines:
            raise IndexError(start_line)

        anchor_idx  = start_line // self.n
        anchor_line = anchor_idx * self.n
        skip_lines  = start_line - anchor_line

        with open(self.filepath, "rb") as f:
            f.seek(self.line_positions[anchor_idx])
            for _ in range(skip_lines):
                if not f.readline():
                    return [], []
            window = []
            for _ in range(self.window_size):
                raw = f.readline()
                if not raw:
                    break
                window.append(raw.decode("latin-1", errors="replace"))

        labels = max(self.labels[start_line : start_line + len(window)])
        return window, labels

    def __len__(self):
        return max(0, self.total_lines - self.window_size + 1)

import numpy as np
class JitterBalancedSampler(Sampler):
    def __init__(
        self,
        dataset,
        target_ratio=0.3,
        step_size=200,
        max_samples=None,
        min_samples=50_000,
        seed=None,
    ):
        self.dataset = dataset
        self.W = dataset.window_size
        self.N = dataset.total_lines
        self.step_size = step_size
        self.target_ratio = target_ratio

        labels = np.asarray(dataset.labels)
        self.anomaly_lines = np.flatnonzero(labels == 1)

        all_starts = np.arange(0, self.N - self.W + 1, step_size, dtype=np.int64)
        prefix = np.zeros(self.N + 1, dtype=np.int64)
        prefix[1:] = np.cumsum(labels)
        has_anom = (prefix[all_starts + self.W] - prefix[all_starts]) > 0
        self.normal_starts = all_starts[~has_anom]

        if len(self.anomaly_lines) == 0:
            raise ValueError("Нет аномалий в датасете")
        if len(self.normal_starts) == 0:
            raise ValueError("Нет нормальных окон без аномалий")

        N_norm = len(self.normal_starts)
        N_min  = len(self.anomaly_lines) # не считается по правильным стартовым позициям из-за аугментации через сдвиг
        self.print_count(N_norm, N_min, "до оверсемлинга")

        # сколько аномальных сэмплов нужно для доли target_ratio
        need_min = int(target_ratio * N_norm / (1 - target_ratio))
        need_min = max(need_min, N_min)
        total    = need_min + N_norm
        self.print_count(N_norm, need_min, "после оверсемплинга")

        if max_samples is not None:
            # всегда выполнено что для минорного класса (аномальных) >= tar_rat
            if max_samples > total:
                # доля 1
                raise ValueError("max_samples > total")
            total    = max_samples
            if N_min > total:
                print(f'после установки {max_samples=} в выборке остались только аномальные для всей эпохи')
            need_min = max(int(target_ratio * total), min(N_min, total))
        elif total < min_samples:
            # если дополняем до нужного числа объектов то доля будет tar_rat
            total    = min_samples
            need_min = max(int(target_ratio * total), N_min)


        self.normal_count    = total - need_min
        self.minority_count  = need_min
        self.total_size      = total
        self.print_count(self.normal_count, self.minority_count, f"после применения жестких ограничителей на размер датасета")
        self.rng = np.random.default_rng(seed)

    def __iter__(self):

        if self.normal_count < len(self.normal_starts):
            normals = self.rng.choice(self.normal_starts, self.normal_count, replace=False)
        else:
            reps = self.normal_count // len(self.normal_starts)
            rem  = self.normal_count - reps * len(self.normal_starts)
            normals = np.tile(self.normal_starts, reps)
            if rem:
                normals = np.concatenate([
                    normals,
                    self.rng.choice(self.normal_starts, rem, replace=False),
                ])
            self.rng.shuffle(normals)

        # с возращением если требуется больше чем есть иначе перестановка
        sampled = self.rng.choice(self.anomaly_lines, self.minority_count,
                                  replace=self.anomaly_lines==self.minority_count)

        # для каждой — валидный диапазон стартов
        # аномалия стоит на строке с индедксом a
        # тогда [lo, hi] набор индексов которые покрывают эту аномалию
        # [lo, lo + ws - 1] содержит a

        # lo <= a
        # lo + ws - 1 >= a

        # lo <= a
        # lo >= a - ws + 1
        # трбеование валидного старта
        # t - 1 - x + 1 = ws, x = t - ws
        # lo <= total - ws
        # трбеование не выхода за границы индексов окон со stride=1

        lo = np.maximum(0, sampled - self.W + 1)
        hi = np.minimum(sampled, self.N - self.W)

        # hi >= lo всегда, поскольку W <= N; проверка на всякий
        # assert np.all(hi >= lo)

        # случайный старт в [lo, hi]
        spans = hi - lo + 1
        # генерация в диапазоне [0, 1) соотв после приведения к int останется [0, ..., spans_i-1],
        # spans_i никогда не выпадет
        offsets = (self.rng.random(self.minority_count) * spans).astype(np.int64)
        anomalous = lo + np.minimum(offsets, spans - 1)

        combined = np.concatenate([normals, anomalous])
        self.rng.shuffle(combined)
        return iter(combined)

    def __len__(self):
        return self.total_size

    def print_count(self, n, a, phrase=''):
        print(f'{phrase}: число нормальных {n=}, аномальных {a=}, общее {n+a=}')
        print(f'их доли: доля нормальных={n/(n+a)*100:.3f}, аномальных={a/(n+a)*100:.3f}')



