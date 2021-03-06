"""
data.py
"""
from __future__ import (
    print_function,
)

import torch.utils.data

import os
import re
import csv
import json
import nltk
import random
import collections
import unicodedata
import numpy as np

from tqdm import (
    tqdm,
)

from random import (
    shuffle,
)

from config import (
    basedir,
    get_config,
)

def get_sentences(data_dir, data_file):
    """
    Get sentences from the raw text file.
    """

    # Read the text
    with open(os.path.join(basedir, data_dir, data_file), 'r') as f:
        text = ' '.join([line.strip() for line in f.readlines()])

    # Tokenize into sentences
    sentences = []
    for sentence in nltk.sent_tokenize(text):

        # Remove punctuation
        sentence = re.compile('\w+').findall(sentence)
        # lowercase all the words
        sentence = [word.lower() for word in sentence]
        # Add to sentences
        sentences.append(' '.join([word for word in sentence]))

    return sentences

def tokenize_sentences(data_dir, sentences, vocab_size):
    """
    Tokenize the sentences.
    """

    # Get unique words
    words = ' '.join([word for word in sentences]).split(' ')

    # Get counts for top <VOCAB_SIZE> words
    count = [["UNK", -1]]
    count.extend(collections.Counter(words).most_common(vocab_size - 1))
    num_unique_words = len(count)

    # Get the top words
    frequent_words = []
    for word, freq in count:
        frequent_words.append(word)

    # Dicts
    word_to_idx = {char:i for i,char in enumerate(frequent_words)}
    idx_to_word = {i:char for i,char in enumerate(frequent_words)}

    # Counts for unknown words
    unknown_count = 1 # avoid div by 0 for subsampling
    for word in words:
        if word not in word_to_idx:
            unknown_count +=1
    count[0] = ("UNK", unknown_count)

    # Get frequencies for sampling
    idx_to_freq = {}
    for item in count:
        idx_to_freq[word_to_idx[item[0]]] = item[1]

    # Tokensize sentences with indexes
    tokenized_sentences = []
    for sentence in sentences:
        tokenized_sentence = [word_to_idx[word] \
            if word in word_to_idx \
            else word_to_idx["UNK"] \
            for word in sentence.split(' ')]
        tokenized_sentences.append(tokenized_sentence)

    # Save dictionaries
    with open(os.path.join(basedir, data_dir, "word_to_idx.json"), 'w') as f:
        json.dump(word_to_idx, f)
    with open(os.path.join(basedir, data_dir, "idx_to_word.json"), 'w') as f:
        json.dump(idx_to_word, f)
    with open(os.path.join(basedir, data_dir, "idx_to_freq.json"), 'w') as f:
        json.dump(idx_to_freq, f)

    return tokenized_sentences, num_unique_words

def subsample(data_dir, sentences):
    """
    Subsampling on our data to reduce
    data size.
    """

    # Load frequencies
    with open(os.path.join(basedir, data_dir, "idx_to_freq.json"), 'r') as f:
        idx_to_freq = json.load(f)

    # P(w_i) = (\sqrt{\frac{z(w_i)}{0.001} + 1}) * \frac{0.001}{z(w_i)}
    idx_to_z = {k: v / sum(idx_to_freq.values()) for k, v in idx_to_freq.items()}
    idx_to_P = {k: np.sqrt((z/0.001) + 1.0)*(0.001/z) for k, z in idx_to_freq.items()}

    min_P, max_P = min(idx_to_P.values()), max(idx_to_P.values())
    subsampled_sentences = []
    for sentence in sentences:
        subsampled_sentence = []
        for word_idx in sentence:
            # sampling
            P = idx_to_P[str(word_idx)]
            if P >= random.uniform(0, max_P):
                subsampled_sentence.append(word_idx)
        subsampled_sentences.append(subsampled_sentence)

    return subsampled_sentences

def skip_gram(sentences, window_size):
    """
    Create data based on
    skip-gram approach aka
    (predict context word
    from target word).
    """

    data = []
    for sentence in sentences:

        # For each index
        for i, index in enumerate(sentence):

            # Collect valid context indexes
            contexts = []
            for window in range(window_size):

                # left side
                if i-(window+1) >= 0:
                    contexts.append(sentence[i-(window+1)])
                # right side
                if i+(window+1) < len(sentence):
                    contexts.append(sentence[i+(window+1)])

            # Add to data
            for context in contexts:
                data.append((index, context))

    return data

def create_data_loaders(data, split_ratio, batch_size):
    """
    Create train and test
    data loaders.
    """

    # Shuffle the data
    np.random.shuffle(data)

    # Split into train/test sets
    test_start_index = int(len(data) * split_ratio)
    train_data = data[:test_start_index]
    test_data = data[test_start_index:]

    # Create data loaders
    train_loader = torch.utils.data.DataLoader(
        dataset=train_data,
        batch_size=batch_size,
        shuffle=False,
        )
    test_loader = torch.utils.data.DataLoader(
        dataset=test_data,
        batch_size=batch_size,
        shuffle=False,
        )

    return train_loader, test_loader

def process_data(data_dir, data_file, vocab_size, window_size,
    split_ratio, batch_size):
    """
    """

    # Get sentences from raw text
    sentences = get_sentences(
        data_dir=data_dir,
        data_file=data_file,
        )

    # Tokenize the data
    tokenized_sentences, num_unique_words = tokenize_sentences(
        data_dir=data_dir,
        sentences=sentences,
        vocab_size=vocab_size,
        )

    # Subsampling
    tokenized_sentences = subsample(
        data_dir=data_dir,
        sentences=tokenized_sentences,
        )

    # Create training data
    data = skip_gram(
        sentences=tokenized_sentences,
        window_size=window_size,
        )

    # Create training data
    train_loader, test_loader = create_data_loaders(
        data=data,
        split_ratio=split_ratio,
        batch_size=batch_size,
        )

    return train_loader, test_loader, num_unique_words


