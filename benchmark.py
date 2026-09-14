from drain import LogParser
from benchmark_settings import benchmark_settings
import os
import regex as re
import evaluator
import pandas as pd


benchmark_result = []

re_dict = {
    'ip_port': re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,5}'),
    'ipv4': re.compile(r'::ffff:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'),
    'ip': re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'),
    'mac': re.compile(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}'),
    'user':re.compile(r'#\d+#'),
    'named_pid': re.compile(r'[0-9a-z_.()]+\[\d+]'),
    'hex_num': re.compile(r'0x[0-9a-f]{8}'),
    'hex_num2':re.compile(r'0x[0-9a-f]{2}'),
    '8byte': re.compile(r'[0-9a-f]{8}'),
    'float': re.compile(r'\d+\.\d+'),
    'num': re.compile(r'\d+'),
}


shared_rex = list(re_dict.values())
shared_split_els = ['(',')','[',']','.','_',',','/','-', '=', ':']
for dataset, setting in benchmark_settings.items():
    print("\n=== Evaluation on %s ===" % dataset)

    log_file = os.path.join('loghub/', setting['log_file'])
    parser = LogParser(log_format=setting['log_format'],
                       # depth=setting['depth'],
                       depth=5,
                       # st=setting['st'],
                       st=0.5,
                       maxChild=100,
                       rex=setting['regex'] + shared_rex,
                       # rex=setting['regex'],
                       split_by_el=shared_split_els,
                       # split_by_el=[],
                       content='Content',
                       is_log_format_escaped=True,
                       log_cluster_size=100)


    df = parser.generate_dataframe(log_file)
    non_matched = df['EventId'].isna().sum()
    df['EventId'].mask(df['EventId'].isna(), -1, inplace=True)
    df.to_csv(log_file + 'drain_templates.csv', sep=',', index=False)

    F1_measure, accuracy = evaluator.evaluate(
        groundtruth=os.path.join(log_file + "_structured.csv"),
        df_parsedlog=df
    )
    benchmark_result.append([dataset, F1_measure, accuracy, non_matched, len(df['EventId']),
                             df['EventId'].nunique()])


print("\n=== Overall evaluation results ===")
df_result = pd.DataFrame(benchmark_result, columns=["Dataset", "F1_measure", "Accuracy", "NotMatched",
                                                   "Len", "NumTemplates"])
df_result.set_index("Dataset", inplace=True)
print(df_result)
filepath="Drain_bechmark_result%s.csv"
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
