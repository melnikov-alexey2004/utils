# SPDX-License-Identifier: MIT

import base64
import logging
import re
import time
import zlib
from typing import Optional, Mapping, MutableMapping, NamedTuple, Sequence, Tuple, Union

import jsonpickle  # type: ignore[import]
from cachetools import LRUCache, cachedmethod

from drain3.drain import Drain, DrainBase, LogCluster
from drain3.masking import LogMasker
from drain3.persistence_handler import PersistenceHandler
from drain3.simple_profiler import SimpleProfiler, NullProfiler, Profiler
from drain3.template_miner_config import TemplateMinerConfig
from typing import TypedDict, Literal
import pandas as pd
import math
import tqdm.auto as tqdm


logger = logging.getLogger(__name__)

config_filename = 'drain3.ini'

ExtractedParameter = NamedTuple("ExtractedParameter", [("value", str), ("mask_name", str)])


class TemplateMiner:

    def __init__(self,
                 persistence_handler: Optional[PersistenceHandler] = None,
                 config: Optional[TemplateMinerConfig] = None,
                 ):
        """
        Wrapper for Drain with persistence and masking support
        :param persistence_handler: The type of persistence to use. When None, no persistence is applied.
        :param config: Configuration object. When none, configuration is loaded from default .ini file (if exist)
        """
        logger.info("Starting Drain3 template miner")

        if config is None:
            logger.info(f"Loading configuration from {config_filename}")
            config = TemplateMinerConfig()
            config.load(config_filename)

        self.config = config

        self.profiler: Profiler = NullProfiler()

        if self.config.profiling_enabled:
            self.profiler = SimpleProfiler()

        self.persistence_handler = persistence_handler

        param_str = f"{self.config.mask_prefix}*{self.config.mask_suffix}"

        # Follow the configuration in the configuration file to instantiate Drain
        # target_obj will be "Drain" if the engine argument is not specified.
        target_obj = self.config.engine
        if target_obj not in ["Drain", "JaccardDrain"]:
            raise ValueError(f"Invalid matched_pattern: {target_obj}, must be either 'Drain' or 'JaccardDrain'")

        self.drain: DrainBase = globals()[target_obj](
            sim_th=self.config.drain_sim_th,
            depth=self.config.drain_depth,
            max_children=self.config.drain_max_children,
            max_clusters=self.config.drain_max_clusters,
            extra_delimiters=self.config.drain_extra_delimiters,
            profiler=self.profiler,
            param_str=param_str,
            parametrize_numeric_tokens=self.config.parametrize_numeric_tokens
        )

        self.masker = LogMasker(self.config.masking_instructions, self.config.mask_prefix, self.config.mask_suffix)
        self.parameter_extraction_cache: MutableMapping[Tuple[str, bool], str] = \
            LRUCache(self.config.parameter_extraction_cache_capacity)
        self.last_save_time = time.time()

        if persistence_handler is not None:
            self.load_state()

        self.seen_log_count = 0
        self.log_templ_updated: bool = False

    def load_state(self) -> None:
        logger.info("Checking for saved state")

        assert self.persistence_handler is not None

        state = self.persistence_handler.load_state()
        if state is None:
            logger.info("Saved state not found")
            return

        if self.config.snapshot_compress_state:
            state = zlib.decompress(base64.b64decode(state))

        loaded_drain: Drain = jsonpickle.loads(state, keys=True)

        # json-pickle encoded keys as string by default, so we have to convert those back to int
        # this is only relevant for backwards compatibility when loading a snapshot of my-drain <= v0.9.1
        # which did not use json-pickle's keys=true
        if len(loaded_drain.id_to_cluster) > 0 and isinstance(next(iter(loaded_drain.id_to_cluster.keys())), str):
            loaded_drain.id_to_cluster = {int(k): v for k, v in list(loaded_drain.id_to_cluster.items())}
            if self.config.drain_max_clusters:
                cache: MutableMapping[int, Optional[LogCluster]] = LRUCache(maxsize=self.config.drain_max_clusters)
                cache.update(loaded_drain.id_to_cluster)
                loaded_drain.id_to_cluster = cache

        self.drain.id_to_cluster = loaded_drain.id_to_cluster
        self.drain.clusters_counter = loaded_drain.clusters_counter
        self.drain.root_node = loaded_drain.root_node

        logger.info(f"Restored {len(loaded_drain.clusters)} clusters "
                    f"built from {loaded_drain.get_total_cluster_size()} messages")

    def save_state(self, snapshot_reason: str) -> None:
        assert self.persistence_handler is not None

        state = jsonpickle.dumps(self.drain, keys=True).encode('utf-8')
        if self.config.snapshot_compress_state:
            state = base64.b64encode(zlib.compress(state))

        logger.info(f"Saving state of {len(self.drain.clusters)} clusters "
                    f"with {self.drain.get_total_cluster_size()} messages, {len(state)} bytes, "
                    f"reason: {snapshot_reason}")
        self.persistence_handler.save_state(state)

    class Parsed(TypedDict):
        change_type: Literal["cluster_created", "none", "cluster_template_changed", "not_matched"]
        cluster_id: int
        cluster_size: int
        template_mined: str
        cluster_count: int
        not_matched: bool
        log_content_length: int

    def get_log_content_from_raw(self, line: str, is_raw_log: bool=True) -> str:
        f = self.config.use_custom_content_extractor
        if f is not None and callable(f):
            return f(line, is_raw_log=is_raw_log)

        line = line.lower().rstrip()
        if is_raw_log:

            if self.config.use_fast_content_definition:
                splited = line.split()
                if len(splited) >= len(self.config.headers):
                    splited = splited[self.config.headers.index(self.config.content):]
                    line = " ".join(splited)
                else:
                    line = ""

            else:

                m = self.config.regex.match(line)
                if not m:
                    return ""

                line = m[self.config.content]

        return line.strip()

    def add_log_message(self, raw_log: str, is_raw_log: bool=True) -> Parsed:
        self.profiler.start_section("total")

        self.profiler.start_section("get-log-content")
        log_message = self.get_log_content_from_raw(raw_log, is_raw_log)
        log_content_length = len(log_message)
        self.profiler.end_section()

        self.profiler.start_section("mask")
        masked_content = self.masker.mask(log_message)
        self.profiler.end_section()

        self.profiler.start_section("my-drain")
        cluster, change_type = self.drain.add_log_message(masked_content)
        self.profiler.end_section("my-drain")

        result: TemplateMiner.Parsed = {
            "change_type": change_type if masked_content else "not_matched",
            "cluster_id": cluster.cluster_id,
            "cluster_size": cluster.size,
            "template_mined": cluster.get_template(),
            "cluster_count": len(self.drain.clusters),
            "not_matched": False if masked_content else True,
            "log_content_length": log_content_length,
        }
        if result["change_type"] not in ["none", "not_matched"]:
            self.log_templ_updated = True

        self.seen_log_count += (1 if masked_content else 0)

        if self.persistence_handler is not None:
            self.profiler.start_section("save_state")

            if self.log_templ_updated and self.seen_log_count >= self.config.trigger_save_after_seen_log_count:

                diff_time_sec = time.time() - self.last_save_time
                if diff_time_sec >= self.config.snapshot_interval_minutes * 60:

                    self.save_state(f"after {self.seen_log_count} matched log, timestamp = {time.time()}")
                    self.last_save_time = time.time()
                    self.seen_log_count = 0
                    self.log_templ_updated = False

            self.profiler.end_section()

        self.profiler.end_section("total")
        self.profiler.report(self.config.profiling_report_sec)
        return result

    def match(self, raw_log: str, full_search_strategy: str = "never", is_raw_log: bool=True) -> Optional[LogCluster]:
        """
        Mask log message and match against an already existing cluster.
        Match shall be perfect (sim_th=1.0).
        New cluster will not be created as a result of this call, nor any cluster modifications.

        :param log_message: log message to match
        :param full_search_strategy: when to perform full cluster search.
            (1) "never" is the fastest, will always perform a tree search [O(log(n)] but might produce
            false negatives (wrong mismatches) on some edge cases;
            (2) "fallback" will perform a linear search [O(n)] among all clusters with the same token count, but only in
            case tree search found no match.
            It should not have false negatives, however tree-search may find a non-optimal match with
            more wildcard parameters than necessary;
            (3) "always" is the slowest. It will select the best match among all known clusters, by always evaluating
            all clusters with the same token count, and selecting the cluster with perfect all token match and least
            count of wildcard matches.
        :return: Matched cluster or None if no match found.
        """
        if is_raw_log:
            log_message = self.get_log_content_from_raw(raw_log, is_raw_log)
        else:
            log_message = raw_log
        masked_content = self.masker.mask(log_message)
        matched_cluster = self.drain.match(masked_content, full_search_strategy)
        return matched_cluster

    def get_parameter_list(self, log_template: str, raw_log: str, is_raw_log: bool=True) -> Sequence[str]:
        """
        Extract parameters from a log message according to a provided template that was generated
        by calling `add_log_message()`.

        This function is deprecated. Please use extract_parameters instead.

        :param log_template: log template corresponding to the log message
        :param log_message: log message to extract parameters from
        :return: An ordered list of parameter values present in the log message.
        """
        if is_raw_log:
            log_message = self.get_log_content_from_raw(raw_log, is_raw_log)
        else:
            log_message = raw_log

        extracted_parameters = self.extract_parameters(log_template, log_message, is_raw_log=False, exact_matching=False)
        if not extracted_parameters:
            return []
        return [parameter.value for parameter in extracted_parameters]

    def extract_parameters(self,
                           log_template: str,
                           log_message: str,
                           is_raw_log: bool = True,
                           exact_matching: bool = True) -> Optional[Sequence[ExtractedParameter]]:
        """
        Extract parameters from a log message according to a provided template that was generated
        by calling `add_log_message()`.

        For most accurate results, it is recommended that
        - Each `MaskingInstruction` has a unique `mask_with` value,
        - No `MaskingInstruction` has a `mask_with` value of `*`,
        - The regex-patterns of `MaskingInstruction` do not use unnamed back-references;
          instead use back-references to named groups e.g. `(?P=some-name)`.

        :param log_template: log template corresponding to the log message
        :param log_message: log message to extract parameters from
        :param exact_matching: whether to apply the correct masking-patterns to match parameters, or try to approximate;
            disabling exact_matching may be faster but may lead to situations in which parameters
            are wrongly identified.
        :return: A ordered list of ExtractedParameter for the log message
            or None if log_message does not correspond to log_template.
        """

        if is_raw_log:
            log_message = self.get_log_content_from_raw(log_message, is_raw_log)

        # todo: а не быстрее ли re.split
        for delimiter in self.config.drain_extra_delimiters:
            log_message = log_message.replace(delimiter, " ")

        template_regex, param_group_name_to_mask_name = self._get_template_parameter_extraction_regex(
            log_template, exact_matching)

        # Parameters are represented by specific named groups inside template_regex.
        parameter_match = re.match(template_regex, log_message)

        # log template does not match template
        if not parameter_match:
            return None

        # create list of extracted parameters
        extracted_parameters = []
        for group_name, parameter in parameter_match.groupdict().items():
            if group_name in param_group_name_to_mask_name:
                mask_name = param_group_name_to_mask_name[group_name]
                extracted_parameter = ExtractedParameter(parameter, mask_name)
                extracted_parameters.append(extracted_parameter)

        return extracted_parameters

    @cachedmethod(lambda self: self.parameter_extraction_cache)
    def _get_template_parameter_extraction_regex(self,
                                                 log_template: str,
                                                 exact_matching: bool) -> Tuple[str, Mapping[str, str]]:
        param_group_name_to_mask_name = {}
        param_name_counter = [0]

        def get_next_param_name() -> str:
            param_group_name = f"p_{str(param_name_counter[0])}"
            param_name_counter[0] += 1
            return param_group_name

        # Create a named group with the respective patterns for the given mask-name.
        def create_capture_regex(_mask_name: str) -> str:
            allowed_patterns = []
            if exact_matching:
                # get all possible regex patterns from masking instructions that match this mask name
                masking_instructions = self.masker.instructions_by_mask_name(_mask_name)
                for mi in masking_instructions:
                    # MaskingInstruction may already contain named groups.
                    # We replace group names in those named groups, to avoid conflicts due to duplicate names.
                    if hasattr(mi, 'regex') and hasattr(mi, 'pattern'):
                        mi_groups = mi.regex.groupindex.keys()
                        pattern: str = mi.pattern
                    else:
                        # non regex masking instructions - support only non-exact matching
                        mi_groups = []
                        pattern = ".+?"

                    for group_name in mi_groups:
                        param_group_name = get_next_param_name()

                        def replace_captured_param_name(param_pattern: str) -> str:
                            _search_str = param_pattern.format(group_name)
                            _replace_str = param_pattern.format(param_group_name)
                            return pattern.replace(_search_str, _replace_str)

                        pattern = replace_captured_param_name("(?P={}")
                        pattern = replace_captured_param_name("(?P<{}>")

                    # support unnamed back-references in masks (simple cases only)
                    pattern = re.sub(r"\\(?!0)\d{1,2}", r"(?:.+?)", pattern)
                    allowed_patterns.append(pattern)

            if not exact_matching or _mask_name == "*":
                allowed_patterns.append(r".+?")

            # Give each capture group a unique name to avoid conflicts.
            param_group_name = get_next_param_name()
            param_group_name_to_mask_name[param_group_name] = _mask_name
            joined_patterns = "|".join(allowed_patterns)
            capture_regex = f"(?P<{param_group_name}>{joined_patterns})"
            return capture_regex

        # For every mask in the template, replace it with a named group of all
        # possible masking-patterns it could represent (in order).
        mask_names = set(self.masker.mask_names)

        # the Drain catch-all mask
        mask_names.add("*")

        escaped_prefix = re.escape(self.masker.mask_prefix)
        escaped_suffix = re.escape(self.masker.mask_suffix)
        template_regex = re.escape(log_template)

        # replace each mask name with a proper regex that captures it
        for mask_name in mask_names:
            search_str = escaped_prefix + re.escape(mask_name) + escaped_suffix
            while True:
                rep_str = create_capture_regex(mask_name)
                # Replace one-by-one to get a new param group name for each replacement.
                template_regex_new = template_regex.replace(search_str, rep_str, 1)
                # Break when all replaces for this mask are done.
                if template_regex_new == template_regex:
                    break
                template_regex = template_regex_new

        # match also messages with multiple spaces or other whitespace chars between tokens
        template_regex = re.sub(r"\\ ", r"\\s+", template_regex)
        template_regex = f"^{template_regex}$"
        return template_regex, param_group_name_to_mask_name

    def split_raw_log_into_columns(self, raw_log) -> list[str]:
        f = self.config.use_custom_raw_log_spliter
        if f is not None and callable(f):
            return f(raw_log)

        raw_log = raw_log.strip()
        # if do_lower:
        #     raw_log = raw_log.lower()
        # log format больше не приводится к нижнему   регистру
        if not self.config.use_fast_content_definition:
            m = self.config.regex.match(raw_log)
            if not m or not raw_log:
                return []
            return [m[h] for h in self.config.headers if h != self.config.content] + [m[self.config.content]]

        m = raw_log.split()
        if len(m) >= len(self.config.headers):
            cnt_ind = self.config.headers.index(self.config.content)
            return m[:cnt_ind] + [" ".join(m[cnt_ind:])]

        return []

    def generate_dataframe(self, filepath: str, readline_num:Optional[float]=None) -> pd.DataFrame:

        df: list[list] = []
        columns = [h for h in self.config.headers if h != self.config.content] + [self.config.content]
        columns += ['ParameterList', 'Template', 'EventId']
        pbar = tqdm.tqdm(total=None if readline_num is None else int(readline_num))
        if readline_num is None: readline_num = math.inf
        m_cnt=0

        with open(filepath, 'r', encoding='latin-1') as file:
            for i, line in enumerate(file):
                if i >= readline_num: break

                t = self.split_raw_log_into_columns(line)
                # t=self.add_log_message(line, is_raw_log=True)
                # if t["not_matched"]:
                if not t:
                    df.append([""]*len(self.config.headers) + [[], "", math.nan])
                    pbar.set_postfix(not_matched_count=i + 1 - m_cnt)
                    continue

                cnt=t[-1]
                r=self.add_log_message(cnt, is_raw_log=False)
                if r["not_matched"]:
                    df.append( t + [[], "", math.nan])
                    pbar.set_postfix(not_matched_count=i + 1 - m_cnt)
                else:
                    m_cnt += 1
                    params_list = self.get_parameter_list(r["template_mined"], cnt, is_raw_log=False)
                    df.append( t + [params_list, r["template_mined"].split(), r["cluster_id"]])
                pbar.update(1)

        return pd.DataFrame(df, columns=columns)
