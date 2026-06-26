import argparse
import re
from itertools import zip_longest
from pathlib import Path

import pandas as pd

SENTENCE_END_RE = re.compile(r'([^。！？；…!?]+[。！？；…!?]+)|([^。！？；…!?]+$)', re.S)


def split_sentences(text: str) -> list[str]:
    text = text.replace('\r\n', '\n').strip()
    sentences = [match.group(0).strip() for match in SENTENCE_END_RE.finditer(text)]
    return [sentence for sentence in sentences if sentence]


def read_text(path: str) -> str:
    return Path(path).read_text(encoding='utf-8', errors='replace')


def build_dataframe(sentences1: list[str], sentences2: list[str], label1: str, label2: str) -> pd.DataFrame:
    rows = []
    for left, right in zip_longest(sentences1, sentences2, fillvalue=''):
        rows.append({label1: left, label2: right})
    df = pd.DataFrame(rows)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Sentence-level align two documents and export a Russian-Chinese xlsx file.'
    )
    parser.add_argument('file1', help='First input text file')
    parser.add_argument('file2', help='Second input text file')
    parser.add_argument('-o', '--output', default='aligned.xlsx', help='Output xlsx file path')
    parser.add_argument('--label1', default='俄文', help='Column label for first file')
    parser.add_argument('--label2', default='中文', help='Column label for second file')
    args = parser.parse_args()

    text1 = read_text(args.file1)
    text2 = read_text(args.file2)
    sentences1 = split_sentences(text1)
    sentences2 = split_sentences(text2)
    df = build_dataframe(sentences1, sentences2, args.label1, args.label2)
    df.index += 1
    df.index.name = '序号'
    df.to_excel(args.output, index=True)
    print(f'已生成: {args.output}, 句数: {len(sentences1)} / {len(sentences2)}')


if __name__ == '__main__':
    main()
