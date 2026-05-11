from collections import defaultdict, OrderedDict
from pprint import pprint
file_path = "/Users/valentin.lapparov/Downloads/Affluences_ISSUES_KPI_GROUPED_30days.log"
days = {'Mon', 'Fri', 'Sat', 'Wed', 'Tue', 'Thu', 'Sun'}
search_metric = Input()
with open(file_path, "r") as f:
    lines = f.readlines()
    fitered_days = filter(lambda x: not any(day in x for day in days), lines)
    fitered_data = filter(lambda x: not x.strip().startswith("-") or "network"
                                    in x,
                          fitered_days)
    # print(list(fitered_data))
    # print("".join(fitered_data))
    d = defaultdict(int)
    current_key = "None"
    for doc in fitered_data:
        if not doc.strip().startswith("-"):
            current_key = doc.replace("\n", "").replace(":", "")
            d[current_key] = 0
        else:
            d[current_key] += int(doc.split("=> ")[-1].replace("\n", ""))
    pprint(list(OrderedDict(sorted(d.items(), key=lambda item: item[1],
                              reverse=True)).items())[:10])
    # print(sorted(d.items(), key=lambda item: item[1], reverse=True))