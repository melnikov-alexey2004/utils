import regex as re
from typing import Optional, Union, NamedTuple, Literal, cast
from collections.abc import Collection
import pickle
import dataclasses
import pandas as pd
import math
import tqdm.auto as tqdm
import warnings


class LogCluster:

    def __init__(self, logTemplate: list[str], index:int, max_container_size:int):
        self.logTemplate = logTemplate
        self.index=index # always >= 0 because -1 is UNK
        self.size=0
        self.bounded_set: set[str] = set()
        self.max_container_size=max_container_size

    def add(self, log_content: str):
        self.size += 1
        if len(self.bounded_set) >= self.max_container_size:
            return
        self.bounded_set.add(log_content)



class Node:
    def __init__(self, childD=None, depth=0, digitOrtoken=None):
        if childD is None:
            childD = dict()
        self.childD = childD
        self.depth = depth
        self.digitOrtoken = digitOrtoken


class LogParser:
    def __init__(
        self,
        log_format:str,
        depth=5,
        st=0.5,
        maxChild=100,
        rex=None,
        split_by_el: Optional[list[str]]=None,
        content='Content',
        log_cluster_size=100,
        is_log_format_escaped=False, # True on benchmark
        is_split_seqs_escaped=False,
    ):
        # log_format упадет на верхнем регистре. я не привожу к нижнему ибо тогда
        # регулярки не правильно сработают. хотя лог приводится к нижнему.

        self.depth = depth - 2
        self.is_log_format_escaped=is_log_format_escaped
        self.is_split_seqs_escaped=is_split_seqs_escaped
        self.st = st
        self.maxChild = maxChild
        self.logName = None
        self.df_log = None
        self.log_format = log_format # потенциально регулярка
        rex = [] if rex is None else rex
        self.rex = []
        for r in rex:
            self.rex.append( re.compile(r, re.IGNORECASE) if isinstance(r, str) else r) # сломает идентфикаторы регитсрозависимые

        assert f'<{content}>' in self.log_format, 'change content parameter'
        assert isinstance(self.rex, (tuple, list))
        headers, regex = self.generate_logformat_regex(self.log_format, self.is_log_format_escaped)
        self.headers=headers
        self.regex=regex
        if isinstance(split_by_el, str): raise TypeError('collection of str')
        if split_by_el is None: split_by_el = []


        if is_split_seqs_escaped and split_by_el and not any('\\' in seq for seq in split_by_el): warnings.warn(
            'is_split_seqs_escaped = True')

        split_by_el = [c for c in split_by_el if c and c not in (r'\s', r'\s+')]

        if split_by_el:
            split_by_el.sort(reverse=True, key=len)
            split = "|".join([c if is_split_seqs_escaped else re.escape(c) for c in split_by_el]) + r'|\s+'
        else:
            split = r'\s+'


        self.split=re.compile(split)
        self.content=content
        self.rootNode=Node()
        self.logCluL: list[LogCluster]=[]
        self.log_cluster_size = log_cluster_size


    def hasNumbers(self, s):
        return any(char.isdigit() for char in s)

    def treeSearch(self, rn, seq):
        retLogClust = None

        seqLen = len(seq)
        if seqLen not in rn.childD:
            return retLogClust

        parentn = rn.childD[seqLen]

        currentDepth = 1
        for token in seq:
            if currentDepth >= self.depth or currentDepth >= seqLen:
                break

            if token in parentn.childD:
                parentn = parentn.childD[token]
            elif "<*>" in parentn.childD:
                parentn = parentn.childD["<*>"]
            else:
                return retLogClust
            currentDepth += 1

        logClustL = parentn.childD

        retLogClust = self.fastMatch(logClustL, seq)

        return retLogClust

    def addSeqToPrefixTree(self, rn, logClust):
        seqLen = len(logClust.logTemplate)
        if seqLen not in rn.childD:
            firtLayerNode = Node(depth=1, digitOrtoken=seqLen)
            rn.childD[seqLen] = firtLayerNode
        else:
            firtLayerNode = rn.childD[seqLen]

        parentn = firtLayerNode

        currentDepth = 1
        for token in logClust.logTemplate:
            # Add current log cluster to the leaf node
            if currentDepth >= self.depth or currentDepth >= seqLen:
                if len(parentn.childD) == 0:
                    parentn.childD = [logClust]
                else:
                    parentn.childD.append(logClust)
                break

            # If token not matched in this layer of existing tree.
            if token not in parentn.childD:
                if not self.hasNumbers(token):
                    if "<*>" in parentn.childD:
                        if len(parentn.childD) < self.maxChild:
                            newNode = Node(depth=currentDepth + 1, digitOrtoken=token)
                            parentn.childD[token] = newNode
                            parentn = newNode
                        else:
                            parentn = parentn.childD["<*>"]
                    else:
                        if len(parentn.childD) + 1 < self.maxChild:
                            newNode = Node(depth=currentDepth + 1, digitOrtoken=token)
                            parentn.childD[token] = newNode
                            parentn = newNode
                        elif len(parentn.childD) + 1 == self.maxChild:
                            newNode = Node(depth=currentDepth + 1, digitOrtoken="<*>")
                            parentn.childD["<*>"] = newNode
                            parentn = newNode
                        else:
                            parentn = parentn.childD["<*>"]

                else:
                    if "<*>" not in parentn.childD:
                        newNode = Node(depth=currentDepth + 1, digitOrtoken="<*>")
                        parentn.childD["<*>"] = newNode
                        parentn = newNode
                    else:
                        parentn = parentn.childD["<*>"]

            # If the token is matched
            else:
                parentn = parentn.childD[token]

            currentDepth += 1

    # seq1 is template
    def seqDist(self, seq1, seq2):
        assert len(seq1) == len(seq2)
        simTokens = 0
        numOfPar = 0

        for token1, token2 in zip(seq1, seq2):
            if token1 == "<*>":
                numOfPar += 1
            elif token1 == token2:
                simTokens += 1

        # retVal = simTokens + numOfPar
        retVal = simTokens
        retVal = retVal/len(seq1) # сравниваем с порогом
        # simTokens вторым даст хуже качество
        # зачем  заменять на плейсхолдер где и и так мало. их класс разрастется
        # если есть уже "сломанный" который содержит в себе несколько

        # проверить retVal, simTokens
        return retVal, numOfPar
        # return retVal, simTokens

    # стратегию добавить чтобы сравнивать по статическим токенам то
    # есть без учета плейсхолдеров
    def fastMatch(self, logClustL, seq):
        retLogClust = None

        maxSim = -1
        maxNumOfParams = -1
        maxClust = None

        for logClust in logClustL:
            curSim, curNumOfParams = self.seqDist(logClust.logTemplate, seq)
            if curSim > maxSim or (curSim == maxSim and curNumOfParams > maxNumOfParams):
                maxSim = curSim
                maxNumOfParams = curNumOfParams
                maxClust = logClust

        # если eval режим и есть общий префикс так еще и длина совпала
        # то берём даже с мин-ым совпадением если есть хотя бы один не <*>

        # если только <*> то это скорее всего точно другой шаблон
        if maxSim >= self.st:
            retLogClust = maxClust

        return retLogClust

    #seq2 template
    def updateTemplate(self, seq1, seq2):
        assert len(seq1) == len(seq2)

        for i in range(len(seq2)):
            if seq1[i] != seq2[i]:
                seq2[i] = "<*>"

    def printTree(self, node=None, dep=0):
        raise NotImplementedError
    
    @dataclasses.dataclass()
    class Parsed:
        ind: Optional[int] = None
        is_new: bool = False
        params_list: list[str] = dataclasses.field(default_factory=list)

    def __call__(self, log_msg: str, is_raw_log: bool=True,
                 take_into_account: bool=True,
                 return_params_list: bool=False) -> Parsed:

        if not isinstance(log_msg, str):
            raise ValueError


        tokens = self.preprocess_and_get_tokens(log_msg, is_raw_log)

        if not tokens:
            # будет деление на ноль в seqDist
            # логично выйти
            return self.Parsed(None)

        matchCluster: Optional[LogCluster] = self.treeSearch(self.rootNode, tokens)

        # Match no existing log cluster
        is_new = False
        if matchCluster is None:
            newCluster = LogCluster(logTemplate=tokens, index=len(self.logCluL),
                                    max_container_size=self.log_cluster_size)  # logID
            newCluster.add(log_msg)
            self.logCluL.append(newCluster)
            self.addSeqToPrefixTree(self.rootNode, newCluster)
            matchCluster = newCluster
            is_new=True

        # Add the new log message to the existing cluster
        # из-за того что в eval режиме идет поиск вообще по любому порогу
        # где есть хотя бы один общий статичный токен то не обновляем шаблон
        # поскольку он практически всё заменит на <*>
        elif matchCluster is not None and take_into_account:
            self.updateTemplate(tokens, matchCluster.logTemplate)
            matchCluster.add(log_msg) # вместо токенов. лучше видеть параметры

            # matchCluster.logIDL.append(logID)
            # if " ".join(newTemplate) != " ".join(matchCluster.logTemplate):
            # if newTemplate != matchCluster.logTemplate:
            #     matchCluster.logTemplate = newTemplate

        params_list=[]
        if return_params_list:
            for tok, tok_templ in zip(tokens, matchCluster.logTemplate):
                if tok_templ == "<*>":
                    # даже для нового кластера найдутся парметры из за сраббатывания регулярок.
                    # но вот дрейн считает любой токен содержащий цифру * а я нет.
                    # todo: решить неоднозначность
                    # todo: парамтеры после прменения регулярок не извлекюатся. только <*>
                    params_list.append(tok)

        return self.Parsed(matchCluster.index, is_new, params_list)

    def check_preprocessing(self, raw_log_msg: Union[str, list[str]]) -> list[list[str]]:
        batch_log_msgs = None
        if isinstance(raw_log_msg, str):
            batch_log_msgs = [raw_log_msg]
        elif isinstance(raw_log_msg, Collection):
            batch_log_msgs = raw_log_msg
        if batch_log_msgs is None: raise ValueError('apply str or Collection(iter,len,in) of str')

        return [self.preprocess_and_get_tokens(log, True) for log in batch_log_msgs]

    def split_raw_log_into_columns(self, raw_log) -> list[str]:
        raw_log = raw_log.strip()
        # if do_lower:
        #     raw_log = raw_log.lower()
        # log format больше не приводится к нижнему   регистру
        m = self.regex.match(raw_log)
        if not m or not raw_log:
            return []
        return [m[h] for h in self.headers if h != self.content] + [m[self.content]]

    def preprocess_and_get_tokens(self, line:str, is_raw_log=True)-> list[str]:
        line=line.lower().rstrip()

        if is_raw_log:

            m = self.regex.match(line)
            if not m or not line:
                return []

            line = m[self.content]

        for currentRex in self.rex:
            line = re.sub(currentRex, "<*>", line)

        tokens = self.split.split(line)
        tokens = [t for t in tokens if t]
        return tokens

    def generate_dataframe(self, filepath: str, readline_num:Optional[float]=None) -> pd.DataFrame:

        df: list[list] = []
        columns = [h for h in self.headers if h != self.content] + [self.content]
        columns += ['ParameterList', 'Template', 'EventId']
        pbar = tqdm.tqdm(total=None if readline_num is None else int(readline_num))
        if readline_num is None: readline_num = math.inf
        m_cnt=0

        with open(filepath, 'r', encoding='latin-1') as file:
            for i, line in enumerate(file):
                if i >= readline_num: break

                t=self.split_raw_log_into_columns(line)
                if not t:
                    df.append([""]*len(self.headers) + [[], "", math.nan])
                    pbar.set_postfix(not_matched_count=i + 1 - m_cnt)
                    continue

                cnt=t[-1]
                r = self.__call__(cnt, is_raw_log=False, return_params_list=True) # log content
                if r.ind is None:
                    df.append( t + [r.params_list, "", math.nan])
                    pbar.set_postfix(not_matched_count=i + 1 - m_cnt)
                else:
                    m_cnt += 1
                    df.append( t + [r.params_list, self.logCluL[r.ind].logTemplate, r.ind])
                pbar.update(1)

        return pd.DataFrame(df, columns=columns)

    @staticmethod
    def generate_logformat_regex(logformat, is_log_format_escaped):
        """Function to generate regular expression to split log messages"""
        headers = []
        splitters = re.split(r"(<[^<>]+>)", logformat)
        regex = ""
        for k in range(len(splitters)):
            if k % 2 == 0:
                if  not is_log_format_escaped:
                    splitter = re.escape(splitters[k])
                    splitter = re.sub(r"(:?\\ +)+", r"\\s+", splitter)
                else:
                    splitter = re.sub(r" +", r"\\s+", splitters[k])

                regex += splitter
            else:
                header = splitters[k].strip("<").strip(">")
                regex += "(?P<%s>.*?)" % header
                headers.append(header)
        regex = re.compile("^" + regex + "$")
        return headers, regex


    @classmethod
    def load(cls, path_to_file:str) -> "LogParser":
        with open(path_to_file, 'rb') as file:
            parser: LogParser = pickle.load(file)

        assert len(parser.logCluL) > 0, "empty LogParser create through __init__ call"
        print('loaded parser with params:')
        for attr in dir(parser):
            if attr.startswith('__'): continue
            print('-', attr, getattr(parser, attr))
        return parser


    def save(self, path_to_file:str):
        with open(path_to_file, 'wb') as file:
            pickle.dump(self, file)

