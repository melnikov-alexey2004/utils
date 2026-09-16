# SPDX-License-Identifier: MIT

import ast
import configparser
import json
import logging
from typing import Collection, Optional, Callable, Protocol
from dataclasses import dataclass, field
from drain3.masking import AbstractMaskingInstruction, MaskingInstruction
from my_drain import LogParser
import warnings
import regex as re


logger = logging.getLogger(__name__)


class ExtractContentFuncT(Protocol):
    def __call__(self, line: str, is_raw_log: bool=True) -> str:
        pass


class TemplateMinerConfig:
    log_format: str = "" # section_logformat
    use_fast_content_definition: bool = True # section_logformat
    use_custom_content_extractor: ExtractContentFuncT = None
    use_custom_raw_log_spliter: Callable[[str,], list[str]] = None
    engine: str = "Drain"
    profiling_enabled: bool = False
    profiling_report_sec: int = 60
    snapshot_interval_minutes: int = 5
    snapshot_compress_state: bool = True
    drain_extra_delimiters: Collection[str] = []
    drain_sim_th: float = 0.4
    drain_depth: int = 4
    drain_max_children: int = 100
    drain_max_clusters: Optional[int] = None
    masking_instructions: Collection[AbstractMaskingInstruction] = []
    mask_prefix: str = "<"
    mask_suffix: str = ">"
    parameter_extraction_cache_capacity: int = 3000
    parametrize_numeric_tokens: bool = True
    content: str = 'Content' #
    is_log_format_escaped: bool = False  # section_logformat. True on benchmark
    is_split_seqs_escaped: bool = False # section_logformat #todo: бесполезный если не сдлеаю re.split

    def __init__(self, log_format: str="", drain_extra_delimiters: Collection[str]=None,
                 masking_instructions: Collection[AbstractMaskingInstruction]=None,
                 use_fast_content_definition: bool = True,
                 use_custom_content_extractor: ExtractContentFuncT = None,
                 use_custom_raw_log_spliter: Callable[[str, ], list[str]] = None,
                 engine: str = "Drain", profiling_enabled = False, profiling_report_sec = 60,
                 snapshot_interval_minutes = 5, snapshot_compress_state = True,
                 drain_sim_th = 0.4, drain_depth = 4, drain_max_children = 100,
                 drain_max_clusters: Optional[int] = None, mask_prefix = "<", mask_suffix = ">",
                 parameter_extraction_cache_capacity=3000, parametrize_numeric_tokens = True,
                 content: str = 'Content',
                 is_log_format_escaped = False, is_split_seqs_escaped: bool = False
                 ):
        self.log_format = log_format
        self.use_fast_content_definition = use_fast_content_definition
        self.engine = engine
        self.profiling_enabled = profiling_enabled
        self.profiling_report_sec = profiling_report_sec
        self.snapshot_interval_minutes = snapshot_interval_minutes
        self.snapshot_compress_state = snapshot_compress_state
        if drain_extra_delimiters is None:
            drain_extra_delimiters = []

        for el in drain_extra_delimiters:
            if not isinstance(el, str):
                warnings.warn(f"exist at least elem that {type(el)}"
                              f" is not str in config.drain_extra_delimiters, it will cast to str")
                break

        drain_extra_delimiters = [el.pattern if isinstance(el, re.Pattern) else str(el) for el in drain_extra_delimiters]

        self.drain_extra_delimiters: Collection[str] = drain_extra_delimiters

        self.drain_sim_th = drain_sim_th
        self.drain_depth = drain_depth
        self.drain_max_children = drain_max_children
        self.drain_max_clusters = drain_max_clusters
        if masking_instructions is None: masking_instructions = []
        self.masking_instructions = masking_instructions
        self.mask_prefix = mask_prefix
        self.mask_suffix = mask_suffix
        self.parameter_extraction_cache_capacity = parameter_extraction_cache_capacity
        self.parametrize_numeric_tokens = parametrize_numeric_tokens
        self.content = content
        self.is_log_format_escaped = is_log_format_escaped
        self.is_split_seqs_escaped = is_split_seqs_escaped
        self.use_custom_content_extractor = use_custom_content_extractor
        self.use_custom_raw_log_spliter = use_custom_raw_log_spliter
        assert not self.log_format or f'<{content}>' in self.log_format, 'change content parameter'
        if not self.log_format:
            warnings.warn('empty log format')
        if self.log_format != "":
            headers, regex = LogParser.generate_logformat_regex(self.log_format, self.is_log_format_escaped)
            self.headers = headers
            self.regex = regex
        if self.use_fast_content_definition:
            assert self.headers.index(self.content) == len(self.headers) - 1

    def load(self, config_filename: str) -> None:
        parser = configparser.ConfigParser()
        read_files = parser.read(config_filename)
        if len(read_files) == 0:
            logger.warning(f"config file not found: {config_filename}")

        section_profiling = 'PROFILING'
        section_snapshot = 'SNAPSHOT'
        section_drain = 'DRAIN'
        section_masking = 'MASKING'
        section_logformat = 'LOGFORMAT'

        self.log_format = parser.get(section_logformat, 'logformat', fallback=self.log_format)
        self.use_fast_content_definition = parser.getboolean(section_logformat, 'use_fast_content_definition',
                                            fallback=self.use_fast_content_definition)
        self.content = parser.get(section_logformat, 'content', fallback=self.content)
        self.is_log_format_escaped = parser.getboolean(section_logformat, 'is_log_format_escaped',
                                                       fallback=self.is_log_format_escaped)
        if self.use_custom_raw_log_spliter is None:
            warnings.warn('load dont set up use_custom_raw_log_spliter because globals() store variables'
                          'from current file only and dont have access to namespace from ypur file')
        if self.use_custom_content_extractor is None:
            warnings.warn('you can use .use_custom_content_extractor = some_func() now or  re-instanciate this'
                          'and pass to constructor use_custom_raw_log_spliter and/or use_custom_content_extractor')

        self.engine = parser.get(section_drain, 'engine', fallback=self.engine)

        self.profiling_enabled = parser.getboolean(section_profiling, 'enabled',
                                                   fallback=self.profiling_enabled)
        self.profiling_report_sec = parser.getint(section_profiling, 'report_sec',
                                                  fallback=self.profiling_report_sec)

        self.snapshot_interval_minutes = parser.getint(section_snapshot, 'snapshot_interval_minutes',
                                                       fallback=self.snapshot_interval_minutes)
        self.snapshot_compress_state = parser.getboolean(section_snapshot, 'compress_state',
                                                         fallback=self.snapshot_compress_state)

        drain_extra_delimiters_str = parser.get(section_drain, 'extra_delimiters',
                                                fallback=str(self.drain_extra_delimiters))
        self.drain_extra_delimiters = ast.literal_eval(drain_extra_delimiters_str)

        self.drain_sim_th = parser.getfloat(section_drain, 'sim_th',
                                            fallback=self.drain_sim_th)
        self.drain_depth = parser.getint(section_drain, 'depth',
                                         fallback=self.drain_depth)
        self.drain_max_children = parser.getint(section_drain, 'max_children',
                                                fallback=self.drain_max_children)
        self.drain_max_clusters = parser.getint(section_drain, 'max_clusters',
                                                fallback=self.drain_max_clusters)
        self.parametrize_numeric_tokens = parser.getboolean(section_drain, 'parametrize_numeric_tokens',
                                                            fallback=self.parametrize_numeric_tokens)

        masking_instructions_str = parser.get(section_masking, 'masking',
                                              fallback=str(self.masking_instructions))
        self.mask_prefix = parser.get(section_masking, 'mask_prefix', fallback=self.mask_prefix)
        self.mask_suffix = parser.get(section_masking, 'mask_suffix', fallback=self.mask_suffix)
        self.parameter_extraction_cache_capacity = parser.getint(section_masking, 'parameter_extraction_cache_capacity',
                                                                 fallback=self.parameter_extraction_cache_capacity)

        masking_instructions = []
        masking_list = json.loads(masking_instructions_str)
        for mi in masking_list:
            instruction = MaskingInstruction(mi['regex_pattern'], mi['mask_with'])
            masking_instructions.append(instruction)
        self.masking_instructions = masking_instructions

        assert self.log_format != ""

        if hasattr(self, 'headers') or hasattr(self, 'regex'): raise AttributeError('in constructor log_formast set ""')
        headers, regex = LogParser.generate_logformat_regex(self.log_format, self.is_log_format_escaped)
        self.headers = headers
        self.regex = regex

        if self.use_fast_content_definition:
            assert self.headers.index(self.content) == len(self.headers) - 1