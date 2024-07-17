import json
import argparse
from statistics import mean
from tqdm import tqdm
import nltk
from nltk.tokenize import word_tokenize
from datasets import load_dataset
import pickle

nltk.download('punkt')


def read_jsonlines(dataset_name, config_name, split):
    print(f"Loading examples from {dataset_name}, config: {config_name}, split: {split}")
    dataset = load_dataset(dataset_name, config_name, split=split)
    print(f"First item in dataset: {dataset[0]}")
    print(f"Keys in dataset: {dataset[0].keys()}")
    lines = []
    for obj in dataset:
        lines.append(obj)
    return lines


def evaluate_top_k_hit(embeddings, gt_answers, max_token_num=5000):
    per_lang = {}
    for q_id, embedding in tqdm(embeddings.items()):
        lang = gt_answers[q_id]['lang']
        per_lang.setdefault(lang, {"count": 0, "hit": 0})

        ctxs = embedding['ctxs']

        if q_id not in gt_answers:
            continue

        answers = gt_answers[q_id]['answers']

        span_answers = [answer for answer in answers if answer not in ["yes", "no"]]
        if len(span_answers) == 0:
            continue

        per_lang[lang]["count"] += 1

        concat_string_tokens = []
        for ctx in ctxs:
            tokenized_text = word_tokenize(ctx)
            concat_string_tokens += tokenized_text
            if len(concat_string_tokens) >= max_token_num:
                break
        concat_string_tokens = concat_string_tokens[:max_token_num]
        concat_string = " ".join(concat_string_tokens)
        hit = any(answer in concat_string for answer in span_answers)
        if hit:
            per_lang[lang]["hit"] += 1

    final_results = {lang: result for lang, result in per_lang.items() if result["count"] > 0}

    return final_results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_file", default=None, type=str, help="Dataset name for HF datasets")
    parser.add_argument("--config", default=None, type=str, help="Dataset configuration name")
    parser.add_argument("--split", default=None, type=str, help="Dataset split")
    parser.add_argument("--pred_file", default=None, type=str, help="Path to the predictions file (Pickle format)")
    parser.add_argument("--max_token_num", default=5000, type=int, help="Maximum number of tokens to consider")

    args = parser.parse_args()
    
    with open(args.pred_file, 'rb') as f:
        embeddings = pickle.load(f)
    
    input_data = read_jsonlines(args.data_file, args.config, args.split)
    # Print structure of the dataset items
    print("Inspecting the dataset structure:")
    for item in input_data[:5]:
        print(item)

    # Create a dictionary of query_id to answers
    qid2answers = {item["query_id"]: {"answers": item["answers"], "lang": item["lang"]} for item in input_data}

    # Inspect structure of predictions
    print("Inspecting the predictions structure:")
    print(f"Predictions type: {type(embeddings)}")
    print(f"First 5 predictions: {embeddings[:5]}")

    # Create a dictionary for embeddings with query_id as the key
    embeddings_dict = {query_id: embedding for query_id, embedding in enumerate(embeddings)}

    for topk in [2, 5]:
        print(f"Evaluating R@{topk}kt")
        pred_per_lang_results = evaluate_top_k_hit(embeddings_dict, qid2answers, topk * 1000)
        avg_scores = []
        for lang in pred_per_lang_results:
            print(f"Performance on {lang} ({pred_per_lang_results[lang]['count']} examples)")
            per_lang_score = (pred_per_lang_results[lang]["hit"] / pred_per_lang_results[lang]["count"]) * 100
            print(per_lang_score)
            avg_scores.append(per_lang_score)

        print("Final macro averaged score: ")
        print(mean(avg_scores))


if __name__ == "__main__":
    main()
