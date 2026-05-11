import glob
import json
import tqdm
import zipfile

from DictionarySetUp import dictionaryBuilderPacket, getNGramOccurrences 
from MatchToken import tokenMatch
from masking import LogMasker, MaskingInstruction

def unzip_file(path):
    archive = zipfile.ZipFile(path, 'r')
    result = []
    for fileset in archive.filelist:
        data = archive.read(fileset)
        lines = data.decode().splitlines()
        data = [json.loads(line) for line in lines]
        result.extend(data)
        data = None
    return result


masking_instances = [
MaskingInstruction(r'((?<=[^A-Za-z0-9])|^)(([0-9a-f]{2,}:){3,}([0-9a-f]{2,}))((?=[^A-Za-z0-9])|$)', "ID"),
MaskingInstruction(r'((?<=[^A-Za-z0-9])|^)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})((?=[^A-Za-z0-9])|$)', "IP"),
MaskingInstruction(r'((?<=[^A-Za-z0-9])|^)([0-9a-f]{6,} ?){3,}((?=[^A-Za-z0-9])|$)', "SEQ"),
MaskingInstruction(r'((?<=[^A-Za-z0-9])|^)([0-9A-F]{4} ?){4,}((?=[^A-Za-z0-9])|$)', "SEQ"),
MaskingInstruction(r'((?<=[^A-Za-z0-9])|^)(\d{1,3}\.\d{1,5}\.\d{1,5})((?=[^A-Za-z0-9])|$)', "PID"),
MaskingInstruction(r'((?<=[^A-Za-z0-9])|^)(0x[a-f0-9A-F]+)((?=[^A-Za-z0-9])|$)', "HEX"),
MaskingInstruction(r'((?<=[^A-Za-z0-9])|^)([\-\+]?\d+)((?=[^A-Za-z0-9])|$)', "NUM"),
MaskingInstruction(r'(?<=executed cmd )(".+?")', "CMD"),
MaskingInstruction(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', "MAC"),
    MaskingInstruction(r'(([A-Za-z0-9._%+-])?(\s*)@?(\s*)([A-Za-z0-9.-]+\.[A-Z|a-z]{2,}))', "EMAIL"),
MaskingInstruction(r'(((http|https)\:\/\/)?[a-zA-Z0-9\.\/\?\:@\-_=#]+\.([a-zA-Z]){2,6}([a-zA-Z0-9\.\&\/\?\:@\-_=#])*)', "HTTP"),
                   ]  

path = '/home/hari/data/affluences_s3/stashed_hourly/log/6040a96cdcc614001153fc55-docker/rabbitmqqueue_rabbitmq/2021/09/'

days_list = ['01', '02', '03', '04', '05']  # , '06', '07']

files = []

for cur_day in days_list:
    cur_files = glob.glob(path + cur_day + '/' + '/**/**/**.zip', recursive=True)

    print(f"Number of files {len(cur_files)}")

    files.extend(cur_files)

data = []
for file in tqdm.tqdm(files):
    data.extend(unzip_file(file))

log = []
error = []
for value in data:
    try:
        log.append((value["timestamp_unix"], value["content"]))
    except KeyError:
        error.append(value)
log = sorted(log, key=lambda x: float(x[0]))
timestamp,logs = zip(*log)

lm = LogMasker(masking_instances)

mask_logs = [lm.mask(log) for log in logs]

pairDictionaryList, triDictionaryList, allTokenList = dictionaryBuilderPacket(logs)

pairThresh = getNGramOccurrences(pairDictionaryList, 2)
triThresh = getNGramOccurrences(triDictionaryList, 3)

tokenMatch(allTokenList, pairDictionaryList, triDictionaryList, pairThresh, triThresh, '')
