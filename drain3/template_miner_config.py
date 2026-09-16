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
    def __init__(self, log_format: str="", drain_extra_delimiters: Collection[str]=None,
                 masking_instructions: Collection[AbstractMaskingInstruction]=None,
                 use_fast_content_definition: bool = True,
                 trigger_save_after_seen_log_count: int = 10_000,
                 use_custom_content_extractor: ExtractContentFuncT = None,
                 use_custom_raw_log_spliter: Callable[[str, ], list[str]] = None,
                 engine: str = "Drain", profiling_enabled = False, profiling_report_sec = 10*60,
                 snapshot_interval_minutes = 5, snapshot_compress_state: bool = True,
                 drain_sim_th: float = 0.5, drain_depth: float = 5, drain_max_children: int = 100,
                 drain_max_clusters: Optional[int] = None, mask_prefix: str = "<", mask_suffix: str = ">",
                 parameter_extraction_cache_capacity: int=3000, parametrize_numeric_tokens: bool = True,
                 content: str = 'Content',
                 is_log_format_have_not_escaped_chars = False
                 ):
        self.log_format = log_format
        self.use_fast_content_definition = use_fast_content_definition
        self.trigger_save_after_seen_log_count = trigger_save_after_seen_log_count
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
        self.is_log_format_escaped = is_log_format_have_not_escaped_chars
        self.use_custom_content_extractor = use_custom_content_extractor
        self.use_custom_raw_log_spliter = use_custom_raw_log_spliter
        assert f'<{content}>' in self.log_format, 'change content parameter'
        if not self.log_format:
            warnings.warn('empty log format')
        if self.log_format != "":
            headers, regex = LogParser.generate_logformat_regex(self.log_format, self.is_log_format_escaped)
            self.headers = headers
            self.regex = regex
        if self.use_fast_content_definition:
            assert self.headers.index(self.content) == len(self.headers) - 1

