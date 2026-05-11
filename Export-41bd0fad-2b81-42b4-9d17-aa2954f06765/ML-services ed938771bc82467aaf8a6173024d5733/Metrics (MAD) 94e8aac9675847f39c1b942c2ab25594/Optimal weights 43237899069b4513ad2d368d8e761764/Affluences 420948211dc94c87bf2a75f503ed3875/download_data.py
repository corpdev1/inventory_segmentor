import boto3
from datetime import datetime, timedelta
import os
from itertools import chain
currentDate = datetime.now().strftime('%d/%m/%Y')

S3_BUCKET= "packetai.ingest.affluences"
data_root = "/Users/valentin.lapparov/Desktop/work/optimal_weights/test"
if not os.path.exists(data_root):
    os.mkdir(data_root)

aws_credentials = {
    "aws_access_key_id": 'AKIA3FMT26JDIULRKUF2',
    "aws_secret_access_key":  '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',
}

s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_credentials["aws_access_key_id"],
        aws_secret_access_key=aws_credentials["aws_secret_access_key"],
    )

S3_MODEL_DIR_temp = "mad_metrics_output/6040a96cdcc614001153fc55-docker/"
paginator = s3.get_paginator('list_objects_v2')
pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_MODEL_DIR_temp)

selected_components = {
# 'nodescrapers_scrapers',
#  'nodehyperion-server_hyperion-server',
 'nodeportal_portal', 
 # 'rubylogs_fluentd',
 # 'nodeapp_app-web',
 # 'pythonhyperion-client-plages_hyperion',
 # 'pythonkoios_koios-worker',
 # 'nodereservation_reservation',
 # 'pythondynamic-flow_scheduler',
 # 'pythonkoios_koios-tasks'
 }

dates_dict = {}
sources = [obj['Key'] for obj in chain(*[page['Contents'] for page in pages])]
for doc in [("/".join(s.split("/")[:-1]), int(s.split("/")[-1])) for s in sources]:
    dates_dict[doc[0]] = max(dates_dict.get(doc[0], 0), doc[1])
# print(dates_dict)

cnt = 0
pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_MODEL_DIR_temp)
for page in pages:
    for obj in page['Contents']:
        cnt += 1
        S3_MODEL_DIR = obj['Key']
        if any(component in S3_MODEL_DIR for component in selected_components):
            d = datetime.fromtimestamp(dates_dict.get("/".join(S3_MODEL_DIR.split("/")[:-1]), 0))  - timedelta(days=14)
            file = S3_MODEL_DIR.split('/')[-1]
            folder = S3_MODEL_DIR.split('/')[-2]
            if not os.path.exists(os.path.join(data_root, folder)):
                os.mkdir(os.path.join(data_root, folder))
            current_datetime = datetime.fromtimestamp(int(obj['Key'].split('/')[-1]))
            if current_datetime >= d:
                s3.download_file(S3_BUCKET, S3_MODEL_DIR, os.path.join(data_root, '{}/{}.txt'.format(folder,file)))
                print("Downloaded ", S3_MODEL_DIR)

