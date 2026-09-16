from my_drain import LogParser
from benchmark_settings import *
import os
import regex as re
import evaluator
import datetime, time
import pandas as pd

from drain3.template_miner import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from drain3.masking import MaskingInstruction
from drain3.file_persistence import FilePersistence


benchmark_result = []

USE_BENCH_WITHOUT_ESCAPING_IN_LOG_FORMAT = False
MY_DRAIN = False
DATA_DIR = 'my-drain' if MY_DRAIN else 'Drain3'
DEPTH=5
MAX_CHILD=50
SIM_TR=0.5
if USE_BENCH_WITHOUT_ESCAPING_IN_LOG_FORMAT:
    benchmark_settings = benchmark_settings_without_escaping_in_log_format
# file_persistence = FilePersistence('tmp.drain')
file_persistence = None

start_time = datetime.datetime.utcnow()
for dataset, setting in benchmark_settings.items():
    print("\n=== Evaluation on %s ===" % dataset)

    log_file = os.path.join('../loghub/', setting['log_file'])
    ###############################################################################################

    DEPTH = setting['depth']
    SIM_TR = setting['st']
    re_dict = {
        'ip_port': re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,5}'),
        'ipv4': re.compile(r'::ffff:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'),
        'ip': re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'),
        'mac': re.compile(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}'),
        'user': re.compile(r'#\d+#'),
        'named_pid': re.compile(r'[0-9a-z_.()]+\[\d+]'),
        # 'hex_num': re.compile(r'0x[0-9a-f]{8}'),
        # 'hex_num2':re.compile(r'0x[0-9a-f]{2}'),
        # '8byte': re.compile(r'[0-9a-f]{8}'),
        # 'float': re.compile(r'\d+\.\d+'),
        # 'num': re.compile(r'\d+'),
    }
    # re_dict = {}
    re_dict.update({f"restr{i}":re.compile(restr) for i, restr in enumerate(setting['regex'])})


    # shared_rex = list(re_dict.values())
    shared_split_els = ['(', ')', '[', ']', '.', '_', ',', '/', '-', '=', ':']
    # shared_split_els = []
    #############################################################################################

    param_str = "*"
    masking_instr = [MaskingInstruction(re_dict[pat].pattern, param_str) for pat in re_dict]
    config = TemplateMinerConfig(
        log_format=setting['log_format'],
        profiling_enabled=True,
        drain_extra_delimiters=shared_split_els,
        drain_sim_th=SIM_TR,
        drain_depth=DEPTH,
        drain_max_children=MAX_CHILD,
        drain_max_clusters=100_000,
        masking_instructions=masking_instr,
        parameter_extraction_cache_capacity=100_000,
        is_log_format_have_not_escaped_chars=USE_BENCH_WITHOUT_ESCAPING_IN_LOG_FORMAT, # False on benchmark
        snapshot_interval_minutes=30,
        profiling_report_sec=5*60,
        snapshot_compress_state=False,
        use_fast_content_definition=True,
        trigger_save_after_seen_log_count=10_000,

    )

    parser_drain3 = TemplateMiner(persistence_handler=file_persistence, config=config)

    parser = LogParser(log_format=setting['log_format'],
                       depth=DEPTH,
                       st=SIM_TR,
                       maxChild=MAX_CHILD,
                       rex=list(re_dict.values()),
                       split_by_el=shared_split_els,
                       content='Content',
                       is_log_format_escaped=USE_BENCH_WITHOUT_ESCAPING_IN_LOG_FORMAT,
                       log_cluster_size=100)

    if not  MY_DRAIN: parser = parser_drain3
    start_new_time = datetime.datetime.utcnow()

    df = parser.generate_dataframe(log_file)
    end_new_time = datetime.datetime.utcnow() - start_new_time

    non_matched = df['EventId'].isna().sum()
    df['EventId'].mask(df['EventId'].isna(), -1, inplace=True)
    df.to_csv(log_file + 'drain_templates.csv', sep=',', index=False)

    F1_measure, accuracy = evaluator.evaluate(
        groundtruth=os.path.join(log_file + "_structured.csv"),
        df_parsedlog=df
    )
    benchmark_result.append([dataset, F1_measure, accuracy, non_matched, len(df['EventId']),
                             df['EventId'].nunique(), end_new_time.total_seconds()])


    if not MY_DRAIN:
        print("Prefix Tree:")
        # parser.drain.print_tree()

        parser.profiler.report(0)

        # inference
        # cluster = template_miner.match(log_line)
        # if cluster is None:
        #     ...
        # else:
        #     template = cluster.get_template()
        #     cluster.cluster_id
        #     template_miner.get_parameter_list(template, log_line)


print("\n=== Overall evaluation results ===")
duration = datetime.datetime.fromtimestamp(time.time()) - start_time
benchmark_result.append(['TotalTime'] + [pd.NA]*5 + [(datetime.datetime.utcnow() - start_time).total_seconds()])
df_result = pd.DataFrame(benchmark_result, columns=["Dataset", "F1_measure", "Accuracy", "NotMatched",
                                                   "Len", "NumTemplates", "TimeSec"])
df_result.set_index("Dataset", inplace=True)
print(df_result)
filepath=os.path.join(DATA_DIR, "Drain_benchmark_result%s.csv")
num = 0
while True:
    s = str(num) if num > 0 else ""
    if os.path.exists(filepath % s):
        num += 1
        continue
    filepath = filepath % s
    break

df_result.to_csv(filepath, float_format="%.8f")
print('saved as ', filepath)
