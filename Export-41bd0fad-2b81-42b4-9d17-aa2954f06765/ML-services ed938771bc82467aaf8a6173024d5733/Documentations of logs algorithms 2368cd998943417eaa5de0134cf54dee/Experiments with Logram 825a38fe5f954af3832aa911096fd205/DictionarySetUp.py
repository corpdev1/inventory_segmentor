from Common import regexGenerator
from Common import tokenSpliter
from kneed import KneeLocator
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from statsmodels.nonparametric.smoothers_lowess import lowess

def dictionaryBuilder(log_format, logFile, rex):
    doubleDictionaryList = {'dictionary^DHT': -1};
    triDictionaryList = {'dictionary^DHT^triple': -1};
    allTokenList = []

    regex = regexGenerator(log_format)

    for line in open(logFile, 'r'):
        tokens = tokenSpliter(line, regex, rex)
        if(tokens == None):
            pass;
        else:
            allTokenList.append(tokens)
            for index in range(len(tokens)):
                if index >= len(tokens) - 2:
                    break;
                tripleTmp = tokens[index] + '^' + tokens[index + 1] + '^' + tokens[index + 2];
                if tripleTmp in triDictionaryList:
                    triDictionaryList[tripleTmp] = triDictionaryList[tripleTmp] + 1;
                else:
                    triDictionaryList[tripleTmp] = 1;
            for index in range(len(tokens)):
                if index == len(tokens)-1:
                    doubleTmp = tokens[index] + '^' + tokens[0]
                    if doubleTmp in doubleDictionaryList:
                        doubleDictionaryList[doubleTmp] = doubleDictionaryList[doubleTmp] + 1;
                    else:
                        doubleDictionaryList[doubleTmp] = 1;
                    break;
                doubleTmp = tokens[index] + '^' + tokens[index+1];
                if doubleTmp in doubleDictionaryList:
                    doubleDictionaryList[doubleTmp] = doubleDictionaryList[doubleTmp] + 1;
                else:
                    doubleDictionaryList[doubleTmp] = 1;
    return doubleDictionaryList, triDictionaryList, allTokenList

def dictionaryBuilderPacket(log_lines):
    doubleDictionaryList = {'dictionary^DHT': -1};
    triDictionaryList = {'dictionary^DHT^triple': -1};
    allTokenList = []

    for log_line in log_lines:
        tokens = log_line.split()
        if(tokens == None):
            pass;
        else:
            allTokenList.append(tokens)
            for index in range(len(tokens)):
                if index >= len(tokens) - 2:
                    break;
                tripleTmp = tokens[index] + '^' + tokens[index + 1] + '^' + tokens[index + 2];
                if tripleTmp in triDictionaryList:
                    triDictionaryList[tripleTmp] = triDictionaryList[tripleTmp] + 1;
                else:
                    triDictionaryList[tripleTmp] = 1;
            for index in range(len(tokens)):
                if index == len(tokens)-1:
                    doubleTmp = tokens[index] + '^' + tokens[0]
                    if doubleTmp in doubleDictionaryList:
                        doubleDictionaryList[doubleTmp] = doubleDictionaryList[doubleTmp] + 1;
                    else:
                        doubleDictionaryList[doubleTmp] = 1;
                    break;
                doubleTmp = tokens[index] + '^' + tokens[index+1];
                if doubleTmp in doubleDictionaryList:
                    doubleDictionaryList[doubleTmp] = doubleDictionaryList[doubleTmp] + 1;
                else:
                    doubleDictionaryList[doubleTmp] = 1;
    return doubleDictionaryList, triDictionaryList, allTokenList


def getNGramOccurrences(ip_dict, ngram_size):
    ngram_occur_dict = {}

    for ngram, cnt in ip_dict.items():
        if cnt in ngram_occur_dict:
            ngram_occur_dict[cnt] += 1
        else:
            ngram_occur_dict[cnt] = 1

    import collections

    ordered_pairs = sorted(ngram_occur_dict.items())

    x, y = zip(*ordered_pairs)

    x = x[1:]
    y = y[1:]

    x_cdf = [0]
    y_cdf = [0]

    for x_cur, y_cur in zip(x, y):
        x_cdf.append(x_cur)
        y_cdf.append(y_cdf[-1] + y_cur)

    kneedle = KneeLocator(x_cdf, y_cdf, S=1.0, curve="concave", direction="increasing")

    thresh_val = kneedle.knee
    print(f"Tuple size: {ngram_size}. Threshold values: {thresh_val}. Total number of tuples: {sum(x)}.")

    smooth_occur = lowess(y, x)

    # plt.plot(x, y)
    # plt.plot(smooth_occur[:, 0], smooth_occur[:, 1])
    # plt.plot(x_cdf, y_cdf)
    # plt.axvline(x=thresh_val, color='k', linestyle='--')
    # plt.title(f"Knee at {thresh_val}")
    # plt.savefig(str(ngram_size) + '_plot.png')

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, name='True', opacity=0.5))
    fig.add_trace(go.Scatter(x=smooth_occur[:, 0], y=smooth_occur[:, 1], name='Smooth', opacity=0.5))
    # fig.update_layout(showlegend=True, title='')
    fig.write_image(str(ngram_size) + '_plot.png')
    fig.write_html(str(ngram_size) + '_plot.html')

    return thresh_val
