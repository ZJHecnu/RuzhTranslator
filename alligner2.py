# (1) 读取txt文件
import os

# 直接指定中文和英文txt文件的路径（请根据实际情况修改）
chinese_txt_path = r'/Users/zjh/Library/Mobile Documents/com~apple~CloudDocs/ECNU/01★ 课程与教学/俄汉对比研究/篇章对比研究/file1.txt'
english_txt_path = r'/Users/zjh/Library/Mobile Documents/com~apple~CloudDocs/ECNU/01★ 课程与教学/俄汉对比研究/篇章对比研究/file2.txt'

# 读取中文文本
with open(chinese_txt_path, 'r') as f:
    chinese_text = f.read()

# 读取俄文文本
with open(english_txt_path, 'r') as f:
    english_text = f.read()

textList = [chinese_text, english_text]

###（2）段落对齐
textChn1 = textList[0].split('\n')
textChn2 = [line for line in textChn1 if len(line) > 0]
textChn3 = []
for line in textChn2:
    textChn3.append(line)
textEng1 = textList[1].split('\n')
textEng2 = [line for line in textEng1 if len(line) > 0]
textEng3 = []
for line in textEng2:
    textEng3.append(line)
combine = list(zip(textChn3, textEng3))

###（3）中文分句
import re
def cut_sent(para):
    para = re.sub('([。！？\?])([^”’])', r"\1\n\2", para) 
    para = re.sub('(\.{6})([^”’])', r"\1\n\2", para)
    para = re.sub('(\…{2})([^”’])', r"\1\n\2", para)
    para = re.sub('([。！？\?][”’])([^，。！？\?])', r'\1\n\2', para)
    para = para.rstrip()
    return para.split("\n")

###（4）句对齐
###加载cuda
import nltk
import torch
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f'Using device: {device}')
###双语对齐
from sentence_transformers import SentenceTransformer, util
model = SentenceTransformer('LaBSE').to(device)
results = []
for item in combine:
    chnSents = cut_sent(item[0])
    engSents = nltk.sent_tokenize(item[1])
    chnRev = model.encode(chnSents)#, device=device)
    engRev = model.encode(engSents)#, device=device)
    align = []
    if len(chnRev) >= len(engRev):
        for chnSent, query in zip(chnSents, chnRev):
            id_, score = util.semantic_search(query, engRev)[0][0].values()
            comb = (round(score, 4), chnSent, engSents[id_])
            align.append(comb)
    elif len(chnRev) < len(engRev):
        for engSent, query in zip(engSents, engRev):
            id_, score = util.semantic_search(query, chnRev)[0][0].values()
            comb2 = (round(score, 4), chnSents[id_], engSent)
            align.append(comb2)
    results += align

###（5）输入Excel
import pandas as pd
df1 = pd.DataFrame(results)
writer = pd.ExcelWriter(r'双语平行对齐.xlsx')
df1.to_excel(writer, header = None, index = None)#
writer.close() 